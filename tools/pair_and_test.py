#!/usr/bin/env python3
"""配对 + 立即验证「板子能不能操控电视」。

流程：
  1. 打开串口监听（不复位）
  2. 触发板子进入「可被发现」广播状态
  3. 等电视那边点配对（脚本会一直等到超时）
  4. 一旦日志里出现 Connected，立刻按一次音量+ / 音量-，
     看串口里有没有按键发出的记录 —— 顺便请你看看电视屏幕上有没有音量 OSD
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

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM6"
WAIT_SECONDS = float(sys.argv[2]) if len(sys.argv) > 2 else 300.0
REMOTE = r"D:\esp32-c3开发版\tools\tv_remote.py"

lines: list[tuple[float, str]] = []
stop = threading.Event()
t0 = time.time()


def log(msg: str) -> None:
    print(f"[{time.time() - t0:6.1f}] {msg}", flush=True)


def reader() -> None:
    import serial

    try:
        with serial.Serial(PORT, 115200, timeout=0.3) as ser:
            ser.reset_input_buffer()
            while not stop.is_set():
                chunk = ser.read(4096)
                if chunk:
                    for raw in chunk.decode("utf-8", "replace").splitlines():
                        if raw.strip():
                            lines.append((time.time(), raw.rstrip()))
                            if any(k in raw for k in ("Connect", "onConnect", "pair", "bond",
                                                     "encrypt", "security", "Disconnected",
                                                     "advert", "reconnect")):
                                log("LOG: " + raw.strip()[:160])
                else:
                    time.sleep(0.05)
    except Exception as err:  # noqa: BLE001
        log(f"串口错误: {err}")


def press(entity: str) -> None:
    log(f"按键: {entity}")
    subprocess.run([sys.executable, REMOTE, entity], timeout=25)


def main() -> int:
    th = threading.Thread(target=reader, daemon=True)
    th.start()
    time.sleep(1.5)

    log("触发板子进入可发现广播（--reconnect）")
    subprocess.run([sys.executable, REMOTE, "--reconnect"], timeout=25)

    log("请在电视上点「MI Remote」配对，等待中……")
    deadline = time.time() + WAIT_SECONDS
    connected = False
    while time.time() < deadline:
        if any("onConnect" in l or "Connected" in l for _, l in lines):
            if not any("Disconnected" in l for _, l in lines[-6:]):
                connected = True
                break
        time.sleep(1.0)

    if not connected:
        log("超时：没等到连接。")
        stop.set()
        th.join(timeout=3)
        print("\n--- 串口日志尾部 ---")
        for ts, line in lines[-40:]:
            print(f"  [{ts - t0:6.1f}] {line}")
        return 2

    log("连上了！✅ 现在按音量+/- 测试，请看电视屏幕有没有音量 OSD")
    time.sleep(1)
    press("Volume Up")
    time.sleep(2)
    press("Volume Down")
    time.sleep(2)
    press("Home" if False else "Android TV")
    time.sleep(2)

    stop.set()
    th.join(timeout=3)
    print("\n--- 串口日志尾部 ---")
    for ts, line in lines[-60:]:
        print(f"  [{ts - t0:6.1f}] {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
