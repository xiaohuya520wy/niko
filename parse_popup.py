"""Extract every series on a Liquipedia bracket/tournament page via popup scoreholders."""
import re
import sys
import datetime


def extract(html):
    out = []
    for m in re.finditer(r'match-info-header-scoreholder"', html):
        p = m.end()
        seg = html[p:p + 900]
        sc = re.findall(r'scoreholder-score[^"]*">(\d+)</span>', seg)
        if len(sc) < 2:
            continue
        bo = re.search(r'scoreholder-lower">\((Bo\d)\)', seg)
        left_ctx = html[max(0, m.start() - 4000):m.start()]
        right_ctx = html[p:p + 4000]

        def team(ctx, reverse=False):
            names = re.findall(r'data-team-name="([^"]+)"', ctx)
            if not names:
                names = re.findall(r'aria-label="([^"]+)"', ctx)
            if not names:
                return ""
            return names[-1] if reverse else names[0]

        left = team(left_ctx, reverse=True)
        right = team(right_ctx)
        ts = re.findall(r'data-timestamp="(\d+)"', left_ctx)
        out.append({
            "left": left.replace("Team ", ""),
            "right": right.replace("Team ", ""),
            "score": [int(sc[0]), int(sc[1])],
            "bo": bo.group(1) if bo else "",
            "ts": int(ts[-1]) if ts else None,
            "left_win": 'match-info-header-winner' in left_ctx[-1500:],
        })
    return out


def main():
    html = open(sys.argv[1], encoding="utf-8").read()
    seen = set()
    rows = []
    for m in extract(html):
        if "Falcons" not in m["left"] + m["right"]:
            continue
        k = (m["left"], m["right"], tuple(m["score"]))
        if k in seen:
            continue
        seen.add(k)
        rows.append(m)
    rows.sort(key=lambda x: x["ts"] or 0)
    for m in rows:
        dt = (datetime.datetime.fromtimestamp(m["ts"], datetime.UTC).strftime("%m-%d %H:%M")
              if m["ts"] else "??-?? ??:??")
        fi = 0 if "Falcons" in m["left"] else 1
        fs, os_ = m["score"][fi], m["score"][1 - fi]
        res = "W" if (m["left_win"] == (fi == 0)) else "L"
        print(f"{dt} | {fs}-{os_} {res} vs {m['right'] if fi == 0 else m['left']} | {m['bo']}")


if __name__ == "__main__":
    main()
