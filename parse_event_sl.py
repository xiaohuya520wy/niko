"""Liquipedia 解析「自愈层」——基于 Scrapling，只在主解析器产不出数据时补位。

为什么要有这一层
----------------
主解析器 parse_event.py 是正则 + 硬编码 class 名。Liquipedia 一改版，
这些 class 名整体失效 → 解析结果变空 → 页面静默失守（历史上翻过两次：
瑞士轮表的 <th> 结构变化、赛程从分支图搬到 Upcoming Matches 区）。

这一层不改变主流程，只做「补空白」，因此天然不会让现有数据变差。

※ 最重要的教训（2026-10-03 实测）
----------------------------------
第一版兜底用宽泛的 `a[href^="/counterstrike/"]` 找队伍，结果把
**地图链接（Ancient/cs2）、选手链接（ApEX vs ZywOo）、国家分类表
（Category:New Zealand）** 全当成对阵/参赛队，补进 103 场垃圾数据。
**脏数据比空数据更害人**——宁缺毋滥。所以现在每个字段都必须有「强判据」：

  upcoming     必须同时具备 data-timestamp + 两支合格队伍   → 已验证质量优秀
  brackets     必须锚定 [data-team-shortname]（对阵条目专属）→ 拿不到就不补
  groups       必须同一 table 且 ≥4 行、行名非 Category      → 拿不到就不补
  participants 不独立猜，从已验证的 groups/upcoming 反推     → 拿不到就不补

L2 adaptive（历史指纹重定位）作为二次尝试，同样受上述质量门槛约束。

指纹库：默认 `_cache/scrapling/adaptive.db`（约 4KB，已在 .gitignore）。
**只在主解析器健康时才写入指纹**，避免把「改版后的残缺形态」写进库里毒化后续。

环境变量 NIKO_SL=0 可整体关闭（排障用）。Scrapling 缺失或异常一律静默降级。
"""
import os
import re

ROOT = __import__("pathlib").Path(__file__).parent
DB_FILE = ROOT / "_cache" / "scrapling" / "adaptive.db"
ENABLED = os.environ.get("NIKO_SL", "1") != "0"

try:                                            # noqa: SIM105
    from scrapling.parser import Selector
except Exception:                               # Scrapling 未安装 → 全程降级
    Selector = None


def available() -> bool:
    return bool(ENABLED and Selector is not None)


def _prep(h: str) -> str:
    """MediaWiki 把类名里的下划线转义成 &#95;，先还原。"""
    return h.replace("&#95;", "_")


def _page(html: str, url: str, adaptive: bool):
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    return Selector(
        _prep(html),
        url=url or "",
        adaptive=adaptive,
        storage_args={"storage_file": str(DB_FILE), "url": url or ""},
    )


# ------------------------------------------------------- 队伍名合法性（强判据）

TEAM_A = 'a[href^="/counterstrike/"]'
ENEMY_A = '[data-team-shortname]'
TIMER_A = '[data-timestamp]'

_MAPS = {
    "ancient", "anubis", "cache", "cobblestone", "dust ii", "dust2", "inferno",
    "mirage", "nuke", "overpass", "train", "vertigo", "chlorine", "basil",
    "edin", "insertion ii", "breach", "gold", "agency", "gravity", "gauntlet",
}


def _unesc(s: str) -> str:
    import html as _H
    return re.sub(r"\s+", " ", _H.unescape(s or "")).strip()


_BAD_WORDS = {
    "previous", "next", "edit", "edit source", "source", "page", "talk",
    "cs2", "counter-strike", "counterstrike", "liquipedia", "liquipedia.net",
    "members", "staff", "ranking", "rankings", "overview", "portal", "main",
    "tournaments", "results", "statistics", "transfers", "all", "upcoming",
}


def ok_team(t: str) -> bool:
    """是不是一个像样的队伍名。宁可漏判，不可误纳。"""
    if not t or len(t) < 2 or len(t) > 30:
        return False
    low = t.lower()
    if low in _BAD_WORDS:                       # 导航/版面词
        return False
    if t.startswith(("Category:", "File:", "Edit", "Template:")):
        return False
    if "/" in t:                       # 页面路径型链接（赛事子页/地图壳）
        return False
    if re.search(r"\b20\d{2}\b", t):   # 「Boston 2026」之类
        return False
    if low in _MAPS:                   # 地图名
        return False
    if re.fullmatch(r"[\d\s\W]+", t):  # 纯数字/符号
        return False
    return True


