#!/usr/bin/env python3
"""刷完固件后检查板子是否真的起来了。

查三件事：
  1. 网络：板子有没有拿到 IP、ESPHome 的 web server (80) 和原生 API (6053) 在不在
  2. mDNS：`_esphomelib._tcp` 有没有广播出来（HA 就是靠这个发现设备的）
  3. 实体：web server 上真实存在哪些 button / binary_sensor，
     顺便核对 HA 面板里写的 entity id 对不对得上

用法:
    python tools/check_board.py [IP]
    python tools/check_board.py 192.168.6.101
"""
from __future__ import annotations

import gzip
import hashlib
import os
import re
import socket
import sys
import urllib.error
import urllib.request

try:
    from credentials import BOARD_IP, WEB_PASS, WEB_USER
except ImportError:  # 没建 credentials.py 就读环境变量
    DEFAULT_IP = os.environ.get("TV_REMOTE_BOARD_IP", "192.168.6.101")
    WEB_USER = os.environ.get("TV_REMOTE_WEB_USER", "admin")
    WEB_PASS = os.environ.get("TV_REMOTE_WEB_PASS", "")
else:
    DEFAULT_IP = BOARD_IP

MDNS_NAME = "mi-tv-remote.local"


def tcp_open(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def fetch_web(host: str, user: str, password: str) -> str:
    """取 web server 首页（digest 认证）。响应是 gzip，必须全程走 bytes。"""
    url = f"http://{host}/"
    req = urllib.request.Request(url)
    try:
        resp = urllib.request.urlopen(req, timeout=8)
        raw, encoding = resp.read(), resp.headers.get("Content-Encoding", "")
    except urllib.error.HTTPError as err:
        challenge = err.headers.get("WWW-Authenticate", "")
        if err.code != 401 or not challenge.lower().startswith("digest"):
            raise
        fields = dict(re.findall(r'(\w+)="([^"]*)"', challenge))
        nonce = fields.get("nonce", "")
        realm = fields.get("realm", "")
        qop = fields.get("qop", "")
        ha1 = hashlib.md5(f"{user}:{realm}:{password}".encode()).hexdigest()
        ha2 = hashlib.md5(b"GET:/").hexdigest()
        if qop:
            cnonce = "0a4f113b"
            response = hashlib.md5(
                f"{ha1}:{nonce}:00000001:{cnonce}:auth:{ha2}".encode()
            ).hexdigest()
            header = (
                f'Digest username="{user}", realm="{realm}", nonce="{nonce}", '
                f'uri="/", qop=auth, nc=00000001, cnonce="{cnonce}", '
                f'response="{response}", algorithm=MD5'
            )
        else:
            response = hashlib.md5(f"{ha1}:{nonce}:{ha2}".encode()).hexdigest()
            header = (
                f'Digest username="{user}", realm="{realm}", nonce="{nonce}", '
                f'uri="/", response="{response}", algorithm=MD5'
            )
        req = urllib.request.Request(url)
        req.add_header("Authorization", header)
        resp = urllib.request.urlopen(req, timeout=8)
        raw, encoding = resp.read(), resp.headers.get("Content-Encoding", "")

    if encoding == "gzip" or raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return raw.decode("utf-8", "replace")


def main() -> int:
    ip = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_IP
    print(f"== 板子 {ip} ==")

    for port, label in ((80, "web server"), (6053, "API"), (3232, "网络下载")):
        ok = tcp_open(ip, port)
        print(f"  port {port:>5} {label:<10} {'OPEN' if ok else '-'}")

    print("== mDNS ==")
    try:
        print(f"  {MDNS_NAME} -> {socket.gethostbyname(MDNS_NAME)}")
    except OSError as err:
        print(f"  {MDNS_NAME} 解析失败: {err}")

    print("== web server 实体 ==")
    try:
        body = fetch_web(ip, WEB_USER, WEB_PASS)
    except Exception as err:  # noqa: BLE001
        print(f"  读取失败: {err}")
        return 1

    ids = sorted(set(re.findall(r"\b(button|binary_sensor|sensor)\.([a-z0-9_]+)", body)))
    if not ids:
        print("  （页面里没有实体 id，新版前端是走 API 拉的）")
        names = sorted(set(re.findall(r'"name"\s*:\s*"([^"]+)"', body)))
        for name in names:
            print(f"  {name}")
        return 0

    print(f"  共 {len(ids)} 个：")
    for domain, name in ids:
        print(f"    {domain}.{name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
