"""抓取 NiKo 本人的官方照片，生成可滑动「照片墙」素材。

铁律（2026-11-10 用户明确要求）：这是 NiKo 个人站，照片墙里每一张都必须有 NiKo。
  - 只收 Liquipedia 上以大写 K 的 "NiKo..." 命名的选手本人照片；
  - 队友单人照、全队合照一律不进 photos.json（队友 2026 新队服照在 assets/players/ 供阵容页使用）；
  - 小写 "Niko ..." 是另一位戴眼镜的丹麦选手，绝不能混进来；
  - 历史遗留的 niko_ts.jpg 与 NiKo 不符，列入黑名单。
来源：Liquipedia 选手页画廊（liquipedia.net/counterstrike/NiKo）。
产出：
  assets/photos/<slug>.jpg   NiKo 本人照片（统一压到最长边 <=880px，JPEG q76）
  photos.json                [{src, caption, year, recent, who}] 按年份倒序
重跑本脚本只会补充 NiKo 新照片，并自动清理任何混进来的非 NiKo 条目。
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
PAGE = "NiKo"
API = "https://liquipedia.net/counterstrike/api.php"
MAX_EDGE = 880
QUALITY = 76

# 明确不是 NiKo 本人 / 无法确认出镜的文件，重跑时永远剔除。
# niko_ts.jpg 来源 NiKo TS.png，画面里是另一位黑衣抱臂的选手，与 NiKo 不符。
BLOCKLIST = {"niko_ts.jpg"}

# 允许的手工补充照片：必须是逐张核验过确实有 NiKo 的，才能加进这个白名单。
# 目前是 Liquipedia commons 的 "NiKo @ APM Season 2 Finals.jpg"（年轻 NiKo 红衣）。
MANUAL_NIKO = [
    {"src": "assets/photos/niko_at_apm_season_2_finals_2.jpg",
     "caption": "NiKo · APM Season 2 总决赛", "year": 0, "recent": False, "who": "NiKo"},
]

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
    # 缓存实际散落在几个位置，依次找；之前只认 _cache/events 导致重跑时
    # 静默退化到 API parse（拿不到画廊），照片墙会被清空。
    for rel in ("_cache/events/NiKo.html",
                "_verify/photos/NiKo.html",
                "_verify/photos/NiKo_page.html",
                "_fixtures/player-niko.html"):
        cache = ROOT / rel
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


def is_niko_photo(title: str) -> bool:
    """NiKo 本人照片的硬门槛。

    Liquipedia 上大写 K 的 "NiKo ..." 才是 Nikola Kovač；
    小写 "Niko ..." 多数是另一位戴眼镜的丹麦选手（另有 "Niko Swedish player"、
    "Niko (Danish player)"、"MYTH Niko" 等），绝不能进 NiKo 的照片墙。
    队伍合照/队标（Falcons/G2/Mousesports...）同样不符合「每张必须有 NiKo」。
    """
    real = urllib.parse.unquote(title)
    stem = re.sub(r"\.(jpg|jpeg|png|webp)$", "", real, flags=re.I)
    if not stem.startswith("NiKo"):
        return False
    if slugify(real) + ".jpg" in BLOCKLIST:
        return False
    return True


def gallery_files(h):
    """抽取画廊里 NiKo 本人的文件标题（去重，只认 NiKo 前缀）。"""
    titles = []
    for m in re.finditer(r'href="[^"]*File:([^"]+)"', h):
        t = m.group(1)
        if t.lower().endswith((".jpg", ".jpeg", ".png", ".webp")) and is_niko_photo(t):
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
    print("load NiKo gallery (NiKo-only guard ON)")
    h = get_html_cache()
    files = gallery_files(h)
    print("NiKo gallery photos:", len(files))
    fresh = []
    for i, f in enumerate(files):
        print(f"  [{i+1}/{len(files)}] {f}")
        res = download(f)
        if res:
            src, _cap, _yr, size = res
            if pathlib.Path(src).name in BLOCKLIST:
                continue
            real = urllib.parse.unquote(f)
            event, year = humanize(real)
            caption = "NiKo · " + (f"{event} {year}" if year else event).strip()
            fresh.append({"src": src, "caption": caption,
                          "year": year or 0, "recent": (year or 0) >= 2024,
                          "who": "NiKo"})
        time.sleep(1.2)

    # 与现有 photos.json 合并，但只保留 NiKo 本人：
    # 队友单人照 / 全队合照 / 任何 who != 'NiKo' 的条目一律剔除（自愈）。
    store = ROOT / "photos.json"
    existing = []
    if store.exists():
        try:
            existing = json.loads(store.read_text(encoding="utf-8"))
        except Exception:
            existing = []
    by_src = {}
    dropped = 0
    for p in existing:
        if p.get("who") != "NiKo" or pathlib.Path(p.get("src", "")).name in BLOCKLIST:
            dropped += 1
            continue
        by_src[p["src"]] = p
    # 逐张人工核验过的补充照片
    for p in MANUAL_NIKO:
        if (ROOT / p["src"]).exists():
            by_src.setdefault(p["src"], dict(p))
    added = 0
    for p in fresh:
        if p["src"] not in by_src:
            added += 1
        by_src[p["src"]] = p

    final = list(by_src.values())
    for p in final:
        cap = re.sub(r"^NiKo\s*[·・:：]\s*", "", p.get("caption", "")).strip()
        p["caption"] = "NiKo · " + cap
        p["who"] = "NiKo"
        p.pop("w", None)
        p.pop("h", None)
    # 年份倒序；同年按说明文字。最新一张作为首图（hero / 「最新」角标）。
    final.sort(key=lambda p: (-(p.get("year") or 0), p.get("caption", "")))

    # 写盘前的硬断言：任何一张不是 NiKo，就拒绝生成，避免再次污染照片墙。
    bad = [p["src"] for p in final
           if p.get("who") != "NiKo"
           or pathlib.Path(p["src"]).name in BLOCKLIST
           or not (ROOT / p["src"]).exists()]
    if bad:
        raise SystemExit(f"[ABORT] 照片墙存在非 NiKo / 缺失条目：{bad}")

    store.write_text(json.dumps(final, ensure_ascii=False, indent=1),
                     encoding="utf-8")
    print(f"wrote photos.json: {len(final)} 张（全部 NiKo 本人；新增 {added}，"
          f"清理非 NiKo 条目 {dropped}）")
    print("hero (newest):", final[0]["src"], final[0]["caption"], final[0]["year"])


if __name__ == "__main__":
    main()
