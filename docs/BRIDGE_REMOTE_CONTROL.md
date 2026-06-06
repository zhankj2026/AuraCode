# Bridge / Remote Control 架构分析

## 1. 概述

Bridge（Remote Control）是 Claude Code 的远程控制系统，允许用户通过 **claude.ai Web UI** 远程操控本地 CLI 实例。  
核心链路：**Web UI → CCR Server → 本地 CLI Bridge**

整个系统包含 **31 个文件、约 12000+ 行 TypeScript 代码**，涵盖两种运行模式和两代传输协议。

---

## 2. 两种运行模式

### 2.1 Standalone Bridge（独立模式）
- **入口**: `claude remote-control` 命令
- **核心文件**: `bridgeMain.ts` (3000 行)
- **工作机制**: 独立进程，通过子进程 spawn 运行 Claude CLI
- **多会话**: 支持最多 32 个并发会话（`--capacity` 参数）
- **Spawn 模式**:
  - `single-session` — 单会话，完成即退出
  - `worktree` — git worktree 隔离，每个会话独立分支
  - `same-dir` — 共享工作目录

### 2.2 REPL Bridge（内嵌模式）
- **入口**: `/remote-control` 斜杠命令
- **核心文件**: `replBridge.ts` (2407 行) + `remoteBridgeCore.ts` (1009 行)
- **工作机制**: 在已有 REPL 会话内启用，共享当前对话上下文
- **会话数**: 单会话（当前 REPL 进程）

---

## 3. 两代传输协议

### 3.1 V1 — 基于 Environments API（env-based）

```
本地 CLI                              CCR Server                        Web UI
   |                                     |                                |
   |-- POST /v1/environments/bridge ---->|  注册为"环境"                   |
   |<-- {environment_id, secret} --------|                                |
   |                                     |                                |
   |-- GET /v1/env/{id}/work/poll ------>|  长轮询等待任务                  |
   |<-- WorkResponse {secret, data} -----|  (用户从 Web 发起会话)           |
   |                                     |                                |
   |  [decode WorkSecret]                |                                |
   |  [base64url → JSON]                 |                                |
   |  {session_ingress_token,            |                                |
   |   api_base_url, sources, auth}      |                                |
   |                                     |                                |
   |-- WebSocket (ws/wss) -------------->|  建立实时通信                    |
   |   session_ingress/ws/{sessionId}    |                                |
   |<========= 双向消息流 ===============>|<====== 用户输入/查看 ===========>|
   |                                     |                                |
   |-- POST .../work/{id}/heartbeat ---->|  维持租约（每 20s）              |
   |-- POST .../work/{id}/ack ---------->|  确认工作                       |
```

**关键文件**: `bridgeApi.ts`, `replBridge.ts`, `bridgeMain.ts`

### 3.2 V2 — 无环境层（env-less）

```
本地 CLI                              CCR Server                        Web UI
   |                                     |                                |
   |-- POST /v1/code/sessions ---------->|  直接创建会话（无环境注册）       |
   |<-- {session: {id: "cse_*"}} --------|                                |
   |                                     |                                |
   |-- POST .../sessions/{id}/bridge --->|  获取 worker JWT                |
   |<-- {worker_jwt, expires_in,         |  (每次调用自动 bump epoch)       |
   |     api_base_url, worker_epoch} ----|                                |
   |                                     |                                |
   |  [SSE 读流]  /worker/events/stream  |                                |
   |  [HTTP 写]   /worker/events (POST)  |                                |
   |  [心跳]      /worker/heartbeat      |                                |
   |<========= 双向通信 =================>|<====== 用户输入/查看 ===========>|
```

**关键文件**: `remoteBridgeCore.ts`, `codeSessionApi.ts`, `replBridgeTransport.ts`

**核心优势**: 省去 register/poll/ack/heartbeat/deregister 整个环境生命周期，一步到位获取 worker JWT。

---

## 4. 核心组件详解

### 4.1 文件职责矩阵

