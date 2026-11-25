#!/usr/bin/env python3
"""探测板子 web_server 对某个按钮名的响应（诊断用）。"""
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


def digest_header(user, password, realm, nonce, uri, qop="", opaque="", method="GET"):
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
        response = hashlib.md5(f"{ha1}:{nonce}:{nc}:{cnonce}:{qop}:{ha2}".encode()).hexdigest()
        parts += [f"qop={qop}", f"nc={nc}", f'cnonce="{cnonce}"']
    else:
        response = hashlib.md5(f"{ha1}:{nonce}:{ha2}".encode()).hexdigest()
    parts.append(f'response="{response}"')
    parts.append("algorithm=MD5")
    if opaque:
        parts.append(f'opaque="{opaque}"')
    return "Digest " + ", ".join(parts)


def probe(uri, method="POST", label=""):
    url = f"http://{HOST}{uri}"
    req = urllib.request.Request(url, method=method, data=b"" if method == "POST" else None)
    try:
        resp = urllib.request.urlopen(req, timeout=8)
        print(f"  [{label}] {method} {uri} -> {resp.status} {resp.reason}")
        return resp.status
    except urllib.error.HTTPError as err:
        print(f"  [{label}] {method} {uri} -> {err.code} {err.reason}")
        challenge = err.headers.get("WWW-Authenticate", "")
        if err.code == 401 and challenge.lower().startswith("digest"):
            fields = dict(re.findall(r'(\w+)="([^"]*)"', challenge))
            print(f"        challenge fields: {fields}")
            req2 = urllib.request.Request(url, method=method, data=b"" if method == "POST" else None)
            req2.add_header(
                "Authorization",
                digest_header(
                    WEB_USER, WEB_PASS, fields.get("realm", ""), fields.get("nonce", ""),
                    uri, qop=fields.get("qop", ""), opaque=fields.get("opaque", ""), method=method,
                ),
            )
            try:
                resp2 = urllib.request.urlopen(req2, timeout=8)
                print(f"  [{label}]   -> with digest: {resp2.status} {resp2.reason}")
                return resp2.status
            except urllib.error.HTTPError as err2:
                print(f"  [{label}]   -> with digest: {err2.code} {err2.reason}")
                return err2.code
        return err.code
    except Exception as exc:  # noqa: BLE001
        print(f"  [{label}] {method} {uri} -> EXC {type(exc).__name__}: {exc}")
        return -1


def main():
    names = sys.argv[1:] or ["TV Reconnect"]
    for name in names:
        print(f"== {name} ==")
        variants = [
            ("name-encoded", urllib.parse.quote(name, safe="")),
            ("name-encoded-20", name.replace(" ", "%20")),
            ("objid", name.lower().replace(" ", "_")),
            ("objid-hyphen", name.lower().replace(" ", "-")),
        ]
        for label, enc in variants:
            probe(f"/button/{enc}/press", "POST", label)


if __name__ == "__main__":
    main()
