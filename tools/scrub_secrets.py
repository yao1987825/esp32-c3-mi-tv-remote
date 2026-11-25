#!/usr/bin/env python3
"""把 ESPHome 配置里的凭据换成 !secret 引用（发布到公开仓库前的脱敏）。

处理的文件：
  · esp32-adb-remote/esphome/tv-remote.yaml      （主配置）
  · esp32-adb-remote/release/v*/tv-remote.yaml    （各版本归档）

幂等：已经脱敏过的文件再跑一次不会有变化。
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(r"D:\esp32-c3开发版\esp32-adb-remote")

# (正则, 替换) —— 全部是「已经脱敏就跳过」的写法
RULES = [
    # WiFi 凭据（substitutions 里的定义）
    (re.compile(r'^(\s*)wifi_ssid:\s*\S+$', re.M), r'\1wifi_ssid: !secret wifi_ssid'),
    (re.compile(r'^(\s*)wifi_password:\s*.*$', re.M), r'\1wifi_password: !secret wifi_password'),
    # OTA / web 密码
    (re.compile(r'^(\s*)ota_password:\s*.*$', re.M), r'\1ota_password: !secret ota_password'),
    (re.compile(r'^(\s*)web_password:\s*.*$', re.M), r'\1web_password: !secret web_password'),
    # ESPHome 原生 API 加密密钥
    (re.compile(r'^(\s*)key:\s*"?[A-Za-z0-9+/=]{40,}"?$', re.M),
     r'\1key: !secret api_encryption_key'),
]


def scrub(path: pathlib.Path) -> bool:
    text = path.read_text(encoding="utf-8")
    original = text
    for pat, repl in RULES:
        text = pat.sub(repl, text)
    if text != original:
        path.write_text(text, encoding="utf-8", newline="\n")
        return True
    return False


def main() -> int:
    targets = [ROOT / "esphome" / "tv-remote.yaml"]
    targets += sorted((ROOT / "release").glob("v*/tv-remote.yaml"))
    if not targets:
        print("没找到要脱敏的配置文件")
        return 1
    changed = 0
    for t in targets:
        if not t.exists():
            print(f"  跳过（不存在）: {t}")
            continue
        if scrub(t):
            changed += 1
            print(f"  ✅ 已脱敏: {t.relative_to(ROOT)}")
        else:
            print(f"  – 无需改动: {t.relative_to(ROOT)}")
    print(f"\n共改动 {changed} 个文件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
