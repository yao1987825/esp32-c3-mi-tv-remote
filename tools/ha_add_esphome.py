#!/usr/bin/env python3
"""把 ESP32-C3 板子加进 Home Assistant（2026.11 的 REST 配置流）。

HA 2026.11 把「创建配置流」从 WebSocket 挪到了 REST：

    POST /api/config/config_entries/flow              {"handler": "esphome"}
      -> {"type":"form","flow_id":"...","data_schema":[...],"step_id":"user"}

    POST /api/config/config_entries/flow/{flow_id}    {"user_input": {...}}
      -> {"type":"create_entry", ...} / {"type":"form", ... 下一个步骤}

（WebSocket 的 `config_entries/flow/init` 在这个版本已经不存在，会报
`unknown_command` —— 这就是之前一直试不出来的原因。）

用法:
    python tools/ha_add_esphome.py --token <TOKEN> --host 192.168.6.101
"""
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request

API = "/api/config/config_entries/flow"


class HaRest:
    def __init__(self, base: str, token: str) -> None:
        self.base = base.rstrip("/")
        self.token = token

    def post(self, path: str, body: dict) -> tuple[int, dict | str]:
        url = f"{self.base}{path}"
        req = urllib.request.Request(
            url, data=json.dumps(body).encode(), method="POST",
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.token}"},
        )
        try:
            resp = urllib.request.urlopen(req, timeout=30)
            raw = resp.read().decode("utf-8", "replace")
            try:
                return resp.status, json.loads(raw)
            except Exception:  # noqa: BLE001
                return resp.status, raw
        except urllib.error.HTTPError as err:
            raw = err.read().decode("utf-8", "replace")
            try:
                return err.code, json.loads(raw)
            except Exception:  # noqa: BLE001
                return err.code, raw

    def get(self, path: str) -> tuple[int, object]:
        req = urllib.request.Request(
            f"{self.base}{path}", headers={"Authorization": f"Bearer {self.token}"})
        try:
            resp = urllib.request.urlopen(req, timeout=30)
            raw = resp.read().decode("utf-8", "replace")
            try:
                return resp.status, json.loads(raw)
            except Exception:  # noqa: BLE001
                return resp.status, raw
        except urllib.error.HTTPError as err:
            raw = err.read().decode("utf-8", "replace")
            try:
                return err.code, json.loads(raw)
            except Exception:  # noqa: BLE001
                return err.code, raw


def show_schema(schema) -> None:
    print("  配置流要的字段:")
    for f in schema or []:
        print(f"    - {f.get('name')}: {f.get('type')}  "
              f"required={f.get('required')} default={f.get('default')}")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--ha", default="http://192.168.6.135:8123")
    p.add_argument("--token", required=True)
    p.add_argument("--host", default="192.168.6.101")
    p.add_argument("--port", type=int, default=6053)
    p.add_argument("--password", default="")
    p.add_argument("--key", default="", help="加密密钥（base64），板子开了 api.encryption 时需要")
    p.add_argument("--force", action="store_true", help="已存在也照样再加一条")
    args = p.parse_args()

    ha = HaRest(args.ha, args.token)

    # --- 已有的 esphome 条目 ---
    code, entries = ha.get("/api/config/config_entries")
    if code == 200 and isinstance(entries, list):
        existing = [e for e in entries if e.get("domain") == "esphome"]
        if existing:
            print("HA 里已有的 esphome 条目:")
            for e in existing:
                print(f"  - {e.get('title')}  state={e.get('state')}  "
                      f"entry_id={e.get('entry_id')}")
                print(f"    data={e.get('data')}")
            if not args.force:
                print("\n（已存在，未重复添加。用 --force 强制再加一条。）")
                return 0
        else:
            print("HA 里还没有 esphome 条目。")

    # --- 启动配置流 ---
    print("\n启动 ESPHome 配置流 ...")
    code, flow = ha.post(API, {"handler": "esphome"})
    if code != 200 or not isinstance(flow, dict) or "flow_id" not in flow:
        print(f"❌ 启动失败 (HTTP {code}): {flow}")
        return 1
    flow_id = flow["flow_id"]
    print(f"✅ flow_id = {flow_id}  step = {flow.get('step_id')}")
    show_schema(flow.get("data_schema"))

    # --- 填表 ---
    # 这个版本的 schema 只有 host / port 两个字段，多传 key 会报
    # "not a valid option at 'key'"。
    values: dict = {"host": args.host, "port": args.port}
    if args.password:
        values["password"] = args.password
    if args.key:
        values["noise_psk"] = args.key
        values["key"] = args.key
        values["encryption_key"] = args.key

    # 多步流程：user(host/port) -> encryption_key(noise_psk) -> create_entry
    # 每一步只提交**这一步 schema 里有的**字段，多传会被 voluptuous 拒绝
    # （"not a valid option at 'xxx'"）。
    for _ in range(6):
        schema = flow.get("data_schema") or []
        names = {f.get("name") for f in schema}
        payload = {k: v for k, v in values.items() if k in names}
        missing = [n for n in names if n not in payload]
        if missing:
            print(f"\n❌ 这一步还缺字段: {missing}")
            print(f"   可用的字段: {sorted(names)}")
            print("   用 --password / --key 把值补上再跑。")
            return 2

        print(f"\n[{flow.get('step_id')}] 提交 = {payload}")
        code, flow = ha.post(f"{API}/{flow_id}", payload)
        if code != 200 or not isinstance(flow, dict):
            print(f"❌ HTTP {code}: {flow}")
            return 1

        if flow.get("type") == "create_entry":
            print(f"\n✅ 成功！条目: {flow.get('result', {}).get('title')}")
            print(json.dumps(flow.get("result", {}), ensure_ascii=False, indent=2)[:1500])
            return 0
        if flow.get("type") == "form":
            print(f"   → 下一步: {flow.get('step_id')}")
            show_schema(flow.get("data_schema"))
            continue
        if flow.get("type") == "abort":
            print(f"❌ 流程被中止: {flow.get('reason')}")
            return 1
        print(f"❌ 意料之外的返回: {flow}")
        return 1

    print("❌ 步骤太多，放弃了")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
