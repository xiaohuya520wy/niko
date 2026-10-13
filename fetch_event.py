"""抓取「当前/下一站 + 最近赛事」的分组、分支、赛程，产出 event.json。

数据源：Liquipedia（CC BY-SA 3.0）。解析见 parse_event.py。

- 优先读本地缓存 _cache/events/*.html，缺失才联网（Liquipedia parse 限流 1 次/30 秒）。
- 队标下载到 assets/teams/，避免热链。
- 日期区间：有对阵时间戳就用时间戳，没有就用 base.json/data.json 里已确认的赛程。
"""
import datetime as dt
import json
import pathlib
import re
import sys
import time
import urllib.parse
import urllib.request

import parse_event as PE
import parse_detail as PD

ROOT = pathlib.Path(__file__).parent
class ParseDegraded(RuntimeError):
    """Liquipedia 页面改版导致解析器失效（旧数据已保留，需人工修 parse_event.py）。
    触发 run.py / GitHub Actions 报警（workflow 变红 + 邮件）。"""
CACHE = ROOT / "_cache" / "events"
OUT_JSON = ROOT / "event.json"
TEAM_DIR = ROOT / "assets" / "teams"
UA = {"User-Agent": "NikoTracker/1.0 (personal CS2 fan page; contact: user@example.com)",
      "Accept-Encoding": "gzip"}

# 缓存文件名与页面名不一致时的别名
CACHE_ALIAS = {"ESL/Pro League/Season 24": "epl_s24.html"}

# 展示用配置（tag: next=当前/下一站, recent=最近赛事）
CONFIG = [
    {"page": "ESL/Pro League/Season 24", "zh": "ESL 职业联赛 S24", "short": "EPL S24",
     "tag": "next", "tier": "S-Tier", "match": "ESL Pro League"},
    {"page": "Intel Extreme Masters/2026/Beijing", "zh": "IEM 北京 2026", "short": "IEM 北京",
     "tag": "next", "tier": "S-Tier", "match": "Beijing"},
    {"page": "Thunderpick/World_Championship/2026", "zh": "Thunderpick 世界冠军赛 2026", "short": "TWC 2026",
     "tag": "next", "tier": "A-Tier", "match": "Thunderpick"},
    {"page": "BLAST/Open/2026/Fall", "zh": "BLAST 公开赛 波尔图站", "short": "BLAST 波尔图",
     "tag": "recent", "tier": "S-Tier", "match": "BLAST"},
    {"page": "Intel Extreme Masters/2026/Cologne/Playoffs", "zh": "IEM 科隆 Major 2026",
     "short": "IEM 科隆", "tag": "recent", "tier": "S-Tier", "match": "Cologne",
     "teams_page": "Intel Extreme Masters/2026/Cologne"},
]

CONFIG_CACHE = ROOT / "_cache" / "events_cache.json"


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def _nk(n):
    """队名归一（去非字母数字、小写），用于跨源（event.json ↔ parse_detail）匹配。"""
    return re.sub(r"[^a-z0-9]", "", (n or "").lower())


# 小组赛（brkts-matchlist）轮次名形如「10月3日」——由 parse_event._date_header_zh 从
# Liquipedia 的 'October 3, 2026' 日期头转换而来。
_ROUND_DATE_RE = re.compile(r"^(\d{1,2})月(\d{1,2})日$")


def _round_date_ts(name, year):
    """把小组赛轮次名「10月3日」还原成 UTC 当天 00:00 的时间戳；不是日期头就返回 None。

    为什么需要：brkts-matchlist 的对阵本身没有时间戳（ts=None），如果不看轮次名，
    可用的时间戳就只剩「还没开打的那几场」，赛事 start 会被算成下一场的时间。
    于是已经打完好几天的赛事仍被判成 upcoming —— 赛事中心显示「即将开始」、
    首页 hero 也会漏掉正在进行的比赛（ESL S24 实际 10/03 开打，却算成 10/05）。
    """
    m = _ROUND_DATE_RE.match((name or "").strip())
    if not m:
        return None
    try:
        return int(dt.datetime(int(year), int(m.group(1)), int(m.group(2)),
                               tzinfo=dt.timezone.utc).timestamp())
    except ValueError:
        return None


def _extract_series_detail(html):
    """从 Liquipedia bracket popup 抓逐图详情；页面无 popup 时返回空列表不崩。"""
    try:
        return PD.extract(html)
    except Exception:
        return []


