#!/usr/bin/env python3
"""复位 ESP32-C3 并抓取完整启动日志。

板子用原生 USB (USB Serial/JTAG)，复位靠 RTS/DTR 组合，不是老式的
DTR/RTS 对调 —— 这里用 esptool 同样的时序：
    DTR=0, RTS=1  → 复位
    DTR=1, RTS=0  → 正常启动

复位后 USB 会重新枚举，所以要关掉再打开串口才能读到启动日志。

用法:
    python tools/capture_boot.py [COM口] [秒数]
    python tools/capture_boot.py COM6 25
"""
from __future__ import annotations

import sys
import time

import serial


def reset_port(port: str) -> None:
    """用 USB-Serial/JTAG 的时序复位板子。"""
    with serial.Serial(port, 115200, timeout=0.2) as ser:
        ser.dtr = False
        ser.rts = True
        time.sleep(0.15)
        ser.dtr = True
        ser.rts = False


def open_when_ready(port: str, timeout: float = 20.0) -> serial.Serial:
    """复位后 USB 会重新枚举，COM 口会短暂消失 —— 轮询等它回来。"""
    deadline = time.time() + timeout
    last: Exception | None = None
    while time.time() < deadline:
        try:
            return serial.Serial(port, 115200, timeout=0.3)
        except Exception as err:  # noqa: BLE001
            last = err
            time.sleep(0.1)
    raise RuntimeError(f"串口 {port} 一直没回来: {last}")


def capture(port: str, seconds: float) -> None:
    deadline = time.time() + seconds
    buf = bytearray()
    with open_when_ready(port) as ser:
        ser.reset_input_buffer()
        while time.time() < deadline:
            chunk = ser.read(4096)
            if chunk:
                buf.extend(chunk)
            else:
                time.sleep(0.05)
    sys.stdout.write(buf.decode("utf-8", "replace"))


def main() -> int:
    port = sys.argv[1] if len(sys.argv) > 1 else "COM6"
    seconds = float(sys.argv[2]) if len(sys.argv) > 2 else 25.0
    no_reset = "--no-reset" in sys.argv
    if no_reset:
        print(f"# 监听 {port} {seconds:.0f} 秒（不复位）", flush=True)
    else:
        print(f"# 复位 {port} 并抓 {seconds:.0f} 秒日志", flush=True)
        reset_port(port)
    capture(port, seconds)
    return 0


if __name__ == "__main__":
    sys.exit(main())
