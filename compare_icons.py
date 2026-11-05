# -*- coding: utf-8 -*-
"""生成「美居截图 vs 重绘图标」逐格对比图。"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parent
SHOT = Path(r"C:\Users\72919\.workbuddy\clipboard-images"
            r"\clipboard-2026-10-20T12-20-27-292Z-cf6a2318.png")

PAIRS = [
    ("防直吹", "shield", (30, 34, 104, 96)),
    ("上下摆风", "updown", (192, 34, 282, 96)),
    ("左右摆风", "leftright", (362, 34, 452, 96)),
    ("出风方向", "wind", (532, 34, 622, 96)),
    ("电辅热", "auxheat", (30, 209, 104, 272)),
    ("智控温", "thermo", (192, 209, 282, 272)),
    ("强冷", "turbo", (362, 209, 452, 272)),
    ("省电", "leaf", (532, 209, 622, 272)),
]

app = QGuiApplication(sys.argv)
shot = Image.open(SHOT).convert("RGB")

cell, pad, top = 108, 6, 40
W = pad + len(PAIRS) * (cell + pad)
H = top + cell * 2 + 46
out = Image.new("RGB", (W, H), (255, 255, 255))
d = ImageDraw.Draw(out)

# 参考图标：截图裁切后等比放进格子
for i, (label, name, box) in enumerate(PAIRS):
    crop = shot.crop(box)
    w, h = crop.size
    s = (cell - 8) / max(w, h)
    crop = crop.resize((int(w * s), int(h * s)), Image.LANCZOS)
    x = pad + i * (cell + pad)
    out.paste(crop, (x + (cell - crop.width) // 2, top + (cell - crop.height) // 2))

# 重绘图标：Qt 渲染
for i, (label, name, box) in enumerate(PAIRS):
    img = QImage(cell, cell, QImage.Format_ARGB32)
    img.fill(QColor("#FFFFFF"))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    QSvgRenderer(str(ROOT / "icons" / ("%s.svg" % name))).render(
        p, QRectF(20, 20, cell - 40, cell - 40))
    p.end()
    img.save(str(ROOT / "_tmp_{}.png".format(name)))
    icon = Image.open(ROOT / "_tmp_{}.png".format(name)).convert("RGB")
    x = pad + i * (cell + pad)
    out.paste(icon, (x, top + cell))

for i, (label, _n, _b) in enumerate(PAIRS):
    x = pad + i * (cell + pad)
    d.text((x + cell // 2 - len(label) * 5, H - 26), label, fill=(90, 94, 100))

d.text((8, 12), "上排: 美居截图", fill=(120, 124, 130))
d.text((8, H - 44), "下排: 重绘", fill=(120, 124, 130))

out.save(ROOT / "icon_compare.png")
print("saved icon_compare.png", out.size)
