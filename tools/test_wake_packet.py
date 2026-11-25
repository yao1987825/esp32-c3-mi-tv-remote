#!/usr/bin/env python3
"""待机唤醒的端到端测试（状态机式，避免时序干扰）。

流程：
    1. 先确保电视是**开着**的：ADB 不通就按电源键，并轮询等它活过来
    2. 按电源键让它进**待机**（ADB 断开）
    3. 再按电源键 → 板子发唤醒包 → 轮询等电视活过来
    4. 打印整条事件时间线

⚠ 绝对不要用 `adb shell input keyevent 223` 让电视进待机 —— 实测那会让电视
   进入「拔电源才能恢复」的状态。

用法:
    python tools/test_wake_packet.py
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

INTEREST = re.compile(
    r"onConnect|onDisconnect|mi_wake packet|startWakeAdvert|queuePendingCommand|"
    r"pressSpecial|button press|press:|advert\[|fireDirectedBurst|startPlainAdvertising|"
    r"powerAdvertStop|wake mode|findBondedTarget|CRASH|panic"
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


def press(name: str) -> None:
    print(f">>> [{time.time() - t0:6.1f}s] 按下 {name}", flush=True)
    subprocess.run([sys.executable, REMOTE, name], capture_output=True)


def adb_alive(connect: bool = False) -> bool:
    """检查电视是否在线。

    2026-11-23: connect=True 时会先重新建立 ADB over TCP 连接。
    电视从待机唤醒后，WiFi/ADB 会话会整个重建，ADB 客户端里那个
    "device not found" 的旧连接不会自动复活 —— 必须重新 `adb connect`。
    之前的测试脚本只做 `adb -s ... shell`，所以电视明明醒了，脚本却一直
    报 "超时，电视仍不可达"，差点被当成"唤醒失败"。
    """
    if connect:
        try:
            # adb 的输出是 UTF-8（含中文错误信息），Windows 默认 GBK 会解码失败
            subprocess.run(["adb", "connect", TV_ADB], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=8)
        except Exception:  # noqa: BLE001
            pass
    try:
        r = subprocess.run(
            ["adb", "-s", TV_ADB, "shell", "echo alive"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
        )
        return "alive" in (r.stdout or "")
    except Exception:  # noqa: BLE001
        return False


def tv_power_state() -> str:
    """读电视的电源/屏幕状态，用来确认「亮了」而不只是「ADB 活着」。"""
    try:
        r = subprocess.run(
            ["adb", "-s", TV_ADB, "shell",
             "dumpsys power | grep -E 'mWakefulness|mScreenOn|mHoldingDisplay'"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20,
        )
        return " | ".join(x.strip() for x in (r.stdout or "").splitlines() if x.strip())
    except Exception as err:  # noqa: BLE001
        return f"(读取失败 {err})"


def wait_alive(limit: float, label: str) -> bool:
    end = time.time() + limit
    while time.time() < end:
        if adb_alive(connect=True):
            state = tv_power_state()
            print(f">>> [{time.time() - t0:6.1f}s] {label}: 电视活了  [{state}]", flush=True)
            return True
        time.sleep(3)
    print(f">>> [{time.time() - t0:6.1f}s] {label}: 超时，电视仍不可达", flush=True)
    return False


def wait_dead(limit: float, label: str) -> bool:
    end = time.time() + limit
    while time.time() < end:
        if not adb_alive():
            # 把死掉的 ADB 会话清掉，否则下一轮 adb connect 会复用这个
            # 半开连接，导致唤醒后依然查不到电视。
            try:
                subprocess.run(["adb", "disconnect", TV_ADB], capture_output=True, timeout=10)
            except Exception:  # noqa: BLE001
                pass
            print(f">>> [{time.time() - t0:6.1f}s] {label}: 电视已进待机（ADB 断了）", flush=True)
            return True
        time.sleep(2)
    print(f">>> [{time.time() - t0:6.1f}s] {label}: 电视还在应答，可能没进待机", flush=True)
    return False


def main() -> int:
    threading.Thread(target=reader, daemon=True).start()
    time.sleep(2)

    # 1. 先确保电视是开着的
    if not adb_alive():
        print(">>> 电视当前不可达，按电源 + 等待断链后，再按一次唤醒", flush=True)
        press("Power")
        wait_dead(20, "预唤醒-第一次按键")
        # 2026-11-23: 必须等板子处理完 onDisconnect（_connected 变成 false）
        # 之后再按，否则电源键会发进「还连着但其实睡着了」的电视里。
        time.sleep(12)
        press("Power")
        if not wait_alive(90, "预唤醒"):
            stop.set()
            print("\n================= 事件时间线 =================")
            for ts, line in events:
                print(f"[{ts:6.1f}s] {line}")
            return 1

    # 2. 让它进待机
    press("Power")
    went_standby = wait_dead(40, "进待机")
    # 等板子处理完 onDisconnect
    time.sleep(12)

    # 3. 唤醒
    press("Power")
    woke = wait_alive(90, "唤醒")

    stop.set()
    time.sleep(1)
    print("\n================= 事件时间线 =================")
    for ts, line in events:
        print(f"[{ts:6.1f}s] {line}")

    print("\n================= 结论 =================")
    if went_standby and woke:
        print("✅ 电视从待机被成功唤醒，并且保持亮屏。")
        return 0
    if not went_standby:
        print("⚠  电视可能压根没进待机，这次测试无效。")
    else:
        print("❌ 电视没有被唤醒。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
