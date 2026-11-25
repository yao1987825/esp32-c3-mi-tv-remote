#!/usr/bin/env python3
"""用 ESPHome 原生 API 查板子的实时状态（BLE 是否连上电视等）。

比抓串口可靠：串口只能看到「事件」，API 能直接问「现在的状态是什么」。

用法:
    python tools/board_status.py
"""
from __future__ import annotations

import asyncio
import os
import sys

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

from aioesphomeapi import APIClient  # noqa: E402
from aioesphomeapi.core import APIConnectionError  # noqa: E402

HOST = "192.168.6.101"
PORT = 6053

try:
    from credentials import BOARD_IP, NOISE_PSK
except ImportError:  # 没建 credentials.py 就读环境变量
    HOST = os.environ.get("TV_REMOTE_BOARD_IP", HOST)
    NOISE_PSK = os.environ.get("TV_REMOTE_NOISE_PSK", "")
else:
    HOST = BOARD_IP

KEY = NOISE_PSK


async def main() -> int:
    # 2026.11 起 API 用 Noise 加密，密钥就是 yaml 里的 api.encryption.key
    client = APIClient(HOST, PORT, password=None, noise_psk=KEY)
    await client.connect(login=True)
    try:
        info = await client.device_info()
        print(f"设备: {info.name}  固件 {info.esphome_version}")

        # 实体 key(数字) -> 名字
        names: dict[int, str] = {}
        try:
            svc = await client.list_entities_services()
            # 返回 (entities, services) 两个 list
            for group in svc[0] if isinstance(svc, tuple) else svc:
                for ent in getattr(group, "entities", []) or []:
                    names[ent.key] = ent.name
                if hasattr(group, "key") and hasattr(group, "name"):
                    names[group.key] = group.name
        except Exception as err:  # noqa: BLE001
            print(f"(实体列表拿不到: {err})")

        states: dict[int, object] = {}

        def on_state(ev) -> None:
            states[ev.key] = ev.state

        client.subscribe_states(on_state)
        await asyncio.sleep(3)

        print(f"有状态的实体数: {len(states)}")
        print("-" * 64)
        for key in sorted(states, key=lambda k: names.get(k, str(k))):
            label = names.get(key, f"key={key}")
            print(f"  {label:<48} = {states[key]}")
        print("-" * 64)
        for key in sorted(states, key=lambda k: names.get(k, str(k))):
            label = names.get(key, f"key={key}")
            if "connect" in label.lower() or "连接" in label:
                print(f"★ 连接状态 [{label}] = {states[key]}")
        return 0
    finally:
        await client.disconnect()


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except APIConnectionError as err:
        print(f"连接板子失败: {err}")
        sys.exit(1)
