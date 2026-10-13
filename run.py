"""NikoTracker 数据管线（GitHub Actions 版，仅标准库）。

抓取 Liquipedia 赛事页 -> 解析 Team Falcons 每一场系列赛（含逐图回合比分、
上下半场拆分、HLTV 对局链接）-> 与 base.json / players.json 合并 -> 写出
data.json。由 .github/workflows/update.yml 每 30 分钟自动运行一次。

抓取与解析逻辑与本机的 pipeline.py / parse_detail.py 完全一致，
保证本地迭代和线上产出一致。

⚠ 关键安全阀（write_guard）：
Liquipedia 对数据中心 IP（含 GitHub Actions）限流很严，抓取失败时 pages 为空，
旧版本仍会把「0 场比赛」的空 data.json 写回仓库并 push —— 线上的真实战绩
（58 场）就被覆盖成 0，页面全部显示 0 胜 0 负。
现在写入前会拿新数据和仓库里已有的数据比一比，明显变少就放弃写入，
宁可用旧数据也不要把页面清空。
"""
import datetime
import gzip
import json
import pathlib
import sys
import time
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).parent
UA = {
    "User-Agent": "NikoTracker/1.0 (CS2 fan page; contact: user@example.com)",
    "Accept-Encoding": "gzip",
}
API = "https://liquipedia.net/counterstrike/api.php?"

# 新数据至少要达到旧数据的这个比例，才允许覆盖写入
MIN_KEEP = 0.8

# event.json（赛事中心板块）最大年龄：超过才重新抓取，避免每次运行都白跑一遍。
# 已结束/未开赛的赛事变化慢，2 小时足够；但**有赛事正在进行**时要加密到分钟级，
# 否则分支图/赛程的实时比分会滞后很久（用户 2026-10-03 反馈）。
EVENT_MAX_AGE_HOURS = 2
EVENT_MAX_AGE_LIVE_HOURS = 0.2

# 需要抓取的 Liquipedia 赛事页（Major 拆成主页面 + Stage_3 + Playoffs）
PAGES = [
    "BLAST/Open/2025/Fall",
    "FISSURE/Playground/2",
    "FISSURE/Playground/3",
    "ESL/Pro_League/Season_22",
    "BLAST/Bounty/2026/Winter",
    "Intel_Extreme_Masters/2026/Kraków",
    "PGL/2026/Cluj-Napoca",
    "BLAST/Open/2026/Spring",
    "BLAST/Open/2026/Fall",
    "Intel_Extreme_Masters/2026/Rio",
    "PGL/2026/Astana",
    "CS_Asia_Championships/2026",
    "Esports_World_Cup/2026",
    "Intel_Extreme_Masters/2026/Cologne",
    "BLAST/Bounty/2026/Summer",
    "Intel_Extreme_Masters/2026/Cologne/Stage_3",
    "Intel_Extreme_Masters/2026/Cologne/Playoffs",
    "BLAST/Bounty/2026/Summer/Qualifier",
]


def fetch(page, tries=4):
    """抓一个赛事页的渲染后 HTML。Liquipedia 要求自定义 UA，且限流较严。"""
    url = API + urllib.parse.urlencode(
        {"action": "parse", "page": page, "prop": "text", "format": "json"})
    last = None
    for _ in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            r = urllib.request.urlopen(req, timeout=90)
            raw = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
            return json.loads(raw.decode("utf-8"))["parse"]["text"]["*"]
        except Exception as e:          # noqa: BLE001
            last = e
            time.sleep(10)
    print(f"  FETCH FAIL {page}: {last}", file=sys.stderr)
    return None


def count_matches(path):
    """读一个 data.json 里有多少场系列赛；读不到返回 0。"""
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        return len(d.get("recent_matches") or [])
    except Exception:                   # noqa: BLE001
        return 0


def event_age_hours(path):
    """event.json 的年龄（小时）；读不到返回一个大数。"""
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        t = d.get("updated", "").replace("Z", "")
        dt = datetime.datetime.fromisoformat(t)
        if dt.tzinfo is None:              # 无时区标记的按 UTC 算
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return (datetime.datetime.now(datetime.timezone.utc) - dt).total_seconds() / 3600
    except Exception:                   # noqa: BLE001
        return 1e9


