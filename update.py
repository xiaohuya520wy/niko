"""Refresh data.json from Liquipedia, then rebuild index.html.

Run manually or from a scheduler. Respects Liquipedia's API terms:
custom User-Agent, gzip, and 1 `action=parse` request per 30 seconds.
"""
import datetime
import html as H
import json
import pathlib
import re
import sys
import time
import urllib.parse
import urllib.request
import gzip

ROOT = pathlib.Path(__file__).parent
UA = {
    "User-Agent": "NikoTracker/1.0 (personal CS2 fan page; contact: user@example.com)",
    "Accept-Encoding": "gzip",
}
API = "https://liquipedia.net/counterstrike/api.php?"


def fetch(page):
    url = API + urllib.parse.urlencode(
        {"action": "parse", "page": page, "prop": "text", "format": "json"})
    req = urllib.request.Request(url, headers=UA)
    r = urllib.request.urlopen(req, timeout=90)
    raw = r.read()
    if r.headers.get("Content-Encoding") == "gzip":
        raw = gzip.decompress(raw)
    return H.unescape(json.loads(raw.decode("utf-8"))["parse"]["text"]["*"])


def tournament_of(block):
    if "match-info-tournament" not in block:
        return ""
    seg = re.sub(r"<img[^>]*>", "", block[block.find("match-info-tournament"):])
    for t in re.findall(r"<a[^>]*>([^<]+)</a>", seg):
        if t.strip():
            return t.strip()
    for t in re.findall(r'<a[^>]*title="([^"]+)"', seg):
        if t.strip():
            return t.strip().split("#")[0].replace("/", " ")
    return ""


def parse_ticker(html):
    """Pull every Falcons series out of the main-page MatchTicker."""
    idx = [m.start() for m in re.finditer(r'<div class="match-info">', html)]
    out = []
    for i, s in enumerate(idx):
        b = html[s:(idx[i + 1] if i + 1 < len(idx) else len(html))]
        ts = re.search(r'data-timestamp="(\d+)"', b)
        if not ts:
            continue
        names = re.findall(r'<span class="name"[^>]*>\s*<a[^>]*title="([^"]+)"', b)
        if len(names) < 2:
            continue
        if not any("Falcons" in n for n in names[:2]):
            continue
        names = [n.replace("Team ", "") for n in names[:2]]
        sc = re.findall(r'match-info-header-scoreholder-score[^"]*">(\d+)</span>', b)
        bo = re.search(r'scoreholder-lower">\((Bo\d)\)', b)
        left_win = "match-info-header-opponent-left match-info-header-winner" in b
        finished = 'data-finished="finished"' in b
        fi = 0 if "Falcons" in names[0] else 1
        opp = names[1 - fi]
        if len(sc) == 2:
            fs, os_ = int(sc[fi]), int(sc[1 - fi])
            score = f"{fs}-{os_}"
            result = "W" if (left_win == (fi == 0)) else "L"
        else:
            score, result = "-", ""
        out.append({
            "date": datetime.datetime.fromtimestamp(
                int(ts.group(1)), datetime.UTC).strftime("%Y-%m-%dT%H:%M:00Z"),
            "opponent": opp,
            "score": score,
            "result": result,
            "bo": bo.group(1) if bo else "",
            "event": tournament_of(b),
            "stage": "",
            "finished": finished,
        })
    return out


def parse_upcoming(html):
    i = html.find("Upcoming Tournaments")
    seg = html[i:i + 12000] if i >= 0 else html
    out = []
    for m in re.finditer(
            r'<div class="tournaments-list-item">(.*?)(?=<div class="tournaments-list-item">|$)',
            seg, re.S):
        b = m.group(1)
        name = re.search(r'tournaments-list-item__name"><a[^>]*>([^<]+)</a>', b)
        date = re.search(r'tournaments-list-item__date">([^<]*)<', b)
        tier = re.search(r'tournament-badge__text">([^<]+)<', b)
        link = re.search(r'href="(/counterstrike/[^"]+)"', b)
        if not name:
            continue
        dt = (date.group(1) if date else "").replace("–", " – ")
        out.append({
            "name": name.group(1),
            "short": name.group(1),
            "tier": tier.group(1) if tier else "",
            "date_text": dt,
            "start": "",
            "status": "opponent_tbd",
            "url": "https://liquipedia.net" + link.group(1) if link else "",
        })
    return out


def main():
    data = json.loads((ROOT / "data.json").read_text(encoding="utf-8"))
    changed = []

    if "--no-fetch" not in sys.argv:
        main_html = fetch("Main_Page")
        time.sleep(32)
        team_html = fetch("Team_Falcons")
        (ROOT / "cache_main.html").write_text(main_html, encoding="utf-8")
        (ROOT / "cache_team.html").write_text(team_html, encoding="utf-8")
    else:
        main_html = (ROOT / "cache_main.html").read_text(encoding="utf-8")
        team_html = (ROOT / "cache_team.html").read_text(encoding="utf-8")

    ticker = parse_ticker(main_html)
    print(f"ticker: {len(ticker)} Falcons series")

    known = {(m["date"][:10], m["opponent"]): m for m in data["recent_matches"]}
    added = 0
    for t in ticker:
        if not t["finished"] or not t["result"]:
            continue
        key = (t["date"][:10], t["opponent"])
        if key in known:
            old = known[key]
            if old["score"] != t["score"] or old["result"] != t["result"]:
                old.update(score=t["score"], result=t["result"])
                changed.append(f"{key} -> {t['score']} {t['result']}")
            if t["event"] and not old.get("event"):
                old["event"] = t["event"]
        else:
            t.pop("finished")
            t["niko"] = {"ratings": []}
            data["recent_matches"].append(t)
            known[key] = t
            added += 1
            changed.append(f"+ {key} {t['score']} {t['result']}")

    data["recent_matches"].sort(key=lambda m: m["date"], reverse=True)
    data["recent_matches"] = data["recent_matches"][:15]

    ups = parse_upcoming(team_html)
    if ups:
        merged = []
        old_by_name = {u["name"]: u for u in data["upcoming_tournaments"]}
        for u in ups:
            prev = old_by_name.get(u["name"])
            if prev:
                u["start"] = prev.get("start", "")
                u["short"] = prev.get("short", u["short"])
            merged.append(u)
        data["upcoming_tournaments"] = merged
        changed.append(f"upcoming: {[u['name'] for u in merged]}")

    data["meta"]["updated"] = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    (ROOT / "data.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"added {added} new, {len(changed)} changes")
    for c in changed:
        print("  ", c)


if __name__ == "__main__":
    main()