| 文件 | 行数 | 职责 |
|------|------|------|
| `bridgeMain.ts` | 3000 | Standalone 主循环：多会话管理、心跳、令牌刷新、worktree |
| `replBridge.ts` | 2407 | REPL Bridge v1 核心：环境注册→轮询→传输→消息路由 |
| `remoteBridgeCore.ts` | 1009 | REPL Bridge v2 核心：直接会话创建→JWT→SSE/CCR 传输 |
| `bridgeApi.ts` | 540 | Environments REST API 客户端 |
| `codeSessionApi.ts` | 169 | CCR v2 Code Session API 客户端 |
| `sessionRunner.ts` | 551 | 子进程 spawn 与 NDJSON 通信 |
| `replBridgeTransport.ts` | 371 | 传输抽象层（v1=WebSocket, v2=SSE+CCRClient） |
| `bridgeMessaging.ts` | 462 | 消息解析、回环去重、控制请求处理 |
| `initReplBridge.ts` | 570 | REPL Bridge 启动编排：门控、OAuth、标题派生 |
| `jwtUtils.ts` | 257 | JWT 刷新调度器 |
| `bridgeUI.ts` | 531 | 终端 UI：QR码、状态行、会话列表 |
| `bridgePointer.ts` | 211 | 崩溃恢复指针文件 |
| `createSession.ts` | 385 | 会话 CRUD API |
| `workSecret.ts` | 128 | WorkSecret 解码 + URL 构建 |
| `bridgeEnabled.ts` | 203 | 功能开关（GrowthBook + OAuth + 策略） |
| `bridgeConfig.ts` | 49 | 认证令牌和 URL 解析 |
| `flushGate.ts` | 72 | 历史 flush 期间的写消息队列 |
| `inboundMessages.ts` | 81 | 入站消息解析与图片格式规范化 |
| `replBridgeHandle.ts` | 37 | 全局单例句柄 |
| `bridgePermissionCallbacks.ts` | 44 | 权限响应类型定义 |

### 4.2 WorkSecret 解码流程

```
Server 返回 secret (base64url 编码)
    ↓
decodeWorkSecret(secret)
    ↓ base64url decode → JSON parse
    ↓ 验证 version === 1
    ↓
WorkSecret {
  version: 1,
  session_ingress_token: "sk-ant-si-...",   // WebSocket 认证
  api_base_url: "https://...",               // API 基址
  sources: [{type: "git_repository", ...}],  // 代码源
  auth: [{type: "session_access_token", ...}]// 认证信息
}
    ↓
buildSdkUrl(apiBaseUrl, sessionId)
    ↓ https → wss, http → ws
    ↓ 生产: /v1/session_ingress/ws/{id}
    ↓ 本地: /v2/session_ingress/ws/{id}
    ↓
WebSocket URL 就绪
```

### 4.3 消息通信协议

#### 出站消息（CLI → Server → Web）
- `SDKMessage`: 带 `type` 鉴别器的联合类型
  - `user` — 用户消息
  - `assistant` — AI 回复
  - `result` — 会话结果
  - `system` (subtype=local_command) — 系统命令事件

#### 入站消息（Web → Server → CLI）
- `user` 消息 — 用户在 Web 端的输入
- `control_response` — 权限审批结果
- `control_request` — 服务端控制指令

#### 控制请求（Server → CLI）
| subtype | 用途 |
|---------|------|
| `initialize` | 初始化握手 |
| `set_model` | 切换模型 |
| `set_max_thinking_tokens` | 设置思考 token 上限 |
| `set_permission_mode` | 切换权限模式 |
| `interrupt` | 中断当前操作 |

### 4.4 权限审批流程

```
子进程检测到 tool_use 需要权限
    ↓
发送 control_request (subtype=can_use_tool)
    ↓
Bridge 转发到 Server (transport.write)
    ↓ reportState('requires_action')
Server 推送权限提示到 Web UI
    ↓
用户在 Web 点击 Allow/Deny
    ↓
Server 发回 control_response
    ↓ {behavior: 'allow' | 'deny', updatedInput?, updatedPermissions?}
Bridge 转发回子进程 (stdin NDJSON)
    ↓
子进程继续/取消 tool 执行
```

### 4.5 消息去重机制

- **BoundedUUIDSet** — 环形缓冲区（容量 2000），FIFO 淘汰
- **回环去重**: `recentPostedUUIDs` — 过滤自己发出的消息的服务端回显
- **入站去重**: `recentInboundUUIDs` — 防止重发的入站消息被重复处理
- **FlushGate** — 历史 flush 期间排队新消息，保证顺序

### 4.6 JWT 令牌刷新

