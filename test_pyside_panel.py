# -*- coding: utf-8 -*-
"""QML 面板离屏测试: FakeCtrl 驱动, 加载 panel.qml, 截帧存 PNG。
校验: QML 无错误加载、bridge 状态字段齐全。"""
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

from PySide6.QtCore import QObject, QTimer, qInstallMessageHandler
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

import pyside_panel as psp
from fake_ctrl import FakeCtrl

msgs = []
qInstallMessageHandler(lambda mode, ctx, m: msgs.append(m))

ctrl = FakeCtrl()
app = QGuiApplication(sys.argv)
bridge = psp.PanelBridge(ctrl)
engine = QQmlApplicationEngine()
engine.rootContext().setContextProperty("bridge", bridge)
engine.rootContext().setContextProperty("FEATURES", psp.FEATURES)
engine.load(str(BASE / "panel.qml"))
roots = engine.rootObjects()
assert len(roots) == 1, "QML 加载失败: %s" % msgs
win = roots[0]

# 字段齐全性: QML 用到的键必须存在
need = ["online", "power", "outdoor", "indoor", "target", "minTemp",
        "maxTemp", "modeName", "fanName", "feat", "set", "dirPick",
        "vAngle", "hAngle", "today", "total", "filterAlert", "error"]
st = bridge.state
missing = [k for k in need if k not in st.keys()]
assert not missing, "state 缺字段: %s" % missing
print("state 字段齐全 OK (%d 项)" % len(st))

win.show()

def snap():
    out = BASE / "panel_qml.png"
    win.snapTo(str(out))
    QTimer.singleShot(500, snap_bottom)


def snap_bottom():
    ctrl.power = True          # 滚到底的截图要在开机态下看(否则设置项是灰的)
    bridge.publish()
    flick = win.findChild(QObject, "flick")
    if flick is not None:
        ch = flick.property("contentHeight")
        h = flick.property("height")
        flick.setProperty("contentY", max(0, ch - h))
    out = BASE / "panel_qml_bottom.png"
    win.snapTo(str(out))
    QTimer.singleShot(500, snap_picker)


def snap_picker():
    flick = win.findChild(QObject, "flick")
    if flick is not None:
        flick.setProperty("contentY", 0)
    win.setProperty("pickerType", "mode")
    out = BASE / "panel_qml_picker.png"
    win.snapTo(str(out))
    QTimer.singleShot(500, snap_fan)


def snap_fan():
    win.setProperty("pickerType", "fan")
    win.snapTo(str(BASE / "panel_qml_fan.png"))
    QTimer.singleShot(500, snap_dir)


def snap_dir():
    win.setProperty("pickerType", "")
    ctrl.power = True          # 弹层要在开机态下看
    bridge._dir_pick = True
    bridge.publish()
    bridge.setAngle("v", 5)    # 选中第 5 档, 校验高亮
    bridge.setAngle("h", 3)
    QTimer.singleShot(900, do_snap_dir)


def do_snap_dir():
    win.snapTo(str(BASE / "panel_qml_dir.png"))
    QTimer.singleShot(600, snap_off)


def snap_off():
    bridge._dir_pick = False
    ctrl.power = False         # 关机置灰对照
    bridge.publish()
    QTimer.singleShot(300, lambda: (
        win.snapTo(str(BASE / "panel_qml_off.png")),
        QTimer.singleShot(600, lambda: (print("截帧 -> panel_qml*.png x6"),
                                        app.quit()))))

QTimer.singleShot(900, snap)
app.exec()

errors = [m for m in msgs
          if "error" in m.lower() or "failed" in m.lower()
          or "cannot" in m.lower() or "unable" in m.lower()]
if errors:
    print("QML 警告/错误:")
    for m in errors:
        print(" ", m)
else:
    print("QML 零错误 OK")
for m in msgs:
    if "SNAP" in m:
        print(m)
