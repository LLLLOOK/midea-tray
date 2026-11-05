# -*- coding: utf-8 -*-
"""从美居截图裁出出风方向的 10 个档位图标(竖5+横5), 生成灰/蓝两版透明 PNG。

每格包含"导风板 + 5 条风线", 直接按原图像素还原, 避免 Canvas 画出来的偏差。
"""
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
SHOT = Path(r"C:\Users\72919\.workbuddy\clipboard-images"
            r"\clipboard-2026-10-20T13-33-18-976Z-60f67a9a.png")
OUT = ROOT / "icons"

X0 = 25                       # 内容左边界
CW = 241                      # 每格宽(原图)
ROWS = {                      # 行 -> (格子顶, 格子高, 输出宽, 输出高)
    "v": (289, 244, 68, 66),
    "h": (666, 205, 68, 56),
}
DARK = 158.0                  # 线的纯色亮度基准
GRAY = (158, 162, 166)
BLUE = (38, 170, 255)


def cut(kind, idx):
    top, h, ow, oh = ROWS[kind]
    box = (X0 + CW * idx, top, X0 + CW * (idx + 1), top + h)
    cell = Image.open(SHOT).convert("L").crop(box).resize((ow, oh), Image.LANCZOS)
    w, hh = cell.size
    alpha = Image.new("L", (w, hh), 0)
    src, dst = cell.load(), alpha.load()
    for y in range(hh):
        for x in range(w):
            v = src[x, y]
            a = (255.0 - v) / (255.0 - DARK)
            dst[x, y] = 0 if a < 0.02 else min(255, int(a * 255))
    for suffix, rgb in (("", GRAY), ("_on", BLUE)):
        out = Image.new("RGBA", (w, hh), rgb + (0,))
        out.putalpha(alpha)
        out.save(OUT / "{}{}{}.png".format(kind, "dir", idx + 1).replace(
            "dir", "dir" + (suffix and "-on" or "")))


def cut2(kind, idx, suffix, rgb):
    top, h, ow, oh = ROWS[kind]
    box = (X0 + CW * idx, top, X0 + CW * (idx + 1), top + h)
    cell = Image.open(SHOT).convert("L").crop(box).resize((ow, oh), Image.LANCZOS)
    w, hh = cell.size
    alpha = Image.new("L", (w, hh), 0)
    src, dst = cell.load(), alpha.load()
    for y in range(hh):
        for x in range(w):
            v = src[x, y]
            a = (255.0 - v) / (255.0 - DARK)
            dst[x, y] = 0 if a < 0.02 else min(255, int(a * 255))
    out = Image.new("RGBA", (w, hh), rgb + (0,))
    out.putalpha(alpha)
    name = "{}{}{}{}.png".format(kind, "dir", idx + 1, suffix)
    out.save(OUT / name)
    return name


def main():
    OUT.mkdir(exist_ok=True)
    for kind in ("v", "h"):
        for i in range(5):
            a = cut2(kind, i, "", GRAY)
            b = cut2(kind, i, "_on", BLUE)
            print(" {} / {}".format(a, b))


if __name__ == "__main__":
    main()
