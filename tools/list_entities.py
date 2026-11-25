#!/usr/bin/env python3
"""列出板子（ESPHome）当前的全部实体名。"""
import asyncio
import os
import sys

from aioesphomeapi import APIClient

try:
    from credentials import BOARD_IP, NOISE_PSK
except ImportError:  # 没建 credentials.py 就读环境变量
    HOST = os.environ.get("TV_REMOTE_BOARD_IP", "192.168.6.101")
    NOISE_PSK = os.environ.get("TV_REMOTE_NOISE_PSK", "")
else:
    HOST = BOARD_IP


async def main():
    client = APIClient(HOST, 6053, None, noise_psk=NOISE_PSK)
    await client.connect(login=True)
    info = await client.device_info_and_list_entities()
    entities = info[1] if isinstance(info, tuple) else info.entities
    rows = []
    for ent in entities:
        attrs = []
        for attr in ("name", "object_id", "key", "unique_id", "type"):
            val = getattr(ent, attr, None)
            if val:
                attrs.append(f"{attr}={val}")
        rows.append(f"{type(ent).__name__:<20} {' '.join(attrs)}")
    print(f"共 {len(rows)} 个实体：")
    for r in sorted(rows):
        print("  " + r)
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
    sys.exit(0)