def _match_series(a, b, sa, sb, ts, series):
    """为 (a,b,比分,ts) 这场对阵，从 parse_detail 系列里挑最合适的一条。"""
    pa, pb = _nk(a), _nk(b)
    if pa == pb:
        return None
    cands = [s for s in series
             if _nk(s["left"]) in (pa, pb) and _nk(s["right"]) in (pa, pb)]
    if not cands:
        return None
    played = sa is not None and sb is not None
    if played:
        # 已出比分：优先比分完全吻合的那条（兼顾 left/right 两种顺序）
        for s in cands:
            la, lb = s["score"]
            if (sa == la and sb == lb) or (sa == lb and sb == la):
                return s
        wm = [s for s in cands if s["maps"]]
        return wm[0] if wm else cands[0]
    # 未开打（TBD/即将开始）：优先时间戳吻合，再优先「未比赛」的（maps 为空）
    if ts:
        tc = [s for s in cands if s["ts"] == ts]
        if tc:
            cands = tc
    up = [s for s in cands if not s["maps"]]
    return up[0] if up else cands[0]


def _orient(s, a, b):
    """把 parse_detail 的 left/right 对齐到赛事对阵的 a/b，返回
    {maps(已按 a/b 定向), links}。逐图 left_win 缺失时用回合比分反推。"""
    ka, kl, kr = _nk(a), _nk(s["left"]), _nk(s["right"])
    a_is_left = (ka == kl)
    maps = []
    for mp in s["maps"]:
        lw = mp["left_win"]
        if lw is None:
            try:
                ar = int(mp["left"].get("rounds") or 0)
                br = int(mp["right"].get("rounds") or 0)
                lw = True if ar > br else (False if br > ar else None)
            except Exception:
                lw = None
        if a_is_left:
            aw, m_a, m_b = lw, mp["left"], mp["right"]
        else:
            aw = (None if lw is None else (not lw))
            m_a, m_b = mp["right"], mp["left"]
        maps.append({
            "map": mp["map"], "vetoed": mp["vetoed"],
            "a_win": aw,
            "a": {"rounds": m_a.get("rounds", ""), "t": m_a.get("t", ""),
                  "ct": m_a.get("ct", "")},
            "b": {"rounds": m_b.get("rounds", ""), "t": m_b.get("t", ""),
                  "ct": m_b.get("ct", "")},
        })
    return {
        "maps": maps,
        "links": {"hltv_match": s["hltv_match"], "hltv_maps": s["hltv_maps"],
                  "vods": s["vods"]},
    }


def _attach_detail(brackets, sched, series, ev_id):
    """给 brackets / sched 每场对阵补 id（稳定）+ maps + links（有则补）。
    返回成功挂上逐图详情的场次数。id 规则：evid__队对__ts（ts 缺失时借系列 ts，
    让分支图 TBD 与赛程项指向同一场详情页）。"""
    n = 0

    def fix(m, a_name, b_name, sa, sb, ts, stage=""):
        nonlocal n
        s = _match_series(a_name, b_name, sa, sb, ts, series)
        ts_for_id = ts or (s["ts"] if s else None)
        pair = "-".join(sorted([_nk(a_name), _nk(b_name)]))
        m["id"] = f"{ev_id}__{pair}" + (f"__{ts_for_id}" if ts_for_id else "")
        if s:
            o = _orient(s, a_name, b_name)
            m["maps"] = o["maps"]
            m["links"] = o["links"]
            n += 1
        else:
            m["maps"] = []
            m["links"] = {}
        if stage:
            m["stage"] = stage

    for b in brackets:
        for rd in b["rounds"]:
            for m in rd["matches"]:
                fix(m, m["a"]["name"], m["b"]["name"],
                    m["a"].get("score"), m["b"].get("score"), m["ts"], rd["name"])
    for m in sched:
        fix(m, m["a"], m["b"], m.get("sa"), m.get("sb"), m["ts"],
            m.get("stage") or m.get("round"))
    return n


