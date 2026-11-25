#!/usr/bin/env python3
"""唤醒后守候：观察电视醒来之后会不会又自己睡回去。

会同时做两件事：
  1. 每隔几秒用 `adb connect` + `dumpsys power` 查电视的电源状态
  2. 抓板子串口日志，看这段时间板子有没有发什么 HID 报告

用法:
    python tools/watch_after_wake.py [秒数]
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
TV_ADB = "192.168.6.209:5555"
TOTAL = float(sys.argv[1]) if len(sys.argv) > 1 else 150.0

stop = threading.Event()
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
                    if line and re.search(
                        r"press|release|Send:|onConnect|onDisconnect|wake|queue|power",
                        line,
                        re.I,
                    ):
                        print(f"[{time.time() - t0:6.1f}s] [board] {line}", flush=True)
    except Exception as err:  # noqa: BLE001
        print(f"[{time.time() - t0:6.1f}s] [board] serial error: {err}", flush=True)


def adb_state() -> str:
    # 2026-11-24: 必须先 disconnect。电视从待机唤醒后，adb server 里那条
    # 192.168.6.209:5555 会变成 "offline" 的陈旧条目，此时 `adb connect`
    # 会直接回 "already connected" 而不再真正建连 → 永远读到 "device offline"。
    for cmd in (["adb", "disconnect", TV_ADB], ["adb", "connect", TV_ADB]):
        try:
            subprocess.run(cmd, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=8)
        except Exception:  # noqa: BLE001
            pass
    try:
        r = subprocess.run(
            ["adb", "-s", TV_ADB, "shell",
             "dumpsys power | grep -E 'mWakefulness|mScreenOn'"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
        )
        out = " | ".join(x.strip() for x in (r.stdout or "").splitlines() if x.strip())
        if not out:
            err = (r.stderr or "").strip().replace("\n", " ")
            return f"(无输出 {err})"
        return out
    except Exception as err:  # noqa: BLE001
        return f"(不可达 {err})"


def main() -> int:
    threading.Thread(target=reader, daemon=True).start()
    time.sleep(2)
    deadline = time.time() + TOTAL
    while time.time() < deadline:
        state = adb_state()
        print(f"[{time.time() - t0:6.1f}s] [tv] {state}", flush=True)
        time.sleep(8)
    stop.set()
    time.sleep(1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
