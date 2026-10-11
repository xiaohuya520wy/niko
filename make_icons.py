"""生成主屏 / PWA 图标（扁平靛蓝渐变 + 白色准星）。

要点：
- 4 倍超采样绘制再降采样，边缘抗锯齿，任何尺寸都锐利；
- 输出全幅方形不透明图（iOS / Android 由系统自己切圆角），
  比原来「20x20 像素化头像放大」清晰得多；
- 同时输出矢量 favicon.svg，浏览器标签页任意缩放都不糊。

用法：python make_icons.py
"""
import pathlib
import base64
from PIL import Image, ImageDraw, ImageFilter

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "assets" / "pixel"
OUT.mkdir(parents=True, exist_ok=True)

BASE = 1024          # 设计基准尺寸
SS = 4               # 超采样倍数
S = BASE * SS

# 主题色（与新 UI 一致）
C1 = (91, 92, 230)    # #5B5CE6 靛蓝
C2 = (147, 125, 245)  # #937DF5 浅紫


def gradient(size):
    """对角线渐变：左上深靛蓝 → 右下浅紫。"""
    small = 256
    g = Image.new("RGB", (small, small))
    px = g.load()
    for y in range(small):
        for x in range(small):
            t = (x + y) / (2 * (small - 1))
            px[x, y] = (
                round(C1[0] + (C2[0] - C1[0]) * t),
                round(C1[1] + (C2[1] - C1[1]) * t),
                round(C1[2] + (C2[2] - C1[2]) * t),
            )
    return g.resize((size, size), Image.LANCZOS)


def radial_glow(size, cx, cy, r, peak):
    """柔和径向光斑，用于提亮/压暗，返回 RGBA 叠加层。"""
    small = 256
    m = Image.new("L", (small, small), 0)
    pm = m.load()
    for y in range(small):
        for x in range(small):
            d = (((x - cx * small) ** 2 + (y - cy * small) ** 2) ** 0.5) / (r * small)
            pm[x, y] = 0 if d >= 1 else round(peak * (1 - d) ** 2)
    m = m.resize((size, size), Image.LANCZOS)
    layer = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    layer.putalpha(m)
    return layer


def build_master():
    im = gradient(S).convert("RGBA")
    # 左上柔光
    im = Image.alpha_composite(im, radial_glow(S, 0.26, 0.18, 0.95, 78))
    # 右下压暗，增加层次
    dark = radial_glow(S, 0.92, 1.02, 1.1, 62)
    dark = Image.merge("RGBA", (
        Image.new("L", (S, S), 38), Image.new("L", (S, S), 24),
        Image.new("L", (S, S), 96), dark.getchannel("A")))
    im = Image.alpha_composite(im, dark)

    d = ImageDraw.Draw(im, "RGBA")
    K = SS  # 单位换算：设计值 * K
    C = BASE / 2  # 中心（设计基准坐标）

    # 单圈细环：把准星收在环内，形成"靶心"结构，小尺寸下依然清晰
    R = 306
    d.ellipse(((C - R) * K, (C - R) * K, (C + R) * K, (C + R) * K),
              outline=(255, 255, 255, 66), width=round(11 * K))

    # CS 风格四臂准星（圆头，全部落在环内）
    gap, arm, th, r = 66, 150, 68, 34
    for (x0, y0, x1, y1) in [
        (C - th / 2, C - gap - arm, C + th / 2, C - gap),          # 上
        (C - th / 2, C + gap, C + th / 2, C + gap + arm),          # 下
        (C - gap - arm, C - th / 2, C - gap, C + th / 2),          # 左
        (C + gap, C - th / 2, C + gap + arm, C + th / 2),          # 右
    ]:
        d.rounded_rectangle((x0 * K, y0 * K, x1 * K, y1 * K),
                            radius=round(r * K), fill=(255, 255, 255, 248))

    # 中心点
    dot = 14 * K
    d.ellipse(((C - dot) * K, (C - dot) * K, (C + dot) * K, (C + dot) * K),
              fill=(255, 255, 255, 248))
    return im


def main():
    master = build_master()

    out = {
        "icon-1024.png": 1024,          # iOS 主屏（系统会挑最大的一张）
        "icon-512.png": 512,            # PWA / Android
        "icon-192.png": 192,            # PWA / Android
        "favicon_256.png": 256,         # 通用
        "apple-touch-icon.png": 180,    # iOS 主屏首选尺寸
        "apple-touch-icon-152.png": 152,
        "favicon-48.png": 48,
        "favicon.png": 32,
    }
    for name, size in out.items():
        master.resize((size, size), Image.LANCZOS).convert("RGB").save(
            OUT / name, optimize=True)
        print(f"{name:28s} {size}x{size}")

    # 矢量 favicon：与栅格图同一套几何，任意尺寸都不糊
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024" width="1024" height="1024">
<defs>
<linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
<stop offset="0" stop-color="#5B5CE6"/><stop offset="1" stop-color="#937DF5"/>
</linearGradient>
<radialGradient id="glow" cx="26%" cy="18%" r="95%">
<stop offset="0" stop-color="#ffffff" stop-opacity=".31"/>
<stop offset="1" stop-color="#ffffff" stop-opacity="0"/>
</radialGradient>
</defs>
<rect width="1024" height="1024" fill="url(#g)"/>
<rect width="1024" height="1024" fill="url(#glow)"/>
<circle cx="512" cy="512" r="306" fill="none" stroke="#ffffff" stroke-opacity=".26" stroke-width="11"/>
<g fill="#ffffff" fill-opacity=".97">
<rect x="478" y="296" width="68" height="150" rx="34"/>
<rect x="478" y="578" width="68" height="150" rx="34"/>
<rect x="296" y="478" width="150" height="68" rx="34"/>
<rect x="578" y="478" width="150" height="68" rx="34"/>
<circle cx="512" cy="512" r="14"/>
</g>
</svg>
'''
    (OUT / "favicon.svg").write_text(svg, encoding="utf-8")
    print("favicon.svg                 矢量")


if __name__ == "__main__":
    main()
