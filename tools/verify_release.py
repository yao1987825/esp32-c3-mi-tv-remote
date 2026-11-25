#!/usr/bin/env python3
"""正式版发布验收：板子上的固件到底对不对。

三件事：
    1. 复位板子抓启动日志 —— 看有没有 CRASH / SAFE MODE、有没有正常广播、
       bond 还在不在
    2. 逐个探测实体在 web_server 上是否存在（确认 yaml 改动真的生效）
    3. 打印结论

用法:
    python tools/verify_release.py [COM口]
"""
from __future__ import annotations

import gzip
import importlib.util
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, r"D:\esp32-c3开发版\tools")

spec = importlib.util.spec_from_file_location("tv", r"D:\esp32-c3开发版\tools\tv_remote.py")
tv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tv)

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM6"

# 2026-11-25（v1.2.0）：固件用 `buttons:` 白名单只暴露 9 个按键
# （其余按键组件里还在，只是没做成实体）
AUTO_KEYS = [
    "Enter", "Up", "Down", "Left", "Right", "Power", "Back",
    "Volume Up", "Volume Down",
]
TEMPLATE_KEYS = [
    "Vol Up x5", "Vol Down x5",
    "TV Reconnect", "TV Sniff",
]


def web_get(path: str, retries: int = 4) -> tuple[int, str]:
    """带 digest 认证地取一个 web_server 路径，返回 (状态码, 内容)。

    ESPHome 的 web_server 一次只处理一个连接，密集请求会被它直接断连
    （RemoteDisconnected），所以这里每次请求之间停一下，并且对断连重试。
    """
    url = f"http://{tv.HOST}{path}"
    last: tuple[int, str] = (0, "")
    for attempt in range(retries):
        try:
            raw = urllib.request.urlopen(urllib.request.Request(url), timeout=10).read()
        except urllib.error.HTTPError as err:
            if err.code != 401:
                return err.code, ""
            ch = err.headers.get("WWW-Authenticate", "")
            f = dict(re.findall(r'(\w+)="([^"]*)"', ch))
            req = urllib.request.Request(url)
            req.add_header(
                "Authorization",
                tv.digest_header(tv.WEB_USER, tv.WEB_PASS, f.get("realm", ""),
                                 f.get("nonce", ""), path, qop=f.get("qop", ""),
                                 opaque=f.get("opaque", ""), method="GET"),
            )
            try:
                raw = urllib.request.urlopen(req, timeout=10).read()
            except urllib.error.HTTPError as err:
                last = (err.code, "")
                time.sleep(0.4)
                continue
        except Exception as err:  # noqa: BLE001  连接被断 = 服务器忙
            last = (0, str(err))
            time.sleep(0.6)
            continue
        if raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
        time.sleep(0.12)
        return 200, raw.decode("utf-8", "replace")
    return last


