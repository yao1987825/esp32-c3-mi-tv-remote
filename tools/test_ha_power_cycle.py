#!/usr/bin/env python3
"""通过 Home Assistant 按电源键，验证「HA → 板子 → 电视」整条链路。

流程：
    1. HA 里按 `button.mi_tv_remote_power` → 电视应该进待机（ADB 断）
    2. 等板子处理完 onDisconnect
    3. 再按一次 → 板子发唤醒广播 → 电视重新亮屏（mWakefulness=Awake）

用法:
    python tools/test_ha_power_cycle.py --token <TOKEN>
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

import serial  # noqa: E402

PORT = "COM6"
TV_ADB = "192.168.6.209:5555"
HA_ENTITY = "button.mi_tv_remote_power"

INTEREST = re.compile(
    r"onConnect|onDisconnect|startWakeAdvert|pressSpecial|button press|"
    r"fireDirectedBurst|powerAdvertStop|queuePendingCommand"
)

stop = threading.Event()
events: list[tuple[float, str]] = []
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
                    if line and INTEREST.search(line):
                        events.append((time.time() - t0, line))
    except Exception as err:  # noqa: BLE001
        events.append((time.time() - t0, f"[serial error] {err}"))


def ha_press(ha: str, token: str, entity: str) -> str:
    url = f"{ha}/api/services/button/press"
    body = json.dumps({"entity_id": entity}).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        return f"HTTP {resp.status}"
    except urllib.error.HTTPError as err:
        return f"HTTP {err.code}: {err.read().decode('utf-8', 'replace')[:200]}"
    except Exception as err:  # noqa: BLE001
        return f"异常 {err}"


def adb_exec(*args: str, timeout: int = 15) -> str:
    # 必须先 disconnect：电视唤醒后 adb 里那条会变成 offline 陈旧条目，
    # 直接 `adb connect` 会回 already connected 而不真正建连。
    for cmd in (["adb", "disconnect", TV_ADB], ["adb", "connect", TV_ADB]):
        try:
            subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=8)
        except Exception:  # noqa: BLE001
            pass
    try:
        r = subprocess.run(["adb", "-s", TV_ADB, *args], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=timeout)
        return (r.stdout or "") + (r.stderr or "")
    except Exception as err:  # noqa: BLE001
        return f"(异常 {err})"


def adb_alive() -> bool:
    return "alive" in adb_exec("shell", "echo alive")


def power_state() -> str:
    out = adb_exec("shell", "dumpsys power | grep -E 'mWakefulness|mScreenOn'")
    return " | ".join(x.strip() for x in out.splitlines() if x.strip()) or "(无输出)"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--ha", default="http://192.168.6.135:8123")
    p.add_argument("--token", required=True)
    args = p.parse_args()

    threading.Thread(target=reader, daemon=True).start()
    time.sleep(2)

    print(f">>> HA 按 {HA_ENTITY}（第一次）→ 期望电视进待机")
    print(f">>> {ha_press(args.ha, args.token, HA_ENTITY)}", flush=True)

    end = time.time() + 60
    went_standby = False
    while time.time() < end:
        if not adb_alive():
            went_standby = True
            print(f">>> [{time.time() - t0:6.1f}s] 电视已进待机（ADB 断了）", flush=True)
            break
        time.sleep(2)
    if not went_standby:
        print("❌ 电视没进待机，测试无效。")

    # 等板子处理完 onDisconnect
    time.sleep(12)

    print(f">>> [{time.time() - t0:6.1f}s] HA 再按一次 → 期望电视被唤醒")
    print(f">>> {ha_press(args.ha, args.token, HA_ENTITY)}", flush=True)

    end = time.time() + 120
    woke = False
    while time.time() < end:
        if adb_alive():
            woke = True
            print(f">>> [{time.time() - t0:6.1f}s] 电视亮了  [{power_state()}]", flush=True)
            break
        time.sleep(3)

    stop.set()
    time.sleep(1)
    print("\n================= 板子事件时间线 =================")
    for ts, line in events:
        print(f"[{ts:6.1f}s] {line}")

    print("\n================= 结论 =================")
    if went_standby and woke:
        print("✅ HA → 板子 → 电视 全链路通：待机 + 唤醒都成功。")
        return 0
    if not went_standby:
        print("⚠  电视没进待机，这次测试无效。")
    else:
        print("❌ 电视没被唤醒。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
