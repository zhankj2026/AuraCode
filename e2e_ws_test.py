#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
E2E 测试：验证 Bridge 后端 WebSocket 事件流是否真的把事件推送到连接的 WS 客户端。

流程：
1. 先建立 WS 连接（在创建会话之前，确保能收到 session_started / session_created）。
2. 通过 REST 创建会话。
3. 通过 REST 发送一条消息。
4. 收集 WS 收到的事件 ~8 秒。
5. 同时通过 REST 拉取同一会话的事件做对照。
6. 把结果写入 e2e_ws_result.json。
"""

import asyncio
import json
import os
import sys
import urllib.request
import websockets

BASE = os.environ.get("E2E_BASE", "http://127.0.0.1:8803")
TOKEN = os.environ.get("E2E_TOKEN", "e2etoken")

# 绕过沙箱注入的 http_proxy/https_proxy，直接访问 loopback
_proxy_handler = urllib.request.ProxyHandler({})
_opener = urllib.request.build_opener(_proxy_handler)
urllib.request.install_opener(_opener)


def _req(method, url, data=None, headers=None):
    h = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    if headers:
        h.update(headers)
    body = json.dumps(data).encode() if data is not None else None
    r = urllib.request.Request(url, data=body, headers=h, method=method)
    with urllib.request.urlopen(r, timeout=15) as resp:
        return resp.status, resp.read().decode("utf-8", "replace")


async def main():
    collected = []

    # 1. 先连 WS
    ws_url = f"ws://127.0.0.1:8803/ws/events?token={TOKEN}"
    print(f"[client] connecting WS {ws_url}", flush=True)
    async with websockets.connect(ws_url) as ws:
        print("[client] WS connected", flush=True)

        # 2. 创建会话
        status, body = _req("POST", f"{BASE}/api/sessions", {
            "work_dir": "F:\\tmp",
            "model": "glm-4-flash",
            "permission_mode": "bypass",
            "max_iterations": 1,
        })
        print(f"[client] create session -> {status} {body}", flush=True)
        sid = json.loads(body).get("session_id")
        if not sid:
            print("[client] NO session_id, aborting", flush=True)
            return
        print(f"[client] session_id={sid}", flush=True)

        # 3. 发送消息
        status, body = _req("POST", f"{BASE}/api/sessions/{sid}/message",
                            {"content": "你好，这是端到端测试消息"})
        print(f"[client] send message -> {status} {body}", flush=True)

        # 4. 收集 WS 事件 8 秒
        try:
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=8.0)
                try:
                    ev = json.loads(msg)
                except Exception:
                    ev = msg
                collected.append(ev)
                t = ev.get("type") if isinstance(ev, dict) else "?"
                print(f"[client] WS EVENT type={t}", flush=True)
        except asyncio.TimeoutError:
            print(f"[client] WS idle 8s, collected={len(collected)}", flush=True)

    # 5. REST 对照
    try:
        status, body = _req("GET", f"{BASE}/api/sessions/{sid}/events?since=0")
        rest_events = json.loads(body) if status == 200 else []
        print(f"[client] REST events count={len(rest_events)}", flush=True)
    except Exception as e:
        rest_events = []
        print(f"[client] REST fetch failed: {e}", flush=True)

    out = {
        "ws_count": len(collected),
        "ws_types": [e.get("type") for e in collected if isinstance(e, dict)],
        "rest_count": len(rest_events),
        "rest_types": [e.get("type") for e in rest_events if isinstance(e, dict)],
    }
    print(f"[client] RESULT {json.dumps(out, ensure_ascii=False)}", flush=True)

    with open("e2e_ws_result.json", "w", encoding="utf-8") as f:
        json.dump({"ws": collected, "rest": rest_events}, f, ensure_ascii=False, indent=2)
    print("[client] written e2e_ws_result.json", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
