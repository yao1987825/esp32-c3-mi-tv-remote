#!/usr/bin/env python3
"""端到端测试：用板子把电视关掉，再试各种唤醒方式。

关机走板子的 HID 电源键（和真遥控器一样）；
唤醒依次尝试 4 种方式，每次用 ping 判断电视是不是真的醒了。
"""
import subprocess
import sys
import time

PY = r"C:\Users\Administrator\AppData\Local\esphome\Cache\idf\penvs\5.5.6\Scripts\python.EXE"
CAP = r"D:\esp32-c3开发版\tools\capture_boot.py"
REM = r"D:\esp32-c3开发版\tools\tv_remote.py"
TV = "192.168.6.209"

lines = []
marks = []


def reader():
    proc = subprocess.Popen(
        [PY, CAP, "COM6", "150", "--no-reset"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", bufsize=1,
    )
    for raw in proc.stdout:
        lines.append((time.time(), raw.rstrip("\n")))
    proc.wait()


def remote(*args):
    subprocess.run([sys.executable, REM] + list(args))


def ping_ok(timeout_ms=800):
    out = subprocess.run(
        ["ping", "-n", "1", "-w", str(timeout_ms), TV],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stdout
    return f"Reply from {TV}" in out


def wait_wake(seconds=30):
    deadline = time.time() + seconds
    while time.time() < deadline:
        if ping_ok():
            return True
        time.sleep(1.0)
    return False


def tv_is_up():
    """电视是否完全断电（连不上 ping 且 adb 离线）。"""
    out = subprocess.run(["adb", "-s", f"{TV}:5555", "shell", "echo up"],
                         capture_output=True, text=True,
                         encoding="utf-8", errors="replace", timeout=20)
    return "up" in out.stdout


def main():
    t = __import__("threading").Thread(target=reader, daemon=True)
    t.start()
    time.sleep(3)

    print("=== 1. 让电视处于关机状态 ===", flush=True)
    if ping_ok():
        print("    电视还开着 -> 用板子的 HID 电源键关机", flush=True)
        remote("Power")
        time.sleep(12)
    else:
        print("    电视已经是关机状态（跳过关机步骤）", flush=True)
    up = ping_ok()
    print(f"    电视还能 ping 通: {up}（False = 已关机）", flush=True)
    if up:
        print("    电视没关掉，测试中止", flush=True)
        return 1

    for method, label in [
        ("--wake", "反向连接（板子当 central 连电视，保持 15 秒）"),
        ("--wake-long", "反向连接（保持 45 秒）"),
        ("--wake-advert", "唤醒广播（经典 MiPower 包，非定向）"),
        ("--wake-named", "唤醒广播（带设备名）"),
        ("--wake-directed", "唤醒广播（定向发给已绑定的电视）"),
    ]:
        print(f"\n=== 2. 尝试 {method} —— {label} ===", flush=True)
        marks.append((f"{method} @ {time.strftime('%H:%M:%S')}", time.time()))
        remote(method)
        woke = wait_wake(30)
        print(f"    -> {'电视已唤醒 ✅' if woke else '仍然没醒 ❌'}", flush=True)
        if woke:
            break

    time.sleep(3)
    t.join(timeout=180)
    print("\n================ 板子串口日志 ================")
    t0 = lines[0][0] if lines else 0
    for ts, line in lines:
        print(f"[{ts - t0:6.1f}] {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
