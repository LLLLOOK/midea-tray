# -*- coding: utf-8 -*-
"""本地验证 _inject_ext_bits: 全 False 应与原帧逐字节一致;
置位后仅差对应的功能位 + CRC8 + 校验和, 且帧校验和必须合法。"""
import sys
from pathlib import Path

BASE = Path("C:/Users/72919/WorkBuddy/2026-10-12-20-32-31/midea-tray")
sys.path.insert(0, str(BASE))

from msmart.device.AC.command import SetStateCommand  # noqa: E402
from msmart.frame import Frame  # noqa: E402

from midea_tray import _EXT_BITS, _HEADER_LEN, _build_set_state_command, _inject_ext_bits  # noqa: E402


class FakeDev:
    """最小 device 桩, 只提供 _build_set_state_command 用到的公开属性。"""
    power_state = True
    target_temperature = 26.0
    operational_mode = 1  # COOL
    fan_speed = 102       # AUTO
    swing_mode = 0
    eco = False
    turbo = False
    freeze_protection = False
    sleep = False
    fahrenheit = False
    follow_me = False
    purifier = False
    target_humidity = 40
    aux_mode = None
    sound = False


cmd = _build_set_state_command(FakeDev())
raw = cmd.tobytes()
print("原帧:", raw.hex())

# 1) 全 False: 必须与原帧一致
same = _inject_ext_bits(raw, {k: False for k in _EXT_BITS})
assert same == raw, "全 False 注入应与原帧逐字节一致!\n%s\n%s" % (same.hex(), raw.hex())
print("全 False 注入 = 原帧 ✓")

# 2) 逐个置位: 仅功能位/crc8/校验和变化, 且校验和合法
for name, (idx, bit) in _EXT_BITS.items():
    out = _inject_ext_bits(raw, {name: True})
    diff = [i for i in range(len(raw)) if out[i] != raw[i]]
    expect = {_HEADER_LEN + idx, len(raw) - 2, len(raw) - 1}
    assert set(diff) == expect, "%s 置位后差异字节 %s, 期望 %s" % (name, diff, expect)
    assert out[_HEADER_LEN + idx] & bit, "%s 的功能位没置上" % name
    # 用库自己的校验逻辑验证整帧合法
    Frame.validate(memoryview(out), __import__("msmart.const", fromlist=["DeviceType"]).DeviceType.AIR_CONDITIONER)
    print("%-12s 置位 ✓ (byte%d |= 0x%02X, crc/校验和已重算, 帧校验通过)" % (name, idx, bit))

# 3) 全部置位
out = _inject_ext_bits(raw, {k: True for k in _EXT_BITS})
Frame.validate(memoryview(out), __import__("msmart.const", fromlist=["DeviceType"]).DeviceType.AIR_CONDITIONER)
assert out[19] & 0x04 and out[20] & 0x08 and out[20] & 0x10
print("三位同时置位 ✓ 帧校验通过")
print("OK")
