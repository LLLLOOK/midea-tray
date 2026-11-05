"""美的空调 Windows 托盘控制条。

设备信息通过 msmart-ng discover 获得并填入 ac_config.json,
之后本程序直接与空调走局域网协议通信, 不经过美的云端。
"""
import asyncio
import functools
import json
import logging
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pystray
from PIL import Image, ImageDraw, ImageFont
from msmart import crc8
from msmart.device import AirConditioner as AC
from msmart.device.AC import command as ac_command
from msmart.device.AC.command import (PropertyId, SetPropertiesCommand,
                                     SetStateCommand)
from msmart.frame import Frame

_T_START = time.perf_counter()  # 启动计时

# ---------------------------------------------------------------------------
# msmart-ng 未启用的功能位(原作者注释掉了, 语义未确认):
#   状态帧 payload[9]  & 0x04 = dry_clean    干燥防霉
#   状态帧 payload[10] & 0x08 = catch_cold   智控温(防着凉)
#   状态帧 payload[10] & 0x10 = night_light  智能光感
# 下发命令的同名字节是空闲位, 与上报位一一对应, 可注入后下发。
# 帧结构: header(10) + payload + msg_id(1) + crc8(1) + checksum(1)
#
# 真机验证(2026-10-16, 神机二代 KFR-35G/N8HE1II, 开机状态):
#   dry_clean    可读可写, 翻转后设备立即生效并回显 —— 已支持
#   catch_cold   置位后设备回显不变(忽略), 注释里其他候选位同样忽略
#   night_light  同上
# 另发现设备支持库枚举外属性 0x007E(实时镜像全量状态, 含 dry_clean 位),
# 智控温/智能光感若走该属性, 需在 App 侧切换时抓包对比定位(未完成)。
# ---------------------------------------------------------------------------
_EXT_BITS = {"dry_clean": (9, 0x04), "catch_cold": (10, 0x08),
             "night_light": (10, 0x10)}
_HEADER_LEN = 10

# 能力集没广告、但真机实测可读写的属性(网关到不了 capability 帧):
#   0x0009/0x000A 上下/左右出风角度, 0x0042 防直吹, 0x022C 声音
# 不加入轮询列表的话: 读不到手机端设置, 写指令也会被库当"不支持"跳过
_EXTRA_PROPS = (PropertyId.SWING_UD_ANGLE, PropertyId.SWING_LR_ANGLE,
                PropertyId.BREEZE_AWAY, PropertyId.SOUND)

_orig_parse = ac_command.StateResponse._parse


def _parse_with_ext(self, payload):
    _orig_parse(self, payload)
    self.dry_clean = bool(payload[9] & 0x04)
    self.catch_cold = bool(payload[10] & 0x08)
    self.night_light = bool(payload[10] & 0x10)


ac_command.StateResponse._parse = _parse_with_ext

_orig_update_state = AC._update_state


def _update_state_with_ext(self, response):
    _orig_update_state(self, response)
    for name in _EXT_BITS:
        if hasattr(response, name):
            setattr(self, name, getattr(response, name))


AC._update_state = _update_state_with_ext

_orig_update_supported = AC._update_supported_properties


def _update_supported_with_ext(self):
    _orig_update_supported(self)
    self._supported_properties.update(_EXTRA_PROPS)


AC._update_supported_properties = _update_supported_with_ext


def _build_set_state_command(dv):
    """按设备当前公开属性构造 SetStateCommand(与 device.apply 内部逻辑一致)。"""
    cmd = SetStateCommand()
    cmd.beep_on = dv.sound
    cmd.power_on = bool(dv.power_state)
    cmd.target_temperature = dv.target_temperature or 25
    cmd.operational_mode = dv.operational_mode
    cmd.fan_speed = dv.fan_speed
    cmd.swing_mode = dv.swing_mode
    cmd.eco = bool(dv.eco)
    cmd.turbo = bool(dv.turbo)
    cmd.freeze_protection = bool(dv.freeze_protection)
    cmd.sleep = bool(dv.sleep)
    cmd.fahrenheit = bool(dv.fahrenheit)
    cmd.follow_me = bool(dv.follow_me)
    cmd.purifier = bool(dv.purifier)
    cmd.target_humidity = dv.target_humidity or 40
    cmd.aux_heat = dv.aux_mode == AC.AuxHeatMode.AUX_HEAT
    cmd.independent_aux_heat = dv.aux_mode == AC.AuxHeatMode.AUX_ONLY
    return cmd


