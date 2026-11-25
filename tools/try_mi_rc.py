#!/usr/bin/env python3
"""用照抄原装遥控器的唤醒包（mi_rc）尝试开机。

先确认电视是关的，然后触发唤醒广播，观察：
  * 电视有没有被唤醒（ping 通）
  * 电视有没有主动连回板子（板子的 connected 状态）
"""
import asyncio
import os
import subprocess
import sys
import time

from aioesphomeapi import APIClient

try:
    from credentials import BOARD_IP, NOISE_PSK, TV_ADB
except ImportError:  # 没建 credentials.py 就读环境变量
    HOST = os.environ.get("TV_REMOTE_BOARD_IP", "192.168.6.101")
    NOISE_PSK = os.environ.get("TV_REMOTE_NOISE_PSK", "")
    TV = os.environ.get("TV_REMOTE_TV_ADB", "192.168.6.209:5555").split(":")[0]
else:
    HOST = BOARD_IP
    TV = TV_ADB.split(":")[0]

REM = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tv_remote.py")
CONNECTED_KEY = 1629494038


def ping_ok(timeout_ms=800):
    out = subprocess.run(
        ["ping", "-n", "1", "-w", str(timeout_ms), TV],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stdout
    return f"Reply from {TV}" in out


async def main():
    method = sys.argv[1] if len(sys.argv) > 1 else "--wake-mi-rc"

    client = APIClient(HOST, 6053, None, noise_psk=NOISE_PSK)
    await client.connect(login=True)
    states = {}
    client.subscribe_states(lambda e: states.__setitem__(getattr(e, "key", None), e.state))
    await asyncio.sleep(1.5)

    print(f"电视当前可达: {ping_ok()}（False = 关着）", flush=True)
    print(f"触发 {method} ...", flush=True)
    subprocess.run([sys.executable, REM, method])

    woke = False
    connected = False
    deadline = time.time() + 60
    while time.time() < deadline:
        await asyncio.sleep(1.5)
        if states.get(CONNECTED_KEY):
            connected = True
            print("*** 电视已经连回板子了 ***", flush=True)
        if ping_ok():
            woke = True
            print("*** 电视已开机（网络可达）✅ ***", flush=True)
            break

    print(f"结果: 电视开机={woke}  连回板子={connected}", flush=True)
    await client.disconnect()
    return 0 if woke else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
