"""Parse Falcons series results out of a rendered Liquipedia bracket page."""
import re
import sys


def split_matches(html):
    idx = [m.start() for m in re.finditer(r'<div class="brkts-match[ "]', html)]
    return [html[s:(idx[i + 1] if i + 1 < len(idx) else len(html))] for i, s in enumerate(idx)]


def parse(b):
    entries = re.findall(
        r'<div class="brkts-opponent-entry[^"]*" aria-label="([^"]*)"(.*?)(?=<div class="brkts-opponent-entry|$)',
        b, re.S)
    if len(entries) < 2:
        return None
    teams, scores, wins = [], [], []
    for name, rest in entries[:2]:
        teams.append(name.replace("Team ", "").replace(" Esports", ""))
        sc = re.search(r'brkts-opponent-score-inner[^>]*><b>(\d+)</b>', rest)
        scores.append(int(sc.group(1)) if sc else None)
        wins.append("brkts-opponent-win" in rest[:400])
    if "Falcons" not in " ".join(teams):
        return None
    ts = re.search(r'data-timestamp="(\d+)"', b)
    bo = re.search(r'match-info-header-scoreholder-lower">\((Bo\d)\)', b)
    return {
        "teams": teams,
        "scores": scores,
        "wins": wins,
        "ts": int(ts.group(1)) if ts else None,
        "bo": bo.group(1) if bo else "",
    }


def main():
    html = open(sys.argv[1], encoding="utf-8").read()
    seen = set()
    for b in split_matches(html):
        m = parse(b)
        if not m or None in m["scores"]:
            continue
        key = tuple(m["teams"])
        if key in seen:
            continue
        seen.add(key)
        fi = 0 if "Falcons" in m["teams"][0] else 1
        opp = m["teams"][1 - fi]
        fs, os_ = m["scores"][fi], m["scores"][1 - fi]
        print(f"Falcons {fs}:{os_} {opp}  win={m['wins'][fi]}  bo={m['bo']}  ts={m['ts']}")


if __name__ == "__main__":
    main()