def _inject_ext_bits(frame, flags):
    """把三个扩展功能位注入 SetStateCommand 帧并重算 CRC8 与帧校验和。
    帧结构: header(10) + payload + msg_id(1) + crc8(1) + checksum(1)"""
    data = bytearray(frame)
    for name, value in flags.items():
        idx, bit = _EXT_BITS[name]
        if value:
            data[_HEADER_LEN + idx] |= bit
        else:
            data[_HEADER_LEN + idx] &= ~bit & 0xFF
    data[-2] = crc8.calculate(bytes(data[_HEADER_LEN:-2]))  # payload+msg_id 的 CRC8
    data[-1] = Frame.checksum(bytes(data[1:-1]))           # 帧校验和
    return bytes(data)

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "ac_config.json"
ENERGY_PATH = BASE_DIR / "energy.json"  # 今日用电基线
DEBUG_LOG = BASE_DIR / "panel_debug.log"


def _dbg(msg):
    """面板操作诊断日志(排查"点了没反应"用, 可随时删)。"""
    try:
        if DEBUG_LOG.exists() and DEBUG_LOG.stat().st_size > 1_000_000:
            DEBUG_LOG.unlink()   # 超过 1MB 直接重来, 这是排障日志不是归档
        with DEBUG_LOG.open("a", encoding="utf-8") as fp:
            fp.write("%s %s\n" % (time.strftime("%H:%M:%S"), msg))
    except Exception:
        pass
POLL_INTERVAL = 30       # 开机状态轮询间隔(秒)
POLL_INTERVAL_OFF = 120  # 关机后降频, 只为感知"被遥控器开机"


class _NoiseFilter(logging.Filter):
    """设备会回 0x007E(镜像全量状态), msmart 不认这条属性, 每轮刷一条警告。"""

    def filter(self, record):
        return "Unknown property ID 0x007E" not in record.getMessage()




MODE_NAMES = {
    AC.OperationalMode.AUTO: "自动",
    AC.OperationalMode.COOL: "制冷",
    AC.OperationalMode.DRY: "除湿",
    AC.OperationalMode.HEAT: "制热",
    AC.OperationalMode.FAN_ONLY: "送风",
}
FAN_NAMES = {
    AC.FanSpeed.SILENT: "静音",
    AC.FanSpeed.LOW: "低风",
    AC.FanSpeed.MEDIUM: "中风",
    AC.FanSpeed.HIGH: "高风",
    AC.FanSpeed.MAX: "强劲",
    AC.FanSpeed.AUTO: "自动",
}
MODE_COLORS = {
    AC.OperationalMode.AUTO: (52, 120, 246, 255),
    AC.OperationalMode.COOL: (46, 144, 255, 255),
    AC.OperationalMode.DRY: (0, 176, 174, 255),
    AC.OperationalMode.HEAT: (244, 128, 40, 255),
    AC.OperationalMode.FAN_ONLY: (0, 178, 118, 255),
}
OFF_COLOR = (110, 116, 126, 255)

LOOP = None  # 后台线程中的 asyncio 事件循环


def load_config():
    if not CONFIG_PATH.exists():
        raise SystemExit("缺少配置文件 ac_config.json")
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if not cfg.get("ip") or not cfg.get("device_id"):
        raise SystemExit("ac_config.json 中 ip / device_id 未填写, 请先运行 msmart-ng discover")
    return cfg


def build_device(cfg):
    return AC(ip=cfg["ip"], device_id=int(cfg["device_id"]),
              port=int(cfg.get("port", 6444)))


def scan_port(prefix, port):
    """扫描 prefix+'1' ~ prefix+'254' 中 port 开放的主机, 返回 IP 列表。"""
    def probe(ip):
        s = socket.socket()
        s.settimeout(0.6)
        try:
            s.connect((ip, port))
            return ip
        except Exception:
            return None
        finally:
            s.close()

    with ThreadPoolExecutor(150) as ex:
        return [r for r in ex.map(probe, [prefix + str(i) for i in range(1, 255)]) if r]


