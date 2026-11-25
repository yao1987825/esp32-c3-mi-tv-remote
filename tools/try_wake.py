#!/usr/bin/env python3
"""依次尝试各种唤醒方式，用 ping 判断电视有没有真的醒来。

电视在待机时 ICMP 不通；一旦被唤醒，192.168.6.209 会重新应答。
"""
import subprocess
import sys
import time

REM = r"D:\esp32-c3开发版\tools\tv_remote.py"
TV = "192.168.6.209"


def ping_ok(timeout_ms=1000):
    out = subprocess.run(
        ["ping", "-n", "1", "-w", str(timeout_ms), TV],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stdout
    return "Reply from 192.168.6.209" in out


def wait_wake(seconds=25):
    """等电视醒来，每秒 ping 一次。"""
    deadline = time.time() + seconds
    while time.time() < deadline:
        if ping_ok():
            return True
        time.sleep(1.0)
    return False


def main():
    methods = sys.argv[1:] or ["--wake-advert", "--wake-directed", "--wake"]
    for m in methods:
        print(f"\n=== 尝试 {m} ===", flush=True)
        subprocess.run([sys.executable, REM, m])
        woke = wait_wake(25)
        print(f"    -> {'电视已唤醒 ✅' if woke else '电视仍在待机 ❌'}", flush=True)
        if woke:
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
