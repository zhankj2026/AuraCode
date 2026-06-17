# Bridge 远程控制

Bridge 是基于 FastAPI 的 REST + WebSocket 远程控制服务，支持从浏览器或其他客户端实时操控 OpenCode。

---

## 启动 Bridge

```bash
# 默认配置
python cli.py --bridge

# 自定义端口和最大会话数
python cli.py --bridge --bridge-port 9000 --bridge-max-sessions 10

# 指定认证 Token
python cli.py --bridge --bridge-token my-secret-token
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--bridge` | 启用 Bridge 模式 | `false` |
| `--bridge-port` | 服务端口 | `8765` |
| `--bridge-host` | 绑定地址 | `127.0.0.1` |
| `--bridge-max-sessions` | 最大并行会话数 | `5` |
| `--bridge-token` | 认证 Token | 自动生成 |

---

## REST API

### 会话管理

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/sessions` | 创建新会话 |
| `GET` | `/sessions` | 列出所有会话 |
| `GET` | `/sessions/{id}` | 获取会话详情 |
| `DELETE` | `/sessions/{id}` | 关闭会话 |

### 消息与命令

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/sessions/{id}/message` | 发送消息 |
| `POST` | `/sessions/{id}/command` | 执行命令 |

### 系统

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/health` | 健康检查 |
| `GET` | `/status` | 系统状态 |

---

## WebSocket 实时事件

连接 `ws://host:port/ws?token=xxx` 即可接收实时事件推送：

### 事件类型

| 事件 | 说明 |
|------|------|
| `session_created` | 新会话创建 |
| `tool_use` | AI 调用工具 |
| `tool_result` | 工具执行结果 |
| `assistant_message` | AI 回复消息 |
| `token_usage` | Token 消耗统计 |
| `error` | 错误通知 |
| `session_complete` | 会话任务完成 |

### 事件示例

```json
{
  "type": "tool_use",
  "data": {
    "session_id": "abc123",
    "tool": "read_file",
    "input": {"path": "src/main.py", "start_line": 1, "end_line": 50}
  }
}
```

---

## Web UI

内置 Web 控制面板（`bridge/test_bridge.html`），可直接在浏览器中操作：

```
http://localhost:8765/static/test_bridge.html
```

功能包括：
- 会话列表与管理
- 实时消息显示
- 事件面板（工具调用、Token 消耗、错误通知）
- 命令执行

---

## Token 认证

Bridge 使用 Bearer Token 进行认证：

```bash
# REST 请求
curl -H "Authorization: Bearer your-token" http://localhost:8765/sessions

# WebSocket 连接
ws://localhost:8765/ws?token=your-token
```

---

## 多会话并行

Bridge 支持同时运行多个独立会话，每个会话有自己的上下文和状态：

```
> /bridge sessions

Bridge 会话 (3 个活跃 / 最大 5):
  #1  session_abc  运行中  迭代 5/20  Token: 12,400
  #2  session_def  等待中  迭代 0/20  Token: 0
  #3  session_ghi  运行中  迭代 8/20  Token: 23,100
```

---

## 相关命令

| 命令 | 说明 |
|------|------|
| `/bridge` | Bridge 管理入口 |
| `/bridge sessions` | 查看活跃会话 |
| `/bridge status` | Bridge 服务状态 |
