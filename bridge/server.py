"""
Bridge FastAPI 服务器

提供 REST API + WebSocket 端点，支持多会话远程控制。
REST API 用于会话管理和消息发送，WebSocket 用于实时事件推送。
"""

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import asdict
from typing import Any, Dict, List, Optional, Set

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from bridge.auth import SimpleTokenAuth
from bridge.config import BridgeServerConfig
from bridge.manager import BridgeSessionManager
from bridge.types import BridgeEvent, SessionConfig

logger = logging.getLogger(__name__)


# ── Pydantic 请求/响应模型 ──────────────────────────────────────────────────

class CreateSessionRequest(BaseModel):
    work_dir: str = "."
    model: str = ""
    permission_mode: str = ""
    max_iterations: int = 20
    api_key: Optional[str] = None
    base_url: Optional[str] = None


class CreateSessionResponse(BaseModel):
    session_id: str
    state: str
    message: str = "Session created"


class MessageRequest(BaseModel):
    content: str


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


class EventResponse(BaseModel):
    event_id: str
    type: str
    session_id: str
    data: Dict[str, Any]
    timestamp: float


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

    logger.info(
        f"Bridge server started on {_server_config.host}:{_server_config.port}"
    )
    logger.info(f"Auth token: {_auth.get_token()}")

    yield

    # 关闭：停止所有会话
    if _manager:
        _manager.stop_all()
    logger.info("Bridge server stopped")


def create_app(config: Optional[BridgeServerConfig] = None) -> FastAPI:
    """创建并配置 FastAPI 应用"""
    global _server_config, _auth

    _server_config = config or BridgeServerConfig()
    _auth = SimpleTokenAuth(token=_server_config.auth_token)

    app = FastAPI(
        title="OpenCode Bridge Server",
        description="Multi-session remote control for OpenCode AI assistant",
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
                model=req.model or _server_config.default_model,
                permission_mode=req.permission_mode or _server_config.default_permission_mode,
                max_iterations=req.max_iterations,
                api_key=req.api_key,
                base_url=req.base_url,
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
        """发送消息到会话"""
        if not _manager.send_message(session_id, req.content):
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

    @app.delete("/api/sessions/{session_id}")
    async def delete_session(
        session_id: str,
        auth: bool = Depends(_auth.verify),
    ):
        """删除会话（先停止再移除）"""
        if not _manager.remove_session(session_id):
            raise HTTPException(status_code=404, detail="Session not found")
        return {"status": "deleted", "session_id": session_id}

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
    ):
        """单会话事件流 WebSocket"""
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
            f"({len(_ws_session_clients[session_id])} total)"
        )

        # 先发送已有事件历史
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
    )

    app = create_app(config)

    print(f"\n{'=' * 60}")
    print(f"  OpenCode Bridge Server")
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
