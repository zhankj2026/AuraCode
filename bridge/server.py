#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2026 zhankj
#
# This source code is licensed under the [ Apache-2.0] license.
# For the full license text, please refer to the LICENSE file in the root directory.
#
# Author: zhankj <creating2018@aliyun.com>
# Project Homepage: http://www.auracode.top
#

"""
Bridge FastAPI 服务器

提供 REST API + WebSocket 端点，支持多会话远程控制。
REST API 用于会话管理和消息发送，WebSocket 用于实时事件推送。
"""

import asyncio
import base64
import binascii
import difflib
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from contextlib import asynccontextmanager
from dataclasses import asdict
from typing import Any, Dict, List, Optional, Set

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from bridge.auth import SimpleTokenAuth
from bridge.config import BridgeServerConfig
from bridge.manager import BridgeSessionManager
from bridge.types import BridgeEvent, BridgeEventType, SessionConfig, is_path_within

logger = logging.getLogger(__name__)


# ── Pydantic 请求/响应模型 ──────────────────────────────────────────────────

class CreateSessionRequest(BaseModel):
    work_dir: str = "."
    model: str = ""
    permission_mode: str = ""
    max_iterations: Optional[int] = None  # None 表示无限制，由配置文件控制
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    restore_history: bool = True  # 是否按 work_dir 恢复最近归档会话（False=全新开始）


class CreateSessionResponse(BaseModel):
    session_id: str
    state: str
    message: str = "Session created"


class MessageRequest(BaseModel):
    content: str
    attachments: list = []  # [{path, name, type, content?}]


class FileWriteRequest(BaseModel):
    path: str
    type: str = "file"  # "file" | "directory" | "image" | "binary"
    content: Optional[str] = None  # directory 时可空；image/binary 为 data URL(base64)


class FileRenameRequest(BaseModel):
    old_path: str
    new_path: str


class PermissionRequest(BaseModel):
    request_id: str
    behavior: str  # "allow" | "deny"
    message: str = ""


class StatusResponse(BaseModel):
    uptime: float
    total_sessions: int
    active_sessions: int
    max_sessions: int
    host: str
    port: int


class SessionInfoResponse(BaseModel):
    session_id: str
    state: str
    work_dir: str
    model: str
    created_at: float
    event_count: int
    last_activity: float
    title: str
    current_activity: Optional[Dict[str, Any]] = None
    round_count: int = 0
    archived: bool = False  # True=磁盘归档会话（需 resume 恢复后才能交互）


class EventResponse(BaseModel):
    event_id: str
    type: str
    session_id: str
    data: Dict[str, Any]
    timestamp: float


class ModelSwitchRequest(BaseModel):
    model: str
    # 自定义模型可携带独立的接口地址与密钥；省略则沿用会话既有的引擎配置。
    base_url: Optional[str] = None
    api_key: Optional[str] = None


class ModeSwitchRequest(BaseModel):
    # 运行时切换会话权限模式：normal / auto / plan / bypass
    permission_mode: str


class InterruptResponse(BaseModel):
    status: str
    session_id: str


class ModelSwitchResponse(BaseModel):
    status: str
    session_id: str
    old_model: str
    new_model: str


class LLMConfigResponse(BaseModel):
    """当前引擎 LLM 配置（api_key 绝不返回明文，只给是否已设置）"""
    provider: str = ""
    model: str = ""
    base_url: str = ""
    has_api_key: bool = False
    default_model: str = ""  # bridge 服务端当前默认模型（新建会话未指定时采用）


class LLMConfigUpdate(BaseModel):
    provider: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None


class ModelCatalogItem(BaseModel):
    id: str
    provider: str = ""
    note: str = ""


class ModelsResponse(BaseModel):
    models: List[ModelCatalogItem] = []
    default: str = ""


# 模型目录（前端下拉的真实来源，取代原先硬编码的 MODEL_OPTIONS）。
# 仅为常用候选；最终可用模型以用户实际配置/填入为准。
_MODEL_CATALOG = [
    ModelCatalogItem(id="GLM-4-Flash", provider="zhipu", note="免费 · 实测可用（也是 fallback）"),
    ModelCatalogItem(id="glm-4.7-flash", provider="zhipu", note="免费档/强健"),
    ModelCatalogItem(id="glm-4.7", provider="zhipu", note="付费"),
    ModelCatalogItem(id="glm-4.6", provider="zhipu", note="付费"),
    ModelCatalogItem(id="glm-4.5-air", provider="zhipu", note="付费"),
    ModelCatalogItem(id="GLM-5.3-Flash", provider="zhipu", note="注意：当前 Key 余额"),
    ModelCatalogItem(id="glm-5.3-flashx", provider="zhipu", note="注意：当前 Key 余额"),
    ModelCatalogItem(id="deepseek-chat", provider="deepseek", note="需另配 Key/BaseURL"),
    ModelCatalogItem(id="gpt-4o", provider="openai", note="OpenAI 兼容"),
]


# ── 全局状态 ─────────────────────────────────────────────────────────────────

_server_config: Optional[BridgeServerConfig] = None
_auth: Optional[SimpleTokenAuth] = None
_manager: Optional[BridgeSessionManager] = None
_start_time: float = 0.0

# WebSocket 客户端管理
_ws_clients: List[WebSocket] = []  # 全局事件流客户端
_ws_session_clients: Dict[str, List[WebSocket]] = {}  # 会话事件流客户端 {session_id: [ws]}
_ws_lock = asyncio.Lock()

# 事件队列（从同步线程桥接到异步）
_event_loop: Optional[asyncio.AbstractEventLoop] = None


# ── 事件桥接 ─────────────────────────────────────────────────────────────────

def _on_event(event: BridgeEvent):
    """
    从 BridgeSession 线程回调（同步）。
    使用 run_coroutine_threadsafe 将事件投递到 async 事件循环。
    """
    if _event_loop is not None and not _event_loop.is_closed():
        asyncio.run_coroutine_threadsafe(
            _broadcast_event(event), _event_loop
        )


