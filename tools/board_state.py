#!/usr/bin/env python3
"""读板子的 BLE 连接状态（走 web_server 的 digest 认证）。

用法:
    python tools/board_state.py            # 打印一次状态
    python tools/board_state.py --watch 30 # 持续监控 30 秒
"""
from __future__ import annotations

import re
import sys
import time
import urllib.error
import urllib.request

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

HOST = "192.168.6.101"
USER = "admin"
PASS = "tv-remote"


def digest_header(user, password, realm, nonce, uri, qop="", opaque="", method="GET"):
    import hashlib

    ha1 = hashlib.md5(f"{user}:{realm}:{password}".encode()).hexdigest()
    ha2 = hashlib.md5(f"{method}:{uri}".encode()).hexdigest()
    parts = [f'username="{user}"', f'realm="{realm}"', f'nonce="{nonce}"', f'uri="{uri}"']
    if qop:
        nc, cnonce = "00000001", "0a4f113b"
        response = hashlib.md5(f"{ha1}:{nonce}:{nc}:{cnonce}:{qop}:{ha2}".encode()).hexdigest()
        parts += [f"qop={qop}", f"nc={nc}", f'cnonce="{cnonce}"']
    else:
        response = hashlib.md5(f"{ha1}:{nonce}:{ha2}".encode()).hexdigest()
    parts.append(f'response="{response}"')
    parts.append("algorithm=MD5")
    if opaque:
        parts.append(f'opaque="{opaque}"')
    return "Digest " + ", ".join(parts)


def get(path: str) -> str:
    url = f"http://{HOST}{path}"
    req = urllib.request.Request(url, method="GET")
    try:
        return urllib.request.urlopen(req, timeout=8).read().decode("utf-8", "replace")
    except urllib.error.HTTPError as err:
        if err.code != 401:
            return f"HTTP {err.code}"
        challenge = err.headers.get("WWW-Authenticate", "")
        fields = dict(re.findall(r'(\w+)="([^"]*)"', challenge))
        req = urllib.request.Request(url, method="GET")
        req.add_header("Authorization", digest_header(
            USER, PASS, fields.get("realm", ""), fields.get("nonce", ""), path,
            qop=fields.get("qop", ""), opaque=fields.get("opaque", ""), method="GET"))
        try:
            return urllib.request.urlopen(req, timeout=8).read().decode("utf-8", "replace")
        except urllib.error.HTTPError as err2:
            return f"HTTP {err2.code} {err2.reason}"
    except Exception as err:  # noqa: BLE001
        return f"ERR {err}"


def main() -> int:
    args = sys.argv[1:]
    watch = False
    secs = 30.0
    if args and args[0] == "--watch":
        watch = True
        secs = float(args[1]) if len(args) > 1 else 30.0

    if not watch:
        print(get("/binary_sensor/connected"))
        return 0

    end = time.time() + secs
    last = None
    while time.time() < end:
        val = get("/binary_sensor/connected").strip()
        if val != last:
            print(f"[{time.strftime('%H:%M:%S')}] connected = {val}", flush=True)
            last = val
        time.sleep(0.7)
    return 0


if __name__ == "__main__":
    sys.exit(main())
