#!/usr/bin/env python3
"""一边开串口，一边持续触发板子动作，全程记录 BLE 事件。

用途：抓「电视连上来之后到底发生了什么」——onConnect / startSecurity /
配对结果 / onDisconnect 的 reason。串口如果开晚了就会错过这些事件，
所以这个脚本先开串口再动作。

用法:
    python tools/watch_ble.py 120            # 监听 120 秒，每 20 秒点一次 reconnect
    python tools/watch_ble.py 120 --press    # 顺便按音量+
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
DO_PRESS = "--press" in sys.argv

stop = threading.Event()
t0 = time.time()
events: list[str] = []


def reader() -> None:
    try:
        with serial.Serial(PORT, 115200, timeout=0.3) as ser:
            ser.reset_input_buffer()
            while not stop.is_set():
                chunk = ser.read(4096)
                if chunk:
                    for raw in chunk.decode("utf-8", "replace").splitlines():
                        if not raw.strip():
                            continue
                        line = raw.strip()
                        events.append(f"[{time.time() - t0:6.1f}] {line}")
                        low = line.lower()
                        if any(k in low for k in (
                            "connect", "bond", "security", "pair", "encrypt",
                            "advert", "disconnect", "ble_mi_remote", "mtu",
                            "error", "fail", "warn", "nimble"
                        )):
                            print(f"[{time.time() - t0:6.1f}] {line}", flush=True)
                else:
                    time.sleep(0.05)
    except Exception as err:  # noqa: BLE001
        print(f"串口错误: {err}", flush=True)


def press(entity: str) -> None:
    subprocess.run([sys.executable, REMOTE, entity], timeout=25,
                   capture_output=True)


def main() -> int:
    th = threading.Thread(target=reader, daemon=True)
    th.start()
    time.sleep(1.5)
    print(f">>> 串口已打开，开始监听 {DURATION:.0f} 秒", flush=True)

    print(">>> 触发 --reconnect（让板子进入可发现广播）", flush=True)
    subprocess.run([sys.executable, REMOTE, "--reconnect"], timeout=25,
                   capture_output=True)

    end = time.time() + DURATION
    tick = 0
    while time.time() < end:
        time.sleep(15)
        tick += 1
        print(f">>> [{time.time() - t0:.0f}s] 再触发一次 reconnect", flush=True)
        subprocess.run([sys.executable, REMOTE, "--reconnect"], timeout=25,
                       capture_output=True)
        if DO_PRESS:
            print(">>> 按音量+", flush=True)
            press("Volume Up")

    stop.set()
    th.join(timeout=3)

    out = r"C:\Users\Administrator\AppData\Local\Temp\watch_ble.log"
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(events))
    print(f"\n>>> 完整串口日志: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
