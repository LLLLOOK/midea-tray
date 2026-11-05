# -*- coding: utf-8 -*-
"""把 icons/*.svg 渲染成对比图, 用于跟美居截图逐格比对形状。"""
import sys
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

NAMES = ["snow", "fan", "shield", "updown", "leftright", "wind",
         "auxheat", "thermo", "turbo", "leaf"]

app = QGuiApplication(sys.argv)
ICONS = Path(__file__).resolve().parent / "icons"

cell, pad, cols = 170, 10, 5
rows = (len(NAMES) + cols - 1) // cols
img = QImage(cols * (cell + pad) + pad, rows * (cell + pad + 22) + pad,
             QImage.Format_ARGB32)
img.fill(QColor("#FFFFFF"))
p = QPainter(img)
p.setRenderHint(QPainter.Antialiasing)
f = QFont("Microsoft YaHei", 10)

for i, n in enumerate(NAMES):
    r = QSvgRenderer(str(ICONS / ("%s.svg" % n)))
    x = pad + (i % cols) * (cell + pad)
    y = pad + (i // cols) * (cell + pad + 22)
    r.render(p, QRectF(x, y, cell, cell))
    p.setFont(f)
    p.setPen(QColor("#888888"))
    p.drawText(QRectF(x, y + cell, cell, 20), Qt.AlignCenter, n)

p.end()
img.save(str(Path(__file__).resolve().parent / "icon_check.png"))
print("saved icon_check.png", img.width(), img.height())
