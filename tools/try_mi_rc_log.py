#!/usr/bin/env python3
"""触发 mi_rc 唤醒，同时抓板子日志（验证实际发出的字节 + 电视是否连回来）。"""
import subprocess
import sys
import threading
import time

PY = r"C:\Users\Administrator\AppData\Local\esphome\Cache\idf\penvs\5.5.6\Scripts\python.EXE"
CAP = r"D:\esp32-c3开发版\tools\capture_boot.py"
REM = r"D:\esp32-c3开发版\tools\tv_remote.py"
TV = "192.168.6.209"

lines = []


def reader():
    proc = subprocess.Popen(
        [PY, CAP, "COM6", "95", "--no-reset"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", bufsize=1,
    )
    for raw in proc.stdout:
        lines.append((time.time(), raw.rstrip("\n")))
    proc.wait()


def ping_ok():
    out = subprocess.run(["ping", "-n", "1", "-w", "800", TV],
                         capture_output=True, text=True,
                         encoding="utf-8", errors="replace").stdout
    return f"Reply from {TV}" in out


def main():
    method = sys.argv[1] if len(sys.argv) > 1 else "--wake-mi-rc"
    t = threading.Thread(target=reader, daemon=True)
    t.start()
    time.sleep(3)
    print(f"电视当前可达: {ping_ok()}（False=关着）", flush=True)
    print(f"触发 {method}", flush=True)
    subprocess.run([sys.executable, REM, method])
    woke = False
    deadline = time.time() + 75
    while time.time() < deadline:
        if ping_ok():
            woke = True
            print("*** 电视开机了 ✅ ***", flush=True)
            break
        time.sleep(1.5)
    if not woke:
        print("*** 电视没醒 ❌ ***", flush=True)
    t.join(timeout=120)
    print("\n================ 板子日志（关键行） ================")
    for ts, line in lines:
        s = line.strip()
        if any(k in s for k in ("mi_rc wake packet", "powerAdvertStart:", "onConnect",
                                "wake mode", "powerAdvertStop", "startPlainAdvertising",
                                "Disconnected")):
            print(s)
    return 0 if woke else 1


if __name__ == "__main__":
    sys.exit(main())
