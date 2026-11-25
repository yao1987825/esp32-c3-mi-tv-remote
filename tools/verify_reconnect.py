#!/usr/bin/env python3
"""验证「断联修复」：板子重启后能否自动重连电视（无需重新配对）。

修复内容：onDisconnect 不再删除 bond（之前电视正常休眠断线会触发删 bond，
导致每次都要重新配对）。

验证流程：
  1. 检查当前连接状态
  2. 复位板子（capture_boot 的 RTS/DTR 复位）
  3. 等待 60 秒，每 3 秒查一次 Connected 状态
  4. 报告是否自动重连

用法:
    python tools/verify_reconnect.py
"""
from __future__ import annotations

import subprocess
import sys
import time

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

STATUS = r"D:\esp32-c3开发版\tools\board_status.py"
CAP = r"D:\esp32-c3开发版\tools\capture_boot.py"


def connected() -> bool:
    r = subprocess.run([sys.executable, STATUS], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=40)
    return "= True" in r.stdout


def main() -> int:
    print(">>> 验证断联修复：重启板子后应自动重连（无需配对）", flush=True)
    print(f">>> 重启前连接状态: {connected()}", flush=True)

    print(">>> 复位板子（RTS/DTR）...", flush=True)
    r = subprocess.run([sys.executable, CAP, "COM6", "6"], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=40)
    # 在日志里找 bond 状态
    for line in r.stdout.splitlines():
        if "saved bonds" in line or "bond[" in line or "onConnect" in line:
            print(f"    {line}", flush=True)

    print(">>> 等待自动重连（最多 75 秒）...", flush=True)
    deadline = time.time() + 75
    t0 = time.time()
    last = None
    while time.time() < deadline:
        cur = connected()
        if cur != last:
            print(f"  [{time.time() - t0:5.1f}s] Connected = {cur}", flush=True)
            last = cur
        if cur:
            print("\n>>> ✅ 自动重连成功！断联问题已解决。", flush=True)
            return 0
        time.sleep(3)

    print("\n>>> ❌ 75 秒内没有自动重连，可能还需要手动配对。", flush=True)
    return 2


if __name__ == "__main__":
    sys.exit(main())