async def _broadcast_event(event: BridgeEvent):
    """广播事件到所有已连接的 WebSocket 客户端"""
    payload = json.dumps(event.to_dict(), ensure_ascii=False)

    # 1. 全局事件流
    disconnected: List[WebSocket] = []
    for ws in _ws_clients:
        try:
            await ws.send_text(payload)
        except Exception:
            disconnected.append(ws)
    # 清理断开的连接
    for ws in disconnected:
        if ws in _ws_clients:
            _ws_clients.remove(ws)

    # 2. 对应会话的事件流
    sid = event.session_id
    if sid in _ws_session_clients:
        disconnected_session: List[WebSocket] = []
        for ws in _ws_session_clients[sid]:
            try:
                await ws.send_text(payload)
            except Exception:
                disconnected_session.append(ws)
        for ws in disconnected_session:
            if ws in _ws_session_clients[sid]:
                _ws_session_clients[sid].remove(ws)
        if not _ws_session_clients[sid]:
            del _ws_session_clients[sid]


# ── FastAPI App ──────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动/关闭生命周期"""
    global _manager, _event_loop, _start_time

    _event_loop = asyncio.get_running_loop()
    _start_time = time.time()

    # 创建管理器并绑定事件回调
    _manager = BridgeSessionManager(
        max_sessions=_server_config.max_sessions,
        event_callback=_on_event,
    )

    # 启动过期会话清理定时任务
    cleanup_task = asyncio.create_task(_periodic_cleanup())

    logger.info(
        f"Bridge server started on {_server_config.host}:{_server_config.port}"
    )
    logger.info(f"Auth token: {_auth.get_token()}")

    yield

    # ── 优雅关闭流程 ──
    # 1. 广播 server_shutting_down 事件，让 WS 客户端提前感知
    shutdown_event = BridgeEvent(
        type=BridgeEventType.SERVER_SHUTTING_DOWN.value,
        session_id="",
        data={"message": "Server is shutting down"},
    )
    await _broadcast_event(shutdown_event)

    # 2. 等待 2s 让客户端收到关闭通知
    await asyncio.sleep(2.0)

    # 3. 取消清理任务
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass

    # 4. 停止所有会话
    if _manager:
        _manager.stop_all()
    logger.info("Bridge server stopped")


async def _periodic_cleanup():
    """定期清理过期会话（每 5 分钟）"""
    while True:
        await asyncio.sleep(300)
        if _manager:
            cleaned = _manager.cleanup_stale_sessions()
            if cleaned > 0:
                logger.info(f"Periodic cleanup: {cleaned} sessions removed")


def _safe_file_target(work_dir: str, path: str) -> str:
    """将相对 path 解析到 work_dir 下，做路径遍历防护，返回绝对路径。

    复用 is_path_within（os.path.commonpath 分量比较），避免 startswith 的前缀碰撞弱点
    （如 work_dir=.../proj 允许写入 .../proj-evil）。失败抛 HTTPException。

    注意：本函数对 write/rename 保持严格语义——拒绝 "." / "./"（不允许直接
    操作工作目录根）。只读/列举类端点请直接用 is_path_within，"." 会被判为合法。
    """
    if not path or path in (".", "./"):
        raise HTTPException(status_code=400, detail="Invalid path")
    wd_abs = os.path.abspath(work_dir or ".")
    tgt_abs = os.path.abspath(os.path.normpath(os.path.join(wd_abs, path)))
    if not is_path_within(wd_abs, tgt_abs):
        raise HTTPException(status_code=403, detail="Path traversal denied")
    return tgt_abs