```python
# 伪代码
scheduler = createTokenRefreshScheduler(
    refreshBufferMs=5*60*1000,  # 过期前5分钟刷新
    getAccessToken=getOAuthToken,
    onRefresh=rebuildTransport,
)
scheduler.scheduleFromExpiresIn(sessionId, credentials.expires_in)

# 刷新时：
# 1. 重新获取 OAuth token
# 2. 调用 POST /bridge 获取新 worker_jwt（epoch 自动+1）
# 3. 重建传输层（新 JWT + 新 epoch + 续接 seq-num）
# 4. 调度下一次刷新
```

### 4.7 崩溃恢复（BridgePointer）

```
写入时机: Bridge 会话创建后
文件位置: ~/.claude/projects/{sanitized-cwd}/bridge-pointer.json
内容: { sessionId, environmentId, source: "standalone"|"repl" }
TTL: 4 小时（基于文件 mtime）

启动时检测:
  - 发现未过期指针 → 提示用户恢复上次会话
  - worktree 感知: 扫描所有 worktree 兄弟目录寻找最新指针
  - 正常退出时清除文件
```

---

## 5. Standalone Bridge 主循环

```
runBridgeLoop(config, environmentId, environmentSecret, api, spawner, ...)
    │
    ├── 注册环境 → environment_id + environment_secret
    │
    ├── 主循环 (while !signal.aborted):
    │     ├── pollForWork() — 长轮询获取任务
    │     │
    │     ├── 收到 work:
    │     │     ├── decodeWorkSecret(secret)
    │     │     ├── 检查容量 (activeSessions.size < maxSessions)
    │     │     ├── 创建 worktree（如果 spawnMode=worktree）
    │     │     ├── spawner.spawn(opts, dir) → SessionHandle
    │     │     ├── acknowledgeWork()
    │     │     └── 加入 activeSessions Map
    │     │
    │     ├── 心跳所有活跃 work items (每 20s)
    │     │     └── auth_failed → reconnectSession 重新排队
    │     │
    │     ├── 会话完成检测 (onSessionDone):
    │     │     ├── stopWork()
    │     │     ├── 清理 worktree
    │     │     ├── 从 activeSessions 移除
    │     │     └── capacityWake.signal() 唤醒等待
    │     │
    │     └── 容量满时 capacityWake.wait() 阻塞
    │
    └── 退出清理:
          ├── stopWork() 所有活跃会话
          ├── deregisterEnvironment()
          └── 移除所有 worktree
```

---

## 6. Session Runner（子进程管理）

```typescript
// 子进程启动参数
const args = [
  '--print',                    // 非交互模式
  '--sdk-url', sdkUrl,         // WebSocket URL
  '--session-id', sessionId,   // 会话 ID
  '--input-format', 'stream-json',   // stdin NDJSON
  '--output-format', 'stream-json',  // stdout NDJSON
  '--model', model,
  '--permission-mode', mode,
]

const child = spawn(execPath, args, {
  cwd: dir,
  stdio: ['pipe', 'pipe', 'pipe'],
  env: { ...process.env, CLAUDE_CODE_SESSION_ACCESS_TOKEN: token }
})

// stdout NDJSON 解析
child.stdout → readline → JSON.parse → 
  extractActivities() → tool_start / text / result / error
  detect control_request → onPermissionRequest 回调

// stdin 写入（token 刷新）
child.stdin.write(JSON.stringify({
  type: 'update_environment_variables',
  session_access_token: newToken
}) + '\n')
```

---

## 7. 状态机

### Bridge 状态
```
ready → connected → (reconnecting ↔ connected) → failed
```

### 会话状态（SessionState）
```
idle → running → (requires_action ↔ running) → idle
```

### FlushGate 状态
```
inactive → start() → active → end() → [drain items] → inactive
                              → drop() → [discard items] → inactive
```

---

## 8. 关键设计模式

| 模式 | 用途 | 示例文件 |
|------|------|---------|
| 工厂函数 | API 客户端创建 | `createBridgeApiClient()`, `createSessionSpawner()` |
| 传输抽象 | v1/v2 统一接口 | `ReplBridgeTransport` 类型 |
| 令牌调度 | JWT 自动刷新 | `createTokenRefreshScheduler()` |
| 环形缓冲 | 消息去重 | `BoundedUUIDSet` |
| 崩溃恢复 | 进程意外退出后恢复 | `BridgePointer` 文件 |
| 指数退避 | 连接重试 | `withRetry()`, backoff 配置 |
| 回调注入 | 解耦业务逻辑 | `onInboundMessage`, `onPermissionResponse` |
| 全局单例 | 跨模块访问 | `replBridgeHandle.ts` |

