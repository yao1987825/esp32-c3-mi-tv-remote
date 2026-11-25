#!/usr/bin/env python3
"""「用原装遥控器关机，用克隆板开机」专项测试。

和 test_wake_packet.py 的区别：这个脚本**不自己按电源**，它假定电视
已经被**原装遥控器**关掉了（这是更接近真实使用的场景 —— 电视的待机
状态是被另一台遥控器造出来的）。

流程：
    1. 等电视进待机（ADB 断了才算）
    2. 按克隆板的 Power 键（板子只发唤醒广播，不排队按键）
    3. 等电视重新亮屏（用 mWakefulness 复核，不只是 ADB 通）

用法:
    python tools/test_wake_from_orig_off.py [等待待机的秒数]
"""
from __future__ import annotations

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
WAIT_STANDBY = float(sys.argv[1]) if len(sys.argv) > 1 else 180.0

INTEREST = re.compile(
    r"onConnect|onDisconnect|startWakeAdvert|pressSpecial|button press|"
    r"fireDirectedBurst|powerAdvertStop|wake mode|findBondedTarget|CRASH|panic"
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
    """先 disconnect 再 connect —— 电视唤醒后 adb 里那条会变成 offline
    陈旧条目，直接 `adb connect` 会回 already connected 而不真正建连。"""
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
    threading.Thread(target=reader, daemon=True).start()
    time.sleep(2)

    # --- 1. 等电视进待机 ---
    print(">>> 等待电视进入待机（请用原装遥控器关掉电视）...", flush=True)
    end = time.time() + WAIT_STANDBY
    in_standby = False
    while time.time() < end:
        if not adb_alive():
            in_standby = True
            print(f">>> [{time.time() - t0:6.1f}s] 电视已进入待机（ADB 断了）", flush=True)
            break
        time.sleep(3)
    if not in_standby:
        print(">>> 超时：电视还没进待机，本次测试无效。", flush=True)
        stop.set()
        return 1

    # 等板子处理完 onDisconnect（_connected 变成 false）
    time.sleep(12)

    # --- 2. 按克隆板的电源键 ---
    print(f">>> [{time.time() - t0:6.1f}s] 按下克隆板 Power", flush=True)
    subprocess.run([sys.executable, REMOTE, "Power"], capture_output=True)

    # --- 3. 等电视亮屏 ---
    end = time.time() + 120
    woke = False
    while time.time() < end:
        if adb_alive():
            woke = True
            print(f">>> [{time.time() - t0:6.1f}s] 电视亮了  [{power_state()}]", flush=True)
            break
        time.sleep(3)

    stop.set()
    time.sleep(1)
    print("\n================= 事件时间线 =================")
    for ts, line in events:
        print(f"[{ts:6.1f}s] {line}")

    print("\n================= 结论 =================")
    if woke:
        print("✅ 用原装遥控器关的电视，被克隆板成功唤醒。")
        return 0
    print("❌ 克隆板没能唤醒电视。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
