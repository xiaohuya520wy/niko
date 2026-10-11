"""用 NiKo 本人高清照片生成主屏图标 + 站内头像（Falcons 白色队服版）。

流程：
  1. 原图 assets/_src/NiKo_orig.jpg（Liquipedia CC-BY-SA）
  2. Haar 级联人脸检测，取最大的一张脸
  3. 以脸为基准裁两个不同的取景：
       - 站内头像：留白多（frame 大），能看到队服，方便辨认 Falcons
       - 主屏图标：脸占满（frame 小），180px 下五官清晰，才是"高清头像"
  4. LANCZOS 降采样 + 轻度 USM 锐化输出各档位

用法：
  python make_avatar_icon.py            # 正常生成
  python make_avatar_icon.py --debug    # 额外输出裁切框可视化
"""
import pathlib
import sys

import cv2
import numpy as np
from PIL import Image, ImageFilter

ROOT = pathlib.Path(__file__).parent
SRC = ROOT / "assets" / "_src" / "NiKo_orig.jpg"
CASCADE = ROOT / "assets" / "_src" / "haarcascade_frontalface_default.xml"
OUT = ROOT / "assets" / "pixel"
PLAYERS = ROOT / "assets" / "players"
OUT.mkdir(parents=True, exist_ok=True)
PLAYERS.mkdir(parents=True, exist_ok=True)

MASTER = 1024                 # 图标母版尺寸
ICON_FRAME = 2.05             # 图标取景系数（小 → 脸占满）
ICON_BIAS = 0.15              # 图标中心相对脸心下移比例
# 头像取景收得比较紧：原图右下角有 BLAST 赛事水印，
# 放宽取景会把水印裁进来，故边长控制在脸高 2 倍左右、避开右下角。
AVATAR_FRAME = 2.0            # 站内头像取景系数（脸高倍数）
AVATAR_BIAS = 0.25            # 头像中心相对脸心下移比例（略下移，露出队徽/赞助）


def detect_face(bgr):
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    g = cv2.equalizeHist(g)
    clf = cv2.CascadeClassifier(str(CASCADE))
    faces = clf.detectMultiScale(g, scaleFactor=1.08, minNeighbors=6, minSize=(60, 60))
    if len(faces) == 0:
        faces = clf.detectMultiScale(g, scaleFactor=1.05, minNeighbors=3, minSize=(40, 40))
    if len(faces) == 0:
        return None
    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
    return (int(x), int(y), int(w), int(h))


def square_box(img_w, img_h, face, frame, bias):
    fx, fy, fw, fh = face
    cx = fx + fw / 2
    cy = fy + fh / 2 + fh * bias
    side = min(fh * frame, img_w, img_h)
    x0 = min(max(0.0, cx - side / 2), img_w - side)
    y0 = min(max(0.0, cy - side / 2), img_h - side)
    return (int(round(x0)), int(round(y0)),
            int(round(x0 + side)), int(round(y0 + side)))


def crop_square(im, box, master=MASTER):
    c = im.crop(box).resize((master, master), Image.LANCZOS)
    return c.filter(ImageFilter.UnsharpMask(radius=1.2, percent=85, threshold=2))


def main():
    if not SRC.exists():
        print("缺原图：", SRC)
        return 1

    bgr = cv2.imdecode(np.fromfile(str(SRC), dtype=np.uint8), cv2.IMREAD_COLOR)
    if bgr is None:
        bgr = cv2.imread(str(SRC))
    h, w = bgr.shape[:2]
    print("原图:", w, "x", h)
    rgb = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))

    face = detect_face(bgr)
    if face:
        print(f"人脸: x={face[0]} y={face[1]} {face[2]}x{face[3]} (占图高 {face[3]/h*100:.1f}%)")
    else:
        print("未检测到人脸，退化为居中裁切")

    def box_for(frame, bias):
        if face:
            return square_box(w, h, face, frame, bias)
        side = min(w, h)
        return ((w - side) // 2, (h - side) // 2,
                (w - side) // 2 + side, (h - side) // 2 + side)

    avatar_box = box_for(AVATAR_FRAME, AVATAR_BIAS)
    icon_box = box_for(ICON_FRAME, ICON_BIAS)
    print("头像裁切框:", avatar_box, "  图标裁切框:", icon_box)

    if "--debug" in sys.argv:
        from PIL import ImageDraw
        dbg = rgb.copy()
        d = ImageDraw.Draw(dbg)
        d.rectangle(avatar_box, outline=(255, 0, 0), width=6)
        d.rectangle(icon_box, outline=(0, 160, 255), width=6)
        if face:
            d.rectangle((face[0], face[1], face[0] + face[2], face[1] + face[3]),
                        outline=(0, 255, 0), width=6)
        dbg.resize((dbg.width // 3, dbg.height // 3), Image.LANCZOS).save(
            ROOT / "assets" / "_src" / "crop_debug.png")
        print("裁切预览 -> assets/_src/crop_debug.png")

    # 主屏图标：脸部特写母版
    icon_master = crop_square(rgb, icon_box)
    # 站内头像：能看到队服的母版
    avatar_master = crop_square(rgb, avatar_box)

    out_sizes = {
        "icon-512.png": 512,            # PWA / Android 最高档
        "icon-192.png": 192,            # PWA / Android
        "apple-touch-icon.png": 180,    # iOS 主屏标准档
        "apple-touch-icon-152.png": 152,
        "favicon_256.png": 256,
        "favicon-48.png": 48,
        "favicon.png": 32,
    }
    for name, size in out_sizes.items():
        icon_master.resize((size, size), Image.LANCZOS).save(OUT / name, optimize=True)
        print(f"{name:26s} {size}x{size}")

    avatar_master.resize((512, 512), Image.LANCZOS).save(
        PLAYERS / "NiKo.jpg", quality=90, optimize=True)
    print("assets/players/NiKo.jpg      512x512（露队服）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
