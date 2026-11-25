#!/usr/bin/env python3
"""发布前的最后一道关：扫描**将要提交进仓库**的内容里有没有凭据。

检查对象是 git 暂存区（`git diff --cached`）里所有文本文件的内容，
不是工作区 —— 所以本地文件（secrets.yaml / credentials.py）不会误报。

用法:
    python tools/audit_repo_secrets.py
退出码 0 = 干净，1 = 发现敏感内容。
"""
from __future__ import annotations

import re
import subprocess
import sys

# (说明, 正则) —— 命中就是泄露
PATTERNS = [
    ("ESPHome API 加密密钥", re.compile(r"[A-Za-z0-9+/]{43}=")),
    ("HA 长期访问令牌 (JWT)", re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}")),
    ("WiFi 密码 (已知明文)", re.compile(r"3971247yaojiwei")),
    ("WiFi SSID (已知明文)", re.compile(r"Kwrt_2\.4G")),
    ("GitHub token", re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}")),
    ("AWS key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("私钥", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
]

# 这些行即使命中关键词也是安全的（文档里在讲「怎么配密钥」）
SAFE_CONTEXT = re.compile(
    r"secrets\.yaml|credentials\.py|credentials\.example|!secret|"
    r"api_encryption_key|TV_REMOTE_HA_TOKEN|生成|生成一条|你的WiFi|改成你自己",
)

# 二进制/大文件不扫
SKIP_EXT = {".bin", ".png", ".jpg", ".jpeg", ".gif", ".zip", ".pdf", ".ico"}


def staged_files() -> list[str]:
    out = subprocess.run(["git", "diff", "--cached", "--name-only", "-z"],
                         capture_output=True, text=True, encoding="utf-8",
                         errors="replace", check=True).stdout
    return [f for f in out.split("\0") if f]


def main() -> int:
    files = staged_files()
    print(f"暂存区共 {len(files)} 个文件，开始扫描…\n")
    hits = []
    for rel in files:
        if rel.lower().endswith(tuple(SKIP_EXT)):
            continue
        try:
            with open(rel, "rb") as fh:
                raw = fh.read()
        except OSError:
            continue
        if b"\x00" in raw[:4096]:
            continue
        text = raw.decode("utf-8", "replace")
        for line_no, line in enumerate(text.splitlines(), 1):
            for label, pat in PATTERNS:
                m = pat.search(line)
                if not m:
                    continue
                if SAFE_CONTEXT.search(line):
                    continue
                hits.append((rel, line_no, label, m.group(0)[:60], line.strip()[:100]))

    if not hits:
        print("✅ 没发现任何凭据泄露")
        return 0

    print(f"❌ 发现 {len(hits)} 处疑似敏感内容：\n")
    for rel, line_no, label, matched, line in hits:
        print(f"  {rel}:{line_no}  [{label}]")
        print(f"      命中: {matched}")
        print(f"      原文: {line}\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
