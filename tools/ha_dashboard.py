#!/usr/bin/env python3
"""通过 WebSocket 读 / 写 HA 的 Lovelace 面板。

2026.11 的 /api/lovelace/* REST 端点全部 404，面板配置只能走
WebSocket 的 lovelace/config 命令（用 url_path 选面板）。

用法:
    python tools/ha_dashboard.py --token <TOKEN> list
    python tools/ha_dashboard.py --token <TOKEN> show [url_path]
    python tools/ha_dashboard.py --token <TOKEN> set --file panel.json [url_path]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys

import websockets

WS = "/api/websocket"


class HaWs:
    def __init__(self, ws) -> None:
        self.ws = ws
        self._id = 0

    async def cmd(self, typ: str, **payload) -> dict:
        self._id += 1
        mid = self._id
        await self.ws.send(json.dumps({"id": mid, "type": typ, **payload}))
        while True:
            data = json.loads(await self.ws.recv())
            if data.get("id") == mid:
                return data


async def run(args) -> int:
    url = f"ws://{args.ha}{WS}"
    async with websockets.connect(url, max_size=None, open_timeout=20) as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "auth", "access_token": args.token}))
        auth = json.loads(await ws.recv())
        if auth.get("type") != "auth_ok":
            print(f"认证失败: {auth}")
            return 1
        print(f"已连接 HA {auth.get('ha_version')}", file=sys.stderr)
        c = HaWs(ws)

        if args.action == "list":
            res = await c.cmd("lovelace/dashboards/list")
            print(json.dumps(res.get("result"), ensure_ascii=False, indent=2))
            return 0

        if args.action == "show":
            payload = {"url_path": args.url_path} if args.url_path else {}
            res = await c.cmd("lovelace/config", **payload)
            if not res.get("success"):
                print(f"失败: {res}")
                return 1
            result = res.get("result")
            print(json.dumps(result, ensure_ascii=False, indent=2)
                  if not isinstance(result, str) else result)
            return 0

        # set
        if not args.file:
            print("set 模式需要 --file")
            return 1
        with open(args.file, "r", encoding="utf-8") as fh:
            cfg = json.load(fh)
        payload = {"url_path": args.url_path} if args.url_path else {}
        res = await c.cmd("lovelace/config/save", config=cfg, **payload)
        print(json.dumps(res, ensure_ascii=False, indent=2)[:3000])
        return 0 if res.get("success") else 1


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--ha", default="192.168.6.135:8123")
    p.add_argument("--token", required=True)
    p.add_argument("--file", help="set 模式：写入的 JSON 文件")
    p.add_argument("action", choices=["list", "show", "set"])
    p.add_argument("url_path", nargs="?", help="面板 url_path（不填 = 默认面板）")
    args = p.parse_args()
    try:
        return asyncio.run(run(args))
    except Exception as err:  # noqa: BLE001
        print(f"异常: {type(err).__name__}: {err}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