def create_app(config: Optional[BridgeServerConfig] = None) -> FastAPI:
    """创建并配置 FastAPI 应用"""
    global _server_config, _auth

    _server_config = config or BridgeServerConfig()
    _auth = SimpleTokenAuth(token=_server_config.auth_token)

    app = FastAPI(
        title="AuraCode Bridge Server",
        description="Multi-session remote control for AuraCode AI assistant",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS 中间件：允许浏览器跨域访问（测试页面需要）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── REST API 端点 ────────────────────────────────────────────────

    @app.get("/api/status", response_model=StatusResponse)
    async def get_status(auth: bool = Depends(_auth.verify)):
        """服务器状态"""
        return StatusResponse(
            uptime=time.time() - _start_time,
            total_sessions=_manager.session_count,
            active_sessions=_manager.active_count,
            max_sessions=_server_config.max_sessions,
            host=_server_config.host,
            port=_server_config.port,
        )

    @app.post("/api/sessions", response_model=CreateSessionResponse)
    async def create_session(
        req: CreateSessionRequest,
        auth: bool = Depends(_auth.verify),
    ):
        """创建新会话"""
        try:
            # 调试日志：打印收到的参数
            print(f"\n[CREATE SESSION] 收到请求参数:")
            print(f"  work_dir: {req.work_dir}")
            print(f"  model: {req.model or _server_config.default_model}")
            print(f"  permission_mode: {req.permission_mode or _server_config.default_permission_mode}")
            print(f"  api_key: {'✅ 已提供 (' + req.api_key[:8] + '...)' if req.api_key else '❌ 未提供 (将读环境变量)'}")
            print(f"  base_url: {req.base_url or '❌ 未提供 (将读环境变量)'}")

            cfg = SessionConfig(
                work_dir=req.work_dir,
                model=req.model or _live_default_model(),
                permission_mode=req.permission_mode or _server_config.default_permission_mode,
                max_iterations=req.max_iterations,
                # 前端未显式传 key/url 时，回退到 config.yaml 的 llm.*（由前端配置界面持久化），
                # 再退到环境变量。这样「前端改配置」对新会话真正生效。
                api_key=req.api_key or _live_llm_value("api_key") or None,
                base_url=req.base_url or _live_llm_value("base_url") or None,
                restore_history=req.restore_history,
            )
            session = _manager.create_session(cfg)
            return CreateSessionResponse(
                session_id=session.session_id,
                state=session.state.value,
            )
        except RuntimeError as e:
            raise HTTPException(status_code=409, detail=str(e))

    @app.get("/api/sessions", response_model=List[SessionInfoResponse])
    async def list_sessions(auth: bool = Depends(_auth.verify)):
        """列出所有会话"""
        infos = _manager.list_sessions()
        return [SessionInfoResponse(**info.to_dict()) for info in infos]

    @app.get("/api/sessions/{session_id}", response_model=SessionInfoResponse)
    async def get_session(
        session_id: str,
        auth: bool = Depends(_auth.verify),
    ):
        """获取会话详情"""
        session = _manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        info = session.get_info()
        return SessionInfoResponse(**info.to_dict())

    @app.post("/api/sessions/{session_id}/message")
    async def send_message(
        session_id: str,
        req: MessageRequest,
        auth: bool = Depends(_auth.verify),
    ):
        """发送消息到会话（支持附件）"""
        if not _manager.send_message(session_id, req.content, attachments=req.attachments):
            raise HTTPException(status_code=404, detail="Session not found or stopped")
        return {"status": "sent", "session_id": session_id}

    @app.post("/api/sessions/{session_id}/permission")
    async def respond_permission(
        session_id: str,
        req: PermissionRequest,
        auth: bool = Depends(_auth.verify),
    ):
        """回复权限请求"""
        if req.behavior not in ("allow", "deny"):
            raise HTTPException(status_code=400, detail="behavior must be 'allow' or 'deny'")
        ok = _manager.respond_permission(
            session_id, req.request_id, req.behavior, req.message
        )
        if not ok:
            raise HTTPException(
                status_code=404,
                detail="Session or permission request not found",
            )
        return {"status": "responded", "request_id": req.request_id}

    @app.post("/api/sessions/{session_id}/stop")
    async def stop_session(
        session_id: str,
        auth: bool = Depends(_auth.verify),
    ):
        """停止会话"""
        if not _manager.stop_session(session_id):
            raise HTTPException(status_code=404, detail="Session not found")
        return {"status": "stopped", "session_id": session_id}

    @app.post(
        "/api/sessions/{session_id}/interrupt",
        response_model=InterruptResponse,
    )
    async def interrupt_session(
        session_id: str,
        auth: bool = Depends(_auth.verify),
    ):
        """
        中断当前 turn（不终止会话）。

        参考标准实现 interrupt control_request。
        """
        session = _manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        ok = _manager.interrupt_session(session_id)
        return InterruptResponse(
            status="interrupted" if ok else "not_running",
            session_id=session_id,
        )

    @app.post(
        "/api/sessions/{session_id}/model",
        response_model=ModelSwitchResponse,
    )
    async def switch_model(
        session_id: str,
        req: ModelSwitchRequest,
        auth: bool = Depends(_auth.verify),
    ):
        """
        热切换模型（仅空闲时生效）。

        参考标准实现 set_model control_request。
        """
        session = _manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        old_model = session.config.model
        ok = _manager.switch_model(
            session_id,
            req.model,
            base_url=req.base_url,
            api_key=req.api_key,
        )
        if not ok:
            # switch_model 仅在会话非空闲时返回 False（模型未变化已按幂等成功处理）
            raise HTTPException(
                status_code=409,
                detail="会话正在执行任务，请等当前任务完成（或先停止）后再切换模型",
            )
        return ModelSwitchResponse(
            status="switched",
            session_id=session_id,
            old_model=old_model,
            new_model=req.model,
        )

    @app.post("/api/sessions/{session_id}/mode")
    async def set_mode(
        session_id: str,
        req: ModeSwitchRequest,
        auth: bool = Depends(_auth.verify),
    ):
        """
        运行时切换会话权限模式（normal/auto/plan/bypass）。

        解决：顶部「绕过/自动/计划」选择器此前只影响新建会话，已运行的会话
        仍用建会话时的模式，导致切到「绕过」后 run_command 仍弹权限窗。
        这里把新模式实时下发到正在运行的会话。
        """
        mode = req.permission_mode
        if mode not in ("normal", "auto", "plan", "bypass"):
            raise HTTPException(status_code=400, detail="invalid permission_mode")
        session = _manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        old_mode = session.config.permission_mode
        session.set_permission_mode(mode)
        return {
            "status": "switched",
            "session_id": session_id,
            "old_mode": old_mode,
            "new_mode": mode,
        }

    @app.post("/api/sessions/{session_id}/clear")
    async def clear_context(
        session_id: str,
        auth: bool = Depends(_auth.verify),
    ):
        """
        清空会话对话上下文（消息历史），保留 token/cost 累计。

        供前端「清空上下文」按钮调用：让当前会话从空白历史重新开始，
        下一轮对话自动重新初始化系统提示。
        """
        session = _manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        ok = _manager.clear_context(session_id)
        return {
            "status": "cleared" if ok else "no_op",
            "session_id": session_id,
        }

    @app.get("/api/config/llm", response_model=LLMConfigResponse)
    async def get_llm_config(
        auth: bool = Depends(_auth.verify),
    ):
        """读取当前引擎 LLM 配置（api_key 不返回明文）。"""
        info = _read_llm_config()
        info["default_model"] = _server_config.default_model if _server_config else ""
        return LLMConfigResponse(**info)

    @app.put("/api/config/llm", response_model=LLMConfigResponse)
    async def put_llm_config(
        req: LLMConfigUpdate,
        auth: bool = Depends(_auth.verify),
    ):
        """保存 LLM 配置到 config.yaml 的 llm.* 并热更新。

        仅写入提供的非空字段（null 跳过，不覆盖未改项）；api_key 为空串表示清空。
        """
        patch = {k: v for k, v in req.model_dump().items() if v is not None}
        allowed = {"provider", "model", "base_url", "api_key"}
        patch = {k: v for k, v in patch.items() if k in allowed}
        if not patch:
            raise HTTPException(status_code=400, detail="未提供任何可更新的配置字段")
        info = _write_llm_config(patch)
        info["default_model"] = _server_config.default_model if _server_config else ""
        return LLMConfigResponse(**info)

    @app.get("/api/models", response_model=ModelsResponse)
    async def list_models(
        auth: bool = Depends(_auth.verify),
    ):
        """返回可选模型目录（前端下拉来源）+ 当前默认模型。"""
        return ModelsResponse(
            models=_MODEL_CATALOG,
            default=_server_config.default_model if _server_config else "",
        )

    @app.get("/api/commands")
    async def list_commands(
        auth: bool = Depends(_auth.verify),
    ):
        """列出引擎内置命令（供前端 # 命令自动补全）。"""
        try:
            from commands.registry import COMMAND_REGISTRY
        except Exception:
            return {"commands": []}
        cmds = []
        for name, cmd in COMMAND_REGISTRY.items():
            cmds.append(
                {
                    "name": name,
                    "description": cmd.get("description", ""),
                    "category": cmd.get("category", ""),
                    "args_help": cmd.get("args_help", ""),
                }
            )
        cmds.sort(key=lambda x: x["name"])
        return {"commands": cmds}

    @app.delete("/api/sessions/{session_id}")
    async def delete_session(
        session_id: str,
        auth: bool = Depends(_auth.verify),
    ):
        """删除会话（停止活跃会话 + 清理磁盘归档文件）"""
        if not _manager.delete_session_full(session_id):
            raise HTTPException(status_code=404, detail="Session not found")
        return {"status": "deleted", "session_id": session_id}

    @app.post("/api/sessions/{session_id}/resume")
    async def resume_session(
        session_id: str,
        auth: bool = Depends(_auth.verify),
    ):
        """从磁盘归档恢复会话为活跃会话（历史消息回放）"""
        try:
            session = _manager.resume_session(session_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="Archived session not found")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return {
            "status": "resumed",
            "session_id": session.session_id,
            "restored_from": session_id,
            "work_dir": session.config.work_dir,
        }

    @app.get("/api/archives")
    async def list_archives(
        auth: bool = Depends(_auth.verify),
    ):
        """归档会话列表（专门的归档管理页数据源，与活跃会话列表分离）"""
        return [SessionInfoResponse(**a.to_dict()) for a in _manager.list_archives()]

    @app.get("/api/archives/{session_id}/messages")
    async def get_archive_messages(
        session_id: str,
        limit: int = 500,
        auth: bool = Depends(_auth.verify),
    ):
        """读取归档会话的消息历史（只读查看）"""
        try:
            msgs = _manager.get_archive_messages(session_id, limit)
        except KeyError:
            raise HTTPException(status_code=404, detail="Archived session not found")
        return {"session_id": session_id, "messages": msgs}

    @app.post("/api/sessions/{session_id}/archive")
    async def archive_session(
        session_id: str,
        auth: bool = Depends(_auth.verify),
    ):
        """手动归档：停止会话并写盘归档，从活跃列表移除"""
        if not _manager.archive_session(session_id):
            raise HTTPException(status_code=404, detail="Session not found")
        return {"status": "archived", "session_id": session_id}

    @app.get(
        "/api/sessions/{session_id}/events",
        response_model=List[EventResponse],
    )
    async def get_events(
        session_id: str,
        since: int = Query(0, ge=0),
        auth: bool = Depends(_auth.verify),
    ):
        """获取会话事件历史"""
        events = _manager.get_session_events(session_id, since)
        if events is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return events

    # ── 文件浏览 API（右侧面板）──────────────────────────────────────────

    @app.get("/api/sessions/{session_id}/files")
    async def list_files(
        session_id: str,
        path: str = Query("."),
        auth: bool = Depends(_auth.verify),
    ):
        """列出会话工作目录下的文件/子目录"""
        session = _manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        work_dir = session.config.work_dir or "."
        # 解析相对路径
        target = os.path.normpath(os.path.join(work_dir, path))
        if not os.path.isdir(target):
            raise HTTPException(status_code=404, detail=f"Not a directory: {path}")
        # 安全检查：防止路径遍历
        if not is_path_within(work_dir, target):
            raise HTTPException(status_code=403, detail="Path traversal denied")
        try:
            entries = []
            for name in sorted(os.listdir(target)):
                full = os.path.join(target, name)
                try:
                    st = os.stat(full)
                    entries.append({
                        "name": name,
                        "type": "dir" if os.path.isdir(full) else "file",
                        "size": st.st_size,
                        "modified": st.st_mtime,
                    })
                except OSError:
                    entries.append({"name": name, "type": "unknown", "size": 0, "modified": 0})
            # 目录排前，文件排后
            entries.sort(key=lambda e: (0 if e["type"] == "dir" else 1, e["name"].lower()))
            rel = os.path.relpath(target, work_dir)
            return {"path": rel if rel != "." else "", "entries": entries}
        except PermissionError:
            raise HTTPException(status_code=403, detail="Permission denied")

    @app.get("/api/sessions/{session_id}/files/content")
    async def read_file_content(
        session_id: str,
        path: str = Query(...),
        max_lines: int = Query(200, ge=1, le=2000),
        auth: bool = Depends(_auth.verify),
    ):
        """读取会话工作目录下的文件内容"""
        session = _manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        work_dir = session.config.work_dir or "."
        target = os.path.normpath(os.path.join(work_dir, path))
        if not os.path.isfile(target):
            raise HTTPException(status_code=404, detail=f"Not a file: {path}")
        if not is_path_within(work_dir, target):
            raise HTTPException(status_code=403, detail="Path traversal denied")
        try:
            with open(target, "r", encoding="utf-8", errors="replace") as f:
                lines = []
                for i, line in enumerate(f):
                    if i >= max_lines:
                        break
                    lines.append(line.rstrip("\n"))
                total_lines = i + 1
                truncated = f.readline() != ""
            ext = os.path.splitext(target)[1].lstrip(".")
            return {
                "path": path,
                "content": "\n".join(lines),
                "lines": total_lines,
                "truncated": truncated,
                "ext": ext,
                "size": os.path.getsize(target),
            }
        except PermissionError:
            raise HTTPException(status_code=403, detail="Permission denied")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/sessions/{session_id}/diff")
    async def get_file_diff(
        session_id: str,
        path: str = Query(...),
        auth: bool = Depends(_auth.verify),
    ):
        """返回某次会话内某文件的改前/改后内容与 unified diff。

        改前内容取自工具自动生成的 .bak 备份：write_file / replace_in_file 每次
        编辑前都会把改前原文备份到 <文件所在目录>/.backup/<名>.<时间戳>.bak。
        取该文件最早的一份 = 进入会话前的原始版本；改后取当前磁盘文件。
        因此无论整文件写入还是局部替换，都能给出真实对比，且不依赖 git。
        """
        session = _manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        work_dir = session.config.work_dir or "."
        # 与工具侧一致地解析路径：绝对路径直接用，相对路径基于 work_dir
        if os.path.isabs(path):
            abs_path = os.path.abspath(path)
        else:
            abs_path = os.path.abspath(os.path.join(work_dir, path))
        if not is_path_within(work_dir, abs_path):
            raise HTTPException(status_code=403, detail="Path traversal denied")

        # 改后：当前磁盘文件；不存在（被删除）则视为空
        after = ""
        after_exists = os.path.isfile(abs_path)
        if after_exists:
            try:
                with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                    after = f.read()
            except (PermissionError, OSError):
                raise HTTPException(status_code=403, detail="Permission denied")

        # 改前：该文件所在目录 .backup 下、同名最早的一份 .bak（文件名含零填充时间戳，
        # 字典序 == 时间序；最早一份 = 进入会话前的原始版本）
        before = ""
        source = "none"
        bak_dir = os.path.join(os.path.dirname(abs_path) or ".", ".backup")
        basename = os.path.basename(abs_path)
        if os.path.isdir(bak_dir):
            cands = [
                f for f in os.listdir(bak_dir)
                if f.startswith(basename + ".") and f.endswith(".bak")
            ]
            cands.sort()
            if cands:
                try:
                    with open(os.path.join(bak_dir, cands[0]), "r", encoding="utf-8", errors="replace") as f:
                        before = f.read()
                    source = "backup"
                except (PermissionError, OSError):
                    before = ""

        before_lines = before.splitlines(keepends=True) if before else []
        after_lines = after.splitlines(keepends=True) if after else []
        unified = "".join(difflib.unified_diff(
            before_lines, after_lines,
            fromfile="before", tofile="after", lineterm="",
        ))
        return {
            "path": path,
            "before": before,
            "after": after,
            "unified": unified,
            # "backup"=有改前版本；"none"=全新文件/无历史备份
            "source": source,
            "after_exists": after_exists,
        }

    @app.delete("/api/sessions/{session_id}/files")
    async def delete_file(
        session_id: str,
        path: str = Query(...),
        auth: bool = Depends(_auth.verify),
    ):
        """删除会话工作目录下的文件"""
        session = _manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        work_dir = session.config.work_dir or "."
        target = os.path.normpath(os.path.join(work_dir, path))
        if not is_path_within(work_dir, target):
            raise HTTPException(status_code=403, detail="Path traversal denied")
        if not os.path.exists(target):
            raise HTTPException(status_code=404, detail=f"File not found: {path}")
        if os.path.isdir(target):
            raise HTTPException(status_code=400, detail="Cannot delete directory")
        try:
            os.remove(target)
            return {"success": True, "path": path, "message": f"Deleted: {path}"}
        except PermissionError:
            raise HTTPException(status_code=403, detail="Permission denied")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/sessions/{session_id}/files")
    async def write_file(
        session_id: str,
        req: FileWriteRequest,
        auth: bool = Depends(_auth.verify),
    ):
        """写入/上传文件，或创建目录（type='directory'）。

        - 目录：仅需 path
        - 文件：content 为文本（UTF-8 写入）或 data URL（data:...;base64,.. 二进制解码）
        """
        session = _manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        work_dir = session.config.work_dir or "."
        target = _safe_file_target(work_dir, req.path)
        rel = os.path.relpath(target, os.path.abspath(work_dir)).replace("\\", "/")

        # 创建目录
        if req.type == "directory":
            try:
                os.makedirs(target, exist_ok=True)
                return {"success": True, "path": rel, "type": "directory"}
            except OSError as e:
                raise HTTPException(status_code=500, detail=str(e))

        # 写文件：必须有 content
        if req.content is None:
            raise HTTPException(status_code=400, detail="content is required for file write")
        if len(req.content) > 10 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="File too large (max 10MB)")

        overwritten = os.path.exists(target)
        # 建父目录（裸文件名时 dirname 为空，跳过避免 makedirs('') 崩溃）
        parent = os.path.dirname(target)
        if parent:
            try:
                os.makedirs(parent, exist_ok=True)
            except OSError as e:
                raise HTTPException(status_code=500, detail=str(e))

        # data URL 图片/二进制 → base64 解码后写二进制；否则当文本写
        content = req.content
        if content.startswith("data:") and ";base64," in content and "," in content:
            _, _, payload = content.partition(",")
            try:
                data = base64.b64decode(payload)
            except (binascii.Error, ValueError):
                raise HTTPException(status_code=400, detail="Invalid base64 payload")
            try:
                with open(target, "wb") as f:
                    f.write(data)
            except IsADirectoryError:
                raise HTTPException(status_code=400, detail="Target is a directory")
            except OSError as e:
                raise HTTPException(status_code=500, detail=str(e))
        else:
            try:
                with open(target, "w", encoding="utf-8") as f:
                    f.write(content)
            except IsADirectoryError:
                raise HTTPException(status_code=400, detail="Target is a directory")
            except OSError as e:
                raise HTTPException(status_code=500, detail=str(e))

        try:
            size = os.path.getsize(target)
        except OSError:
            size = len(content)
        return {
            "success": True,
            "path": rel,
            "size": size,
            "overwritten": overwritten,
        }

    @app.post("/api/sessions/{session_id}/files/rename")
    async def rename_file(
        session_id: str,
        req: FileRenameRequest,
        auth: bool = Depends(_auth.verify),
    ):
        """重命名/移动文件或目录（限制在 work_dir 内）"""
        session = _manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        work_dir = session.config.work_dir or "."
        old_target = _safe_file_target(work_dir, req.old_path)
        new_target = _safe_file_target(work_dir, req.new_path)
        if not os.path.exists(old_target):
            raise HTTPException(status_code=404, detail=f"Not found: {req.old_path}")
        try:
            if os.path.exists(new_target):
                raise HTTPException(status_code=409, detail=f"Target exists: {req.new_path}")
            try:
                os.replace(old_target, new_target)
            except OSError:
                # 跨卷时 os.replace 失败，回退到 shutil.move
                shutil.move(old_target, new_target)
        except HTTPException:
            raise
        except OSError as e:
            raise HTTPException(status_code=500, detail=str(e))
        return {
            "success": True,
            "old_path": os.path.relpath(old_target, os.path.abspath(work_dir)).replace("\\", "/"),
            "new_path": os.path.relpath(new_target, os.path.abspath(work_dir)).replace("\\", "/"),
        }

    @app.get("/api/sessions/{session_id}/files/search")
    async def search_files(
        session_id: str,
        q: str = Query(..., min_length=1),
        limit: int = Query(20, ge=1, le=100),
        auth: bool = Depends(_auth.verify),
    ):
        """搜索会话工作目录下的文件（按文件名匹配）"""
        session = _manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        work_dir = session.config.work_dir or "."
        results = []
        q_lower = q.lower()
        try:
            for root, dirs, files in os.walk(work_dir):
                # 跳过隐藏目录和常见非源码目录
                dirs[:] = [d for d in dirs if not d.startswith('.')
                           and d not in ('node_modules', '__pycache__', '.git', 'venv', '.venv')]
                rel_root = os.path.relpath(root, work_dir)
                for fname in files:
                    if q_lower in fname.lower():
                        rel_path = os.path.join(rel_root, fname) if rel_root != '.' else fname
                        rel_path = rel_path.replace('\\', '/')
                        fpath = os.path.join(root, fname)
                        try:
                            sz = os.path.getsize(fpath)
                        except:
                            sz = 0
                        results.append({
                            "name": fname,
                            "path": rel_path,
                            "size": sz,
                            "type": "file",
                        })
                        if len(results) >= limit:
                            break
                if len(results) >= limit:
                    break
        except Exception as e:
            logger.warning(f"File search error: {e}")
        return {"query": q, "results": results, "total": len(results)}

    # ── SkillHub 技能商店 ────────────────────────────────────────────
    # 封装 skillhub CLI（~/.local/bin/skillhub，python 实现）。
    # 安装目标固定为用户级 ~/.auracode/skills/（引擎支持 @namespace 两层布局）。

    def _decode_pipe(data: bytes) -> str:
        """子进程管道输出解码：优先 utf-8（子进程已被强制 UTF-8 输出），
        失败退回 gbk（Windows 本地代码页），最后 replace 兜底。"""
        for enc in ("utf-8", "gbk"):
            try:
                return data.decode(enc)
            except UnicodeDecodeError:
                continue
        return data.decode("utf-8", errors="replace")

    def _run_skillhub(*args: str, timeout: float = 60.0) -> tuple:
        """执行 skillhub CLI，返回 (returncode, stdout, stderr)。

        候选顺序：
          1) ~/.local/bin/skillhub[.exe]  —— 官方安装位置
          2) ~/.skillhub/skills_store_cli.py —— python 直跑（Windows 下首选，
             因为 ~/.local/bin/skillhub 是 bash 包裹脚本，Windows 无法直接 exec）
        调用时剥离 http(s)_proxy 环境变量，避免经由（沙箱/公司）代理访问
        skillhub.cn 失败；CLI 自身仍走系统默认网络栈。
        强制子进程以 UTF-8 输出：Windows 下 Python 子进程的 stdout 为管道时
        默认用本地代码页（GBK），print 含 emoji 直接 UnicodeEncodeError，
        含中文则被父进程按 utf-8 解成乱码（两个症状同一根因）。
        """
        home = os.path.expanduser("~")
        if os.name == "nt":
            candidates = [
                os.path.join(home, ".skillhub", "skills_store_cli.py"),
                os.path.join(home, ".local", "bin", "skillhub.exe"),
                os.path.join(home, ".local", "bin", "skillhub"),
            ]
        else:
            candidates = [
                os.path.join(home, ".local", "bin", "skillhub"),
                os.path.join(home, ".skillhub", "skills_store_cli.py"),
            ]

        env = dict(os.environ)
        for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY",
                  "all_proxy", "ALL_PROXY"):
            env.pop(k, None)
        # 强制子进程 UTF-8 写 stdout/stderr（PYTHONUTF8 连文件系统编码一起管）
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"

        for target in candidates:
            if not os.path.exists(target):
                continue
            cmd = [sys.executable, target, *args] if target.endswith(".py") \
                else [target, *args]
            try:
                # 捕获原始字节自行解码（不依赖子进程遵守编码约定时的兜底）
                r = subprocess.run(cmd, capture_output=True,
                                   timeout=timeout, env=env)
                return r.returncode, _decode_pipe(r.stdout), _decode_pipe(r.stderr)
            except Exception as e:
                logger.warning(f"skillhub 调用失败 ({target}): {e}")
                continue
        return 1, "", "skillhub CLI 未安装（参考 https://skillhub.cn/install/skillhub.md）"

    def _skillhub_user_skills_dir() -> str:
        return os.path.join(os.path.expanduser("~"), ".auracode", "skills")

    @app.get("/api/skillhub/search")
    async def skillhub_search(
        q: str = Query(..., min_length=1),
        limit: int = Query(20, ge=1, le=50),
        auth: bool = Depends(_auth.verify),
    ):
        """搜索 SkillHub 技能商店"""
        code, out, err = _run_skillhub("search", q, "--json", timeout=30)
        if code != 0:
            raise HTTPException(status_code=502, detail=f"skillhub search failed: {err or out}")
        try:
            # 输出可能混有非 JSON 前缀（如 Downloading: ...），取第一个 { 起
            idx = out.find("{")
            data = json.loads(out[idx:]) if idx >= 0 else {}
        except json.JSONDecodeError:
            raise HTTPException(status_code=502, detail=f"skillhub 返回无法解析: {out[:200]}")
        results = data.get("results", [])[:limit]
        # 标注安装状态（按 publicSlug 匹配已装目录名）
        installed_dirs = set()
        skills_root = _skillhub_user_skills_dir()
        if os.path.isdir(skills_root):
            for ns in os.listdir(skills_root):
                ns_path = os.path.join(skills_root, ns)
                if os.path.isdir(ns_path):
                    for s in os.listdir(ns_path):
                        installed_dirs.add(s)
        for item in results:
            slug = item.get("publicSlug", "")
            ns = (item.get("namespace") or {}).get("handle", "")
            item["installed"] = slug in installed_dirs
            item["namespace_handle"] = ns
        return {"query": q, "results": results, "total": len(results)}

    @app.post("/api/skillhub/install")
    async def skillhub_install(
        req: Dict[str, Any] = Body(...),
        auth: bool = Depends(_auth.verify),
    ):
        """安装 SkillHub 技能到用户级 ~/.auracode/skills/"""
        slug = str(req.get("slug", "")).strip()
        namespace = str(req.get("namespace", "")).strip()
        if not slug:
            raise HTTPException(status_code=400, detail="缺少 slug")
        target_dir = _skillhub_user_skills_dir()
        args = ["install", slug, "--dir", target_dir, "--json"]
        if namespace:
            args += ["--namespace", namespace]
        # 下载可能较慢，放宽超时
        code, out, err = _run_skillhub(*args, timeout=180)
        if code != 0:
            raise HTTPException(status_code=502, detail=f"安装失败: {err or out}")
        try:
            idx = out.find("{")
            data = json.loads(out[idx:]) if idx >= 0 else {}
        except json.JSONDecodeError:
            data = {"success": True, "raw": out[:500]}
        if not data.get("success", False):
            raise HTTPException(status_code=502, detail=f"安装失败: {out[:300]}")
        # 找到实际落盘的技能名（@ns/slug 两层）
        installed_name = slug
        ns_dir = os.path.join(target_dir, f"@{namespace}") if namespace else None
        search_dir = ns_dir if ns_dir and os.path.isdir(ns_dir) else target_dir
        if os.path.isdir(search_dir):
            for d in os.listdir(search_dir):
                if os.path.isdir(os.path.join(search_dir, d)) and not d.startswith((".", "@")):
                    if d == slug or slug in d:
                        installed_name = d
                        break
        return {
            "success": True,
            "slug": data.get("slug", slug),
            "installed_name": installed_name,
            "version": data.get("version", ""),
            "target_dir": data.get("targetDir", target_dir),
            "note": "已安装到用户级 ~/.auracode/skills/，新会话自动加载；对话中可让 agent activate_skill 立即使用",
        }

    # ── WebSocket 端点 ────────────────────────────────────────────────

    @app.websocket("/ws/events")
    async def ws_global_events(
        websocket: WebSocket,
        token: Optional[str] = Query(None),
    ):
        """全局事件流 WebSocket（所有会话的事件）"""
        # Token 验证（WebSocket 通过 query param 传 token）
        if not token or token != _auth.get_token():
            await websocket.close(code=4001, reason="Unauthorized")
            return

        await websocket.accept()
        _ws_clients.append(websocket)
        logger.info(f"Global WS client connected ({len(_ws_clients)} total)")

        try:
            while True:
                # 保持连接：接收心跳或忽略客户端消息
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
        except WebSocketDisconnect:
            pass
        finally:
            if websocket in _ws_clients:
                _ws_clients.remove(websocket)
            logger.info(f"Global WS client disconnected ({len(_ws_clients)} total)")

    @app.websocket("/ws/sessions/{session_id}/events")
    async def ws_session_events(
        websocket: WebSocket,
        session_id: str,
        token: Optional[str] = Query(None),
        last_seq: int = Query(0, ge=0),
    ):
        """
        单会话事件流 WebSocket。

        支持断线重连：通过 last_seq 参数只推送断线期间的新事件，
        避免全量重放（参考标准 echo 去重机制）。
        """
        # Token 验证
        if not token or token != _auth.get_token():
            await websocket.close(code=4001, reason="Unauthorized")
            return

        # 检查会话是否存在
        session = _manager.get_session(session_id)
        if not session:
            await websocket.close(code=4004, reason="Session not found")
            return

        await websocket.accept()

        if session_id not in _ws_session_clients:
            _ws_session_clients[session_id] = []
        _ws_session_clients[session_id].append(websocket)
        logger.info(
            f"Session WS client connected: {session_id} "
            f"(last_seq={last_seq}, "
            f"{len(_ws_session_clients[session_id])} total)"
        )

        # 重放缺失事件（仅推送 last_seq 之后的新事件）
        if last_seq > 0:
            events = session.replay_events(last_seq)
            logger.info(
                f"WS reconnect replay: {len(events)} events "
                f"from seq {last_seq} for {session_id}"
            )
        else:
            # 首次连接：推送全量历史
            events = session.get_events()

        for ev in events:
            try:
                await websocket.send_text(json.dumps(ev, ensure_ascii=False))
            except Exception:
                break

        try:
            while True:
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
        except WebSocketDisconnect:
            pass
        finally:
            if session_id in _ws_session_clients:
                if websocket in _ws_session_clients[session_id]:
                    _ws_session_clients[session_id].remove(websocket)
                if not _ws_session_clients[session_id]:
                    del _ws_session_clients[session_id]
            logger.info(
                f"Session WS client disconnected: {session_id}"
            )

    return app