---

# opencode 远程控制实现方案

## 设计目标

基于 Claude Code Bridge 的核心思想，为 opencode 设计一套**简化的远程控制系统**：

- **去除** Anthropic 专有依赖（OAuth、GrowthBook、CCR Server、Environments API）
- **保留** 核心远程控制能力：远程发送指令、查看输出、审批权限
- **简化** 为 HTTP + WebSocket 的轻量级自托管方案
- **支持** 单会话远程控制（最常用场景）

## 架构设计

```
┌──────────────┐     HTTP/WS      ┌──────────────────┐     subprocess     ┌──────────────┐
│  Web Client  │ ◄──────────────► │  Bridge Server    │ ◄──────────────►  │  opencode    │
│  (浏览器)    │   REST + WS      │  (Python FastAPI) │    NDJSON stdin   │  CLI Agent   │
└──────────────┘                   └──────────────────┘    NDJSON stdout  └──────────────┘
                                          │
                                     Token Auth
                                     (简单 Bearer)
```

### 三组件架构

1. **Bridge Server** — FastAPI 应用，提供 REST API + WebSocket
2. **Bridge Worker** — 管理 opencode 子进程，转发 NDJSON
3. **Web Client** — 简单 HTML/JS 前端（或 curl/httpie 命令行）

## 模块结构

```
opencode/bridge/
├── __init__.py
├── server.py          # FastAPI 服务器（REST + WebSocket）
├── worker.py          # 子进程管理（spawn、监控、通信）
├── auth.py            # 简单 Token 认证
├── types.py           # 类型定义
└── config.py          # 配置管理
```

## 详细设计

### 1. types.py — 类型定义

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any

class BridgeState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    REQUIRES_ACTION = "requires_action"
    FAILED = "failed"

class SessionState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    REQUIRES_ACTION = "requires_action"

@dataclass
class SessionInfo:
    session_id: str
    state: SessionState = SessionState.IDLE
    created_at: float = 0.0
    prompt: str = ""
    
@dataclass
class PermissionRequest:
    request_id: str
    tool_name: str
    tool_input: dict
    description: str
    
@dataclass  
class PermissionResponse:
    request_id: str
    behavior: str  # "allow" | "deny"
    message: str = ""

@dataclass
class BridgeEvent:
    """从子进程解析的事件"""
    type: str           # "assistant", "tool_use", "result", "error", "permission_request"
    data: dict = field(default_factory=dict)
    timestamp: float = 0.0
```

### 2. worker.py — 子进程管理

```python
import asyncio
import json
import subprocess
import uuid
from typing import Optional, Callable, Awaitable

