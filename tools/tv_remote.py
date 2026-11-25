#!/usr/bin/env python3
"""从 PC 直接当遥控器操作板子（ESP32-C3 → 电视的蓝牙 HID 遥控器）。

板子跑 ESPHome 固件，24 个按键是 button 实体。这里走板子自带的
web_server 触发按钮动作：

    POST http://<板子>/button/<实体object_id>/press

web_server 用 digest 认证（admin / tv-remote），所以脚本要自己算
digest 响应。

用法:
    python tools/tv_remote.py list
    python tools/tv_remote.py "Volume Up"          # 按一下音量 +
    python tools/tv_remote.py "Volume Up" 3        # 连按 3 下
    python tools/tv_remote.py "Power"              # ★ 电源键（双向）
    python tools/tv_remote.py --power-hold         # 真·HID 长按电源 2 秒
    python tools/tv_remote.py --vol-up-x5          # 一次 5 格
    python tools/tv_remote.py --reconnect          # 强制回到可被发现状态（保留配对）
    python tools/tv_remote.py --sniff              # BLE 嗅探器：打印所有广播的原始字节

★ 电源键是**双向**的（v1.0.0 起）：
    电视亮着  → 发 HID 电源键 → 电视进关屏待机
    电视待机  → 发唤醒广播（31 字节 mi_wake 包）→ 电视重新亮屏
    电视彻底关机（拔电才能恢复）→ 任何 BLE 手段都唤不醒，属硬件限制
"""
from __future__ import annotations

import hashlib
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

try:
    from credentials import BOARD_IP, WEB_PASS, WEB_USER
except ImportError:  # 没建 credentials.py 就读环境变量
    HOST = os.environ.get("TV_REMOTE_BOARD_IP", "192.168.6.101")
    WEB_USER = os.environ.get("TV_REMOTE_WEB_USER", "admin")
    WEB_PASS = os.environ.get("TV_REMOTE_WEB_PASS", "")
else:
    HOST = BOARD_IP

# 组件里 SPECIAL_KEY 的名字（和固件里的实体名一致）
# 2026-11-25: 语音键（Voice / Voice2）已从组件里删除 —— 板子上没有麦克风。
# 固件里用 `buttons:` 白名单只暴露了 9 个：
#   Enter / Up / Down / Left / Right / Power / Back / Volume Up / Volume Down
KEY_NAMES = [
    "Enter", "Up", "Down", "Left", "Right", "Power", "Back",
    "Volume Up", "Volume Down",
]

TEMPLATE_BUTTONS = {
    "vol-up-x5": "Vol Up x5",
    "vol-down-x5": "Vol Down x5",
    # 强制回到「可被发现」状态（保留配对记录）
    "reconnect": "TV Reconnect",
    # BLE 嗅探器：监听空气里的所有广播并打印原始字节
    "sniff": "TV Sniff",
}


def object_id(entity_name: str) -> str:
    """ESPHome 的 object_id 规则：名字转小写，空格换下划线，连字符保留。"""
    return entity_name.lower().replace(" ", "_")


def digest_header(
    user: str,
    password: str,
    realm: str,
    nonce: str,
    uri: str,
    qop: str = "",
    opaque: str = "",
    method: str = "GET",
) -> str:
    """算 HTTP digest 认证的 Authorization 头。

    ESPHome 的 web_server 会带 qop="auth" 和 opaque，两种都得算对，
    否则第二次请求还是 401。
    """
    ha1 = hashlib.md5(f"{user}:{realm}:{password}".encode()).hexdigest()
    ha2 = hashlib.md5(f"{method}:{uri}".encode()).hexdigest()
    parts = [
        f'username="{user}"',
        f'realm="{realm}"',
        f'nonce="{nonce}"',
        f'uri="{uri}"',
    ]
    if qop:
        nc = "00000001"
        cnonce = "0a4f113b"
        response = hashlib.md5(
            f"{ha1}:{nonce}:{nc}:{cnonce}:{qop}:{ha2}".encode()
        ).hexdigest()
        parts += [
            f"qop={qop}",
            f"nc={nc}",
            f'cnonce="{cnonce}"',
        ]
    else:
        response = hashlib.md5(f"{ha1}:{nonce}:{ha2}".encode()).hexdigest()
    parts.append(f'response="{response}"')
    parts.append("algorithm=MD5")
    if opaque:
        parts.append(f'opaque="{opaque}"')
    return "Digest " + ", ".join(parts)


def post_action(entity: str, action: str = "press") -> str:
    """POST /{domain}/{实体名}/{action}。

    web_server 是拿 URL 段和实体的**名字**精确比对的（不是 object_id），
    所以这里用实体名；名字里有空格，先试 %20 编码，不行再试原样。
    """
    candidates = [
        f"/button/{urllib.parse.quote(entity, safe='')}/{action}",
        f"/button/{entity}/{action}",
    ]
    last = "?"
    for uri in candidates:
        url = f"http://{HOST}{uri}"

        req = urllib.request.Request(url, method="POST", data=b"")
        try:
            resp = urllib.request.urlopen(req, timeout=8)
            return f"{resp.status} {resp.reason}"
        except urllib.error.HTTPError as err:
            last = f"{err.code} {err.reason}"
            challenge = err.headers.get("WWW-Authenticate", "")
            if err.code != 401 or not challenge.lower().startswith("digest"):
                continue
            fields = dict(re.findall(r'(\w+)="([^"]*)"', challenge))
            req = urllib.request.Request(url, method="POST", data=b"")
            req.add_header(
                "Authorization",
                digest_header(
                    WEB_USER,
                    WEB_PASS,
                    fields.get("realm", ""),
                    fields.get("nonce", ""),
                    uri,
                    qop=fields.get("qop", ""),
                    opaque=fields.get("opaque", ""),
                    method="POST",
                ),
            )
            try:
                resp = urllib.request.urlopen(req, timeout=8)
                return f"{resp.status} {resp.reason}"
            except urllib.error.HTTPError as err:
                last = f"{err.code} {err.reason}"
    return last


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 1

    if args[0] == "list":
        for name in KEY_NAMES:
            print(f"  {name:<16} -> button.{object_id('ble-mi-remote-' + name)}")
        for alias, name in TEMPLATE_BUTTONS.items():
            print(f"  {alias:<16} -> button.{object_id(name)}")
        return 0

    if args[0].startswith("--"):
        alias = args[0][2:]
        if alias not in TEMPLATE_BUTTONS:
            print(f"未知按钮 '{alias}'。可用：{', '.join(TEMPLATE_BUTTONS)}")
            return 1
        name = TEMPLATE_BUTTONS[alias]
        print(f"触发 {name}: {post_action(name)}")
        return 0

    code = args[0]
    if code not in KEY_NAMES:
        print(f"未知按键 '{code}'。用 'list' 看全部。")
        return 1
    times = int(args[1]) if len(args) > 1 else 1
    entity = f"ble-mi-remote-{code}"
    for i in range(times):
        print(f"  {entity} ({i + 1}/{times}): {post_action(entity)}")
        if i + 1 < times:
            import time

            time.sleep(0.35)
    return 0


if __name__ == "__main__":
    sys.exit(main())
