"""Parse every cached event page and produce a one-year Falcons match history."""
import datetime
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from parse_popup import extract

ROOT = pathlib.Path(__file__).parent
EV = ROOT / "_cache" / "events"

EVENT_NAMES = {
    "BLAST_Open_2026_Fall": "BLAST 波尔图公开赛",
    "Esports_World_Cup_2026": "电竞世界杯 2026",
    "Intel_Extreme_Masters_2026_Cologne": "IEM 科隆 Major 2026",
    "Intel_Extreme_Masters_2026_Cologne_Stage_3": "IEM 科隆 Major 2026",
    "Intel_Extreme_Masters_2026_Cologne_Playoffs": "IEM 科隆 Major 2026",
    "BLAST_Bounty_2026_Summer_Qualifier": "BLAST Bounty 夏季赛资格赛",
    "CS_Asia_Championships_2026": "CS 亚洲锦标赛 2026",
    "PGL_2026_Astana": "PGL 阿斯塔纳 2026",
    "Intel_Extreme_Masters_2026_Rio": "IEM 里约 2026",
    "BLAST_Bounty_2026_Winter": "BLAST Bounty 冬季赛 2026",
    "BLAST_Bounty_2026_Summer": "BLAST Bounty 夏季赛 2026",
    "BLAST_Open_2026_Spring": "BLAST 公开赛 鹿特丹站",
    "PGL_2026_Cluj-Napoca": "PGL 克卢日-纳波卡 2026",
    "Intel_Extreme_Masters_2026_Kraków": "IEM 克拉科夫 2026",
    "FISSURE_Playground_2": "FISSURE Playground #2",
    "FISSURE_Playground_3": "FISSURE Playground #3",
    "BLAST_Open_2025_Fall": "BLAST 公开赛 2025 秋季",
    "ESL_Pro_League_Season_22": "ESL 职业联赛 S22",
}


def clean(t):
    t = t.replace("Team ", "")
    return {"Spirit": "Spirit", "Falcons": "Falcons"}.get(t, t)


def main():
    since = datetime.datetime(2025, 9, 1, tzinfo=datetime.UTC)
    out, per_event = [], {}
    for f in sorted(EV.glob("*.html")):
        key = f.stem
        if key == "NiKo":
            continue
        name = EVENT_NAMES.get(key, key.replace("_", " "))
        html = f.read_text(encoding="utf-8")
        got = []
        for m in extract(html):
            if "Falcons" not in m["left"] + m["right"]:
                continue
            if not m["ts"]:
                continue
            dt = datetime.datetime.fromtimestamp(m["ts"], datetime.UTC)
            if dt < since:
                continue
            fi = 0 if "Falcons" in m["left"] else 1
            opp = clean(m["right"] if fi == 0 else m["left"])
            fs, os_ = m["score"][fi], m["score"][1 - fi]
            got.append({
                "date": dt.strftime("%Y-%m-%dT%H:%M:00Z"),
                "opponent": opp,
                "score": f"{fs}-{os_}",
                "result": "W" if (m["left_win"] == (fi == 0)) else "L",
                "bo": m["bo"],
                "event": name,
                "stage": "",
                "niko": {"ratings": []},
            })
        if got:
            per_event[name] = len(got)
        out.extend(got)

    # de-duplicate on (date, opponent, score)
    seen, uniq = set(), []
    for m in sorted(out, key=lambda x: x["date"], reverse=True):
        k = (m["date"], m["opponent"], m["score"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(m)

    w = sum(1 for m in uniq if m["result"] == "W")
    print(f"events parsed: {len(per_event)}  matches: {len(uniq)}  record: {w}W-{len(uniq)-w}L")
    for n, c in sorted(per_event.items(), key=lambda x: -x[1]):
        print(f"  {c:>2}  {n}")
    (ROOT / "history.json").write_text(
        json.dumps(uniq, ensure_ascii=False, indent=2), encoding="utf-8")
    print("written history.json")
    return uniq


if __name__ == "__main__":
    main()
