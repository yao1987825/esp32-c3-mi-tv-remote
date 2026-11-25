#!/usr/bin/env python3
"""查 / 改 Home Assistant 的实体注册表。

HA 2026.11 的实体注册表**只有 WebSocket 入口**（REST 没有）：
    config/entity_registry/get_entries
    config/entity_registry/update

用法:
    python tools/ha_entity_registry.py --token <TOKEN> list
    python tools/ha_entity_registry.py --token <TOKEN> rename
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
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


# 想要的目标 entity_id：去掉中文前缀，统一用 mi_tv_remote 前缀
ALIAS = {
    "tv_home": "home",
    "tv_power_hold": "power_hold",
    "tv_reconnect": "reconnect",
    "tv_sniff": "sniff",
}


def clean_entity_id(entity_id: str) -> str | None:
    m = re.match(r"^(button|binary_sensor|number|sensor)\.xiao_mi_dian_shi_yao_kong_qi_(.+)$", entity_id)
    if not m:
        return None
    domain, rest = m.group(1), m.group(2)
    # 组件自带的名字已经带了 "ble_mi_remote_"，去掉重复的
    if rest.startswith("ble_mi_remote_"):
        rest = rest[len("ble_mi_remote_"):]
    rest = ALIAS.get(rest, rest)
    return f"{domain}.mi_tv_remote_{rest}"


async def run(args) -> int:
    url = f"ws://{args.ha}/api/websocket"
    async with websockets.connect(url, max_size=None, open_timeout=20) as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "auth", "access_token": args.token}))
        auth = json.loads(await ws.recv())
        if auth.get("type") != "auth_ok":
            print(f"认证失败: {auth}")
            return 1
        print(f"已连接 HA {auth.get('ha_version')}\n")
        c = HaWs(ws)

        res = await c.cmd("config/entity_registry/list_for_display")
        entries = res.get("result", {}).get("entities", [])
        ours = [e for e in entries if "xiao_mi_dian_shi_yao_kong_qi" in e.get("ei", "")]
        print(f"实体注册表共 {len(entries)} 条，其中本板子 {len(ours)} 条\n")

        if args.action == "list":
            for e in sorted(ours, key=lambda x: x["ei"]):
                print(f"  {e.get('ei')}")
                print(f"      name = {e.get('en')}   platform = {e.get('pl')}")
            return 0

        # --- rename ---
        if args.dry_run:
            print("（--dry-run 模式，只打印不改）\n")
        ok = 0
        for e in sorted(ours, key=lambda x: x["ei"]):
            old = e.get("ei")
            new = clean_entity_id(old)
            if not new or new == old:
                continue
            print(f"  {old}\n    -> {new}")
            if args.dry_run:
                ok += 1
                continue
            upd = await c.cmd("config/entity_registry/update",
                              entity_id=old, new_entity_id=new)
            if upd.get("success") is False:
                print(f"    ❌ {upd.get('error')}")
            else:
                print("    ✅")
                ok += 1
        print(f"\n共处理 {ok} 个")
        return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--ha", default="192.168.6.135:8123")
    p.add_argument("--token", required=True)
    p.add_argument("action", choices=["list", "rename"], nargs="?", default="list")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    try:
        return asyncio.run(run(args))
    except Exception as err:  # noqa: BLE001
        print(f"异常: {type(err).__name__}: {err}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