def pages_from_events():
    """从 event.json 登记的赛事反查它的 Liquipedia 页名，自动纳入抓取列表。

    硬编码的 PAGES 列表永远追不上新赛事 —— 最近的教训：ESL/Pro_League/Season_24
    一直没被加进来，而它正是 NiKo 当前正在打的赛事，导致他 10 月的比赛始终进不了
    data.json（站点最多停在 9 月 5 日）。event.json 是当前赛事的事实来源，
    凡它收录的赛事页都补进抓取列表，新赛事就此自动纳入，不用再手工改代码。
    """
    out = []
    try:
        d = json.loads((ROOT / "event.json").read_text(encoding="utf-8"))
    except Exception:                   # noqa: BLE001
        return out
    marker = "/counterstrike/"
    for e in d.get("events") or []:
        src = (e or {}).get("source") or ""
        if marker not in src:
            continue
        # https://liquipedia.net/counterstrike/ESL/Pro%20League/Season%2024
        #   -> ESL/Pro League/Season 24
        page = urllib.parse.unquote(src.split(marker, 1)[1]).strip("/")
        if page:
            out.append(page)
    return out


def collect_pages():
    """本次要抓的赛事页：当前/新赛事优先，其后才是历史赛事表。

    新赛事放前面，这样即使后面被限流拖慢或超时，最先丢的是已经打完、
    数据早已入库的旧赛事，而不是正在进行的那站。
    """
    seq = pages_from_events() + list(PAGES)
    seen, out = set(), []
    for p in seq:
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return out


def has_live_event():
    """event.json 里是否有正在进行的赛事（决定刷新频率）。"""
    try:
        d = json.loads((ROOT / "event.json").read_text(encoding="utf-8"))
        return any((e or {}).get("status") == "live" for e in d.get("events") or [])
    except Exception:                   # noqa: BLE001
        return False


def refresh_event():
    """刷新 event.json（赛事中心板块：分组/分支图/赛程）。

    fetch_event 优先读 _cache 缓存，Actions 上没有缓存就走网络（自带 32s 限流间隔）。
    防劣化守卫：新赛事数比旧文件少时回滚旧文件 —— 宁可旧也不要清空板块。
    返回 "ok" / "degraded"（解析器疑似被 Liquipedia 改版打挂，旧数据已保留）
         / "skip"（网络/其他失败）。
    """
    try:
        import fetch_event              # 仓库根目录里，仅标准库
        old = ROOT / "event.json"
        old_n = 0
        backup = ""
        if old.exists():
            backup = old.read_text(encoding="utf-8")
            try:
                old_n = len(json.loads(backup).get("events") or [])
            except Exception:           # noqa: BLE001
                old_n = 0
        try:
            fetch_event.main()
        except fetch_event.ParseDegraded as e:
            # 改版自检报警：数据已保留，但必须让 workflow 变红（邮件通知）
            print("=" * 64)
            print("[ALARM] Liquipedia 页面疑似改版，解析器失效！")
            print(f"        {e}")
            print("        event.json 已保留旧版数据（站点不会空白），")
            print("        但需要尽快人工修复 parse_event.py，否则数据会逐渐陈旧。")
            print("=" * 64)
            return "degraded"
        new = json.loads(old.read_text(encoding="utf-8"))
        new_n = len(new.get("events") or [])
        if new_n == 0 or new_n < old_n:
            if backup:
                old.write_text(backup, encoding="utf-8")
            print(f"[SKIP event.json] 新 {new_n} 个赛事 < 旧 {old_n} 个，已回滚保留旧文件")
            return "skip"
        print(f"[OK event.json] {new_n} 个赛事，updated={new.get('updated')}")
        return "ok"
    except Exception as e:              # noqa: BLE001
        print(f"[event refresh fail] {type(e).__name__}: {e}", file=sys.stderr)
        return "skip"


