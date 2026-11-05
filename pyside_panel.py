"""美的空调 PySide6/QML 控制面板 (美居同款浅色 UI)。

替代原 tkinter 面板(tray_panel.py): GPU 合成渲染, 滑块/开关原生跟手,
布局 1:1 对标美的美居 App 截图。协议层不动, 仍走 midea_tray.Controller
(乐观更新 + apply/apply_ext 下发)。

结构:
- PanelBridge(QObject): Q_PROPERTY state(QVariantMap) 供 QML 声明式绑定;
  @Slot 方法接收 QML 指令; 每秒比对设备状态, 有变化才发 stateChanged。
- start(ctrl): 在独立 UI 线程创建 QApplication + QML 引擎并进入事件循环,
  返回带 request_show() 的句柄(与旧 tray_panel.start 签名一致)。
"""
import os
import os
import sys
import threading
import time

# 必须在导入 PySide6 之前: 关闭 QML 磁盘缓存, 否则界面改动会因旧 .qmlc
# 缓存不生效(曾导致所有 UI 修复"没反应")
os.environ["QML_DISABLE_DISK_CACHE"] = "1"

# 必须在导入 PySide6 之前: 关闭 QML 磁盘缓存, 否则界面改动会因旧 .qmlc
# 缓存不生效(曾导致所有 UI 修复"没反应")
os.environ["QML_DISABLE_DISK_CACHE"] = "1"

from PySide6.QtCore import (QObject, Property, Signal, Slot, QTimer,
                            QMetaObject, Qt, Q_ARG)
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from pathlib import Path

from msmart.device import AirConditioner as AC

BASE_DIR = Path(__file__).resolve().parent
W, H = 340, 720

MODE_NAMES = {"auto": "自动", "cool": "制冷", "dry": "除湿",
              "heat": "制热", "fan_only": "送风"}

# 常用功能: dict 列表(QML Repeater 需要 map 才能按 key 取值; 元组会被
# QVariant 压平成字符串)
FEATURES = [
    {"key": "breezeless", "name": "防直吹", "icon": "shield", "grey": False},
    {"key": "swing_up", "name": "上下扫风", "icon": "updown", "grey": False},
    {"key": "swing_side", "name": "左右扫风", "icon": "leftright", "grey": False},
    {"key": "wind_dir", "name": "出风方向", "icon": "wind", "grey": False},
    {"key": "aux", "name": "电辅热", "icon": "auxheat", "grey": False},
    {"key": "smart_temp", "name": "智控温", "icon": "thermo", "grey": True},
    {"key": "turbo", "name": "强冷", "icon": "turbo", "grey": False},
    {"key": "eco", "name": "省电", "icon": "leaf", "grey": False},
]


