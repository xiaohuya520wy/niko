"""生成本站的像素风（Minecraft 风）素材：CS 武器 sprite、NiKo 像素头像 favicon、背景纹理。

全部用矩形网格手绘 + 最近邻放大，保证是真像素画而不是糊图。
输出目录：assets/pixel/
"""
import pathlib
from PIL import Image

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "assets" / "pixel"
OUT.mkdir(parents=True, exist_ok=True)

T = None  # 透明

OL = "#2A2A2A"    # 轮廓黑
D = "#4A4A4A"     # 深金属
M = "#7E7E7E"     # 中金属
L = "#B6B6B6"     # 浅金属
W = "#E4E4E4"     # 高光白
WD = "#7A4E23"    # 木深
WM = "#A9713A"    # 木中
WL = "#C79A5B"    # 木浅
PL = "#2E343A"    # 聚合物深
PM = "#3E474F"    # 聚合物中
CT = "#4C7FD9"    # CT 蓝
CTD = "#2F5AA8"
TR = "#D9552F"    # T 红
TN = "#E8A33D"    # T 橙/沙
GR = "#5FBF4A"    # 绿
GD = "#3E8C2F"


class Grid:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.px = [[T] * w for _ in range(h)]

    def put(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h and c is not None:
            self.px[y][x] = c

    def rect(self, x, y, w, h, c):
        for j in range(y, y + h):
            for i in range(x, x + w):
                self.put(i, j, c)

    def outline(self, x, y, w, h, c=OL):
        """只画矩形一圈轮廓"""
        for i in range(x, x + w):
            self.put(i, y, c)
            self.put(i, y + h - 1, c)
        for j in range(y, y + h):
            self.put(x, j, c)
            self.put(x + w - 1, j, c)

    def pxline_h(self, x0, x1, y, c):
        for i in range(x0, min(x1, self.w) + 1):
            self.put(i, y, c)

    def to_img(self, scale=10):
        img = Image.new("RGBA", (self.w * scale, self.h * scale), (0, 0, 0, 0))
        for y in range(self.h):
            for x in range(self.w):
                c = self.px[y][x]
                if not c:
                    continue
                for dy in range(scale):
                    for dx in range(scale):
                        img.putpixel((x * scale + dx, y * scale + dy), hex_rgba(c))
        return img


def hex_rgba(h):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)


# ---------------------------------------------------------------- 武器

def ak47():
    """AK-47：木质护木 + 弯弹匣 + 长枪管"""
    g = Grid(32, 16)
    # 枪托（修长）
    g.rect(0, 6, 7, 3, WM)
    g.rect(0, 5, 2, 5, WM)
    g.rect(0, 5, 2, 1, WL)
    g.rect(0, 9, 2, 1, WD)
    g.pxline_h(0, 6, 6, WD)
    g.pxline_h(0, 6, 8, WD)
    # 机匣（拉长）
    g.rect(7, 5, 9, 4, D)
    g.rect(7, 5, 9, 1, M)
    g.rect(7, 8, 9, 1, OL)
    # 木质护木
    g.rect(15, 5, 6, 4, WM)
    g.rect(15, 5, 6, 1, WL)
    g.rect(15, 8, 6, 1, WD)
    # 活塞导气管（短而贴机匣）
    g.rect(12, 6, 3, 1, M)
    # 枪管（拉长）
    g.rect(21, 7, 9, 2, M)
    g.rect(21, 7, 9, 1, L)
    # 准星
    g.rect(28, 4, 2, 3, D)
    g.rect(28, 4, 2, 1, L)
    # 导气箍
    g.rect(22, 6, 2, 2, D)
    # 握把
    for i in range(4):
        g.rect(8 + i, 9 + i, 3, 2, PL)
    g.rect(10, 9, 1, 1, OL)
    # 弯弹匣
    for i in range(6):
        g.rect(13 + i, 10 + i, 3, 2, D)
    g.rect(18, 15, 3, 1, OL)
    return g


def m4a1s():
    """M4A1-S：黑色战术枪身 + 消音器 + 直弹匣"""
    g = Grid(32, 16)
    # 伸缩枪托
    g.rect(0, 6, 6, 4, PL)
    g.rect(0, 6, 6, 1, PM)
    g.rect(1, 8, 4, 1, OL)
    # 机匣
    g.rect(6, 5, 8, 5, PM)
    g.rect(6, 5, 8, 1, M)
    g.rect(6, 9, 8, 1, OL)
    # 护木
    g.rect(13, 5, 7, 5, PL)
    g.pxline_h(13, 19, 6, PM)
    g.pxline_h(13, 19, 8, PM)
    # 消音器（更长更厚）
    g.rect(20, 5, 10, 5, D)
    g.pxline_h(20, 29, 5, M)
    g.pxline_h(20, 29, 9, OL)
    g.pxline_h(20, 29, 6, M)
    g.rect(22, 4, 2, 1, D)   # 上燕尾槽
    g.rect(26, 4, 2, 1, D)
    # 握把
    for i in range(4):
        g.rect(7 + i, 10 + i, 3, 2, PL)
    g.rect(10, 10, 1, 1, OL)
    # 弹匣（直弹匣）
    for i in range(5):
        g.rect(11 + i, 10 + i, 3, 2, PM)
    return g


