#!/usr/bin/env python3
"""读板子 web_server 上的实体状态（Connected 传感器等），自动处理 gzip。

用法:
    python tools/board_entities.py
"""
from __future__ import annotations

import gzip
import importlib.util
import re
import urllib.error
import urllib.request

spec = importlib.util.spec_from_file_location("tv", r"D:\esp32-c3开发版\tools\tv_remote.py")
tv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tv)


def get(path: str) -> bytes:
    url = f"http://{tv.HOST}{path}"
    try:
        return urllib.request.urlopen(urllib.request.Request(url), timeout=10).read()
    except urllib.error.HTTPError as err:
        if err.code != 401:
            raise
        ch = err.headers.get("WWW-Authenticate", "")
        f = dict(re.findall(r'(\w+)="([^"]*)"', ch))
        req = urllib.request.Request(url)
        req.add_header(
            "Authorization",
            tv.digest_header(
                tv.WEB_USER, tv.WEB_PASS, f.get("realm", ""), f.get("nonce", ""),
                path, qop=f.get("qop", ""), opaque=f.get("opaque", ""), method="GET",
            ),
        )
        return urllib.request.urlopen(req, timeout=10).read()


def main() -> int:
    # ESPHome 的网页版是个 JS 应用，实体状态走 JSON 接口。
    for path in ("/sensor/connected", "/binary_sensor/connected"):
        try:
            raw = get(path)
        except Exception as err:  # noqa: BLE001
            print(f"{path} -> 请求失败: {err}")
            continue
        if raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
        print(f"{path} -> {raw.decode('utf-8', 'replace').strip()[:200]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