def main():
    sys.path.insert(0, str(ROOT))

    # ---------- 先刷新赛事中心（event.json），与比赛列表互相独立 ----------
    ev_path = ROOT / "event.json"
    rc = 0
    max_age = EVENT_MAX_AGE_LIVE_HOURS if has_live_event() else EVENT_MAX_AGE_HOURS
    if has_live_event():
        print("检测到有赛事正在进行 → 赛事刷新间隔加密到 "
              f"{EVENT_MAX_AGE_LIVE_HOURS} 小时")
    if event_age_hours(ev_path) >= max_age:
        print(f"event.json 已 {event_age_hours(ev_path):.1f} 小时未更新，开始刷新…")
        if refresh_event() == "degraded":
            rc = 2                      # 数据已保留，但以非零退出让 Actions 报警
    else:
        print(f"event.json 才 {event_age_hours(ev_path):.1f} 小时，跳过刷新")

    import pipeline

    base = json.loads((ROOT / "base.json").read_text(encoding="utf-8"))
    squad = []
    pfile = ROOT / "players.json"
    if pfile.exists():
        squad = json.loads(pfile.read_text(encoding="utf-8")).get("squad", [])

    # 当前赛事由 event.json 动态补位，历史赛事走 PAGES 常量，两者去重合并
    todo = collect_pages()
    derived = [p for p in pages_from_events()]
    if derived:
        print(f"动态补入 {len(derived)} 个当前赛事页: {', '.join(derived)}")

    pages = {}
    for i, page in enumerate(todo):
        html = fetch(page)
        if not html:
            continue
        pages[page] = html
        print(f"  [{i+1}/{len(todo)}] {page} -> {len(html)} bytes", flush=True)
        if i + 1 < len(todo):
            time.sleep(31)             # Liquipedia: action=parse 限 1 次 / 30 秒

    matches = pipeline.build_matches(pages)
    data = pipeline.assemble(base, matches, squad)

    # ---------- 安全阀：不允许用「更差的数据」覆盖仓库 ----------
    out = ROOT / "data.json"
    old_n = count_matches(out)
    new_n = len(matches)
    if new_n == 0 or (old_n and new_n < old_n * MIN_KEEP):
        print("=" * 64)
        print(f"[SKIP WRITE] 本次只抓到 {new_n} 场系列赛（仓库现有 {old_n} 场，"
              f"阈值 {MIN_KEEP:.0%}）")
        print(f"             成功抓取页面 {len(pages)}/{len(PAGES)} 个")
        print("             判断为 Liquipedia 限流/抓取失败，已放弃写入，")
        print("             保留仓库里已有的 data.json —— 页面不会被清成 0。")
        print("=" * 64)
        return rc

    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # 自动全体：用战队页 upcoming 刷新首页未来赛程（data.json.upcoming_tournaments），
    # 与 event.json 同源，保证「法尔孔所有比赛」在两处都自动收录、不再手抄。
    try:
        import fetch_event as _fe
        up = _fe.derive_upcoming_list()
        if up:
            cur = json.loads(out.read_text(encoding="utf-8"))
            cur["upcoming_tournaments"] = up
            cur["meta"]["updated"] = data["meta"]["updated"]
            out.write_text(json.dumps(cur, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[OK] 刷新 upcoming_tournaments：{len(up)} 个（来自战队页）")
    except Exception as e:                      # noqa: BLE001
        print(f"[warn] 刷新 upcoming_tournaments 失败：{e}", file=sys.stderr)

    # 自动刷新选手基础信息（生涯奖金 / 年龄 / 状态等）来自 Liquipedia 球员页，
    # 替代 base.json 里会过期的手写值；抓不到就保留旧值，不会报错、不会覆盖。
    try:
        import fetch_player as _fp
        time.sleep(31)                          # 与前方赛事页抓取错开限流窗口
        cur = json.loads(out.read_text(encoding="utf-8"))
        if _fp.refresh(cur["player"]):
            cur["meta"]["updated"] = data["meta"]["updated"]
            out.write_text(json.dumps(cur, ensure_ascii=False, indent=2), encoding="utf-8")
            print("[OK] 刷新 player 基础信息（来自 Liquipedia 球员页）")
    except Exception as e:                      # noqa: BLE001
        print(f"[warn] 刷新 player 失败：{e}", file=sys.stderr)

    st = data["year_stats"]
    with_maps = sum(1 for m in matches if m.get("maps"))
    print(f"OK matches={st['matches']} {st['wins']}W-{st['losses']}L "
          f"winrate={st['win_rate']}% events={st['events']} "
          f"with_map_detail={with_maps} squad={len(squad)} "
          f"updated={data['meta']['updated']}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
