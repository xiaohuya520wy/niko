"""把下载好的地图原图压成网页背景图，并生成 LQIP 占位，输出 assets/maps/index.json。

- 每张地图一张 16:9 横图，宽 900、JPEG 质量 74（做卡片背景足够）。
- 同时导出 16px 宽的极模糊缩略图（base64），用于首屏秒显、不闪白。
"""
import base64
import io
import json
import pathlib
from PIL import Image, ImageFilter

ROOT = pathlib.Path(__file__).parent
SRC = ROOT / "assets" / "maps" / "_orig"
DST = ROOT / "assets" / "maps"

# 地图名 -> 选定的原始素材（人眼比对过：都是能一眼认出的该地图实景/CS2 截图）
PICK = {
    "Dust II": "CS2_Dust_2_A_Site.jpg",
    "Mirage": "CS2_Mirage_A_site_behind_triple.jpg",
    "Nuke": "CS2_Nuke_Outside.jpeg",
    "Ancient": "AncientASite.jpg",
    "Anubis": "CS2AnubisWater.jpg",
    "Inferno": "De_infernoCS2BSite.jpeg",
    "Train": "CS2_de_train.png",
}

W = 900
Q = 74


def slug(s):
    return s.lower().replace(" ", "-").replace(".", "")


def cover(im, w, h):
    """按 cover 方式裁成 w:h。"""
    sr = im.width / im.height
    tr = w / h
    if sr > tr:                      # 太宽 → 裁两侧
        nw = int(im.height * tr)
        left = (im.width - nw) // 2
        im = im.crop((left, 0, left + nw, im.height))
    else:                            # 太高 → 略微偏上裁（保留地平线/建筑）
        nh = int(im.width / tr)
        top = int((im.height - nh) * 0.42)
        im = im.crop((0, top, im.width, top + nh))
    return im.resize((w, h), Image.LANCZOS)


def main():
    index = {}
    for name, fn in PICK.items():
        p = SRC / fn
        if not p.exists():
            print("缺素材:", fn)
            continue
        im = Image.open(p).convert("RGB")
        out = cover(im, W, int(W * 9 / 16))
        dst = DST / f"{slug(name)}.jpg"
        out.save(dst, "JPEG", quality=Q, optimize=True, progressive=True)
        # LQIP：16px 宽 + 模糊，内联用
        lq = im.copy()
        lq.thumbnail((16, 16), Image.LANCZOS)
        buf = io.BytesIO()
        lq.filter(ImageFilter.GaussianBlur(0.6)).save(buf, "JPEG", quality=42)
        lqip = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
        index[name] = {"f": f"assets/maps/{dst.name}", "l": lqip,
                       "w": out.width, "h": out.height,
                       "src": "Liquipedia / CC BY-SA 3.0"}
        print(f"{name:9} -> {dst.name:16} {dst.stat().st_size // 1024:3}KB  LQIP {len(lqip)}B")
    (DST / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1),
                                    encoding="utf-8")
    print("已写出 assets/maps/index.json，共", len(index), "张")


if __name__ == "__main__":
    main()
