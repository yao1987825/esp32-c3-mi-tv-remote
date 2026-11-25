#!/usr/bin/env python3
"""验证「待机时只有电源键能唤醒电视」（v1.2.1）。

序列：
  1. 按电源键      → 电视应该进待机（5555 端口关掉）
  2. 按方向键      → 电视应该**毫无反应**（5555 端口仍然关着）
  3. 按音量键      → 电视应该**毫无反应**
  4. 按电源键      → 电视应该重新开机（5555 端口重新打开）

用法:
    python tools/verify_wake_only_power.py
"""
from __future__ import annotations

import json
import os
import socket
import sys
import time
import urllib.request

HA = os.environ.get("TV_REMOTE_HA_HOST", "192.168.6.135:8123")
TV_ADDR = ("192.168.6.209", 5555)


def _token() -> str:
    """HA 长期访问令牌：环境变量优先，其次 tools/credentials.py。"""
    tok = os.environ.get("TV_REMOTE_HA_TOKEN", "")
    if tok:
        return tok
    try:
        from credentials import HA_TOKEN
        return HA_TOKEN
    except ImportError:
        return ""


TOKEN = _token()


def tv_awake() -> bool:
    """5555 端口开着 = 电视醒着（ADB 通道）。"""
    s = socket.socket()
    s.settimeout(2.0)
    try:
        s.connect(TV_ADDR)
        return True
    except OSError:
        return False
    finally:
        s.close()


def press(entity_id: str) -> None:
    req = urllib.request.Request(
        f"http://{HA}/api/services/button/press",
        method="POST",
        data=json.dumps({"entity_id": entity_id}).encode(),
        headers={"Authorization": f"Bearer {TOKEN}",
                 "Content-Type": "application/json"},
    )
    urllib.request.urlopen(req, timeout=30).read()
    print(f"    按下 {entity_id}")


def wait_state(want_awake: bool, timeout: float = 45.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if tv_awake() == want_awake:
            return True
        time.sleep(1.0)
    return False


def step(title: str, entity: str, want_awake: bool, timeout: float = 45.0) -> bool:
    print(f"\n[{title}]")
    press(entity)
    ok = wait_state(want_awake, timeout)
    state = "开机" if tv_awake() else "待机"
    expect = "开机" if want_awake else "待机"
    print(f"    → 电视现在是「{state}」（期望「{expect}」）"
          f"  {'✅' if ok else '❌ 不符合预期'}")
    return ok


def main() -> int:
    print(f"初始状态：电视{'开机' if tv_awake() else '待机'}")

    results = []
    results.append(("电源键 → 电视进待机",
                    step("1/4 亮屏时按电源键", "button.mi_tv_remote_power", False)))
    results.append(("方向键在待机时无效",
                    step("2/4 待机时按「上」", "button.mi_tv_remote_up", False, 20)))
    results.append(("音量键在待机时无效",
                    step("3/4 待机时按「音量+」", "button.mi_tv_remote_volume_up", False, 20)))
    results.append(("电源键 → 电视重新开机",
                    step("4/4 待机时按电源键", "button.mi_tv_remote_power", True, 60)))

    print("\n" + "=" * 56)
    for name, ok in results:
        print(f"  {'✅' if ok else '❌'} {name}")
    all_ok = all(ok for _, ok in results)
    print("=" * 56)
    print("✅ 全部通过" if all_ok else "⚠ 有不符合预期的项")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
