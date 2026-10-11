"""抓取 Team Falcons 现役阵容每位选手的 Liquipedia 页面，供玩家详情/头像提取用。"""
import gzip
import json
import pathlib
import time
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).parent
OUT = ROOT.parent / "_cache" / "players"
OUT.mkdir(parents=True, exist_ok=True)
UA = {
    "User-Agent": "NikoTracker/1.0 (CS2 fan page; contact: user@example.com)",
    "Accept-Encoding": "gzip",
}
API = "https://liquipedia.net/counterstrike/api.php?"

PAGE_IDS = {
    "NiKo": "Nikola Kovač",
    "TeSeS": "René Madsen",
    "m0NESY": "Ilya Osipov",
    "kyousuke": "Maksim Lukin",
    "karrigan": "Finn Andersen",
    "zonic": "Danny Sørensen",
}


def fetch(page, prop="text", tries=4):
    url = API + urllib.parse.urlencode(
        {"action": "parse", "page": page, "prop": prop, "format": "json"})
    last = None
    for _ in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            r = urllib.request.urlopen(req, timeout=90)
            raw = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
            d = json.loads(raw.decode("utf-8"))
            return d["parse"][prop]["*"]
        except Exception as e:
            last = e
            time.sleep(10)
    print(f"  FAIL {page}: {last}")
    return None


def api(params, tries=4):
    url = API + urllib.parse.urlencode(params)
    last = None
    for _ in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            r = urllib.request.urlopen(req, timeout=60)
            raw = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
            return json.loads(raw.decode("utf-8"))
        except Exception as e:
            last = e
            time.sleep(8)
    print(f"  API FAIL: {last}")
    return {}


def main():
    for i, (pid, full) in enumerate(PAGE_IDS.items()):
        html = fetch(pid)
        if html:
            (OUT / f"{pid}.html").write_text(html, encoding="utf-8")
            print(f"[{i+1}/{len(PAGE_IDS)}] {pid} -> {len(html)} bytes", flush=True)
        # 每个选手页面上的图片列表（用于挑最新头像）
        imgs = api({"action": "query", "titles": pid, "prop": "images",
                    "imlimit": "200", "format": "json"})
        pages = imgs.get("query", {}).get("pages", {})
        names = []
        for p in pages.values():
            names = [x["title"] for x in p.get("images", [])]
        names = sorted(set(n for n in names if n.startswith(f"File:{pid} ")))
        (OUT / f"{pid}.images.json").write_text(
            json.dumps(names, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"          -> {len(names)} candidate photos", flush=True)
        if i + 1 < len(PAGE_IDS):
            time.sleep(31)
    print("DONE")


if __name__ == "__main__":
    main()
