# -*- coding: utf-8 -*-
"""从美居截图里直接提取功能图标的像素轮廓, 输出可着色的透明 PNG。

截图是置灰态(图标约 #C9CBC7, 底 #FBFBFB), 用亮度反推 alpha 再按目标色着色,
形状与原图完全一致。
"""
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
SHOT = Path(r"C:\Users\72919\.workbuddy\clipboard-images"
            r"\clipboard-2026-10-20T12-20-27-292Z-cf6a2318.png")
SHOT_CARD = Path(r"C:\Users\72919\.workbuddy\clipboard-images"
                 r"\clipboard-2026-10-20T12-20-27-291Z-28f82703.png")

# (输出名, 裁剪格[仅图标区, 不含下方文字])
GRID = [
    ("shield", (0, 0, 163, 115)),
    ("updown", (163, 0, 326, 115)),
    ("leftright", (326, 0, 489, 115)),
    ("wind", (489, 0, 651, 115)),
    ("auxheat", (0, 190, 163, 300)),
    ("thermo", (163, 190, 326, 300)),
    ("turbo", (326, 190, 489, 300)),
    ("leaf", (489, 190, 651, 300)),
]
CARD = [("snow", (240, 60, 335, 145)), ("fan", (585, 58, 682, 145))]

GRAY = (140, 148, 156)
BLUE = (38, 170, 255)
OUT = ROOT / "icons"


def ink_box(im, cell):
    """在格子里找图标的紧致包围盒(不含下方文字)。"""
    x0, y0, x1, y1 = cell
    px = im.load()
    xs, ys = [], []
    for y in range(y0, y1):
        for x in range(x0, x1):
            r, g, b = px[x, y][:3]
            if r < 245 and abs(r - g) < 12 and abs(g - b) < 12:
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    return min(xs), min(ys), max(xs) + 1, max(ys) + 1


def extract(im, box, name, base=248.0, dark=205.0):
    """按亮度反推 alpha, 输出灰/蓝两版 PNG。

    base 为该处底色亮度(网格格底 #FBFBFB≈251, 卡片底 255), 比它亮的全透明,
    避免把极淡的容器底色一起抠出来。
    """
    crop = im.crop(box).convert("L")
    w, h = crop.size
    alpha = Image.new("L", (w, h), 0)
    src = crop.load()
    dst = alpha.load()
    for y in range(h):
        for x in range(w):
            v = src[x, y]
            a = (base - v) / (base - dark)
            dst[x, y] = 0 if a < 0.06 else min(255, int(a * 255))

    for suffix, rgb in (("", GRAY), ("_on", BLUE)):
        out = Image.new("RGBA", (w, h), rgb + (0,))
        out.putalpha(alpha)
        out.save(OUT / "{}{}.png".format(name, suffix))
    return (w, h)


def main():
    g = Image.open(SHOT).convert("RGB")
    c = Image.open(SHOT_CARD).convert("RGB")
    for name, cell in GRID:
        box = ink_box(g, cell)
        if not box:
            print("skip", name)
            continue
        size = extract(g, box, name, base=248.0)
        print("{:10s} {} -> {}".format(name, box, size))
    for name, cell in CARD:
        box = ink_box(c, cell)
        if not box:
            print("skip", name)
            continue
        size = extract(c, box, name, base=255.0)
        print("{:10s} {} -> {}".format(name, box, size))


if __name__ == "__main__":
    main()
