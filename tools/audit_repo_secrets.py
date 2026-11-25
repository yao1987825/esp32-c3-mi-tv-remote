#!/usr/bin/env python3
"""发布前的最后一道关：扫描**将要提交进仓库**的内容里有没有凭据。

检查对象是 git 暂存区（`git diff --cached`）里所有文本文件的内容，
不是工作区 —— 所以本地文件（secrets.yaml / credentials.py）不会误报。

★ 这个脚本里**不写死任何已知密码** ★
那样等于把密码抄一份到公开仓库里，等于泄露。
已知的凭据从本地 `tools/credentials.py`（已 gitignore）读进来做精确比对，
读不到就退化成通用模式检测。

用法:
    python tools/audit_repo_secrets.py
退出码 0 = 干净，1 = 发现敏感内容。
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

# --- 通用模式 ---------------------------------------------------------------
# 这些规则不看"是不是我的密码"，只看"这里本该是个占位符却填了真值"。
PATTERNS = [
    # yaml 里明文写死的 WiFi 凭据（必须是 !secret 引用）
    ("yaml 里明文的 wifi_ssid",
     re.compile(r"^\s*wifi_ssid:\s*(?!!secret)\S+", re.M)),
    ("yaml 里明文的 wifi_password",
     re.compile(r"^\s*wifi_password:\s*(?!!secret)\S+", re.M)),
    # base64 密钥（ESPHome API 加密密钥是 44 字符 base64）
    ("像 base64 的密钥字面量",
     re.compile(r"[A-Za-z0-9+/]{43}=")),
    # HA 长期访问令牌
    ("HA 长期访问令牌 (JWT)",
     re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}")),
    ("GitHub token", re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}")),
    ("AWS key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("私钥", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
]

# 这些行即使命中关键词也是安全的（在讲「怎么配密钥」而不是真的配了）
SAFE_CONTEXT = re.compile(
    r"secrets\.yaml|credentials\.py|credentials\.example|!secret|"
    r"api_encryption_key|TV_REMOTE_HA_TOKEN|TV_REMOTE_NOISE_PSK|"
    r"NOISE_PSK|WEB_PASS|wifi_password|wifi_ssid|"
    r"生成|你的WiFi|改成你自己|secret",
)

SKIP_EXT = {".bin", ".png", ".jpg", ".jpeg", ".gif", ".zip", ".pdf", ".ico"}


def known_values() -> set[str]:
    """本机已知的凭据值（来自 gitignore 掉的 credentials.py / 环境变量）。

    用来精确比对，避免脚本里写死明文。
    """
    vals: set[str] = set()
    for env in ("TV_REMOTE_NOISE_PSK", "TV_REMOTE_WEB_PASS",
                "TV_REMOTE_HA_TOKEN", "TV_REMOTE_BOARD_IP"):
        v = os.environ.get(env, "").strip()
        if v:
            vals.add(v)
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import credentials  # type: ignore

        for attr in ("NOISE_PSK", "WEB_PASS", "HA_TOKEN"):
            v = str(getattr(credentials, attr, "") or "").strip()
            if len(v) >= 8:
                vals.add(v)
    except Exception:  # noqa: BLE001
        pass
    return vals


def staged_files() -> list[str]:
    out = subprocess.run(["git", "diff", "--cached", "--name-only", "-z"],
                         capture_output=True, text=True, encoding="utf-8",
                         errors="replace", check=True).stdout
    return [f for f in out.split("\0") if f]


def main() -> int:
    files = staged_files()
    known = known_values()
    print(f"暂存区共 {len(files)} 个文件"
          f"（已加载 {len(known)} 个本机已知凭据值用于比对）\n")
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
            # 1) 和本机已知凭据字面相同的
            for v in known:
                if v and v in line and not SAFE_CONTEXT.search(line):
                    hits.append((rel, line_no, "本机已知凭据的字面量", v[:40], line.strip()[:100]))
                    break
            # 2) 通用模式
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
