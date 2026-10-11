"""Parse Falcons matches out of a rendered Liquipedia CS wiki page."""
import re
import sys


def strip_tags(s):
    return re.sub(r"<[^>]+>", "", s)


def split_match_blocks(html):
    idx = [m.start() for m in re.finditer(r'<div class="match-info">', html)]
    blocks = []
    for i, s in enumerate(idx):
        e = idx[i + 1] if i + 1 < len(idx) else len(html)
        blocks.append(html[s:e])
    return blocks


def parse_block(b):
    ts = re.search(r'data-timestamp="(\d+)"', b)
    if not ts:
        return None
    finished = "data-finished=\"finished\"" in b

    names = re.findall(r'<span class="name"[^>]*>\s*<a[^>]*title="([^"]+)"', b)
    if len(names) < 2:
        names = re.findall(r'<div class="block-team[^"]*">.*?<span class="name"[^>]*>\s*<a[^>]*>([^<]+)</a>', b, re.S)
    if len(names) < 2:
        return None

    scores = re.findall(r'match-info-header-scoreholder-score[^"]*">(\d+)</span>', b)
    bo = re.search(r'scoreholder-lower">\(?(Bo\d)\)?', b)

    left_win = 'match-info-header-opponent-left match-info-header-winner' in b

    tpart = b[b.find("match-info-tournament"):] if "match-info-tournament" in b else ""
    tpart = re.sub(r"<img[^>]*>", "", tpart)
    links = re.findall(r'<a[^>]*>([^<]+)</a>', tpart)
    tour = next((x.strip() for x in links if x.strip()), "")
    tour = tour.replace("#Group", " Group").replace("/", " ")

    return {
        "ts": int(ts.group(1)),
        "finished": finished,
        "left": names[0].replace("Team ", ""),
        "right": names[1].replace("Team ", ""),
        "score": [int(x) for x in scores] if len(scores) == 2 else None,
        "bo": bo.group(1) if bo else "",
        "left_win": left_win,
        "tournament": tour,
    }


def main():
    html = open(sys.argv[1], encoding="utf-8").read()
    out = []
    for b in split_match_blocks(html):
        m = parse_block(b)
        if not m:
            continue
        if "Falcons" not in (m["left"], m["right"]):
            continue
        out.append(m)
    out.sort(key=lambda x: x["ts"])
    seen = set()
    for m in out:
        key = (m["ts"], m["left"], m["right"])
        if key in seen:
            continue
        seen.add(key)
        import datetime
        dt = datetime.datetime.utcfromtimestamp(m["ts"])
        print(dt.strftime("%Y-%m-%d %H:%M UTC"), "|", m["left"], "vs", m["right"],
              "|", m["score"], "|", m["bo"], "| fin=", m["finished"],
              "| leftwin=", m["left_win"], "|", m["tournament"])


if __name__ == "__main__":
    main()
