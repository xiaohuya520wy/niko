"""Batch-fetch Liquipedia pages into _cache/events, honouring 1 parse req / 30s."""
import gzip
import json
import pathlib
import time
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "_cache" / "events"
OUT.mkdir(parents=True, exist_ok=True)

UA = {
    "User-Agent": "NikoTracker/1.0 (personal CS2 fan page; contact: user@example.com)",
    "Accept-Encoding": "gzip",
}
API = "https://liquipedia.net/counterstrike/api.php?"

PAGES = [
    "NiKo",
    "BLAST/Open/2025/Fall",
    "FISSURE/Playground/2",
    "FISSURE/Playground/3",
    "ESL/Pro_League/Season_22",
    "BLAST/Bounty/2026/Winter",
    "Intel_Extreme_Masters/2026/Kraków",
    "PGL/2026/Cluj-Napoca",
    "BLAST/Open/2026/Spring",
    "Intel_Extreme_Masters/2026/Rio",
    "PGL/2026/Astana",
    "CS_Asia_Championships/2026",
    "Intel_Extreme_Masters/2026/Cologne",
    "BLAST/Bounty/2026/Summer",
    "Intel_Extreme_Masters/2026/Cologne/Stage_3",
    "Intel_Extreme_Masters/2026/Cologne/Playoffs",
    "BLAST/Bounty/2026/Summer/Qualifier",
]


def fetch(page):
    url = API + urllib.parse.urlencode(
        {"action": "parse", "page": page, "prop": "text", "format": "json"})
    req = urllib.request.Request(url, headers=UA)
    r = urllib.request.urlopen(req, timeout=90)
    raw = r.read()
    if r.headers.get("Content-Encoding") == "gzip":
        raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8"))["parse"]["text"]["*"]


for i, page in enumerate(PAGES):
    fn = OUT / (page.replace("/", "_") + ".html")
    if fn.exists():
        print("skip", page)
        continue
    try:
        h = fetch(page)
        fn.write_text(h, encoding="utf-8")
        flag = "FALCONS" if "Falcons" in h else "-"
        print(f"[{i+1}/{len(PAGES)}] {page} -> {len(h)} bytes  {flag}  scoreholders="
              f"{h.count('match-info-header-scoreholder\"')}", flush=True)
    except Exception as e:
        print(f"[{i+1}/{len(PAGES)}] {page} ERR {type(e).__name__} {e}", flush=True)
    if i + 1 < len(PAGES):
        time.sleep(31)

print("DONE", flush=True)