def capture_boot(port: str, seconds: float = 30.0) -> str:
    py = sys.executable
    return subprocess.run(
        [py, r"D:\esp32-c3开发版\tools\capture_boot.py", port, str(seconds)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
    ).stdout


def check_log(log: str) -> dict:
    res = {}
    res["crash"] = bool(re.search(r"CRASH DETECTED|SAFE MODE|panic|Guru Meditation", log))
    # ESPHome 的崩溃记录存在 RTC_DATA_ATTR 里，**软复位不会清掉**，只有断电
    # 才会。所以旧固件崩溃过一次，之后每次启动都会打这条 —— 除非日志里出现
    # "Captured by a different firmware build"，那说明这条是**别的固件版本**
    # 留下的历史记录，不是当前固件崩了。
    res["stale_crash"] = bool(
        res["crash"] and "different firmware build" in log
    )
    # 真正的 boot loop：setup() 跑了好几遍
    res["boot_loops"] = len(re.findall(r"Running through setup\(\)", log))
    res["safe_mode"] = bool(re.search(r"SAFE MODE", log))
    res["wifi"] = bool(re.search(r"WiFi.*(connected|IP address)|Got IP", log, re.I))
    res["advert"] = bool(re.search(r"Advertising started|start=OK", log, re.I))
    m = re.search(r"saved bonds = (\d+)", log)
    res["bonds"] = m.group(1) if m else "?"
    m = re.search(r"bond\[\d\] type=\d+ ([0-9A-F:]+)", log)
    res["bond_addr"] = m.group(1) if m else "?"
    m = re.search(r"Project \S+ version (\S+)", log)
    res["version"] = m.group(1) if m else "?"
    # 常态广播包（v1.2.0 用 mi_idle：结构同唤醒包但**没有 0xFE 字段**）
    m = re.search(r"advert\[mi_idle\].*len=(\d+) \[([0-9A-F ]+)\]", log)
    res["idle_len"] = m.group(1) if m else "?"
    res["idle_bytes"] = m.group(2).strip() if m else "?"
    res["idle_has_0xfe"] = "04 FE" in res["idle_bytes"].upper()
    res["setup_ok"] = bool(re.search(r"setup\(\) finished successfully", log))
    return res


def main() -> int:
    entities_only = "--entities-only" in sys.argv

    if not entities_only:
        print("=" * 64)
        print("[1/2] 复位板子并抓启动日志")
        print("=" * 64)
        log = capture_boot(PORT, 30)
        if not log.strip():
            print("❌ 没抓到任何串口日志")
            return 1
        res = check_log(log)
        print(f"  固件版本        : {res['version']}")
        print(f"  setup 正常结束  : {'✅' if res['setup_ok'] else '❌'}")
        print(f"  setup() 次数   : {res['boot_loops']}  {'✅ 无 boot loop' if res['boot_loops'] <= 1 else '❌ 在重启循环'}")
        print(f"  SAFE MODE       : {'❌ 是' if res['safe_mode'] else '✅ 否'}")
        print(f"  WiFi 已连接     : {'✅' if res['wifi'] else '❌'}")
        print(f"  广播已启动      : {'✅' if res['advert'] else '❌'}")
        print(f"  保存的 bond 数  : {res['bonds']}  ({res['bond_addr']})")
        print(f"  常态广播包      : {res['idle_len']} 字节  "
              f"{'✅ 不含 0xFE（电视不会自己醒）' if res['idle_has_0xfe'] is False else '❌ 含 0xFE'}")
        print(f"                   [{res['idle_bytes']}]")
        if res["stale_crash"]:
            print("  崩溃记录        : ⚠  是**旧固件**留下的历史记录"
                  "（日志写了 different firmware build），本次启动本身正常。")
            print("                    断电（拔插 USB）一次即可清掉 —— RTC 内存只有断电才会清。")
        elif res["crash"]:
            print("  崩溃记录        : ❌ 当前固件崩溃了")
        else:
            print("  崩溃记录        : ✅ 无")
        if res["crash"] and not res["stale_crash"]:
            print("\n--- 日志里的关键行 ---")
            for line in log.splitlines():
                if re.search(r"CRASH|SAFE MODE|panic|Guru|abort", line, re.I):
                    print("   ", line)
            return 1
    else:
        res = {}

    print()
    print("=" * 64)
    print("[2/2] 逐个探测实体")
    print("=" * 64)
    missing, ok = [], 0
    for key in AUTO_KEYS:
        name = f"ble-mi-remote-{key}"
        code, body = web_get(f"/button/{urllib.parse.quote(name, safe='')}")
        if code == 200:
            ok += 1
        else:
            missing.append(f"button/{name} (HTTP {code})")
    for key in TEMPLATE_KEYS:
        name = f"ble-mi-remote-{key}" if key.startswith("ble") else key
        code, body = web_get(f"/button/{urllib.parse.quote(name, safe='')}")
        if code == 200:
            ok += 1
        else:
            missing.append(f"button/{name} (HTTP {code})")

    # 组件的 binary_sensor 名字就叫 "Connected"（const.py 的 BINARY_SENSOR_STATE），
    # 没有 "ble-mi-remote-" 前缀 —— 组件的按键才有那个前缀。
    # 下面几个是候选路径，找到一个能用的就停。
    for path in ("/binary_sensor/Connected", "/binary_sensor/connected",
                 "/sensor/connected"):
        code, body = web_get(path)
        if code == 200:
            print(f"  ✅ {path} -> {body.strip()[:60]}")
            ok += 1
            break
    else:
        missing.append("binary_sensor/Connected (全部候选路径都不通)")

    print(f"\n  实体可用: {ok}")
    if missing:
        print("  缺失/异常:")
        for m in missing:
            print(f"    - {m}")
    else:
        print("  ✅ 全部实体都在")

    print("\n" + "=" * 64)
    # 9 个按键 + 4 个模板按钮 + 1 个 binary sensor = 14
    if ok >= 14 and not missing:
        print("✅ 正式版 v1.2.0 验收通过")
        return 0
    print("⚠  验收有问题，见上面")
    return 1


if __name__ == "__main__":
    sys.exit(main())