class BridgeWorker:
    """管理 opencode CLI 子进程的生命周期和通信"""
    
    def __init__(self, work_dir: str = "."):
        self.work_dir = work_dir
        self.process: Optional[asyncio.subprocess.Process] = None
        self.session_id: str = str(uuid.uuid4())
        self.state: SessionState = SessionState.IDLE
        self.events: list[BridgeEvent] = []
        self._event_callbacks: list[Callable] = []
        self._permission_future: Optional[asyncio.Future] = None
        self._read_task: Optional[asyncio.Task] = None
        
    async def start(self, model: str = "gpt-4", extra_args: list[str] | None = None):
        """启动 opencode 子进程"""
        args = [
            "python", "-m", "opencode.cli",
            "--print",                          # 非交互模式
            "--output-format", "stream-json",   # NDJSON 输出
            "--input-format", "stream-json",    # NDJSON 输入
            "--model", model,
        ]
        if extra_args:
            args.extend(extra_args)
            
        self.process = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.work_dir,
        )
        self._read_task = asyncio.create_task(self._read_stdout())
        self.state = SessionState.IDLE
        
    async def send_message(self, content: str):
        """向子进程发送用户消息"""
        if not self.process or not self.process.stdin:
            raise RuntimeError("Process not started")
            
        msg = {
            "type": "user",
            "message": {"role": "user", "content": content},
            "uuid": str(uuid.uuid4()),
        }
        self.process.stdin.write(json.dumps(msg).encode() + b"\n")
        await self.process.stdin.drain()
        self.state = SessionState.RUNNING
        
    async def send_permission_response(self, response: PermissionResponse):
        """回复权限审批请求"""
        if self._permission_future and not self._permission_future.done():
            self._permission_future.set_result(response)
            self._permission_future = None
            self.state = SessionState.RUNNING
            
    async def _read_stdout(self):
        """持续读取子进程 stdout NDJSON"""
        assert self.process and self.process.stdout
        while True:
            line = await self.process.stdout.readline()
            if not line:
                break
            try:
                data = json.loads(line.decode().strip())
                event = self._parse_event(data)
                if event:
                    self.events.append(event)
                    # 通知所有监听者
                    for cb in self._event_callbacks:
                        await cb(event) if asyncio.iscoroutinefunction(cb) else cb(event)
            except json.JSONDecodeError:
                continue
                
    def _parse_event(self, data: dict) -> Optional[BridgeEvent]:
        """解析 NDJSON 事件"""
        msg_type = data.get("type", "")
        
        if msg_type == "assistant":
            return BridgeEvent(type="assistant", data=data)
        elif msg_type == "result":
            self.state = SessionState.IDLE
            return BridgeEvent(type="result", data=data)
        elif msg_type == "control_request":
            # 权限请求
            request = data.get("request", {})
            if request.get("subtype") == "can_use_tool":
                self.state = SessionState.REQUIRES_ACTION
                perm_req = PermissionRequest(
                    request_id=data.get("request_id", ""),
                    tool_name=request.get("tool_name", ""),
                    tool_input=request.get("input", {}),
                    description=request.get("description", ""),
                )
                return BridgeEvent(type="permission_request", data=perm_req.__dict__)
        elif msg_type == "error":
            return BridgeEvent(type="error", data=data)
            
        return None
        
    def on_event(self, callback: Callable):
        """注册事件回调"""
        self._event_callbacks.append(callback)
        
    async def stop(self):
        """停止子进程"""
        if self._read_task:
            self._read_task.cancel()
        if self.process:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self.process.kill()
```

### 3. server.py — FastAPI 服务器

```python
from fastapi import FastAPI, WebSocket, HTTPException, Depends
from fastapi.security import HTTPBearer
from pydantic import BaseModel
import asyncio
import uuid

app = FastAPI(title="opencode Bridge Server")

# 全局状态
worker: Optional[BridgeWorker] = None
ws_clients: list[WebSocket] = []
AUTH_TOKEN: str = ""  # 启动时生成

class SendMessageRequest(BaseModel):
    content: str
    
class PermissionResponseRequest(BaseModel):
    request_id: str
    behavior: str  # "allow" | "deny"
    message: str = ""

# ── REST API ──────────────────────────────────────────

@app.post("/api/session/start")
async def start_session(model: str = "gpt-4", work_dir: str = "."):
    """启动新的 bridge 会话"""
    global worker
    if worker and worker.process and worker.process.returncode is None:
        raise HTTPException(400, "Session already active")
    
    worker = BridgeWorker(work_dir=work_dir)
    worker.on_event(broadcast_event)  # 广播到所有 WS 客户端
    await worker.start(model=model)
    return {"session_id": worker.session_id, "state": "started"}

@app.post("/api/session/message")
async def send_message(req: SendMessageRequest):
    """发送用户消息到当前会话"""
    if not worker:
        raise HTTPException(400, "No active session")
    await worker.send_message(req.content)
    return {"status": "sent"}

@app.post("/api/session/permission")
async def respond_permission(req: PermissionResponseRequest):
    """回复权限审批请求"""
    if not worker:
        raise HTTPException(400, "No active session")
    await worker.send_permission_response(
        PermissionResponse(
            request_id=req.request_id,
            behavior=req.behavior,
            message=req.message,
        )
    )
    return {"status": "responded"}

@app.post("/api/session/stop")
async def stop_session():
    """停止当前会话"""
    global worker
    if worker:
        await worker.stop()
        worker = None
    return {"status": "stopped"}

@app.get("/api/session/status")
async def get_status():
    """获取当前会话状态"""
    if not worker:
        return {"state": "no_session"}
    return {
        "session_id": worker.session_id,
        "state": worker.state.value,
        "event_count": len(worker.events),
    }

# ── WebSocket — 实时事件流 ────────────────────────────

@app.websocket("/ws/events")
async def websocket_events(ws: WebSocket):
    """WebSocket 连接：实时推送子进程事件"""
    await ws.accept()
    ws_clients.append(ws)
    try:
        # 发送历史事件
        if worker:
            for event in worker.events[-50:]:  # 最近50条
                await ws.send_json({"type": "history", "data": event.__dict__})
        # 保持连接
        while True:
            # 接收客户端消息（可用于心跳等）
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_json({"type": "pong"})
    except Exception:
        pass
    finally:
        ws_clients.remove(ws)