def _default_model_from_engine_config() -> str:
    """从引擎 config.yaml 读 llm.model 作为 Bridge 会话默认模型。

    修复：Bridge 的 default_model 此前硬编码 glm-4-flash，与引擎 config.yaml 脱节，
    导致桌面端会话用的模型比 CLI 模式弱（长任务每轮 stop、不连锁工具调用）。
    读不到时保持原默认兜底，零行为变化。
    """
    try:
        from config.manager import config_manager
        config_manager.load(os.path.abspath("config.yaml"))
        m = config_manager.get("llm.model")
        return m if isinstance(m, str) and m.strip() else "glm-4-flash"
    except Exception:
        return "glm-4-flash"


def _read_llm_config() -> Dict[str, Any]:
    """从引擎 config.yaml 读取 llm 配置（api_key 只返回是否已设置，绝不返回明文）"""
    info: Dict[str, Any] = {
        "provider": "",
        "model": "",
        "base_url": "",
        "has_api_key": False,
    }
    try:
        from config.manager import config_manager
        llm = config_manager.get("llm", {})
        if not isinstance(llm, dict):
            llm = {}
        info["provider"] = llm.get("provider", "") or ""
        info["model"] = llm.get("model", "") or ""
        info["base_url"] = llm.get("base_url", "") or ""
        api_key = llm.get("api_key") or os.environ.get("OPENAI_API_KEY")
        info["has_api_key"] = bool(api_key and str(api_key).strip())
    except Exception as e:
        logger.warning(f"read llm config failed: {e}")
    return info


