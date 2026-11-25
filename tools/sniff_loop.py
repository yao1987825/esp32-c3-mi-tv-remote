#!/usr/bin/env python3
"""循环嗅探：反复启动板子的 BLE 嗅探器，把空中的广播全部记下来。

用于抓**原装遥控器**在电视待机时发的完整原始包（之前漏掉的
AD type 0x0D / 0xFE 就是这么找到的）。

用法:
    python tools/sniff_loop.py [总秒数] [输出文件]
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
TOTAL = float(sys.argv[1]) if len(sys.argv) > 1 else 300.0
OUT = sys.argv[2] if len(sys.argv) > 2 else r"C:\Users\Administrator\AppData\Local\Temp\sniff_raw.txt"

stop = threading.Event()
all_lines: list[str] = []

# 2026-11-23: 之前是「跑完才一次性写文件」，中途 Ctrl-C / 任务被取消就全丢了
# （实测白白按了一次原装遥控器）。改成边收边写、边收边打关键行。
fh = open(OUT, "w", encoding="utf-8", buffering=1)
KEY = re.compile(r"MI RC|MI Remote|raw=|0xFE|D4:B8|D4:B8:FF|onResult")


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
                    if line:
                        all_lines.append(line)
                        fh.write(line + "\n")
                        fh.flush()
                        if KEY.search(line):
                            print(f"[sniff] {line}", flush=True)
    except Exception as err:  # noqa: BLE001
        all_lines.append(f"[serial error] {err}")
        fh.write(f"[serial error] {err}\n")
        fh.flush()


def main() -> int:
    threading.Thread(target=reader, daemon=True).start()
    time.sleep(2)
    deadline = time.time() + TOTAL
    while time.time() < deadline and not stop.is_set():
        print(f">>> 启动嗅探 ({time.strftime('%H:%M:%S')})", flush=True)
        subprocess.run([sys.executable, REMOTE, "--sniff"], capture_output=True)
        time.sleep(2)
    stop.set()
    time.sleep(1)
    fh.close()
    print(f">>> 日志已写入 {OUT}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