async def broadcast_event(event: BridgeEvent):
    """广播事件到所有 WebSocket 客户端"""
    dead = []
    for ws in ws_clients:
        try:
            await ws.send_json(event.__dict__)
        except Exception:
            dead.append(ws)
    for ws in dead:
        ws_clients.remove(ws)
```

### 4. auth.py — 简单认证

```python
import secrets
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

class SimpleAuth:
    """简单 Bearer Token 认证"""
    
    def __init__(self):
        self.token: str = secrets.token_urlsafe(32)
        
    def verify(self, credentials: HTTPAuthorizationCredentials = Depends(security)):
        if credentials.credentials != self.token:
            raise HTTPException(status_code=401, detail="Invalid token")
        return True
        
    def get_token(self) -> str:
        return self.token

auth = SimpleAuth()
```

### 5. config.py — 配置

```python
from dataclasses import dataclass

@dataclass
class BridgeConfig:
    host: str = "127.0.0.1"
    port: int = 8765
    work_dir: str = "."
    model: str = "gpt-4"
    auto_start: bool = False      # 启动时自动创建会话
    max_history: int = 500        # 最大事件历史
    heartbeat_interval: int = 30  # WebSocket 心跳间隔(秒)
```

## 启动方式

```bash
# 启动 Bridge 服务器
python -m opencode.bridge.server --port 8765 --work-dir /path/to/project

# 输出:
# Bridge Server started at http://127.0.0.1:8765
# Auth Token: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
# 
# API:
#   POST /api/session/start    启动会话
#   POST /api/session/message  发送消息
#   POST /api/session/permission  回复权限
#   POST /api/session/stop     停止会话
#   GET  /api/session/status   查看状态
#   WS   /ws/events            实时事件流
```

## 客户端使用示例

```python
import requests, websockets, json, asyncio

TOKEN = "your-auth-token"
BASE = "http://127.0.0.1:8765"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

# 1. 启动会话
r = requests.post(f"{BASE}/api/session/start", headers=HEADERS,
                  params={"model": "gpt-4", "work_dir": "."})
session = r.json()

# 2. 监听事件（异步）
async def listen():
    async with websockets.connect(
        f"ws://127.0.0.1:8765/ws/events",
        additional_headers=HEADERS
    ) as ws:
        async for msg in ws:
            event = json.loads(msg)
            if event["type"] == "permission_request":
                # 自动审批 or 提示用户
                print(f"Permission needed: {event['data']['description']}")
            elif event["type"] == "assistant":
                print(f"AI: {event['data']}")

# 3. 发送消息
requests.post(f"{BASE}/api/session/message", headers=HEADERS,
              json={"content": "帮我写一个 Python 快速排序"})

# 4. 回复权限
requests.post(f"{BASE}/api/session/permission", headers=HEADERS,
              json={"request_id": "xxx", "behavior": "allow"})
```

## 与 Claude Code Bridge 的对比

| 特性 | Claude Code Bridge | opencode Bridge |
|------|-------------------|-----------------|
| 服务端 | Anthropic CCR Server（云端） | 自托管 FastAPI 服务器 |
| 认证 | OAuth + JWT + GrowthBook | 简单 Bearer Token |
| 传输 | WebSocket/SSE + CCRClient | WebSocket + REST |
| 多会话 | 最多 32 个并发 | 单会话（简化） |
| Spawn 模式 | single/worktree/same-dir | 单目录 |
| 消息去重 | BoundedUUIDSet + FlushGate | 简单事件列表 |
| JWT 刷新 | 复杂的调度器 + epoch 管理 | 无需（自托管） |
| 崩溃恢复 | BridgePointer 文件 | 简单状态检测 |
| 代码量 | ~12000 行 TypeScript | ~400 行 Python |

## 核心简化点

1. **去除 Environments API 层** — 不需要云端注册/轮询/心跳
2. **去除 OAuth/JWT 复杂认证** — 自托管用简单 Token 即可
3. **去除多会话/worktree** — 聚焦单会话远程控制
4. **去除消息去重复杂机制** — 本地通信无需处理网络分区
5. **统一为 FastAPI** — REST + WebSocket 一套框架搞定
