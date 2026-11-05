# -*- coding: utf-8 -*-
"""智控温/智能光感协议位定位工具。

原理: 属性 0x007E 是设备全量状态的镜像。你在美居 App 里切换某个功能,
这个属性里对应的字节就会变化。脚本每 2 秒读一次, 自动打印发生变化的字节。

用法:
  1. 运行:  .venv\\Scripts\\python.exe capture_7e.py
  2. 看到"开始监听"后, 在 100 秒内去美居 App:
       - 把【智控温】关掉, 等 5 秒, 再打开
     (如果还想定位智能光感, 同一轮里再切一次智能光感, 切换之间隔开)
  3. 结束后把打印结果发给我, 我就能定位到具体字节。

只读操作, 不改任何设置, 不动电源。
"""
import asyncio
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

from midea_tray import Controller, build_device  # noqa: E402
from msmart.device.AC.command import GetPropertiesCommand  # noqa: E402

PROP = 0x007E
DURATION = int(sys.argv[1]) if len(sys.argv) > 1 else 600  # 监听总时长(秒)
IGNORE = {40, 41}     # 滚动计数器字节(每 ~25s 自增), 屏蔽噪声
INTERVAL = 2          # 采样间隔(秒)


def parse_prop(payload, want):
    count = payload[1]
    i = 2
    for _ in range(count):
        if i + 4 > len(payload):
            break
        pid = payload[i] | (payload[i + 1] << 8)
        size = payload[i + 3]
        if pid == want:
            return bytes(payload[i + 4:i + 4 + size])
        i += 4 + size
    return None


async def read_prop(dv):
    for r in await dv._send_commands_get_responses(
            GetPropertiesCommand([PROP])):
        if type(r).__name__ == "PropertiesResponse":
            data = parse_prop(r.payload, PROP)
            if data:
                return data
        elif r.payload[:1] == b"\xb1":
            data = parse_prop(r.payload, PROP)
            if data:
                return data
    return None


async def main():
    cfg = json.loads((BASE / "ac_config.json").read_text(encoding="utf-8"))
    ctrl = Controller(build_device(cfg), token=cfg.get("token"),
                      key=cfg.get("key"), subnets=cfg.get("known_subnets"))
    await ctrl.authenticate(cfg["token"], cfg["key"])
    for _ in range(4):
        await ctrl.refresh()
        if ctrl.online:
            break
        await ctrl.rediscover()
    if not ctrl.online:
        print("设备不在线, 退出")
        return
    dv = ctrl.device
    print("已连接 %s  电源=%s" % (dv.ip, dv.power_state))

    base = await read_prop(dv)
    if not base:
        print("读不到 0x007E, 退出")
        return
    print("基准 %d 字节: %s" % (len(base), base.hex()))
    print("=== 开始监听 %d 秒, 现在去 App 切换智控温(关→等5秒→开) ==="
          % DURATION)

    prev = base
    changes = []
    t = 0
    while t < DURATION:
        await asyncio.sleep(INTERVAL)
        t += INTERVAL
        cur = await read_prop(dv)
        if not cur or len(cur) != len(prev):
            continue
        diff = [i for i in range(len(cur)) if cur[i] != prev[i]]
        # 最后一字节是滚动计数器, 忽略
        diff = [i for i in diff if i not in IGNORE and i != len(cur) - 1]
        if diff:
            print("[%3ds] 变化字节 %s" % (t, diff))
            for i in diff:
                print("       byte%-2d: 0x%02X -> 0x%02X" % (i, prev[i], cur[i]))
            changes.append({"t": t, "diff": diff,
                            "data": cur.hex()})
            prev = cur
            # 边抓边存, 运行中也能看到中间结果
            (BASE / "7e_capture.json").write_text(
                json.dumps({"base": base.hex(), "changes": changes},
                           ensure_ascii=False, indent=1), encoding="utf-8")
    print("=== 监听结束, 共 %d 次变化 ===" % len(changes))
    (BASE / "7e_capture.json").write_text(
        json.dumps({"base": base.hex(), "changes": changes},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    print("已保存 7e_capture.json, 把它发给我")


asyncio.run(main())