def make_icon(text, color):
    """生成 64x64 托盘图标: 圆角方块 + 居中数字。"""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([2, 2, 61, 61], radius=14, fill=color)
    font = ImageFont.load_default(size=36)
    box = d.textbbox((0, 0), text, font=font)
    d.text(((64 - box[2] + box[0]) / 2, (64 - box[3] + box[1]) / 2),
           text, font=font, fill="white")
    return img


class Controller:
    """持有设备对象与状态快照, 所有设备访问都在 asyncio 线程中串行执行。"""

    def __init__(self, device, token=None, key=None, subnets=None):
        self.device = device
        self._token = token
        self._key = key
        self._subnets = subnets or [device.ip.rsplit(".", 1)[0] + "."]
        self._lock = asyncio.Lock()
        self._fail_count = 0
        self.icon = None
        self.panel = None  # 面板句柄(pyside_panel.Panel), main() 里赋值
        self.online = False
        self.power = None
        self.mode = None
        self.target = None
        self.indoor = None
        self._last_indoor = None   # 关机后设备可能不再上报室内温度, 用它兜底
        self.daily_energy = None
        self._pending_refresh = None
        self._last_error = ""    # 最近一次指令失败的友好提示
        self._error_at = 0.0     # 失败时间, 3 秒后自动过期
        try:
            device.enable_energy_usage_requests = True  # 让设备上报电量数据
            device.enable_group1_data_requests = True  # 室外盘管温度(该机型唯一可用的室外温度)
        except Exception:
            pass
        device._supported_properties.update(_EXTRA_PROPS)

    # ---------- 设备操作 (asyncio 线程) ----------

    async def authenticate(self, token_hex, key_hex):
        try:
            await self.device.authenticate(bytes.fromhex(token_hex), bytes.fromhex(key_hex))
        except Exception as e:
            logging.warning("V3 认证失败 (V2 设备可忽略): %s", e)

    async def refresh(self):
        async with self._lock:
            try:
                await self.device.refresh()
            except Exception as e:
                logging.warning("查询失败: %s", e)
        if self.device.online:
            self._sync_cached()
        else:
            self.online = False
            # 连续失败达到阈值时, 可能是 DHCP 换了 IP, 扫同网段重新找
            self._fail_count += 1
            if self._fail_count == 2 or self._fail_count % 10 == 0:
                if await self.rediscover():
                    return
        self.update_ui()

    def _sync_cached(self):
        """把设备对象上的状态同步到托盘缓存/图标(纯本地, 不发网络请求)。"""
        self.online = True
        self._fail_count = 0
        self.power = self.device.power_state
        self.mode = self.device.operational_mode
        self.target = self.device.target_temperature
        self.indoor = self.device.indoor_temperature
        self._track_daily_energy()
        self.update_ui()

    async def rediscover(self):
        """配置的 IP 失效时, 扫描已知网段 + 本机网段的 6444 端口,
        认证确认是本机空调后切换 IP (空调可能在路由器/光猫多个 WiFi 间跳)。"""
        prefixes = self._candidate_subnets()
        logging.info("设备无响应, 正在这些网段重新查找空调: %s", " ".join(prefixes))
        for prefix in prefixes:
            found = await asyncio.to_thread(scan_port, prefix, self.device.port)
            for ip in found:
                try:
                    dev = AC(ip=ip, device_id=self.device.id, port=self.device.port)
                    dev.enable_energy_usage_requests = True
                    dev.enable_group1_data_requests = True
                    dev._supported_properties.update(_EXTRA_PROPS)
                    if self._token and self._key:
                        await dev.authenticate(bytes.fromhex(self._token),
                                               bytes.fromhex(self._key))
                    await asyncio.wait_for(dev.refresh(), timeout=6)
                except Exception:
                    continue
                if dev.online:
                    logging.info("空调已迁移到 %s, 更新配置", ip)
                    self.device = dev
                    self._save_ip(ip)
                    self._fail_count = 0
                    await self.refresh()
                    return True
        logging.info("未找到可认证的空调")
        return False

    def _candidate_subnets(self):
        """候选网段: known_subnets + 本机主网卡所在网段 (去重)"""
        prefixes = list(self._subnets)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))  # UDP connect 不发包, 仅让内核选出源地址
            own = s.getsockname()[0].rsplit(".", 1)[0] + "."
            s.close()
            if own not in prefixes:
                prefixes.append(own)
        except Exception:
            pass
        return prefixes

    def _save_ip(self, ip):
        try:
            cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            cfg["ip"] = ip
            subnets = cfg.get("known_subnets") or list(self._subnets)
            prefix = ip.rsplit(".", 1)[0] + "."
            if prefix not in subnets:
                subnets.append(prefix)
            cfg["known_subnets"] = subnets
            self._subnets = subnets
            CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False),
                                   encoding="utf-8")
        except Exception as e:
            logging.warning("更新配置文件失败: %s", e)

    async def apply(self, **changes):
        """下发指令。所有 SetState 帧都注入扩展功能位(干燥防霉等),
        否则标准帧里这几位为 0, 设备会把它当成"关闭"——之前点声音
        把干燥防霉关掉就是这个原因。

        """
        async with self._lock:
            dv = self.device
            try:
                for name, value in changes.items():
                    setattr(dv, name, value)
                flags = {n: bool(getattr(dv, n, False)) for n in _EXT_BITS}
                orig = dv._send_commands_get_responses

                async def patched(cmds):
                    if isinstance(cmds, SetStateCommand):
                        raw = _inject_ext_bits(cmds.tobytes(), flags)
                        cmds.tobytes = lambda: raw
                    return await orig(cmds)

                dv._send_commands_get_responses = patched
                try:
                    await dv.apply()
                finally:
                    dv._send_commands_get_responses = orig
            except Exception as e:
                logging.warning("指令下发失败: %s", e)
                self._set_error(e)
        self._sync_cached()  # 指令响应里已带回状态, 本地同步即可

    async def apply_ext(self, **changes):
        """兼容入口: 扩展位已并入 apply, 这里直接转发。"""
        await self.apply(**changes)

    async def _confirm_display(self, want, delay=1.0):
        """屏显是翻转指令, 丢包时设备根本不会变; 查询确认后补发一次。"""
        await asyncio.sleep(delay)
        await self.refresh()
        if bool(self.device.display_on) == bool(want):
            return
        _dbg("屏显未生效(实际=%s 期望=%s), 补发一次" % (
            self.device.display_on, want))
        async with self._lock:
            try:
                await self.device.toggle_display()
            except Exception as e:
                logging.warning("屏显补发失败: %s", e)
        await asyncio.sleep(0.8)
        await self.refresh()
        _dbg("屏显补发后 display_on=%s" % self.device.display_on)

    async def toggle_display(self):
        """屏显是翻转型指令, 必须和其他指令串行(共用一把锁),
        否则会和轮询查询撞在同一条连接上导致偶发失效。"""
        want = not bool(self.device.display_on)  # 期望翻转后的状态
        _dbg("toggle_display 开始, 当前 display_on=%s" % self.device.display_on)
        async with self._lock:
            try:
                await self.device.toggle_display()
                _dbg("toggle_display 指令已发, 本地 display_on=%s" % self.device.display_on)
            except Exception as e:
                logging.warning("屏显切换失败: %s", e)
                _dbg("toggle_display 异常: %s" % e)
        # 延迟确认(不占着锁等, 免得拖慢下一次点击); 没生效会自动补发
        if self._pending_refresh is None or self._pending_refresh.done():
            self._pending_refresh = asyncio.create_task(
                self._confirm_display(want))

    def _track_daily_energy(self):
        """设备"今日电量"寄存器恒为 0(该机型不填), 用累计电量的
        当日基线差值自己算今日用电。基线落盘, 跨重启保持。"""
        total = self.device.get_total_energy_usage()
        if total is None:
            return
        today = time.strftime("%Y-%m-%d")
        base = None
        try:
            if ENERGY_PATH.exists():
                data = json.loads(ENERGY_PATH.read_text(encoding="utf-8"))
                if data.get("date") == today:
                    base = float(data["base"])
        except Exception:
            pass
        if base is None:
            base = total
            try:
                ENERGY_PATH.write_text(
                    json.dumps({"date": today, "base": total}), encoding="utf-8")
            except Exception as e:
                logging.warning("写入电量记录失败: %s", e)
        self.daily_energy = round(max(0.0, total - base), 2)

    async def poll_forever(self):
        # 开机按 30s 轮询; 关机后降到 120s, 既感知遥控器开机又不白耗资源
        while True:
            await asyncio.sleep(POLL_INTERVAL if self.power else POLL_INTERVAL_OFF)
            await self.refresh()

    # ---------- UI ----------

    def status_text(self):
        if not self.online:
            return "离线"
        if not self.power:
            if self.indoor is not None:
                return "已关机 (室内 %.1f°C)" % self.indoor
            return "已关机"
        mode = MODE_NAMES.get(self.mode, "?")
        target = (("%.1f" % self.target).rstrip("0").rstrip(".")
                  if self.target is not None else "?")
        text = "%s %s°C" % (mode, target)
        if self.indoor is not None:
            text += " (室内 %.1f°C)" % self.indoor
        return text

    def _set_error(self, exc):
        s = str(exc).lower()
        if "not capable" in s:
            self._last_error = "该功能当前模式下不可用"
        elif "timeout" in s or "timed out" in s:
            self._last_error = "设备响应超时"
        elif "connection" in s or "refused" in s or "unreachable" in s:
            self._last_error = "连接失败，检查空调是否在线"
        else:
            self._last_error = "指令发送失败"
        self._error_at = time.time()

    def error_text(self):
        """面板顶部提示用: 只保留最近 3 秒内的失败。"""
        if self._last_error and time.time() - self._error_at > 3.0:
            return ""
        return self._last_error

    def tooltip_text(self):
        """托盘悬停提示。Windows 的 szTip 支持换行(上限 128 字符)。"""
        if not self.online:
            return "美的空调 · 离线"
        if not self.power:
            text = "美的空调 · 已关机"
            if self.indoor is not None:
                text += "\n室内 %.1f°C" % self.indoor
            return text
        mode = MODE_NAMES.get(self.mode, "?")
        target = (("%.1f" % self.target).rstrip("0").rstrip(".")
                  if self.target is not None else "?")
        line2 = "目标 %s°C · %s" % (target, mode)
        fan = FAN_NAMES.get(self.device.fan_speed, "")
        if fan:
            line2 += " · " + fan
        lines = ["美的空调 · 运行中", line2]
        if self.indoor is not None:
            lines.append("室内 %.1f°C" % self.indoor)
        return "\n".join(lines)

    def submit(self, coro):
        try:
            if LOOP is None or not LOOP.is_running():
                _dbg("submit 失败: 事件循环未运行 (LOOP=%s)" % LOOP)
                coro.close()
                return None
            return asyncio.run_coroutine_threadsafe(coro, LOOP)
        except Exception as e:
            _dbg("submit 异常: %r" % e)
            return None

    def update_ui(self):
        if self.icon is None:
            return
        if self.indoor is not None:
            self._last_indoor = self.indoor
        # 开机显示设定温度; 关机显示室内温度, 设备停止上报时用最近一次读数兜底
        if self.online and self.power and self.target is not None:
            text, color = str(int(self.target)), MODE_COLORS.get(self.mode, OFF_COLOR)
        elif self.online and self.indoor is not None:
            text, color = str(int(self.indoor)), OFF_COLOR
        elif self.online and self._last_indoor is not None:
            text, color = str(int(self._last_indoor)), OFF_COLOR
        else:
            text, color = "--", OFF_COLOR
        try:
            self.icon.icon = make_icon(text, color)
            self.icon.title = self.tooltip_text()
            self.icon.menu = self.build_menu()
            self.icon.update_menu()
        except Exception as e:
            logging.warning("UI 更新失败: %s", e)

    def open_panel(self, show=True):
        """首次调用时才加载 Qt/QML(冷启动的耗时大头), 之后复用。

        show=False 用于启动后台预热, 只加载不弹出。
        """
        if self.panel is None and not getattr(self, "_panel_failed", False):
            _dbg("面板: 开始加载(Qt/QML)")
            import pyside_panel
            self.panel = pyside_panel.start(self, log=_dbg)
            if self.panel is None:
                # 重试会创建第二个 QGuiApplication, 直接崩溃
                self._panel_failed = True
                _dbg("面板: 加载失败, 不再重试")
            else:
                _dbg("面板: 加载完成")
        if show and self.panel is not None:
            self.panel.request_show()

    def build_menu(self):
        items = [pystray.MenuItem("美的空调 · %s" % self.status_text(), None, enabled=False)]
        # default=True: 托盘图标左键单击直接打开控制面板
        items.append(pystray.MenuItem("打开控制面板",
                                      lambda *a: self.open_panel(),
                                      default=True))
        if not self.online:
            items.append(pystray.MenuItem("刷新", lambda *a: self.submit(self.refresh())))
            items.append(pystray.Menu.SEPARATOR)
            items.append(pystray.MenuItem("退出", lambda *a: self.icon.stop()))
            return pystray.Menu(*items)

        items.append(pystray.MenuItem(
            "关机" if self.power else "开机",
            lambda *a: self.submit(self.apply(power_state=not self.power))))

        # 温度/模式/风速无论开关机都显示, 方便预设
        target = int(self.target or 26)

        def adjust(delta):
            def action(*a):
                lo = self.device.min_target_temperature
                hi = self.device.max_target_temperature
                value = max(lo, min(hi, self.target + delta))
                self.submit(self.apply(target_temperature=value))
            return action

        items.append(pystray.MenuItem("温度 %d°C" % target, pystray.Menu(
            pystray.MenuItem("+ 1°C", adjust(1)),
            pystray.MenuItem("- 1°C", adjust(-1)),
        )))
        items.append(pystray.MenuItem(
            "模式 · %s" % MODE_NAMES.get(self.mode, "?"),
            pystray.Menu(*[
                pystray.MenuItem(
                    name,
                    functools.partial(self.set_mode, mode),
                    checked=functools.partial(self.mode_is, mode))
                for mode, name in MODE_NAMES.items()
            ])))
        items.append(pystray.MenuItem("风速", pystray.Menu(*[
            pystray.MenuItem(
                name,
                functools.partial(self.set_fan, fan),
                checked=functools.partial(self.fan_is, fan))
            for fan, name in FAN_NAMES.items()
        ])))

        items.append(pystray.MenuItem("刷新", lambda *a: self.submit(self.refresh())))
        items.append(pystray.Menu.SEPARATOR)
        items.append(pystray.MenuItem("退出", lambda *a: self.icon.stop()))
        return pystray.Menu(*items)

    def set_mode(self, mode, *args):
        self.submit(self.apply(operational_mode=mode))

    def set_fan(self, fan, *args):
        self.submit(self.apply(fan_speed=fan))

    def mode_is(self, mode, *args):
        return self.mode == mode

    def fan_is(self, fan, *args):
        return self.device.fan_speed == fan