def parse_end_from_date_text(date_text, year):
    """从 base.json 的 date_text（如 '10/03–11' 或 '11/02–11/08'）推导赛事结束 UTC 时刻。

    返回 ISO 字符串或 None。赛事结束日用当天 23:59:59 UTC，避免把跨日赛事提前判为已结束。
    """
    if not date_text:
        return None
    try:
        left, right = date_text.split("–")   # 注意是 en dash（–），不是连字符
    except Exception:
        return None
    try:
        lm, ld = (int(x) for x in left.strip().split("/"))
    except Exception:
        return None
    if "/" in right:
        try:
            rm, rd = (int(x) for x in right.strip().split("/"))
        except Exception:
            return None
    else:
        rm, rd = lm, int(right.strip())
    yr = year + 1 if (rm, rd) < (lm, ld) else year
    try:
        e = dt.datetime(yr, rm, rd, 23, 59, 59, tzinfo=dt.timezone.utc)
    except Exception:
        return None
    return e.isoformat(timespec="seconds")


def cache_path(page: str) -> pathlib.Path:
    if page in CACHE_ALIAS:
        return CACHE / CACHE_ALIAS[page]
    return CACHE / (page.replace("/", "_").replace(" ", "_") + ".html")


def fetch_page(page: str) -> str:
    url = "https://liquipedia.net/counterstrike/api.php?" + urllib.parse.urlencode(
        {"action": "parse", "page": page, "prop": "text", "format": "json"})
    r = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120)
    raw = r.read()
    if r.headers.get("Content-Encoding") == "gzip":
        import gzip
        raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8"))["parse"]["text"]["*"]


# 缓存最大有效期（秒）。快刷场景（每 5 分钟）缓存超过这个时间就当作过期、去联网重抓；
# 过期时间内复用缓存省配额。改为 0 即「每次都联网」（调试用）。
CACHE_MAX_AGE = 240


def load_html(page: str, allow_net: bool):
    p = cache_path(page)
    if p.exists() and p.stat().st_size > 2000:
        age = time.time() - p.stat().st_mtime
        if age < CACHE_MAX_AGE:
            return p.read_text(encoding="utf-8"), "cache"
    if not allow_net:
        # 离线模式：有缓存就用（哪怕旧），没有才放弃
        if p.exists() and p.stat().st_size > 2000:
            return p.read_text(encoding="utf-8"), "cache-stale"
        return "", "missing"
    try:
        h = fetch_page(page)
    except Exception as e:                      # noqa: BLE001
        # 联网失败：还有旧缓存就退而用之（避免把赛事从 event.json 里丢掉），没有才放弃
        if p.exists() and p.stat().st_size > 2000:
            print(f"[cache-fallback] {page} 联网失败（{type(e).__name__}: {e}），回退旧缓存")
            return p.read_text(encoding="utf-8"), "cache-stale"
        print(f"[skip-net] {page} 联网失败且无缓存: {e}")
        return "", "missing"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(h, encoding="utf-8")
    return h, "net"


def norm_team(n: str) -> str:
    n = re.sub(r"^Team\s+", "", n or "").strip()
    return n


def download_logo(logo: str) -> str:
    """把队标下到 assets/teams/，返回本地相对路径（失败返回空）。"""
    if not logo:
        return ""
    TEAM_DIR.mkdir(parents=True, exist_ok=True)
    stem = pathlib.Path(logo.split("?")[0]).stem
    stem = re.sub(r"^\d+px-", "", stem)          # 去掉缩略图前缀 43px-
    fn = slug(stem) + ".png"
    dst = TEAM_DIR / fn
    if dst.exists() and dst.stat().st_size > 200:
        return f"assets/teams/{fn}"
    urls = []
    if re.search(r"/\d+px-", logo):
        urls.append(re.sub(r"/\d+px-", "/88px-", logo))
    urls.append(logo)
    for u in urls:
        full = u if u.startswith("http") else "https://liquipedia.net" + u
        try:
            data = urllib.request.urlopen(
                urllib.request.Request(full, headers=UA), timeout=60).read()
            if len(data) > 200:
                dst.write_bytes(data)
                return f"assets/teams/{fn}"
        except Exception:
            continue
    return ""


def summarize_format(h: str) -> str:
    seg = PE.section_html(h, "Format")
    if not seg:
        return ""
    txt = PE._text(seg)
    txt = re.sub(r"^\s*Format\s*", "", txt)
    txt = re.sub(r"^\[\s*edit\s*\]\s*", "", txt).strip()
    # 只保留第一段（阶段 + 参赛队数 + 赛制 + 晋级规则）
    cut = txt.split("Click here")[0].split("First Round")[0].strip()
    cut = re.sub(r"\s+", " ", cut)
    return cut[:180]