def _team_of(el):
    """从 <a> 取合格队伍名，不合法返回 ''。"""
    t = _unesc(el.attrib.get("title") or "")
    if not t:
        t = _unesc(el.get_all_text() if hasattr(el, "get_all_text") else "")
    t = re.sub(r"^Team\s+", "", t).strip()
    return t if ok_team(t) else ""


def _teams_in(node, maxn=2):
    """节点子树里的合格队伍名（至多 maxn 个，按出现顺序）。"""
    out = []
    for lk in node.css(TEAM_A):
        n = _team_of(lk)
        if n and n not in out:
            out.append(n)
        if len(out) >= maxn:
            break
    return out


def _ancestors(el, upto=8):
    cur, out = [], []
    cur = el
    for _ in range(upto):
        try:
            cur = cur.parent
        except Exception:
            break
        if cur is None:
            break
        out.append(cur)
    return out


def _attr(el, name):
    return (el.attrib.get(name) or "") if hasattr(el, "attrib") else ""


def _int_cell(node):
    """节点文本是否为一个战绩/比分数字。"""
    t = _unesc(node.get_all_text() if hasattr(node, "get_all_text") else "")
    return t if re.fullmatch(r"\d+(?:[.:\-]\d+)?", t) else ""


# ------------------------------------------------------------------ upcoming

def sl_upcoming(page, raw_html: str, limit=16):
    """强判据：data-timestamp + 同一祖先内两支合格队伍。实测质量优秀。"""
    out, seen = [], set()
    for t in page.css(TIMER_A):
        ts = _attr(t, "data-timestamp")
        if not ts.isdigit():
            continue
        for anc in _ancestors(t, 6):
            names = _teams_in(anc, 2)
            if len(names) < 2:
                continue
            k = (tuple(sorted(names)), ts)
            if k in seen:
                break
            seen.add(k)
            out.append({
                "stage": "", "bo": "", "ts": int(ts),
                "a": {"name": names[0], "full": names[0], "short": "",
                      "score": None, "win": False},
                "b": {"name": names[1], "full": names[1], "short": "",
                      "score": None, "win": False},
            })
            break
    out.sort(key=lambda x: x["ts"])
    return out[:limit]


# ------------------------------------------------------------------ brackets

def _entry_name(en):
    """一个对阵条目元素 → (队名, 简称, 比分, 是否胜)。"""
    short = _unesc(_attr(en, "data-team-shortname"))
    name = ""
    for lk in en.css(TEAM_A):
        n = _team_of(lk)
        if n:
            name = n
            break
    if not name:
        lbl = _unesc(_attr(en, "aria-label"))
        name = re.sub(r"^Team\s+", "", lbl) if ok_team(lbl) else ""
    score = None
    for cand in ("[class*=brkts-opponent-score-inner]", "b"):
        for sc in en.css(cand):
            t = _unesc(sc.get_all_text() if hasattr(sc, "get_all_text") else "")
            if t.isdigit():
                score = int(t)
                break
        if score is not None:
            break
    cls = (_attr(en, "class") or "")
    return name, short, score, ("brkts-opponent-win" in cls)


# 对阵条目的候选锚点，按顺序尝试：
#   data-team-shortname —— 淘汰赛 / playoffs 模板用（如 IEM Cologne Playoffs）
#   aria-label          —— 小组赛 / 瑞士轮模板用（如 EPL S24）
# 两者都是 data 属性，比 class 名稳定得多。
_BRACKET_ANCHORS = ("[data-team-shortname]", "[aria-label]")


def _ts_of(en, anc):
    """一场对阵的开赛时间戳：自身/容器自身/容器子树/祖先链依次找。"""
    for node in (en, anc):
        v = _attr(node, "data-timestamp")
        if v.isdigit():
            return v
        for t in node.css(TIMER_A):
            v = _attr(t, "data-timestamp")
            if v.isdigit():
                return v
    for p in _ancestors(anc, 6):
        v = _attr(p, "data-timestamp")
        if v.isdigit():
            return v
    return ""


def _matches_by_anchor(page, anchor):
    ents = page.css(anchor)
    if not ents:
        return []
    ms, seen = [], set()
    for en in ents:
        # 找「最小的、只容纳一场对阵」的祖先：
        #   条目数 <2 太细，>4 说明这一层已经是整个赛区（会把所有人配成一场）
        for anc in _ancestors(en, 6):
            sub = anc.css(anchor)
            if not (2 <= len(sub) <= 4):
                continue
            a, b = _entry_name(sub[0]), _entry_name(sub[1])
            ts = _ts_of(en, anc)
            # 硬约束：没有比分也没有开赛时间 → 不是对阵（多为导航/模板碎片）
            if (a[2] is None and b[2] is None) and not ts:
                break
            # 双方缺一、或两边同名（锚点落在同一队伍的两个链接上）→ 不是对阵
            if not a[0] or not b[0] or a[0] == b[0]:
                break
            k = (tuple(sorted([a[0], b[0]])), ts)
            if k in seen:
                break
            seen.add(k)
            ms.append({
                "a": {"name": a[0], "full": a[0], "short": a[1],
                      "score": a[2], "win": a[3]},
                "b": {"name": b[0], "full": b[0], "short": b[1],
                      "score": b[2], "win": b[3]},
                "ts": int(ts) if ts else None,
                "bo": "", "round": 0, "depth": 0,
            })
            break
    ms.sort(key=lambda x: (x["ts"] or 0, x["a"]["name"]))
    return ms


