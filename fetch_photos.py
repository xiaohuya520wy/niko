"""抓取 NiKo 的官方照片，生成可滑动「照片墙」素材。

来源：Liquipedia 选手页画廊（liquipedia.net/counterstrike/Nikola_Kovac）。
产出：
  assets/photos/<slug>.jpg   每张官方照片（统一压到最长边 <=880px，JPEG q76 渐进式）
  photos.json                [{src, caption, event, year, recent}] 按年份倒序
重跑本脚本即可拉取 Liquipedia 新发布的官方照片（"有更新的"）。
"""
import gzip
import json
import os
import pathlib
import re
import time
import urllib.parse
import urllib.request

from PIL import Image
from io import BytesIO

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "assets" / "photos"
OUT.mkdir(parents=True, exist_ok=True)
UA = {
    "User-Agent": "NikoTracker/1.0 (personal CS2 fan page; contact: user@example.com)",
    "Accept-Encoding": "gzip",
}
PAGE = "Niko"
API = "https://liquipedia.net/counterstrike/api.php"
MAX_EDGE = 880
QUALITY = 76

# 缩写 -> 可读名，用于把文件名整理成说明文字
ABBREV = [
    (r"\bIEM\b", "IEM"),
    (r"\bEPL\b", "EPL"),
    (r"\bBLAST\b", "BLAST"),
    (r"\bDH\b", "DreamHack"),
    (r"\bDHM\b", "DreamHack Masters"),
    (r"\bESL\b", "ESL"),
    (r"\bESLM\b", "ESL Masters"),
    (r"\bEU\b", "欧洲"),
    (r"\bRMR\b", "RMR"),
    (r"\bS(\d)\b", r"S\1"),
    (r"\bFinals?\b", "总决赛"),
    (r"\bMajor\b", "Major"),
]


def get_html_cache():
    """画廊只存在于渲染后的完整 HTML，而 API 解析会把画廊剥掉、直接抓文章又被拦。
    因此优先读已缓存的渲染页（_cache/events/NiKo.html）；用它抽取画廊文件标题最稳。"""
    cache = ROOT / "_cache" / "events" / "NiKo.html"
    if cache.exists():
        return cache.read_text(encoding="utf-8", errors="replace")
    # 兜底：缓存缺失时尝试一次 API 解析（可能不含画廊，但至少有信息框图）
    try:
        url = API + "?" + urllib.parse.urlencode(
            {"action": "parse", "page": PAGE, "prop": "text", "format": "json"})
        r = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90)
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
        return json.loads(raw.decode("utf-8"))["parse"]["text"]["*"]
    except Exception as e:
        print("cache + parse both failed:", e)
        return ""


def gallery_files(h):
    """抽取画廊里每个文件标题（去重）。"""
    titles = []
    for m in re.finditer(r'href="/counterstrike/File:([^"]+)"', h):
        t = m.group(1)
        if t.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            titles.append(t)
    # 去重保序
    seen, uniq = set(), []
    for t in titles:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq


def humanize(title):
    """NiKo_at_BLAST_Open_Spring_2026.jpg -> ('BLAST Open Spring', 2026)。"""
    name = title
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        if name.lower().endswith(ext):
            name = name[: -len(ext)]
            break
    name = re.sub(r"^NiKo_?", "", name)
    name = name.replace("_@_", " @ ").replace("_at_", " @ ").replace("@ ", "@ ")
    year = None
    ym = re.search(r"(20\d{2})", name)
    if ym:
        year = int(ym.group(1))
        name = name.replace(ym.group(1), "").strip(" _-")
    # 缩写美化
    s = name.replace("_", " ").strip()
    s = re.sub(r"\s+", " ", s)
    for pat, rep in ABBREV:
        s = re.sub(pat, rep, s)
    s = re.sub(r"\s+", " ", s).strip(" -@")
    # 去掉开头的 "at "/"@ " 这类连接词
    s = re.sub(r"^(?:at|@)\s*", "", s, flags=re.I).strip(" -@")
    # Season 9 -> S9；清理多余连字符空格
    s = re.sub(r"Season\s+(\d+)", r"S\1", s, flags=re.I)
    s = re.sub(r"\s*-\s*", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s, year


def slugify(title):
    # 先去掉文件扩展名，避免 niko_x_2025_jpg.jpg 这种双后缀
    base = title
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        if base.lower().endswith(ext):
            base = base[: -len(ext)]
            break
    s = base.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")


def download(file_title):
    """用 Special:FilePath 取原图，压尺寸后落盘，返回 (path, caption, year)。
    若目标文件已存在则跳过下载，仅重算元数据（重跑很快）。"""
    # 画廊 href 里的标题可能带 %C3%B6 这种百分号编码，先解码成真实文件名
    real_title = urllib.parse.unquote(file_title)
    slug = slugify(real_title)
    out = OUT / (slug + ".jpg")
    if out.exists() and out.stat().st_size > 2000:
        caption, year = humanize(real_title)
        try:
            with Image.open(out) as im:
                size = im.size
        except Exception:
            size = (0, 0)
        return str(out.relative_to(ROOT)).replace("\\", "/"), caption, year, size
    url = ("https://liquipedia.net/counterstrike/Special:FilePath/"
           + urllib.parse.quote(real_title))
    data = None
    for attempt in range(3):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120)
            data = r.read()
            break
        except Exception as e:
            print(f"  download retry {attempt+1}", real_title, e)
            time.sleep(2)
    if not data:
        return None
    try:
        im = Image.open(BytesIO(data)).convert("RGB")
    except Exception as e:
        print("  decode ERR", real_title, e)
        return None
    w, h = im.size
    if max(w, h) > MAX_EDGE:
        scale = MAX_EDGE / max(w, h)
        im = im.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    im.save(out, "JPEG", quality=QUALITY, optimize=True)
    caption, year = humanize(real_title)
    return str(out.relative_to(ROOT)).replace("\\", "/"), caption, year, im.size


def main():
    print("load NiKo gallery (cached render)")
    h = get_html_cache()
    files = gallery_files(h)
    print("gallery photos:", len(files))
    photos = []
    for i, f in enumerate(files):
        print(f"  [{i+1}/{len(files)}] {f}")
        res = download(f)
        if res:
            src, _cap, _yr, size = res
            real = urllib.parse.unquote(f)
            event, year = humanize(real)
            caption = (f"{event} {year}" if year else event).strip()
            photos.append({"src": src, "caption": caption,
                           "year": year or 0, "recent": (year or 0) >= 2024,
                           "w": size[0], "h": size[1]})
        time.sleep(1.2)
    # 按年份倒序（新的在前）；同年按 caption
    photos.sort(key=lambda p: (-(p["year"] or 0), p["caption"]))
    for p in photos:
        p.pop("w", None)
        p.pop("h", None)
    (ROOT / "photos.json").write_text(
        json.dumps(photos, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote photos.json:", len(photos), "photos")
    print("hero (newest):", photos[0]["src"], photos[0]["caption"], photos[0]["year"])


if __name__ == "__main__":
    main()
