#!/usr/bin/env python3
"""全面测试所有遥控器按键 —— 抓 DEBUG 串口日志 + 连接状态。

玩法：
  1. 开串口抓日志（DEBUG 级别固件）
  2. 按顺序触发所有按键，每个之间抓日志
  3. 检测到断开就尝试 reconnect
  4. 生成报告：每个按键是否发出 HID 报告、连接是否保持

用法:
    python tools/test_all_keys.py
"""
from __future__ import annotations

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
STATUS = r"D:\esp32-c3开发版\tools\board_status.py"

# 所有 24 个按键（跳过 Power 避免误关机，单独最后处理）
KEYS = [
    "Volume Up", "Volume Down",
    "Up", "Down", "Left", "Right",
    "Enter", "Back", "Android TV",
    "MI HOME", "Select", "Voice",
    "Movie", "Green", "Blue", "Email", "Calculator", "Files",
    "Voice2", "Forward", "Stop", "Refresh", "Bookmarks",
]

stop = threading.Event()
t0 = time.time()
all_lines: list[tuple[float, str]] = []
markers: list[tuple[float, str]] = []


def reader() -> None:
    try:
        with serial.Serial(PORT, 115200, timeout=0.3) as ser:
            ser.reset_input_buffer()
            while not stop.is_set():
                chunk = ser.read(4096)
                if chunk:
                    for raw in chunk.decode("utf-8", "replace").splitlines():
                        if raw.strip():
                            all_lines.append((time.time(), raw.strip()))
                else:
                    time.sleep(0.05)
    except Exception as err:  # noqa: BLE001
        print(f"串口错误: {err}", flush=True)


def connected() -> bool:
    r = subprocess.run([sys.executable, STATUS], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=30)
    return "= True" in r.stdout


def marker(name: str) -> None:
    t = time.time()
    markers.append((t, name))
    print(f"[{t - t0:6.1f}] === {name} ===", flush=True)


def press(entity: str) -> None:
    subprocess.run([sys.executable, REMOTE, entity], timeout=20, capture_output=True)


def main() -> int:
    th = threading.Thread(target=reader, daemon=True)
    th.start()
    time.sleep(1.5)

    print(">>> 检查连接状态...", flush=True)
    if not connected():
        print(">>> 未连接，触发 reconnect", flush=True)
        press("--reconnect")
        time.sleep(5)
    print(f">>> 连接状态: {connected()}", flush=True)

    marker("开始批量按键")
    for i, key in enumerate(KEYS):
        marker(f"[{i+1}/{len(KEYS)}] {key}")
        before = len(all_lines)
        press(key)
        time.sleep(0.6)
        # 抓这次按键产生的日志
        new_lines = [l for _, l in all_lines[before:]]
        report = [l for l in new_lines if any(k in l for k in
                  ("is_connected", "sendReport", "notify", "press", "connect",
                   "Connect", "reconnect", "key=", "special"))]
        if report:
            for l in report[-4:]:
                print(f"     {l[-150:]}", flush=True)
        else:
            print("     (无相关日志)", flush=True)

    marker("批量按键完成")
    time.sleep(1)
    print(f">>> 最终连接状态: {connected()}", flush=True)

    stop.set()
    th.join(timeout=3)

    out = r"C:\Users\Administrator\AppData\Local\Temp\all_keys.log"
    with open(out, "w", encoding="utf-8") as fh:
        for t, line in all_lines:
            fh.write(f"[{t - t0:6.1f}] {line}\n")
    print(f"\n>>> 完整日志: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
