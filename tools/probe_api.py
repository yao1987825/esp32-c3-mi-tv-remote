import asyncio
import os

from aioesphomeapi import APIClient

try:
    from credentials import BOARD_IP, NOISE_PSK
except ImportError:  # 没建 credentials.py 就读环境变量
    BOARD_IP = os.environ.get("TV_REMOTE_BOARD_IP", "192.168.6.101")
    NOISE_PSK = os.environ.get("TV_REMOTE_NOISE_PSK", "")


async def main():
    client = APIClient(BOARD_IP, 6053, None, noise_psk=NOISE_PSK)
    await client.connect(login=True)
    info = await client.device_info()
    ents, svcs = await client.list_entities_services()
    print("设备:", info.name, "/", info.friendly_name)
    print(f"实体 {len(ents)} 个, 服务 {len(svcs)} 个\n")
    for s in svcs:
        print(f"  key={s.key:<4} name={s.name!r}")
        for a in s.args:
            print(f"        arg {a.name}: {a.type} optional={a.optional} default={a.default_value!r}")
    await client.disconnect()


asyncio.run(main())