def build_event(cfg, html_text, base_info, now):
    h = html_text
    # url 是 Scrapling 自适应指纹的主键；传了才会启用自愈层与指纹更新
    url = "https://liquipedia.net/counterstrike/" + urllib.parse.quote(cfg["page"])
    d = PE.build(cfg["page"], h, cfg["zh"], url=url)
    if d.get("selfhealed"):
        print(f"[SELF-HEAL] {cfg['page']} 主解析器空缺字段已由 Scrapling 补上: "
              f"{', '.join(d['selfhealed'])}")
    parts = d["participants"]
    # 取参赛名单的优先级：
    #   ① teams_page（赛事主页面）—— 最权威，含全部队伍（如 IEM 科隆 24 队）
    #   ② 本页解析结果（可能是 Scrapling 自愈来的，只有淘汰赛那几支）
    # 淘汰赛子页面本来就没有完整名单，子页面自愈出的 8 队不能覆盖主页面的 24 队。
    if cfg.get("teams_page"):
        alt_p = cache_path(cfg["teams_page"])
        if alt_p.exists():
            full = PE.parse_participants(alt_p.read_text(encoding="utf-8"))
            if full:
                parts = full

    # 队标 -> 本地
    teams = []
    for p in parts[:24]:
        logo = download_logo(p.get("logo", ""))
        teams.append({"name": norm_team(p["name"]), "logo": logo})

    # 日期区间（分支图 + Upcoming Matches 的比赛时间都算）
    ts_all = [m["ts"] for b in d["brackets"] for rd in b["rounds"]
              for m in rd["matches"] if m["ts"]]
    ts_all += [u["ts"] for u in d.get("upcoming", [])]
    # 小组赛（brkts-matchlist）的对阵没有时间戳，只有轮次名里带日期（「10月3日」）。
    # 不补进来的话 ts_all 会只剩「还没打的那几场」，赛事 start 被算成下一场的时间，
    # 已经开打的赛事被误判成 upcoming（2026-10-05 修复）。
    ts_all += [t for b in d["brackets"] for rd in b["rounds"]
               for t in [_round_date_ts(rd["name"], now.year)] if t]
    start_iso = end_iso = ""
    if ts_all:
        lo, hi = min(ts_all), max(ts_all)
        start_iso = dt.datetime.fromtimestamp(lo, dt.timezone.utc).isoformat(timespec="seconds")
        end_iso = dt.datetime.fromtimestamp(hi + 4 * 3600, dt.timezone.utc).isoformat(timespec="seconds")
    if cfg["tag"] == "next" and base_info:
        # 页面已抓到真实比赛时间戳时，一律以真实时间戳为准，不能用 base.json 的
        # 手填 start 覆盖——手填值可能陈旧，或把北京时间误写成 UTC（EPL S24 曾因此
        # 把开赛时间错成次日 02:00，比页面真实首场晚了 9 小时）。
        # 手填值只在页面还没有公布具体时间（ts_all 为空）时才兜底。
        if not ts_all:
            start_iso = base_info.get("start") or start_iso
        # end 与 start 相反：页面通常只发布了近期（首日）赛程，max(ts)+4h 会远早于
        # 真实赛事结束日，导致赛事被提前判为「已结束」（EPL S24 实际打到 10/11，首日
        # 只有 5 场，旧逻辑算出的 end 是 10/03 当晚）。这里优先用 base 显式 end，
        # 否则从 date_text 推导完整赛事结束日。
        base_end = base_info.get("end")
        if base_end:
            end_iso = base_end
        else:
            de = parse_end_from_date_text(base_info.get("date_text"), now.year)
            if de:
                end_iso = de
        date_text = base_info.get("date_text") or date_text
        tier = base_info.get("tier") or cfg["tier"]
        note = base_info.get("note", "")
    else:
        tier = cfg["tier"]
        note = ""
        date_text = ""
        if start_iso:
            a = dt.datetime.fromisoformat(start_iso)
            b = dt.datetime.fromisoformat(end_iso) if end_iso else a
            date_text = (f"{a.month:02d}/{a.day:02d}–{b.month:02d}/{b.day:02d}"
                         if a.month == b.month else
                         f"{a.month:02d}/{a.day:02d}–{b.month:02d}/{b.day:02d}")

    # 状态
    status = "upcoming"
    if start_iso:
        s = dt.datetime.fromisoformat(start_iso)
        e = dt.datetime.fromisoformat(end_iso) if end_iso else s + dt.timedelta(days=7)
        if now < s:
            status = "upcoming"
        elif now <= e:
            status = "live"
        else:
            status = "done"
    elif cfg["tag"] == "recent":
        status = "done"

    # 分支图：中文标注
    brackets = []
    for b in d["brackets"]:
        rounds = []
        for rd in b["rounds"]:
            ms = []
            for m in rd["matches"]:
                ms.append({
                    "a": {"name": norm_team(m["a"]["name"]), "score": m["a"]["score"],
                          "win": m["a"]["win"]},
                    "b": {"name": norm_team(m["b"]["name"]), "score": m["b"]["score"],
                          "win": m["b"]["win"]},
                    "ts": m["ts"], "bo": m["bo"],
                })
            rounds.append({"name": rd["name"], "matches": ms})
        if rounds:
            brackets.append({"title": b["title"], "rounds": rounds, "count": b["count"]})

    # 赛程（有时间的对阵）+ Upcoming Matches（开赛前的赛程在页面顶部，分支图里还是 TBD）
    sched = []
    for r in d["schedule"]:
        sched.append({
            "stage": r["stage"], "round": r["round"], "bo": r["bo"], "ts": r["ts"],
            "a": norm_team(r["a"]["name"]), "b": norm_team(r["b"]["name"]),
            "sa": r["a"]["score"], "sb": r["b"]["score"],
        })
    seen_ab = {(r["ts"], r["a"], r["b"]) for r in sched}
    for u in d.get("upcoming", []):
        a, b = norm_team(u["a"]["name"]), norm_team(u["b"]["name"])
        if (u["ts"], a, b) in seen_ab:
            continue
        seen_ab.add((u["ts"], a, b))
        sched.append({
            "stage": u["stage"] or "即将开赛", "round": "小组赛", "bo": u["bo"], "ts": u["ts"],
            # Upcoming 卡片本身就带比分（进行中/已结束的那一批），不能写死 None，
            # 否则赛程里的实时比分始终不显示（2026-10-03 修复）
            "a": a, "b": b,
            "sa": (u["a"] or {}).get("score"), "sb": (u["b"] or {}).get("score"),
        })
    sched.sort(key=lambda r: r["ts"])

    groups = [{"title": g["title"], "cols": g["cols"], "rows": g["rows"]} for g in d["groups"]]

    # 逐图详情（map-level）从 Liquipedia bracket popup 抓取，挂到每场对阵：
    # 有则挂 maps+links，无则仅给稳定 id（让卡片可点、详情页显示「暂无逐图数据」）。
    try:
        series_detail = _extract_series_detail(h)
        n_det = _attach_detail(brackets, sched, series_detail, slug(cfg["page"]))
        if series_detail:
            print(f"    [detail] 解析到 {len(series_detail)} 个系列，挂上逐图详情 {n_det} 场")
    except Exception as e:
        print(f"    [detail] 跳过（{type(e).__name__}: {e}）")

    return {
        "id": slug(cfg["page"]),
        "tag": cfg["tag"],
        "name": cfg["zh"],
        "short": cfg["short"],
        "tier": tier,
        "note": note,
        "status": status,
        "start": start_iso,
        "end": end_iso,
        "date_text": date_text,
        "prize": d["info"].get("prize", ""),
        "format": summarize_format(h),
        "teams": teams,
        "groups": groups,
        "brackets": brackets,
        "schedule": sched,
        "source": "https://liquipedia.net/counterstrike/" + urllib.parse.quote(cfg["page"]),
    }