def awp():
    """AWP：超长枪管 + 狙击镜 + 两脚架"""
    g = Grid(36, 16)
    # 枪托
    g.rect(0, 6, 8, 5, PM)
    g.rect(0, 6, 8, 1, M)
    g.rect(0, 10, 8, 1, OL)
    g.rect(6, 4, 3, 2, PM)
    # 机匣
    g.rect(8, 6, 8, 4, PL)
    g.pxline_h(8, 15, 6, PM)
    g.rect(8, 9, 8, 1, OL)
    # 瞄准镜
    g.rect(10, 2, 9, 4, D)
    g.rect(10, 2, 9, 1, L)
    g.rect(17, 2, 2, 4, OL)
    g.rect(18, 2, 1, 4, CT)
    g.rect(7, 3, 3, 2, D)
    g.rect(8, 3, 1, 2, CT)
    g.rect(11, 6, 7, 1, OL)
    # 枪管（超长）
    g.rect(16, 7, 18, 2, M)
    g.rect(16, 7, 18, 1, L)
    g.rect(33, 6, 2, 1, OL)
    # 弹匣
    g.rect(12, 10, 4, 3, PM)
    g.rect(12, 12, 4, 1, OL)
    # 两脚架
    for i in range(3):
        g.rect(22 + i, 9 + i, 1, 2, D)
    # 握把
    for i in range(4):
        g.rect(9 + i, 10 + i, 2, 2, PL)
    return g


def deagle():
    """沙鹰 Desert Eagle"""
    g = Grid(20, 16)
    # 滑套
    g.rect(2, 4, 13, 5, L)
    g.rect(2, 4, 13, 1, W)
    g.rect(2, 8, 13, 1, M)
    g.pxline_h(3, 13, 6, M)
    for x in range(4, 13, 2):
        g.put(x, 6, OL)
    # 枪管前端
    g.rect(15, 5, 4, 4, M)
    g.rect(15, 5, 4, 1, L)
    g.rect(18, 5, 1, 4, OL)
    # 准星 / 照门
    g.rect(16, 3, 2, 2, D)
    g.rect(2, 2, 2, 2, D)
    # 套筒座
    g.rect(3, 9, 11, 2, D)
    g.rect(3, 10, 11, 1, PL)
    # 击锤
    g.rect(0, 5, 2, 3, PM)
    # 扳机
    g.rect(9, 11, 2, 1, OL)
    g.rect(11, 11, 1, 2, OL)
    g.rect(12, 12, 2, 1, OL)
    # 握把
    for i in range(6):
        g.rect(3 + i, 11 + i, 4, 2, PL)
    g.rect(8, 16, 4, 1, PM)
    return g


def knife():
    """战术匕首：大刀身"""
    g = Grid(20, 16)
    # 刀身：长三角形
    g.rect(0, 4, 14, 4, L)
    g.rect(0, 4, 14, 1, W)
    g.rect(0, 7, 14, 1, M)
    g.rect(0, 3, 12, 1, W)
    g.rect(12, 4, 2, 1, L)
    g.rect(13, 5, 1, 1, L)
    g.rect(14, 5, 1, 1, M)
    # 血槽
    g.rect(4, 6, 6, 1, M)
    # 护手
    g.rect(13, 7, 3, 3, D)
    g.rect(13, 7, 3, 1, M)
    # 刀柄
    g.rect(15, 7, 5, 3, PL)
    g.rect(15, 6, 5, 1, PM)
    g.rect(15, 10, 5, 1, OL)
    g.pxline_h(16, 19, 8, OL)
    g.pxline_h(16, 19, 9, OL)
    return g


def hegrenade():
    """高爆手雷"""
    g = Grid(12, 14)
    g.rect(2, 3, 8, 8, GD)
    g.rect(2, 3, 8, 1, GR)
    g.rect(2, 10, 8, 1, GD)
    for y in range(4, 10, 2):
        g.pxline_h(2, 9, y, GD)
    g.rect(4, 2, 4, 1, M)     # 引信座
    g.rect(5, 0, 2, 2, D)
    g.rect(6, 0, 1, 1, TN)    # 拉环火星
    g.rect(2, 3, 1, 8, OL)
    g.rect(9, 3, 1, 8, OL)
    return g


def c4():
    """C4 炸弹"""
    g = Grid(16, 12)
    g.rect(1, 3, 14, 7, PL)
    g.rect(1, 3, 14, 1, PM)
    g.rect(1, 9, 14, 1, OL)
    g.rect(3, 5, 10, 3, OL)     # 面板
    g.rect(4, 6, 2, 1, TR)
    g.rect(7, 6, 2, 1, GR)
    g.rect(10, 6, 2, 1, TN)
    g.rect(6, 1, 4, 2, D)       # 天线座
    g.rect(7, 0, 2, 1, TR)
    return g


GUNS = {"ak47": ak47, "m4a1s": m4a1s, "awp": awp, "deagle": deagle,
        "knife": knife, "he": hegrenade, "c4": c4}


def main():
    for name, fn in GUNS.items():
        g = fn()
        img = g.to_img(12)
        img.save(OUT / f"{name}.png")
        # 同时给页面一个 1x 的紧凑版本
        g.to_img(4).save(OUT / f"{name}_sm.png")
        print(f"{name:8s} {g.w}x{g.h} -> {img.size}")


if __name__ == "__main__":
    main()
