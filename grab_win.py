# -*- coding: utf-8 -*-
"""从屏幕抓真实窗口(含 setMask 圆角), 验证四角是否被切掉。"""
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

import pyside_panel as psp
from test_panel import FakeCtrl

ctrl = FakeCtrl()
app = QGuiApplication(sys.argv)
bridge = psp.PanelBridge(ctrl)
engine = QQmlApplicationEngine()
engine.rootContext().setContextProperty("bridge", bridge)
engine.rootContext().setContextProperty("FEATURES", psp.FEATURES)
engine.load(str(BASE / "panel.qml"))
win = engine.rootObjects()[0]
from PySide6.QtGui import QColor
win.setProperty("color", QColor(0, 0, 0, 0))
win.setPosition(120, 80)
win.show()
win.requestActivate()
# 与 _run_ui 相同顺序: show 之后立刻 setMask
from PySide6.QtGui import QPainterPath, QRegion
path0 = QPainterPath()
path0.addRoundedRect(0.0, 0.0, float(win.width()), float(win.height()), 24.0, 24.0)
win.setMask(QRegion(path0.toFillPolygon().toPolygon()))

def apply_mask():
    from PySide6.QtGui import QPainterPath, QRegion
    from PySide6.QtCore import QRect
    path = QPainterPath()
    path.addRoundedRect(0.0, 0.0, float(win.width()), float(win.height()), 24.0, 24.0)
    win.setMask(QRegion(path.toFillPolygon().toPolygon()))
    print("mask applied", flush=True)

def shoot():
    scr = QGuiApplication.primaryScreen()
    pm = scr.grabWindow(0, 100, 60, 380, 760)
    pm.save(str(BASE / "win_grab.png"))
    print("saved", pm.size())
    app.quit()

QTimer.singleShot(1100, shoot)
app.exec()