def _angle_idx(v):
    """SwingAngle -> 0(关)/1..5。"""
    if v is None or v == AC.SwingAngle.OFF:
        return 0
    try:
        return int(v.value // 25) + 1 if v.value > 1 else 1
    except Exception:
        return 0


class PanelBridge(QObject):
    """QML <-> Controller 桥。"""

    stateChanged = Signal()
    showRequested = Signal()

    def __init__(self, ctrl, log=None):
        super().__init__()
        self.ctrl = ctrl
        self._log = log or (lambda m: None)
        self._state = {}
        self._visible = False
        self._win = None
        self.showRequested.connect(self._on_show_requested)
        self.publish()  # 初始状态(QML 声明式绑定需要非空 state)

    # ---------- Q_PROPERTY ----------

    def get_state(self):
        return self._state

    state = Property("QVariantMap", get_state, notify=stateChanged)

    # ---------- 状态构建 ----------

    def build_state(self):
        c, dv = self.ctrl, self.ctrl.device
        heat = dv.operational_mode == AC.OperationalMode.HEAT
        # 该机型状态帧 byte12 换出来的"室外温度"实测与盘管温度一致(35.2 vs 35.0),
        # 不是室外环境温度; 局域网只有室外盘管(T3)这一个可信的室外侧数值
        out = dv.outdoor_coil_temperature
        mode = c.mode.name.lower() if c.mode else "auto"
        fan = dv.fan_speed
        fan_key = fan.name.lower() if isinstance(fan, AC.FanSpeed) else None
        v_idx = _angle_idx(getattr(dv, "vertical_swing_angle", None))
        h_idx = _angle_idx(getattr(dv, "horizontal_swing_angle", None))
        # 屏显是翻转型指令, 刚翻转后设备回显可能还是旧值, 保持期内锁乐观值
        disp = bool(dv.display_on)
        if time.time() < getattr(self, "_display_hold", 0):
            disp = getattr(self, "_display_opt", disp)
        return {
            "error": c.error_text(),
            "online": bool(c.online),
            "power": bool(c.power),
            "outdoor": "--" if out is None else "%.1f" % out,
            "indoor": "--" if c.indoor is None else "%.1f" % c.indoor,
            "target": float(c.target or 26.0),
            "minTemp": float(dv.min_target_temperature),
            "maxTemp": float(dv.max_target_temperature),
            "modeName": MODE_NAMES.get(mode, "?"),
            "modeKey": mode,
            "fanName": ("自动" if fan_key == "auto" else "%d%%" % fan)
                       if fan is not None else "--",
            "fanKey": fan_key or "",
            # 风速百分比(0-100), 自动(102)时为 -1
            "fanPct": float(fan) if fan is not None and fan != 102 else -1.0,
            "feat": {
                # 防直吹走 breeze_away(0x0042): 真机验证支持;
                # breezeless(0x0018) 这台机型返回空属性(不支持)
                "breezeless": bool(getattr(dv, "breeze_away", False)),
                "swingUp": dv.swing_mode in (AC.SwingMode.VERTICAL,
                                             AC.SwingMode.BOTH),
                "swingSide": dv.swing_mode in (AC.SwingMode.HORIZONTAL,
                                               AC.SwingMode.BOTH),
                "windDir": v_idx > 0 or h_idx > 0,
                "aux": dv.aux_mode not in (None, AC.AuxHeatMode.OFF),
                "auxEnabled": heat,
                "turbo": bool(dv.turbo),
                "eco": bool(dv.eco),
            },
            "set": {
                "display": bool(disp),
                "sound": bool(dv.sound),
                "dry": bool(getattr(dv, "dry_clean", False)),
            },
            "dirPick": bool(getattr(self, "_dir_pick", False)),
            "vAngle": v_idx,
            "hAngle": h_idx,
            "today": None if c.daily_energy is None
                     else "%.1f" % c.daily_energy,
            "total": None if dv.get_total_energy_usage() is None
                     else "%.1f" % dv.get_total_energy_usage(),
            "filterAlert": bool(dv.filter_alert),
            "error": int(dv.error_code or 0),
        }

    def publish(self):
        self._state = self.build_state()
        self.stateChanged.emit()

    def sync(self):
        """每秒调用: 设备状态有变化才重发(声明式绑定, 无变化零开销)。"""
        new = self.build_state()
        if new != self._state:
            self._state = new
            self.stateChanged.emit()

    # ---------- 显示/隐藏 ----------

    def request_show(self):
        """pystray 线程调用(线程安全, 信号投递到 Qt 线程)。"""
        self.showRequested.emit()

    def _on_show_requested(self):
        self._visible = True
        if self._win is not None:
            self._win.show()
            self._win.raise_()
            self._win.requestActivate()
        self.ctrl.submit(self.ctrl.refresh())

    @Slot()
    def closePanel(self):
        self._visible = False
        if self._win is not None:
            self._win.hide()

    # ---------- 指令(QML 调用, 均在 Qt 线程) ----------

    @Slot()
    def togglePower(self):
        c = self.ctrl
        c.power = not c.power
        self.publish()
        c.submit(c.apply(power_state=bool(c.power)))

    @Slot(float)
    def stepTemp(self, delta):
        dv = self.ctrl.device
        cur = self.ctrl.target or 26.0
        value = max(float(dv.min_target_temperature),
                    min(float(dv.max_target_temperature), cur + delta))
        self.ctrl.target = value
        self.publish()
        self.ctrl.submit(self.ctrl.apply(target_temperature=value))

    @Slot(float)
    def setTarget(self, value):
        self.ctrl.target = value
        self.publish()
        self.ctrl.submit(self.ctrl.apply(target_temperature=value))

    @Slot(str)
    def setMode(self, key):
        c = self.ctrl
        c.mode = AC.OperationalMode[key.upper()]
        self.publish()
        c.submit(c.apply(operational_mode=c.mode))

    @Slot(str)
    def setFan(self, key):
        dv = self.ctrl.device
        dv.fan_speed = AC.FanSpeed[key.upper()]
        self.publish()
        self.ctrl.submit(self.ctrl.apply(fan_speed=dv.fan_speed))

    @Slot(float)
    def setFanPct(self, pct):
        """自定义风速 0-100。"""
        dv = self.ctrl.device
        dv.fan_speed = int(max(0, min(100, round(pct))))
        self.publish()
        self.ctrl.submit(self.ctrl.apply(fan_speed=dv.fan_speed))

    @Slot(str)
    def toggleFeature(self, key):
        c, dv = self.ctrl, self.ctrl.device
        if key == "wind_dir":
            self._dir_pick = not getattr(self, "_dir_pick", False)
            self.publish()
            return
        if key in ("swing_up", "swing_side"):
            self._toggle_swing("up" if key == "swing_up" else "side")
            return
        if key == "aux":
            if dv.operational_mode != AC.OperationalMode.HEAT:
                return  # 电辅热仅制热模式可调(真机限制)
            cur = dv.aux_mode not in (None, AC.AuxHeatMode.OFF)
            dv.aux_mode = AC.AuxHeatMode.OFF if cur else AC.AuxHeatMode.AUX_HEAT
            self.publish()
            c.submit(c.apply(aux_mode=dv.aux_mode))
            return
        if key == "breezeless":
            # 防直吹(breeze_away)与扫风/固定风向互斥
            cur = bool(getattr(dv, "breeze_away", False))
            if not cur:
                self._clear_swing_and_angles(dv)
            dv.breeze_away = not cur
            self.publish()
            c.submit(c.apply(breeze_away=dv.breeze_away))
            return
        cur = bool(getattr(dv, key, False))
        setattr(dv, key, not cur)
        self.publish()
        c.submit(c.apply(**{key: not cur}))

    @staticmethod
    def _clear_swing_and_angles(dv):
        """扫风/固定风向/防直吹三者互斥, 开其中一类时清掉其余。"""
        dv.swing_mode = AC.SwingMode.OFF
        dv.vertical_swing_angle = AC.SwingAngle.OFF
        dv.horizontal_swing_angle = AC.SwingAngle.OFF

    @Slot(str)
    def toggleSetting(self, key):
        c, dv = self.ctrl, self.ctrl.device
        self._log("面板点击 %s" % key)
        if key == "display":
            try:
                # display_on 是库的只读属性, 不能赋值; 乐观值只存在面板侧
                # (此前赋值抛 AttributeError, 导致屏显点击在投递指令前就崩)
                self._display_opt = not bool(dv.display_on)
                self._display_hold = time.time() + 2.5
                self.publish()
                # 走带锁的封装, 避免和轮询查询并发撞车
                c.submit(c.toggle_display())
                self._log("display 指令已投递")
            except Exception as e:
                self._log("display 分支异常: %r" % e)
            return
        if key == "dry":
            dv.dry_clean = not getattr(dv, "dry_clean", False)
            self.publish()
            c.submit(c.apply_ext(dry_clean=dv.dry_clean))
            return
        cur = bool(getattr(dv, key, False))
        setattr(dv, key, not cur)
        self.publish()
        c.submit(c.apply(**{key: not cur}))

    def _toggle_swing(self, axis):
        dv = self.ctrl.device
        V, HZ, B, OFF = (AC.SwingMode.VERTICAL, AC.SwingMode.HORIZONTAL,
                         AC.SwingMode.BOTH, AC.SwingMode.OFF)
        mode = dv.swing_mode
        if axis == "up":
            new = (HZ if mode == B else OFF) if mode in (V, B) \
                else (B if mode == HZ else V)
        else:
            new = (V if mode == B else OFF) if mode in (HZ, B) \
                else (B if mode == V else HZ)
        # 扫风与防直吹/固定风向互斥
        if new != OFF:
            dv.breeze_away = False
            dv.vertical_swing_angle = AC.SwingAngle.OFF
            dv.horizontal_swing_angle = AC.SwingAngle.OFF
        dv.swing_mode = new
        self.publish()
        self.ctrl.submit(self.ctrl.apply())

    @Slot(str, float)
    def setAngle(self, axis, idx):
        """出风方向角度: idx 0=关, 1..5=五档。
        弹层保持打开, 由"关闭弹层"按钮手动关闭。"""
        dv = self.ctrl.device
        angle = AC.SwingAngle.OFF if idx == 0 \
            else AC.SwingAngle["POS_%d" % idx]
        prop = "vertical_swing_angle" if axis == "v" \
            else "horizontal_swing_angle"
        if idx > 0:
            # 固定风向与扫风/防直吹互斥
            dv.breeze_away = False
            dv.swing_mode = AC.SwingMode.OFF
        setattr(dv, prop, angle)
        self.publish()
        self.ctrl.submit(self.ctrl.apply())

    @Slot(str)
    def debugLog(self, msg):
        """QML 侧诊断日志(确认界面版本/点击是否到达)。"""
        self._log("QML %s" % msg)

    @Slot()
    def refreshNow(self):
        self.ctrl.submit(self.ctrl.refresh())


class Panel:
    """start() 返回的句柄, 对外接口与旧 tray_panel 一致。"""

    def __init__(self, bridge, win):
        self._bridge = bridge
        self._win = win

    def request_show(self):
        self._bridge.request_show()


def _run_ui(ctrl, holder, log=None):
    app = QGuiApplication(sys.argv)
    app.setApplicationName("美的空调")
    bridge = PanelBridge(ctrl, log=log)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("bridge", bridge)
    engine.rootContext().setContextProperty("FEATURES", FEATURES)
    engine.load(str(BASE_DIR / "panel.qml"))
    if not engine.rootObjects():
        print("QML 加载失败", file=sys.stderr)
        return
    win = engine.rootObjects()[0]
    bridge._win = win
    # 保证原生窗口背景透明, 否则 QML 里的圆角会被窗口底色填成直角
    # (rootObject 在 PySide6 里暴露为 QWindow, 没有 setColor, 走 property)
    from PySide6.QtGui import QColor
    win.setProperty("color", QColor(0, 0, 0, 0))
    # QML 的圆角在右侧两角画不出来(实测左上圆、右上直角), 用窗口区域补齐。
    # 必须先让原生窗口真正创建(show 一次), 否则 setMask 不生效。
    from PySide6.QtGui import QPainterPath, QRegion
    _p = QPainterPath()
    _p.addRoundedRect(0.0, 0.0, float(W), float(H), 24.0, 24.0)
    win.show()
    win.setMask(QRegion(_p.toFillPolygon().toPolygon()))
    # 位置: 主屏右下角(任务栏上方)
    geo = QGuiApplication.primaryScreen().availableGeometry()
    win.setPosition(geo.right() - W - 12, geo.bottom() - H - 8)
    win.hide()

    # 状态同步: 每秒比对 + 可见时每 5s 拉一次设备(分开定时, 避免每秒
    # 砸一次查询把网络通道/锁占满, 拖慢真正的控制指令)
    sync_t = QTimer()
    sync_t.timeout.connect(lambda: bridge.sync() if bridge._visible else None)
    sync_t.start(1000)

    ref_t = QTimer()
    ref_t.timeout.connect(lambda: ctrl.submit(ctrl.refresh())
                          if bridge._visible else None)
    ref_t.start(5000)

    holder["panel"] = Panel(bridge, win)
    app.exec()


def start(ctrl, timeout=15.0, log=None):
    """在独立 UI 线程启动 QML 面板, 返回 Panel 句柄(失败返回 None)。"""
    holder = {}
    threading.Thread(target=_run_ui, args=(ctrl, holder, log),
                     daemon=True, name="qt-ui").start()
    deadline = time.time() + timeout
    while time.time() < deadline:
        if "panel" in holder:
            return holder["panel"]
        time.sleep(0.05)
    return None
