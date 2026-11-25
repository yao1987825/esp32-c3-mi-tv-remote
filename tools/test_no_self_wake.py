#!/usr/bin/env python3
"""回归测试：电视待机时**不能自己醒**（v1.0.1 修的 bug）。

v1.0.0 的问题：常态广播里就带着 `0xFE`（电视自己的地址），电视每收到
一帧都被点名，于是**没人按遥控器它也会自己开机**。

这个脚本：
    1. 用克隆板把电视打到待机
    2. **什么都不按**，只是盯着电视看 N 分钟
    3. 期间任何一次「电视自己醒了」都算失败
    4. 最后再按一次电源，验证「主动按」仍然能唤醒（对照组）

用法:
    python tools/test_no_self_wake.py --minutes 5
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import threading
import time

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

import serial  # noqa: E402

PORT = "COM6"
REMOTE = r"D:\esp32-c3开发版\tools\tv_remote.py"
TV_ADB = "192.168.6.209:5555"

INTEREST = re.compile(
    r"onConnect|onDisconnect|startWakeAdvert|pressSpecial|button press|"
    r"powerAdvertStop|advert\["
)

stop = threading.Event()
events: list[tuple[float, str]] = []
t0 = time.time()


def reader() -> None:
    try:
        with serial.Serial(PORT, 115200, timeout=0.3) as ser:
            ser.reset_input_buffer()
            while not stop.is_set():
                chunk = ser.read(4096)
                if not chunk:
                    continue
                for raw in chunk.decode("utf-8", "replace").splitlines():
                    line = re.sub(r"\x1b\[[0-9;]*m", "", raw).strip()
                    if line and INTEREST.search(line):
                        events.append((time.time() - t0, line))
    except Exception as err:  # noqa: BLE001
        events.append((time.time() - t0, f"[serial error] {err}"))


def adb_exec(*args: str, timeout: int = 15) -> str:
    for cmd in (["adb", "disconnect", TV_ADB], ["adb", "connect", TV_ADB]):
        try:
            subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=8)
        except Exception:  # noqa: BLE001
            pass
    try:
        r = subprocess.run(["adb", "-s", TV_ADB, *args], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=timeout)
        return (r.stdout or "") + (r.stderr or "")
    except Exception as err:  # noqa: BLE001
        return f"(异常 {err})"


def adb_alive() -> bool:
    return "alive" in adb_exec("shell", "echo alive")


def power_state() -> str:
    out = adb_exec("shell", "dumpsys power | grep -E 'mWakefulness|mScreenOn'")
    return " | ".join(x.strip() for x in out.splitlines() if x.strip()) or "(无输出)"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--minutes", type=float, default=5.0)
    p.add_argument("--skip-control", action="store_true",
                   help="观察完就结束，不再按电源键做对照组")
    args = p.parse_args()
    watch = args.minutes * 60

    threading.Thread(target=reader, daemon=True).start()
    time.sleep(2)

    # --- 1. 电视现在是不是醒的 ---
    if not adb_alive():
        print(">>> 电视已经在待机，直接进入观察", flush=True)
    else:
        print(">>> 按电源让电视进待机", flush=True)
        subprocess.run([sys.executable, REMOTE, "Power"], capture_output=True)
        end = time.time() + 60
        while time.time() < end:
            if not adb_alive():
                break
            time.sleep(2)
        print(f">>> [{time.time() - t0:6.1f}s] 电视已进待机", flush=True)

    # 等板子处理完 onDisconnect
    time.sleep(12)

    # --- 2. 什么都不按，只盯着 ---
    print(f"\n>>> 观察 {args.minutes:.0f} 分钟，期间**不按任何键** ...", flush=True)
    print(">>> 如果电视自己亮了，就是回归失败。\n", flush=True)
    woke_by_itself = False
    end = time.time() + watch
    tick = 0
    while time.time() < end:
        tick += 1
        alive = adb_alive()
        if alive:
            woke_by_itself = True
            print(f">>> [{time.time() - t0:6.1f}s] ❌ 电视自己醒了！[{power_state()}]", flush=True)
            break
        if tick % 5 == 0:
            left = int(end - time.time())
            print(f">>> [{time.time() - t0:6.1f}s] 电视仍在待机（还剩 {left}s）", flush=True)
        time.sleep(10)

    # --- 3. 对照组：主动按一下，应该能唤醒 ---
    if args.skip_control:
        print(f"\n>>> 观察结束（--skip-control，不做对照组）", flush=True)
        stop.set()
        time.sleep(1)
        print("\n================= 板子事件时间线 =================")
        for ts, line in events:
            print(f"[{ts:6.1f}s] {line}")
        print("\n================= 结论 =================")
        if woke_by_itself:
            print("❌ 电视会自己醒 —— 常态广播里还有 0xFE，修复没生效。")
            return 1
        print(f"✅ 待机 {args.minutes:.0f} 分钟，电视没有自己醒。")
        return 0

    print(f"\n>>> 对照组：主动按电源键（期望唤醒）", flush=True)
    subprocess.run([sys.executable, REMOTE, "Power"], capture_output=True)
    end = time.time() + 120
    woke = False
    while time.time() < end:
        if adb_alive():
            woke = True
            print(f">>> [{time.time() - t0:6.1f}s] 电视被唤醒  [{power_state()}]", flush=True)
            break
        time.sleep(3)

    stop.set()
    time.sleep(1)
    print("\n================= 板子事件时间线 =================")
    for ts, line in events:
        print(f"[{ts:6.1f}s] {line}")

    print("\n================= 结论 =================")
    if woke_by_itself:
        print("❌ 电视会自己醒 —— 常态广播里还有 0xFE，修复没生效。")
        return 1
    if not woke:
        print("❌ 待机时不会自己醒了（好），但主动按键也没唤醒（坏）。")
        return 1
    print("✅ 待机时不会自己醒，按键仍然能唤醒 —— 修复生效。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
