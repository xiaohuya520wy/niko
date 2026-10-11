"""把 Liquipedia 赛事页解析成结构化数据：参赛队伍 / 分组积分 / 分支图 / 赛程。

设计要点
--------
1) 分支图的轮次判定：Liquipedia 的 `brkts-round-body` 是**嵌套**的，
   越早的轮次嵌套越深。用祖先栈统计某个对阵身处几层 `brkts-round-body`，
   得到 depth；轮次序号 = maxDepth - depth。这样**轮空(bye)**也能正确归位
   （轮空队伍的首场比赛天然更浅 = 更晚的轮次）。
2) 胜负与比分要**按条目分别取**，不能整块正则（否则只会拿到胜者那一格）。
3) 参赛队伍来自 `team-participant-card`，标题来自最近的上一个 h2/h3/h4。
"""
import html as H
import re
from datetime import datetime, timezone

DIV_TOK = re.compile(r"<div\b([^>]*)>|</div>", re.I)

# ---------------------------------------------------------------- 小工具

def _cls(attrs: str) -> str:
    m = re.search(r'class="([^"]*)"', attrs or "")
    return m.group(1) if m else ""


def _text(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    s = H.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def prep(h: str) -> str:
    """MediaWiki 会把类名里的下划线转义成 &#95;，先还原，否则类名全都匹配不到。"""
    return h.replace("&#95;", "_")


def headings(h: str):
    """返回 [(位置, 层级, 标题)]。"""
    out = []
    for m in re.finditer(r"<h([2-6])\b[^>]*>(.*?)</h\1>", h, re.S):
        t = _text(m.group(2))
        t = re.sub(r"\[edit\]$", "", t).strip()
        if t:
            out.append((m.start(), int(m.group(1)), t))
    return out


def nearest_heading(h: str, pos: int, hs=None) -> str:
    hs = hs if hs is not None else headings(h)
    best = ""
    for p, lvl, t in hs:
        if p < pos:
            best = t
        else:
            break
    return best


def section_html(h: str, name: str, hs=None) -> str:
    """取某个标题到下一个同级或更高级标题之间的 HTML。"""
    hs = hs if hs is not None else headings(h)
    for i, (p, lvl, t) in enumerate(hs):
        if t.lower() == name.lower():
            end = len(h)
            for p2, lvl2, _ in hs[i + 1:]:
                if lvl2 <= lvl:
                    end = p2
                    break
            return h[p:end]
    return ""


# ---------------------------------------------------------------- 参赛队伍

def parse_participants(h: str):
    """从 Participants 区取参赛队伍（含队标），按出现顺序去重。"""
    h = prep(h)
    seg = section_html(h, "Participants")
    if not seg:
        return []
    out, seen = [], set()
    # 队伍卡片：block-team team-participant-card__opponent … <a title="Team Falcons"><img src=...>
    for blk in re.split(r'team-participant-card__opponent(?:"|\s)', seg)[1:]:
        head = blk[:1200]
        nm = re.search(r'<a href="/counterstrike/[^"]+" title="([^"]+)"', head)
        if not nm:
            continue
        name = H.unescape(nm.group(1)).strip()
        if not name or name in seen:
            continue
        # 只要 lightmode / allmode 那一张，不要 darkmode
        logo = ""
        for im in re.finditer(r'<img[^>]*src="([^"]+)"', head):
            u = im.group(1)
            if "darkmode" in u:
                continue
            logo = u
            break
        seen.add(name)
        out.append({"name": name, "logo": logo})
    return out


# ---------------------------------------------------------------- 分组/瑞士轮

_ROUND_COLS = re.compile(r"^Round\s*(\d+)$", re.I)


def _standings_rows(seg: str):
    """积分表数据行 -> [{team, nums}]，跳过 TBD 占位行。"""
    rows = []
    for rm in re.finditer(r"<tr>(.*?)</tr>", seg, re.S):
        r = rm.group(1)
        # 注意：新版瑞士轮表的数据行开头有排名序号 <th>（如 <th class="bg-up">1</th>），
        # 不能按「行内有 th」跳过——只跳过真正的表头行（没有任何 td 的行）。
        if not re.search(r"<td\b", r):
            continue
        # 队名：瑞士轮用 grouptableslot 里的 data-highlightingclass
        team = ""
        for m in re.finditer(r'data-highlightingclass="([^"]+)"', r):
            v = H.unescape(m.group(1)).strip()
            if v and v.upper() != "TBD":
                team = v
                break
        if not team:
            tn = re.search(r'<a href="/counterstrike/[^"]+" title="([^"]+)"', r)
            if tn:
                team = H.unescape(tn.group(1)).strip()
        if not team or team.upper() == "TBD":
            continue
        tds = re.findall(r"<td\b[^>]*>(.*?)</td>", r, re.S)
        nums = []
        for td in tds:
            t = _text(td)
            if re.fullmatch(r"\d+(?:[.:\-]\d+)?", t or ""):
                nums.append(t)
        rows.append({"team": re.sub(r"^Team\s+", "", team), "nums": nums})
    return rows


def parse_group_tables(h: str):
    """解析 Overview / Group Stage 里的分组/瑞士轮积分表。"""
    h = prep(h)
    out = []
    for tm in re.finditer(r'<table[^>]*class="[^"]*(?:swisstable|table2__table|wikitable)[^"]*"[^>]*>', h):
        start = tm.start()
        end = h.find("</table>", start)
        if end < 0:
            continue
        seg = h[start:end]
        title = nearest_heading(h, start) or "积分榜"
        head = re.search(r"<tr>(.*?)</tr>", seg, re.S)
        if not head:
            continue
        cols = [_text(c) for c in re.findall(r"<th\b[^>]*>(.*?)</th>", head.group(1), re.S)]
        cols = [c for c in cols if c]
        joined = " ".join(cols).lower()
        # 只认「队伍 + 战绩」型积分表，跳过国家分布之类
        if "team" not in joined or not any(k in joined for k in ("matches", "rounds", "pts", "points", "w")):
            continue
        rows = _standings_rows(seg)
        if len(rows) < 2:
            continue
        out.append({"title": title, "cols": cols, "rows": rows})
    # 合并同名表（宽/窄两份取并集）
    merged = {}
    for t in out:
        key = t["title"]
        if key not in merged:
            merged[key] = t
        else:
            have = {r["team"] for r in merged[key]["rows"]}
            for r in t["rows"]:
                if r["team"] not in have:
                    merged[key]["rows"].append(r)
    return list(merged.values())


# ---------------------------------------------------------------- 分支图

def _ancestor_depth(h: str, pos: int) -> int:
    """pos 处的元素，祖先里有几个 brkts-round-body（真·栈，闭合要配对）。"""
    stack, depth = [], 0
    for m in DIV_TOK.finditer(h, 0, pos):
        attrs = m.group(1)
        if attrs is None:                       # </div>
            if stack:
                if stack.pop():
                    depth -= 1
        else:
            is_rb = "brkts-round-body" in _cls(attrs)
            stack.append(is_rb)
            if is_rb:
                depth += 1
    return depth


def _entries(blk: str):
    """一个 brkts-match 里的两个对阵条目，逐条取胜负与比分。"""
    # 注意：不能用 \b —— `brkts-opponent-entry-left` 也会命中（- 前也是词边界），
    # 必须要求 entry 后面紧跟引号或空白，即真正的条目容器。
    marks = [m.start() for m in re.finditer(r'<div class="brkts-opponent-entry(?:"|\s)', blk)]
    out = []
    for i, s in enumerate(marks[:2]):
        p = blk[s: (marks[i + 1] if i + 1 < len(marks) else len(blk))]
        nm = re.search(r'aria-label="([^"]*)"', p[:400])
        short = re.search(r'data-team-shortname="([^"]*)"', p[:1500])
        sc = re.search(r'brkts-opponent-score-inner[^>]*>\s*(?:<b>)?\s*(\d+)', p)
        # 胜负标记在条目自己的 entry-left 上
        win = bool(re.search(r'brkts-opponent-entry-left[^"]*brkts-opponent-win', p[:600]))
        name = H.unescape(nm.group(1)).strip() if nm else ""
        name = re.sub(r"^Team\s+", "", name)
        if name.upper() in ("TBD", "TO BE DETERMINED", "–", "-"):
            name = ""
        out.append({
            "name": name,
            "full": name,
            "short": H.unescape(short.group(1)).strip() if short else "",
            "score": int(sc.group(1)) if sc else None,
            "win": win,
        })
    return out


def parse_default_bo(h: str) -> str:
    """从 Format 段抓全局赛制，例如 'All matches are <abbr ...>Bo3</abbr>' → 'Bo3'。
    用于 Upcoming Matches / 小组赛对阵列表里没有单场 BO 标注的情况。

    取舍：优先取 'All matches are BoX' 这种全局默认值（它通常排在 'Grand Final is Bo5'
    之前），这样小组赛/常规轮次回填的是 Bo3 而非被决赛的 Bo5 覆盖。"""
    h = prep(h)
    seg = section_html(h, "Format")
    if not seg:
        return ""
    m = re.search(r"All matches are.*?<abbr[^>]*>\s*(Bo\d)", seg, re.S | re.I)
    if m:
        return m.group(1)
    m = re.search(r'<abbr title="Best of \d">\s*(Bo\d)\s*</abbr>', seg)
    if m:
        return m.group(1)
    m = re.search(r"(Bo\d)", seg)
    return m.group(1) if m else ""


def parse_upcoming(h: str, limit=16):
    """页面顶部 Upcoming Matches 区：即将开赛的对阵与时间戳。
    新版 Liquipedia 在开赛前把赛程放这里（match-info 卡片），分支图里还是 TBD。"""
    h = prep(h)
    seg = section_html(h, "Upcoming Matches")
    if not seg:
        seg = section_html(h, "Upcoming Games")
    if not seg:
        return []
    default_bo = parse_default_bo(h)
    out = []
    for blk in re.split(r'<div class="match-info(?:"|\s)', seg)[1:]:
        ts = re.search(r'timer-object[^>]*data-timestamp="(\d+)"', blk)
        if not ts:
            continue
        stage = re.search(r'match-info-stage">([^<]*)<', blk)
        # 强判据：队伍**只**从 match-info-opponent-row 里取，且同时取该行的比分。
        # 不能在整个 blk 里扫 <a>——右上角 match-info-stream-buttons 里全是
        # Special:Stream/twitch| youtube 直播台链接，会被当成参赛队，
        # 2026-10-03 实测灌出 "Special:Stream/twitch/ESL Counter-Strike" 这种脏对阵。
        sides = []
        for row in re.split(r'<div class="match-info-opponent-row(?:"|\s)', blk)[1:3]:
            nm = ""
            for am in re.finditer(r'<a href="/counterstrike/([^"#?]+)"[^>]*title="([^"]*)"', row):
                path, title = am.group(1), H.unescape(am.group(2)).strip()
                # 去掉 MediaWiki 命名空间（Special/Category/File/Template…）与含冒号的伪链接
                if ":" in path:
                    continue
                nm = re.sub(r"^Team\s+", "", title or path.replace("_", " ").strip())
                break
            if not nm or nm.upper() in ("TBD", "TO BE DETERMINED", "–", "-"):
                continue
            sc = re.search(r'match-info-opponent-score[^>]*>\s*(\d+)', row)
            sides.append({"name": nm, "score": int(sc.group(1)) if sc else None})
        if len(sides) < 2:
            continue
        bo = re.search(r'\((Bo\d)\)', blk)
        wa = wb = False
        sa, sb = sides[0]["score"], sides[1]["score"]
        if sa is not None and sb is not None and sa != sb:
            wa, wb = sa > sb, sb > sa
        out.append({
            "stage": stage.group(1).strip() if stage else "",
            "bo": bo.group(1) if bo else default_bo,
            "ts": int(ts.group(1)),
            "a": {"name": sides[0]["name"], "full": sides[0]["name"], "short": "",
                  "score": sa, "win": wa},
            "b": {"name": sides[1]["name"], "full": sides[1]["name"], "short": "",
                  "score": sb, "win": wb},
        })
    return out[:limit]


def parse_brackets(h: str):
    """返回 [ {title, rounds:[{name, matches:[...]}]} ]"""
    hs = headings(h)
    starts = [m.start() for m in re.finditer(r'<div class="brkts-bracket[ "]', h)]
    brackets = []
    for i, s in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(h)
        body = h[s:end]
        # 截断到本容器真实结束（避免把后续无关内容算进来）
        mpos = [m.start() for m in re.finditer(r'<div class="brkts-match[ "]', body)]
        if not mpos:
            continue
        cut = min(len(body), mpos[-1] + 60000)
        body = body[:cut]

        heads = [H.unescape(x).strip()
                 for x in re.findall(r'<div class="brkts-header brkts-header-div"[^>]*>([^<]*)', body)]
        heads = [x for x in heads if x and x.lower() not in ("qualified", "eliminated")]

        matches = []
        for k, mi in enumerate(mpos):
            blk = body[mi: (mpos[k + 1] if k + 1 < len(mpos) else len(body))]
            ent = _entries(blk)
            if len(ent) < 2:
                continue
            # 赛前占位对阵（两边都还没队名）直接丢掉
            if not ent[0]["name"] and not ent[1]["name"]:
                continue
            ts = re.search(r'data-timestamp="(\d+)"', blk)
            bo = re.search(r'scoreholder-lower">\((Bo\d)\)', blk)
            details = re.search(r'data-highlighted-match|brkts-match-has-details', blk)
            matches.append({
                "a": ent[0], "b": ent[1],
                "ts": int(ts.group(1)) if ts else None,
                "bo": bo.group(1) if bo else "",
                "depth": _ancestor_depth(body, mi),
            })
        if not matches:
            continue
        maxd = max(m["depth"] for m in matches)
        for m in matches:
            m["round"] = maxd - m["depth"]
        nround = maxd
        rounds = []
        for r in range(nround + 1):
            ms = [m for m in matches if m["round"] == r]
            if not ms:
                continue
            name = heads[r] if r < len(heads) else f"第 {r + 1} 轮"
            ms.sort(key=lambda x: (x["ts"] or 0, x["a"]["name"]))
            rounds.append({"name": name, "matches": ms})
        if rounds:
            brackets.append({"title": nearest_heading(h, s, hs) or "分支图",
                             "rounds": rounds, "count": len(matches)})
    # 去重：同一容器窄/宽两份
    seen, uniq = set(), []
    for b in brackets:
        key = (b["title"], b["count"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(b)
    return uniq


# ---------------------------------------------------------------- 小组赛对阵列表

_MONTHS = {"January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
           "July": 7, "August": 8, "September": 9, "October": 10, "November": 11,
           "December": 12}


def _date_header_zh(t: str) -> str:
    """'October 3, 2026' → '10月3日'；解析不出就原样返回。"""
    m = re.match(r"([A-Za-z]+)\s+(\d{1,2})", (t or "").strip())
    mo = _MONTHS.get(m.group(1).title()) if m else None
    if not mo:
        return (t or "").strip()
    return f"{mo}月{int(m.group(2))}日"


def _stage_of(h: str, pos: int, hs=None) -> str:
    """pos 之前最近的「阶段级」标题（跳过 Round N / High / Mid / Low / Overview 等子级）。"""
    hs = hs if hs is not None else headings(h)
    best = ""
    for p, lvl, t in hs:
        if p >= pos:
            break
        if (re.match(r"^Round\s*\d+$", t) or t in
                ("High", "Mid", "Low", "Overview", "Detailed Results")):
            continue
        best = t
    return best


def parse_matchlist(h: str):
    """解析小组赛/第一阶段的对阵列表（brkts-matchlist 结构）。

    Liquipedia 的小组赛不用 brkts-bracket（那是淘汰赛树），而是按日期分组的扁平
    对阵列表：brkts-matchlist-header（如 'October 3, 2026'）+ 一批 brkts-matchlist-match。
    旧版 parse_brackets 只认 brkts-bracket，导致 EPL S24 这类「小组赛已开打、淘汰赛
    还没定」的页面 brackets=0，第一阶段对阵完全显示不出来。

    返回 [ {title, rounds:[{name, matches:[...]}]} ]，结构与 parse_brackets 一致，
    供 build() 并入 brackets。日期作轮次（列）名；对阵无时间戳（ts=None），
    不会污染赛程（schedule_from_brackets 会跳过无 ts 的场次）。"""
    h = prep(h)
    miter = list(re.finditer(r'<div class="brkts-matchlist-match', h))
    if not miter:
        return []
    hdr_pos = [(mh.start(), _text(mh.group(1)).strip()) for mh in
               re.finditer(r'<div class="brkts-matchlist-header[^>]*>(.*?)</div>', h, re.S)]
    default_bo = parse_default_bo(h)
    groups, order = {}, []
    for m in miter:
        name = ""
        for hp, ht in hdr_pos:
            if hp < m.start():
                name = ht
            else:
                break
        blk = h[m.start(): m.start() + 5000]
        names = [re.sub(r"^Team\s+", "", H.unescape(x).strip())
                 for x in re.findall(r'brkts-matchlist-opponent[^>]*aria-label="([^"]*)"', blk)]
        names = [x for x in names
                 if x and x.upper() not in ("TBD", "TO BE DETERMINED", "–", "-")]
        if len(names) < 2:
            continue
        # 比分：两个 brkts-matchlist-score 单元格的 cell-content（未赛为空）
        sc = re.findall(r'brkts-matchlist-score[^>]*>.*?cell-content">([^<]*)', blk, re.S)
        sa = int(sc[0]) if len(sc) > 0 and sc[0].strip().isdigit() else None
        sb = int(sc[1]) if len(sc) > 1 and sc[1].strip().isdigit() else None
        wa = wb = False
        if sa is not None and sb is not None and sa != sb:
            wa, wb = sa > sb, sb > sa
        md = {
            "a": {"name": names[0], "full": names[0], "short": "", "score": sa, "win": wa},
            "b": {"name": names[1], "full": names[1], "short": "", "score": sb, "win": wb},
            "ts": None, "bo": default_bo, "depth": 0,
        }
        key = name or "对阵"
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(md)
    if not groups:
        return []
    title = _stage_of(h, miter[0].start()) or "小组赛"
    rounds = [{"name": _date_header_zh(k) if re.match(r"^[A-Za-z]+ \d", k) else k,
               "matches": groups[k]} for k in order if groups[k]]
    if not rounds:
        return []
    return [{"title": title, "rounds": rounds,
             "count": sum(len(r["matches"]) for r in rounds)}]


# ---------------------------------------------------------------- 赛程 / 比分

def _dedup_sort(rows, limit=40):
    seen, uniq = set(), []
    for r in sorted(rows, key=lambda x: x["ts"]):
        k = (r["ts"], r["a"]["name"], r["b"]["name"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)
    return uniq[:limit]


def schedule_from_brackets(brackets, limit=40):
    """从任意来源的 branches 结构生成赛程（首字母/自愈来的都能用）。"""
    rows = []
    for b in brackets:
        for rd in b.get("rounds", []):
            for m in rd.get("matches", []):
                if not m.get("ts"):
                    continue
                rows.append({
                    "stage": b.get("title", ""),
                    "round": rd.get("name", ""),
                    "bo": m.get("bo", ""),
                    "ts": m["ts"],
                    "a": m["a"], "b": m["b"],
                })
    return _dedup_sort(rows, limit)


def parse_schedule(h: str, limit=40):
    """从分支图里抽出带时间戳的对阵，作为赛程与实时比分来源。"""
    return schedule_from_brackets(parse_brackets(h), limit)


# ---------------------------------------------------------------- 概览信息

def parse_overview(h: str, name: str):
    """日期 / 赛制 / 奖池 / 地点 等。"""
    h = prep(h)
    out = {"name": name}
    about = section_html(h, "About")
    prize = section_html(h, "Prize Pool")
    fmt = section_html(h, "Format")

    def grab(seg, pats, keys):
        for pat, key in zip(pats, keys):
            m = re.search(pat, seg, re.S)
            if m:
                out[key] = _text(m.group(1))[:80]

    grab(about, [r'<div class="infobox-cell-2[^"]*">Dates?</div>\s*<div[^>]*>(.*?)</div>',
                 r'>Dates?</t[dh]>\s*<td[^>]*>(.*?)</td>',
                 r'<div class="infobox-cell-2[^"]*">Location</div>\s*<div[^>]*>(.*?)</div>',
                 r'<div class="infobox-cell-2[^"]*">Venue</div>\s*<div[^>]*>(.*?)</div>',
                 r'<div class="infobox-cell-2[^"]*">Prize Pool</div>\s*<div[^>]*>(.*?)</div>',
                 r'<div class="infobox-cell-2[^"]*">Teams</div>\s*<div[^>]*>(.*?)</div>'],
                ["dates", "dates", "location", "venue", "prize", "teams"])
    if "prize" not in out and prize:
        m = re.search(r'\$[\d,\.]+', _text(prize))
        if m:
            out["prize"] = m.group(0)
    if fmt:
        out["format_raw"] = _text(fmt)[:400]
    return out


# 需要自愈的字段（顺序即优先级）
_HEAL_KEYS = ("participants", "groups", "brackets", "upcoming")


def build(page_name, html_text, display_name="", url=None):
    """解析一个赛事页。

    url 传入时会启用「自愈层」：主解析器（正则）某块产出为空时，
    用 Scrapling 的语义选择器 / 自适应指纹兜底补上；**主解析器有结果时
    绝不覆盖**，因此不会让现有数据变差。

    反过来，**只有主解析器健康时才更新指纹库**，避免把改版后的残缺形态
    写进指纹，导致以后 adaptive 越用越偏。
    """
    d = {
        "page": page_name,
        "info": parse_overview(html_text, display_name or page_name),
        "participants": parse_participants(html_text),
        "groups": parse_group_tables(html_text),
        "brackets": parse_brackets(html_text),
        "upcoming": parse_upcoming(html_text),
    }
    # 小组赛/第一阶段对阵列表（brkts-matchlist）并入分支图：
    # 淘汰赛树还没定（全是 TBD）时，第一阶段对阵也能显示出来（2026-10-03 用户反馈）
    _ml = parse_matchlist(html_text)
    if _ml:
        d["brackets"] = d["brackets"] + _ml
    d["schedule"] = schedule_from_brackets(d["brackets"])

    missing = [k for k in _HEAL_KEYS if not d.get(k)]
    if missing and url:
        try:
            import parse_event_sl as SL
            got = SL.heal(html_text, missing, url)
        except Exception as e:                      # 自愈失败不影响主流程
            got = {}
            parse_health._last_error = repr(e)
        if got:
            d.update(got)
            # 分支图是自愈来的 → 赛程要按自愈结果重算（正则那版是空的）
            if "brackets" in got and not d.get("schedule"):
                d["schedule"] = schedule_from_brackets(got["brackets"])
            d["selfhealed"] = sorted(got)

    if url:
        # 健康（无告警且关键块有数据）才写入指纹
        healthy = not parse_health(html_text, d)
        if healthy:
            try:
                import parse_event_sl as SL
                SL.refresh_fingerprints(html_text, url)
            except Exception:
                pass
    return d


if __name__ == "__main__":
    import pathlib, sys, json
    for f in sys.argv[1:]:
        h = pathlib.Path(f).read_text(encoding="utf-8")
        d = build(pathlib.Path(f).stem, h, pathlib.Path(f).stem)
        print(f"===== {f}")
        print("  info:", {k: v for k, v in d["info"].items() if k != "format_raw"})
        print("  参赛队:", len(d["participants"]), [p["name"] for p in d["participants"]][:8])
        print("  分组表:", [(g["title"], len(g["rows"]), g["rows"][0]["nums"] if g["rows"] else []) for g in d["groups"]][:6])
        for b in d["brackets"]:
            print(f"  分支[{b['title']}] 共{b['count']}场:")
            for rd in b["rounds"]:
                print(f"     {rd['name']}: " + ", ".join(
                    f"{m['a']['name']} {m['a']['score']}-{m['b']['score']} {m['b']['name']}"
                    for m in rd["matches"][:6]))
        print("  赛程:", len(d["schedule"]))


def parse_health(h: str, d: dict):
    """改版自检（2026-10-01 加）：页面原材料明明存在、解析结果却是空
    → 判定解析器已被 Liquipedia 改版打挂，而不是「页面没数据」。
    返回 warnings 列表；空列表 = 健康。

    判据只认「真实材料」（过滤掉 TBD 占位与非积分表，避免误报）：
    1. 含 >=4 个真实队名行的 wikitable 存在但 groups=0
       （对应翻车实例：EPL S24 瑞士轮表改版，17 行全被 th 过滤误杀）
    2. 分支图里有 >=4 个真实队名但 brackets=0
    3. Upcoming 区有带时间戳的比赛但 upcoming=0 且 schedule=0
       （对应翻车实例：开赛前赛程在页面顶部 Upcoming Matches 区，旧代码没抓）
    """
    h = prep(h)
    warns = []

    def _real_teams(seg):
        return set(re.findall(r'<a href="/counterstrike/[^"]+" title="(?!TBD)([^"]+)"', seg))

    # 1. 积分表存在但分组为空
    if not (d.get("groups") or []):
        for m in re.finditer(r'<table class="[^"]*wikitable[^"]*"[^>]*>(.*?)</table>', h, re.S):
            if len(_real_teams(m.group(1))) >= 4:
                warns.append("page has a standings-like wikitable but groups=0")
                break

    # 2. 分支图有真实对阵但解析为空
    if not (d.get("brackets") or []) and "brkts-bracket" in h:
        segs = re.split(r'brkts-bracket', h)[1:]
        if any(len(_real_teams(s[:4000])) >= 4 for s in segs):
            warns.append("page has brackets with real teams but brackets=0")

    # 3. Upcoming 区有时间戳比赛但赛程全空
    if not (d.get("upcoming") or []) and not (d.get("schedule") or []):
        if ("Upcoming Matches" in h or "Upcoming Games" in h)                 and re.search(r'timer-object[^>]*data-timestamp', h):
            warns.append("page has Upcoming Matches with timestamps but upcoming=0 and schedule=0")
    return warns