def _write_llm_config(patch: Dict[str, Any]) -> Dict[str, Any]:
    """把 llm.* 字段写回 config.yaml 并热更新：保存 + reload +
    更新 bridge 服务端默认模型（新会话立即生效）。

    patch 中只接受 provider/model/base_url/api_key；null/None 字段跳过（不覆盖）。
    """
    from config.manager import config_manager

    # 用已知配置文件路径（绝对化，避免相对路径在 Windows 上 save 时 makedirs('') 报错）
    cfg_path = getattr(config_manager, "_config_path", None) or "config.yaml"
    cfg_path = os.path.abspath(cfg_path)
    config_manager.load(cfg_path)
    allowed = {"provider", "model", "base_url", "api_key"}
    for k, v in patch.items():
        if k not in allowed or v is None:
            continue
        # api_key 允许空串（清空），其余字段空串跳过避免写脏值
        if k != "api_key" and isinstance(v, str) and not v.strip():
            continue
        config_manager.set(f"llm.{k}", v)
    config_manager.save()
    config_manager.reload()
    # 热更新 bridge 默认模型，使后续新建会话采用新默认
    new_model = config_manager.get("llm.model")
    if isinstance(new_model, str) and new_model.strip() and _server_config is not None:
        _server_config.default_model = new_model
    return _read_llm_config()


