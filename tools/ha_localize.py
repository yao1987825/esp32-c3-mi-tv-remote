#!/usr/bin/env python3
"""HA 侧的实体收尾：查引用 + 改中文显示名 + 改设备中文名。

为什么显示名在 HA 改、而不在 ESPHome 改：
ESPHome 的实体**显示名**和 **object_id** 是同一个来源（都是 `name:`）。
把 `name:` 改成中文，object_id 就会变成拼音（`dian_yuan`），自动化里没法用。
所以：
  · 固件里实体名保持 ASCII → entity_id 稳定是 `button.mi_tv_remote_power`
  · HA 里用实体注册表把**显示名**改成中文 → 界面好看，实体 id 不变
  · HA 里把**设备名**改成「小米电视遥控器」→ 设备卡片也是中文

用法:
    python tools/ha_localize.py --token <TOKEN> check     # 只查引用
    python tools/ha_localize.py --token <TOKEN> apply     # 改显示名 + 设备名
    python tools/ha_localize.py --token <TOKEN> revert    # 还原成英文显示名
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys

import websockets

WS = "/api/websocket"

# entity_id 后缀 -> 中文显示名
CN = {
    "power": "电源",
    "power_hold": "电源（长按）",
    "volume_up": "音量+",
    "volume_down": "音量-",
    "vol_up_x5": "音量+ ×5",
    "vol_down_x5": "音量- ×5",
    "enter": "确认",
    "up": "上",
    "down": "下",
    "left": "左",
    "right": "右",
    "back": "返回",
    "forward": "前进",
    "home": "主页",
    "android_tv": "主页（Android TV）",
    "mi_home": "MI 主页",
    "movie": "电影",
    "select": "选择",
    "voice": "语音",
    "voice2": "语音（2）",
    "stop": "停止",
    "refresh": "刷新",
    "bookmarks": "书签",
    "green": "绿键",
    "blue": "蓝键",
    "email": "邮件",
    "calculator": "计算器",
    "files": "文件",
    "connected": "已连接",
    "reconnect": "重新广播（维护）",
    "sniff": "BLE 嗅探器（维护）",
}

# 旧的拼音 entity_id 前缀 —— 改名前用过
OLD_PREFIX = "xiao_mi_dian_shi_yao_kong_qi"
NEW_PREFIX = "mi_tv_remote"


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


def suffix_of(entity_id: str) -> str | None:
    m = re.match(r"^[a-z_]+\.(?:mi_tv_remote|ble_mi_remote)_(.+)$", entity_id)
    return m.group(1) if m else None


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

        # ---------- 1. 查自动化 / 脚本里的引用 ----------
        print("=== 自动化 / 脚本里对板子实体的引用 ===")
        hits = 0
        for typ, label in (("automation/config", "自动化"), ("script/config", "脚本")):
            res = await c.cmd(f"config/{typ}")
            items = res.get("result") or {}
            if isinstance(items, dict):
                names = list(items.keys())
                bodies = {k: json.dumps(items[k], ensure_ascii=False) for k in names}
            else:
                names = [i.get("id", "?") for i in items]
                bodies = {i.get("id", "?"): json.dumps(i, ensure_ascii=False) for i in items}
            if not names:
                print(f"  {label}: 无")
            for n in names:
                body = bodies.get(n, "")
                if OLD_PREFIX in body or "mi_tv_remote" in body:
                    hits += 1
                    print(f"  *** {label} {n} 引用了板子实体")
                    for m in re.finditer(r"[a-z_]+\.(?:xiao_mi_dian_shi_yao_kong_qi|mi_tv_remote)[a-z_0-9]*", body):
                        print(f"        {m.group(0)}")
                else:
                    print(f"      {label} {n}")
        if not hits:
            print("  ✅ 没有任何自动化/脚本引用板子实体 —— 改名没有破坏东西")

        # ---------- 2. 实体显示名 ----------
        res = await c.cmd("config/entity_registry/list_for_display")
        ents = res.get("result", {}).get("entities", [])
        ours = [e for e in ents if e.get("ei", "").startswith(f"button.{NEW_PREFIX}")
                or e.get("ei", "").startswith(f"binary_sensor.{NEW_PREFIX}")]

        print(f"\n=== 板子实体 {len(ours)} 个 ===")
        if args.action == "check":
            for e in sorted(ours, key=lambda x: x["ei"]):
                print(f"  {e.get('ei'):<45} 显示名={e.get('en')}")
            return 0

        ok = 0
        for e in sorted(ours, key=lambda x: x["ei"]):
            ei = e.get("ei")
            sfx = suffix_of(ei)
            if not sfx:
                continue
            cn = CN.get(sfx)
            if not cn:
                print(f"  ⚠ {ei} 没有对应的中文名，跳过")
                continue
            if args.action == "revert":
                want = e.get("original_name") or ei.split(".", 1)[1]
            else:
                want = cn
            upd = await c.cmd("config/entity_registry/update", entity_id=ei, name=want)
            if upd.get("success") is False:
                print(f"  ❌ {ei} -> {want}: {upd.get('error')}")
            else:
                print(f"  ✅ {ei} -> 显示名「{want}」")
                ok += 1
        print(f"  共改 {ok} 个")

        # ---------- 3. 设备名 ----------
        devs = await c.cmd("config/device_registry/list")
        for d in devs.get("result", []):
            if d.get("id") == "eef434a996d57bf909f0a60c41695fe1" or \
               any("mi-tv-remote" in str(x) for x in d.get("identifiers", [])):
                print(f"\n=== 设备 ===")
                print(f"  name      = {d.get('name')}")
                print(f"  name_by_user = {d.get('name_by_user')}")
                print(f"  model     = {d.get('model')}  mfr = {d.get('manufacturer')}")
                if args.action == "apply":
                    upd = await c.cmd("config/device_registry/update",
                                     device_id=d.get("id"), name_by_user="小米电视遥控器")
                    print(f"  改名 name_by_user -> 小米电视遥控器: "
                          f"{'✅' if upd.get('success') else '❌ ' + str(upd.get('error'))}")
                break
        return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--ha", default="192.168.6.135:8123")
    p.add_argument("--token", required=True)
    p.add_argument("action", choices=["check", "apply", "revert"], nargs="?", default="check")
    args = p.parse_args()
    try:
        return asyncio.run(run(args))
    except Exception as err:  # noqa: BLE001
        print(f"异常: {type(err).__name__}: {err}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