def main():
    allow_net = "--offline" not in sys.argv
    # 快速刷新模式：只重抓「还没结束」的赛事，已结束赛事内容已定型，保留旧数据即可。
    # 这样定时快刷（每 5 分钟）只花 1~2 个页面的配额，不会被 Liquipedia 限流拖成十几分钟。
    live_only = "--live-only" in sys.argv
    now = dt.datetime.now(dt.timezone.utc)
    base = {}
    try:
        bj = json.loads((ROOT / "data.json").read_text(encoding="utf-8"))
        for t in bj.get("upcoming_tournaments", []):
            base[t.get("short", "")] = t
            base[t.get("name", "")] = t
    except Exception as e:
        print("读取 data.json 失败:", e)

    # 旧数据快照：改版自检失效时逐赛事回补，避免板块变空白
    old_by_id = {}
    known_status = {}
    try:
        for _e in json.loads(OUT_JSON.read_text(encoding="utf-8")).get("events") or []:
            if _e.get("id"):
                old_by_id[_e["id"]] = _e
                known_status[_e["id"]] = _e.get("status")
    except Exception:
        pass

    events = []
    degraded = []
    fetched = 0
    for i, cfg in enumerate(CONFIG):
        # 快刷模式跳过已结束赛事（内容已定型），但要把旧数据保留下来，
        # 否则它们会从 event.json 里消失，赛事中心的历史板块就不见了。
        if live_only and known_status.get(slug(cfg["page"])) == "done":
            _old = old_by_id.get(slug(cfg["page"]))
            if _old:
                events.append(_old)
                print(f"[快刷跳过] {cfg['zh']}（已结束，保留旧数据）")
            continue
        html, src = load_html(cfg["page"], allow_net)
        if not html:
            print(f"[跳过] {cfg['zh']} — 无缓存且未联网")
            continue
        fetched += 1
        if src == "net" and i + 1 < len(CONFIG):
            time.sleep(32)
        # 匹配基础赛程信息
        info = None
        for k, v in base.items():
            if cfg["match"] and cfg["match"].lower() in (k or "").lower():
                info = v
                break
            if cfg["short"] and cfg["short"].lower() in (k or "").lower():
                info = v
                break
        try:
            ev = build_event(cfg, html, info, now)
        except Exception as e:
            print(f"[失败] {cfg['zh']}: {type(e).__name__} {e}")
            continue
        # ---------- 改版自检：页面有料但解析为空 = 解析器被改版打挂 ----------
        warns = PE.parse_health(html, ev)
        if warns:
            ev_old = old_by_id.get(ev["id"])
            old_alive = ev_old and (ev_old.get("groups") or ev_old.get("schedule")
                                    or ev_old.get("brackets"))
            if old_alive:
                ev_old["parse_warning"] = warns
                events.append(ev_old)
                degraded.append(ev["id"])
                print(f"[PARSE-DEGRADED] {ev['name']}: {'; '.join(warns)}；"
                      f"已保留旧版数据（updated={ev_old.get('updated', '?')}）")
                continue
            events.append(ev)
            degraded.append(ev["id"])
            print(f"[PARSE-WARN] {ev['name']}: {'; '.join(warns)}；无旧数据可回补")
            continue
        events.append(ev)
        n_teams = len(ev["teams"])
        n_br = sum(len(rd["matches"]) for b in ev["brackets"] for rd in b["rounds"])
        print(f"[ok:{src}] {ev['name']:22} 状态={ev['status']:8} 队={n_teams:3} "
              f"分支={len(ev['brackets'])}({n_br}场) 分组={len(ev['groups'])} 赛程={len(ev['schedule'])}")

    # 快刷模式下如果一场都没真抓（全是已结束赛事），就不要覆写文件——
    # 否则只刷时间戳、内容没变，既误导页面上「最后更新于」，也白占一次提交。
    if live_only and not fetched:
        print("快刷模式：无活跃赛事需重抓，已跳过写入 event.json")
        return

    events.sort(key=lambda e: (0 if e["tag"] == "next" else 1, e["start"] or "9999"))
    data = {
        "updated": now.isoformat(timespec="seconds"),
        "featured": next((e for e in events if e["tag"] == "next"), None),
        "events": events,
        "source_note": "赛事分组、分支图与赛程抓取自 Liquipedia（CC BY-SA 3.0）。",
    }
    OUT_JSON.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")),
                        encoding="utf-8")
    print("已写出 event.json：", OUT_JSON.stat().st_size // 1024, "KB，赛事数", len(events))

    # 有降级 → 保留数据照常写出，但必须报警（run.py 捕获后让 Actions 变红发邮件）
    if degraded:
        msg = (f"解析器疑似被 Liquipedia 改版打挂，涉及 {len(degraded)} 个赛事: "
               f"{', '.join(degraded)}；旧数据已保留。请检查 parse_event.py 的"
               f"分组/分支图/Upcoming Matches 解析逻辑是否需要跟进新模板。")
        raise ParseDegraded(msg)


if __name__ == "__main__":
    main()