def _live_llm_value(key: str) -> Optional[str]:
    """建会话时回退读 config.yaml 的 llm.<key>（仅当非空）；
    用于让前端保存的 provider/key/url 真正被新会话采用。"""
    try:
        from config.manager import config_manager
        v = config_manager.get(f"llm.{key}")
        if isinstance(v, str) and v.strip():
            return v
    except Exception:
        pass
    return None


def _live_default_model() -> str:
    return _live_llm_value("model") or (
        _server_config.default_model if _server_config else "glm-4-flash"
    )


# ── 启动入口 ─────────────────────────────────────────────────────────────────

def start_bridge_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    max_sessions: int = 5,
    auth_token: Optional[str] = None,
):
    """启动 Bridge 服务器（阻塞）"""
    import secrets

    config = BridgeServerConfig(
        host=host,
        port=port,
        max_sessions=max_sessions,
        auth_token=auth_token or secrets.token_urlsafe(32),
        default_model=_default_model_from_engine_config(),
    )

    app = create_app(config)

    print(f"\n{'=' * 60}")
    print(f"  AuraCode Bridge Server")
    print(f"{'=' * 60}")
    print(f"  Host:       {config.host}")
    print(f"  Port:       {config.port}")
    print(f"  Max Sessions: {config.max_sessions}")
    print(f"  Auth Token: {config.auth_token}")
    print(f"{'=' * 60}")
    print(f"\n  REST API:   http://{config.host}:{config.port}/api/")
    print(f"  WebSocket:  ws://{config.host}:{config.port}/ws/events")
    print(f"  Status:     http://{config.host}:{config.port}/api/status")
    print(f"  Docs:       http://{config.host}:{config.port}/docs")
    print(f"{'=' * 60}\n")

    # 确保 bridge 模块的 INFO 日志可见
    logging.getLogger("bridge").setLevel(logging.INFO)

    uvicorn.run(app, host=config.host, port=config.port, log_level="info")


if __name__ == "__main__":
    start_bridge_server()
