"""核心数据管线：Liquipedia 赛事页 HTML -> 带地图详情的比赛列表 -> 完整 data.json。

run.py（联网抓取）与 build_data.py（读本地缓存）共用这里 mener 的逻辑，
保证本机迭代结果与 GitHub Actions 产出完全一致。
"""
import datetime
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).parent
SINCE = datetime.datetime(2025, 9, 1, tzinfo=datetime.timezone.utc)

EVENT_NAMES = {
    "BLAST/Open/2025/Fall": "BLAST 公开赛 2025 秋季",
    "FISSURE/Playground/2": "FISSURE Playground #2",
    "FISSURE/Playground/3": "FISSURE Playground #3",
    "ESL/Pro_League/Season_22": "ESL 职业联赛 S22",
    "BLAST/Bounty/2026/Winter": "BLAST Bounty 冬季赛 2026",
    "Intel_Extreme_Masters/2026/Kraków": "IEM 克拉科夫 2026",
    "PGL/2026/Cluj-Napoca": "PGL 克卢日-纳波卡 2026",
    "BLAST/Open/2026/Spring": "BLAST 公开赛 鹿特丹站",
    "BLAST/Open/2026/Fall": "BLAST 波尔图公开赛",
    "Intel_Extreme_Masters/2026/Rio": "IEM 里约 2026",
    "PGL/2026/Astana": "PGL 阿斯塔纳 2026",
    "CS_Asia_Championships/2026": "CS 亚洲锦标赛 2026",
    "Esports_World_Cup/2026": "电竞世界杯 2026",
    "Intel_Extreme_Masters/2026/Cologne": "IEM 科隆 Major 2026",
    "BLAST/Bounty/2026/Summer": "BLAST Bounty 夏季赛 2026",
    "Intel_Extreme_Masters/2026/Cologne/Stage_3": "IEM 科隆 Major 2026",
    "Intel_Extreme_Masters/2026/Cologne/Playoffs": "IEM 科隆 Major 2026",
    "BLAST/Bounty/2026/Summer/Qualifier": "BLAST Bounty 夏季赛资格赛",
}


def slug(date, opponent):
    """Stable, URL-safe match id: 2026-09-04-g2-esports"""
    s = re.sub(r"[^a-z0-9]+", "-", opponent.lower()).strip("-")
    return f"{date[:10]}-{s}"


def build_matches(pages):
    """pages: {事件页名: html}. 返回按时间倒序的去重比赛列表。"""
    from parse_detail import extract

    rows = []
    for page, html in pages.items():
        if not html:
            continue
        name = EVENT_NAMES.get(page, page.split("/")[-1].replace("_", " "))
        for m in extract(html):
            if "Falcons" not in m["left"] + m["right"]:
                continue
            if not m["ts"]:
                continue
            dt = datetime.datetime.fromtimestamp(m["ts"], datetime.timezone.utc)
            if dt < SINCE:
                continue
            fi = 0 if "Falcons" in m["left"] else 1
            opp = (m["right"] if fi == 0 else m["left"]).replace("Team ", "")
            fs, os_ = m["score"][fi], m["score"][1 - fi]
            maps_out = []
            for mp in m["maps"]:
                l, r = (mp["left"], mp["right"]) if fi == 0 else (mp["right"], mp["left"])
                win = mp["left_win"] if fi == 0 else (not mp["left_win"] if mp["left_win"] is not None else None)
                maps_out.append({
                    "map": mp["map"],
                    "vetoed": mp["vetoed"],
                    "falcons_win": win,
                    "falcons": l,
                    "opponent": r,
                })
            rows.append({
                "id": slug(dt.strftime("%Y-%m-%dT%H:%M:00Z"), opp),
                "date": dt.strftime("%Y-%m-%dT%H:%M:00Z"),
                "opponent": opp,
                "score": f"{fs}-{os_}",
                "result": "W" if (m["left_win"] == (fi == 0)) else "L",
                "bo": m["bo"],
                "event": name,
                "stage": "",
                "maps": maps_out,
                "links": {
                    "hltv_match": m["hltv_match"],
                    "vods": m["vods"],
                    "hltv_maps": m["hltv_maps"],
                },
                "niko": {"ratings": []},
            })

    seen, uniq = set(), []
    for m in sorted(rows, key=lambda x: x["date"], reverse=True):
        k = (m["date"], m["opponent"], m["score"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(m)
    return uniq


def _opp_key(s):
    """对手名归一化：去空格标点小写，让「G2」能匹配「G2 Esports」。"""
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _load_ratings_store(base):
    """合并 base.json 的 known_ratings（旧）与 ratings.json（新持久库）。"""
    store = {}
    here = pathlib.Path(__file__).parent

    def ingest(entries, prefer=False):
        for d in entries or []:
            date = (d.get("date") or "")[:10]
            key = _opp_key(d.get("opponent") or "")
            if not date or not key:
                continue
            cur = store.get((date, key))
            if cur is None or prefer:
                store[(date, key)] = dict(d)

    ingest(base.get("known_ratings"))
    rf = here / "ratings.json"
    if rf.exists():
        try:
            ingest(json.loads(rf.read_text(encoding="utf-8")).get("entries"), prefer=True)
        except Exception:
            pass
    return store


def _match_ratings(store, date10, opponent):
    """按「日期 + 对手名归一化」精确或前缀匹配评分记录。"""
    k = _opp_key(opponent)
    hit = store.get((date10, k))
    if hit is not None:
        return hit
    for (d, ok), v in store.items():
        if d == date10 and ok and (ok.startswith(k) or k.startswith(ok)):
            return v
    return None


def assemble(base, matches, squad):
    """把静态基座、比赛列表、阵容合并成最终 data.json 结构。"""
    store = _load_ratings_store(base)
    for m in matches:
        src = _match_ratings(store, m["date"][:10], m["opponent"])
        niko = {"ratings": (src or {}).get("ratings", [])}
        for key in ("kd", "adr", "note"):
            if src and src.get(key):
                niko[key] = src[key]
        m["niko"] = niko

    niko_photo = next((p.get("photo", "") for p in squad if p["id"] == "NiKo"), "")

    w = sum(1 for m in matches if m["result"] == "W")
    data = dict(base)
    data.pop("known_ratings", None)
    if niko_photo:
        data["player"]["photo"] = niko_photo
    data["squad"] = squad
    data["recent_matches"] = matches
    data["year_stats"] = {
        "span": "近一年",
        "from": matches[-1]["date"][:10] if matches else "",
        "to": matches[0]["date"][:10] if matches else "",
        "matches": len(matches),
        "wins": w,
        "losses": len(matches) - w,
        "win_rate": round(w / len(matches) * 100, 1) if matches else 0,
        "events": len(set(m["event"] for m in matches)),
    }
    data["meta"]["updated"] = datetime.datetime.now(
        datetime.timezone.utc).isoformat(timespec="seconds")
    return data
