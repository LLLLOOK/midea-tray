# -*- coding: utf-8 -*-
"""离屏测试用的假设备 / 假控制器, 不连真机。"""
from msmart.device import AirConditioner as AC


class FakeDevice:
    min_target_temperature = 16
    max_target_temperature = 30
    indoor_temperature = 28.1
    outdoor_coil_temperature = 29.5
    outdoor_temperature = 30.2
    fan_speed = AC.FanSpeed.AUTO
    swing_mode = AC.SwingMode.OFF
    vertical_swing_angle = None
    horizontal_swing_angle = None
    breezeless = False
    turbo = False
    eco = False
    aux_mode = AC.AuxHeatMode.OFF
    operational_mode = AC.OperationalMode.COOL
    _display_on = True

    @property
    def display_on(self):
        return self._display_on
    sound = False
    filter_alert = False
    error_code = 0
    dry_clean = False      # 干燥防霉(扩展协议位)
    catch_cold = True      # 智控温(扩展协议位, 用户 App 开机即亮)
    night_light = True     # 智能光感(扩展协议位, 用户 App 开机即亮)

    def get_current_energy_usage(self):
        return 1.23

    def get_total_energy_usage(self):
        return 1202.9

    def toggle_display(self):
        pass


class FakeCtrl:
    def __init__(self, **kw):
        self.device = FakeDevice()
        self.online = True
        self.power = True
        self.mode = AC.OperationalMode.COOL
        self.target = 26.0
        self.indoor = 28.1
        for k, v in kw.items():
            setattr(self, k, v)

    def submit(self, coro):
        try:
            coro.close()
        except Exception:
            pass

    daily_energy = 1.23

    async def apply(self, **kw):
        return None

    async def toggle_display(self):
        return None

    async def apply_ext(self, **kw):
        return None

    def _set_error(self, exc):
        pass

    def error_text(self):
        return ""

    async def refresh(self):
        return None
