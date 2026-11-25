#!/usr/bin/env python3
"""电视一连上就立刻连按按键 —— 抓「连接窗口期」内按键是否有效。

背景：
  串口实测 onConnect 在电视点配对后 ~13.5s 发生，连接只维持几秒。
  如果按键能在这几秒内送到电视，就能验证 HID 链路本身是通的
  （哪怕 bond 没建立）。

做法：
  一边读串口，一旦看到 onConnect，立即触发多次按键。
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
DURATION = float(sys.argv[1]) if len(sys.argv) > 1 else 120.0

stop = threading.Event()
t0 = time.time()
connected = threading.Event()


def reader() -> None:
    with serial.Serial(PORT, 115200, timeout=0.3) as ser:
        ser.reset_input_buffer()
        while not stop.is_set():
            chunk = ser.read(4096)
            if chunk:
                for raw in chunk.decode("utf-8", "replace").splitlines():
                    if "onConnect" in raw or "onDisconnect" in raw or "authenticated" in raw:
                        print(f"[{time.time()-t0:6.1f}] {raw.strip()}", flush=True)
                        if "onConnect" in raw:
                            connected.set()
            else:
                time.sleep(0.05)


def press(entity: str) -> None:
    subprocess.run([sys.executable, REMOTE, entity], timeout=20, capture_output=True)


def main() -> int:
    th = threading.Thread(target=reader, daemon=True)
    th.start()
    time.sleep(1)
    print(f">>> 监听 {DURATION:.0f}s，请在电视上点 MI RC / MI Remote 配对", flush=True)
    print(">>> 一旦检测到 onConnect，会立刻连按音量+ 5 次", flush=True)

    end = time.time() + DURATION
    last_press = 0.0
    while time.time() < end:
        if connected.is_set():
            connected.clear()
            print(">>> 检测到连接！立刻按键", flush=True)
            for i in range(5):
                press("Volume Up")
                print(f"    音量+ {i+1}", flush=True)
                time.sleep(0.25)
            last_press = time.time()
        else:
            # 每 15 秒触发一次广播，让电视能连
            if time.time() - last_press > 15:
                subprocess.run([sys.executable, REMOTE, "--reconnect"],
                               timeout=20, capture_output=True)
                last_press = time.time()
        time.sleep(0.5)

    stop.set()
    th.join(timeout=3)
    return 0


if __name__ == "__main__":
    sys.exit(main())