def sl_brackets(page, raw_html: str):
    """强判据：锚定对阵条目的 data 属性，非 class 名。

    页面连这些属性都没有（改版幅度超出预期）就返回空——宁可留白，不塞伪对阵。
    """
    for anchor in _BRACKET_ANCHORS:
        ms = _matches_by_anchor(page, anchor)
        if ms:
            return [{"title": "对阵",
                     "rounds": [{"name": "全部对阵", "matches": ms}],
                     "count": len(ms)}]
    return []


# -------------------------------------------------------------------- groups

def sl_groups(page, raw_html: str):
    """强判据：同一 table 祖先、≥4 行、每行队伍名合格且含≥3个战绩数字。"""
    buckets, order = {}, []
    for tr in page.css("tr"):
        team = ""
        for lk in tr.css(TEAM_A):
            team = _team_of(lk)
            if team:
                break
        if not team:
            for hl in tr.css("[data-highlightingclass]"):
                v = re.sub(r"^Team\s+", "", _unesc(_attr(hl, "data-highlightingclass")))
                if ok_team(v):
                    team = v
                    break
        if not team:
            continue
        nums = [n for n in (_int_cell(td) for td in tr.css("td")) if n]
        if len(nums) < 3:
            continue
        key = None
        for anc in _ancestors(tr, 6):
            tag = (anc.tag or "").lower().split("}")[-1]
            if tag == "table":
                key = id(anc)
                break
        if key is None:
            continue
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        seen = {r["team"] for r in buckets[key]}
        if team not in seen:
            buckets[key].append({"team": team, "nums": nums})

    out = []
    for i, key in enumerate(order, 1):
        rows = buckets[key]
        if len(rows) >= 4:                      # 小组/瑞士轮至少 4 队
            out.append({"title": f"积分榜 {i}", "cols": ["队伍", "战绩"],
                        "rows": rows})
    return out


# ------------------------------------------------------------------ 对外入口

def heal(html: str, missing: list, url: str = "") -> dict:
    """对 missing 里的字段做自愈，返回 {字段: 数据}（没抓到就不含该键）。

    第一轮 L1 语义选择器（强判据）；仍有缺再试 L2 adaptive 指纹重定位。
    """
    res = {}
    if not missing or not available():
        return res
    for first in (True, False):
        todo = [k for k in missing if k not in res]
        if not todo:
            break
        try:
            page = _page(html, url, adaptive=not first)
        except Exception:
            break
        for k in todo:
            if k == "participants":
                continue                        # 留到最后从已验证数据反推
            try:
                got = _HANDLERS[k](page, html)
            except Exception:
                got = []
            if got:
                res[k] = got

    # participants 不独立猜：只从已验证有效的 groups/upcoming 反推
    if "participants" in missing and "participants" not in res:
        names = []
        for g in res.get("groups", []):
            names += [r["team"] for r in g["rows"]]
        for u in res.get("upcoming", []):
            names += [u["a"]["name"], u["b"]["name"]]
        seen, parts = set(), []
        for n in names:
            if n and n not in seen and ok_team(n):
                seen.add(n)
                parts.append({"name": n, "logo": ""})
        if parts:
            res["participants"] = parts
    return res


_HANDLERS = {
    "groups": sl_groups,
    "brackets": sl_brackets,
    "upcoming": sl_upcoming,
}


def refresh_fingerprints(html: str, url: str) -> bool:
    """主解析器健康时调用：把当前形态写入指纹库，供未来改版后 adaptive 重定位。

    返回是否成功写入。任何异常都吞掉——指纹更新失败不影响正常解析。
    """
    if not available() or not url:
        return False
    try:
        page = _page(html, url, adaptive=True)
        for _k, sel in (("m", ".brkts-match"),
                        ("p", ".team-participant-card__opponent"),
                        ("t", "table.wikitable")):
            page.css(sel, identifier=_k, adaptive=True, auto_save=True)
        return True
    except Exception:
        return False