def main():
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    # 过滤器要挂在 handler 上, 挂在 logger 上拦不住子 logger(msmart.xxx) 的记录
    _nf = _NoiseFilter()
    for _h in logging.getLogger().handlers:
        _h.addFilter(_nf)
    cfg = load_config()

    global LOOP
    _t0 = time.perf_counter()
    _dbg("启动: 模块导入完成 %.2fs" % (_t0 - _T_START))
    LOOP = asyncio.new_event_loop()

    def _run_loop():
        _dbg("asyncio 循环线程启动")
        try:
            LOOP.run_forever()
            _dbg("asyncio 循环意外退出")
        except Exception as e:
            _dbg("asyncio 循环异常: %r" % e)

    threading.Thread(target=_run_loop, daemon=True).start()

    ctrl = Controller(build_device(cfg), cfg.get("token"), cfg.get("key"),
                      cfg.get("known_subnets"))

    async def setup():
        if cfg.get("token") and cfg.get("key"):
            await ctrl.authenticate(cfg["token"], cfg["key"])
        await ctrl.refresh()

    # 后台执行认证+首次查询, 不阻塞启动(网络抖动时最长会拖到几十秒,
    # 之前 .result(timeout=60) 让托盘要等整整一分钟才出来)
    asyncio.run_coroutine_threadsafe(setup(), LOOP)
    asyncio.run_coroutine_threadsafe(ctrl.poll_forever(), LOOP)

    _dbg("启动: 事件循环就绪 %.2fs" % (time.perf_counter() - _t0))

    icon = pystray.Icon(
        "midea_ac",
        icon=make_icon("--", OFF_COLOR),
        title="美的空调 · 启动中",
        menu=ctrl.build_menu(),
    )
    ctrl.icon = icon
    _dbg("启动: 托盘就绪 %.2fs" % (time.perf_counter() - _t0))
    # 预热面板: 在后台把 Qt/QML 加载好, 首次点开时不用再等冷启动
    threading.Thread(target=ctrl.open_panel, kwargs={"show": False},
                     daemon=True, name="panel-warmup").start()
    icon.run()


if __name__ == "__main__":
    main()
