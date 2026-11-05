"""美的空调首次配置工具。

流程: 按 IP 发现设备 -> (V3 设备)用美的美居账号登录国内云取 token/key
-> 把 ip / device_id / token / key 写入 ac_config.json。
密码用 getpass 输入, 不落盘、不回显。
"""
import asyncio
import getpass
import json
import sys
from pathlib import Path

from aiohttp import ClientSession
from midealocal.cloud import get_midea_cloud
from msmart.const import DeviceType
from msmart.discover import Discover

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "ac_config.json"


def save_config(ip, device_id, token, key):
    cfg = {}
    if CONFIG_PATH.exists():
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    cfg.update({"ip": ip, "device_id": device_id, "token": token, "key": key})
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False),
                           encoding="utf-8")
    print("已写入 %s" % CONFIG_PATH)


async def fetch_token_china(dev, account, password):
    """用美的美居(国内云)账号获取 V3 设备的 token/key 并完成认证。

    国服已停用 v1 getToken(报 40404), 直接复用 midea-local 的美的美居
    云端实现, 其内部走 v2 接口(homegroupId + applianceCodes 列表)。
    """
    async with ClientSession() as session:
        cloud = get_midea_cloud("美的美居", session, account, password)
        try:
            logged_in = await cloud.login()
        except Exception as e:
            raise SystemExit("美的云登录失败: %s (请检查账号密码)" % e)
        if not logged_in:
            raise SystemExit("美的云登录失败, 请检查账号密码")
        print("美的云登录成功")

        try:
            keys = await cloud.get_cloud_keys(dev.id)
        except Exception as e:
            raise SystemExit("获取 token/key 失败: %s" % e)

    if not keys:
        raise SystemExit("未获取到 token/key, 请确认设备在美的美居 App 中且账号正确")

    # keys 形如 {1: {"token","key"}, 2: {...}}, 两种 udpid 编码, 逐个尝试认证
    last_err = None
    for entry in keys.values():
        try:
            await dev.authenticate(bytes.fromhex(entry["token"]),
                                   bytes.fromhex(entry["key"]))
            print("token/key 获取成功, 设备认证通过")
            return entry["token"], entry["key"]
        except Exception as e:
            last_err = e
    raise SystemExit("设备认证失败: %s" % last_err)


async def main():
    # 优先用命令行参数指定的 IP; 其次用 ac_config.json 里已有的 ip;
    # 都没有才走局域网广播(广播不跨网段, 空调与电脑不同网段时必须指定 IP)
    ip = sys.argv[1] if len(sys.argv) > 1 else None
    if ip is None and CONFIG_PATH.exists():
        ip = json.loads(CONFIG_PATH.read_text(encoding="utf-8")).get("ip") or None

    if ip:
        print("正在发现 %s 上的美的设备..." % ip)
        dev = await Discover.discover_single(ip, auto_connect=False)
        devices = [dev] if dev else []
    else:
        print("正在局域网广播搜索美的设备 (约 5 秒)...")
        devices = await Discover.discover(discovery_packets=3, auto_connect=False)

    devices = [d for d in devices if d.type == DeviceType.AIR_CONDITIONER]
    if not devices:
        raise SystemExit(
            "未发现空调。请检查: 1) 美的美居 App 中设备是否在线; "
            "2) 空调与电脑是否在同一路由器网络; 3) 路由器是否开启了 IoT 隔离")

    for i, dev in enumerate(devices):
        print("  [%d] ip=%s id=%s sn=%s 协议版本=V%s" %
              (i, dev.ip, dev.id, dev.sn, dev.version))
    dev = devices[0] if len(devices) == 1 else devices[int(input("选择设备序号: "))]

    token = key = None
    if (dev.version or 0) >= 3:
        print("该设备为 V3 协议, 需要美的美居账号取一次性 token/key")
        account = input("美的美居账号(手机号/邮箱): ").strip()
        print("(密码输入时不显示任何字符, 属正常现象, 输完按回车)")
        password = getpass.getpass("密码: ")
        token, key = await fetch_token_china(dev, account, password)
    else:
        print("该设备为 V%s 协议, 无需 token/key" % dev.version)

    save_config(dev.ip, dev.id, token or "", key or "")

    # 存完立即验证一次: 能读到状态说明整条链路通了
    await dev.refresh()
    if dev.online:
        print("验证成功: 设备在线, 目标温度 %.0f°C, 双击 run.bat 启动托盘"
              % (dev.target_temperature or 0))
    else:
        print("token/key 已保存, 但设备状态查询未响应, 请双击 run.bat 看托盘显示")


if __name__ == "__main__":
    asyncio.run(main())
