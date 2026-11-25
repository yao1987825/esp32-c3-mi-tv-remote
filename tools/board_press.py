#!/usr/bin/env python3
"""通过 ESPHome 原生 API 按板子上的按键，并持续报告 BLE 连接状态。

比走 web_server 的 digest 认证稳，也比抓串口方便。

用法:
    python tools/board_press.py                 # 按音量+
    python tools/board_press.py "Volume Down"
    python tools/board_press.py --hold Power 2  # 长按 2 秒
    python tools/board_press.py --watch 60      # 只监控连接状态 60 秒
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

# 固件里暴露出来的按键实体名（和 tv-remote.yaml 的 `buttons:` 白名单一致）
KEYS = [
    "ble-mi-remote-Enter", "ble-mi-remote-Up", "ble-mi-remote-Down",
    "ble-mi-remote-Left", "ble-mi-remote-Right", "ble-mi-remote-Power",
    "ble-mi-remote-Back", "ble-mi-remote-Volume Up",
    "ble-mi-remote-Volume Down",
]

# 别名 -> 实体名
ALIAS = {
    "power": "ble-mi-remote-Power",
    "volume up": "ble-mi-remote-Volume Up",
    "volume down": "ble-mi-remote-Volume Down",
    "home": "ble-mi-remote-Android TV",
    "mi home": "ble-mi-remote-MI HOME",
    "up": "ble-mi-remote-Up", "down": "ble-mi-remote-Down",
    "left": "ble-mi-remote-Left", "right": "ble-mi-remote-Right",
    "enter": "ble-mi-remote-Enter", "back": "ble-mi-remote-Back",
}


def resolve(name: str) -> str:
    low = name.lower()
    if low in ALIAS:
        return ALIAS[low]
    for k in KEYS:
        if k.lower() == low or k.lower().endswith("-" + low):
            return k
    raise SystemExit(f"未知按键 '{name}'")


async def main() -> int:
    args = sys.argv[1:]
    hold = False
    watch_only = False
    hold_secs = 2.0
    if args and args[0] == "--hold":
        hold = True
        args = args[1:]
        hold_secs = float(args[0]) if args else 2.0
        args = args[1:]
    if args and args[0] == "--watch":
        watch_only = True
        watch_secs = float(args[1]) if len(args) > 1 else 60.0
        args = args[2:]

    client = APIClient(HOST, PORT, password=None, noise_psk=KEY)
    await client.connect(login=True)
    try:
        states: dict[int, object] = {}
        names: dict[int, str] = {}

        def on_state(ev) -> None:
            states[ev.key] = ev.state
            label = names.get(ev.key, f"key={ev.key}")
            print(f"  [状态变化] {label} = {ev.state}", flush=True)

        client.subscribe_states(on_state)
        await asyncio.sleep(1.5)

        if watch_only:
            end = asyncio.get_event_loop().time() + watch_secs
            while asyncio.get_event_loop().time() < end:
                await asyncio.sleep(1)
            return 0

        name = resolve(args[0] if args else "volume up")
        print(f"按 [{name}]" + ("（长按）" if hold else ""))
        await client.execute_service(
            client.entity_services[0][0] if False else None
        ) if False else None

        # 找到 button 的 service
        svc = await client.list_entities_services()
        buttons = {}
        for item in svc:
            for ent in getattr(item, "entities", []):
                names[ent.key] = ent.name
        for svc_key, svc_obj in svc[1].items() if isinstance(svc[1], dict) else []:
            pass

        # 逐个 services 里找 button 的 press
        pressed = False
        for group in svc:
            for ent in getattr(group, "entities", []):
                if getattr(ent, "name", "") == name and getattr(ent, "key", None):
                    # 从 services 字典里找这个 key
                    for svc_list in svc[1:]:
                        for s in svc_list:
                            for service in getattr(s, "services", []):
                                if service.key == ent.key and service.name == "Press":
                                    await client.execute_service(svc_list, service)
                                    pressed = True
        if not pressed:
            # 兜底：用 entity key 直接构造
            print("没找到 press service，尝试按 key 直接调用")
            ent_key = next((k for k, v in names.items() if v == name), None)
            print(f"  entity key = {ent_key}")
            return 1

        if hold:
            await asyncio.sleep(hold_secs)

        await asyncio.sleep(2)
        for k, v in states.items():
            if names.get(k, "").lower() == "connected":
                print(f"★ BLE 连接状态 = {v}")
        return 0
    finally:
        await client.disconnect()


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except APIConnectionError as err:
        print(f"连接板子失败: {err}")
        sys.exit(1)
