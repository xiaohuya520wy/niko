"""Fetch rendered Liquipedia pages, respecting the 1 req / 30s parse limit."""
import urllib.request
import json
import gzip
import urllib.parse
import time
import sys

UA = {
    "User-Agent": "NikoTracker/1.0 (personal CS2 fan page; contact: user@example.com)",
    "Accept-Encoding": "gzip",
}


def get(page):
    url = "https://liquipedia.net/counterstrike/api.php?" + urllib.parse.urlencode(
        {"action": "parse", "page": page, "prop": "text", "format": "json"})
    req = urllib.request.Request(url, headers=UA)
    r = urllib.request.urlopen(req, timeout=90)
    raw = r.read()
    if r.headers.get("Content-Encoding") == "gzip":
        raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8"))["parse"]["text"]["*"]


if __name__ == "__main__":
    jobs = [("Esports_World_Cup/2026", "ewc26.html"),
            ("Intel_Extreme_Masters/2026/Beijing", "iem_beijing.html")]
    if len(sys.argv) > 1:
        jobs = jobs[:int(sys.argv[1])]
    for i, (page, fn) in enumerate(jobs):
        try:
            h = get(page)
            open(fn, "w", encoding="utf-8").write(h)
            print(page, "->", fn, "len", len(h), "scoreholders",
                  h.count('match-info-header-scoreholder"'), "falcons", h.count("Falcons"))
        except Exception as e:
            print(page, "ERR", type(e).__name__, e)
        if i + 1 < len(jobs):
            time.sleep(32)
