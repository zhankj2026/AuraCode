# MCP 协议集成

AuraCode 完整实现了 [Model Context Protocol](https://modelcontextprotocol.io/) 客户端，可以连接外部 MCP 服务器，动态扩展工具能力。

---

## 概述

MCP 允许你将外部工具和服务接入 AuraCode，例如数据库查询、第三方 API、文件系统等。MCP 工具与内置工具统一调用，对 AI 透明。

```
AuraCode
  └── MCP Manager
        ├── 服务器 A (stdio)  → 数据库工具
        ├── 服务器 B (SSE)    → 文件系统工具
        └── 服务器 C (WS)     → 自定义 API
```

---

## 配置

在 `config.yaml` 中添加 MCP 服务器：

```yaml
mcp:
  servers:
    # 使用 stdio 传输
    postgres:
      command: "npx"
      args: ["-y", "@my/postgres-mcp"]
      transport: stdio
      env:
        DATABASE_URL: "postgresql://user:pass@localhost/db"

    # 使用 SSE 传输
    filesystem:
      command: "node"
      args: ["fs-server.js"]
      transport: sse
      url: "http://localhost:3001"

    # 使用 WebSocket 传输
    custom-api:
      command: "python"
      args: ["mcp_server.py"]
      transport: websocket
      url: "ws://localhost:3002"
      auto_reconnect: true
```

### 传输方式

| 方式 | 说明 | 适用场景 |
|------|------|----------|
| `stdio` | 标准输入/输出 | 本地进程 |
| `sse` | Server-Sent Events | HTTP 服务 |
| `websocket` | WebSocket 双向通信 | 实时交互 |

---

## 管理命令

```
> /mcp list

MCP 服务器 (3 个):
  ✅ postgres        stdio    已连接   工具: 4
  ✅ filesystem      sse      已连接   工具: 6
  ❌ custom-api      ws       未连接

> /mcp connect custom-api

正在连接 custom-api...
✅ 已连接，注册了 3 个工具

> /mcp disconnect postgres

✅ 已断开 postgres

> /mcp tools postgres

postgres 提供的工具:
  - query       执行 SQL 查询
  - list_tables 列出所有表
  - describe    查看表结构
  - insert      插入数据
```

---

## 动态工具注册

MCP 服务器提供的工具会自动注册到 AuraCode 的工具系统，与内置工具统一调用：

```
> 查询 users 表中最近注册的 10 个用户

[AI 自动调用 MCP 工具]:
  tool: postgres.query
  input: {"sql": "SELECT * FROM users ORDER BY created_at DESC LIMIT 10"}
```

---

## 调用链追踪

MCP 工具调用过程可观测，便于调试：

```
[MCP] postgres.query
  请求: {"sql": "SELECT count(*) FROM orders"}
  响应: {"rows": [{"count": 1523}]}
  耗时: 45ms
```

---

## 服务器自动发现

启动时 AuraCode 会自动扫描并连接配置中的所有 MCP 服务器，支持自动重连。

---

## 相关命令

| 命令 | 说明 |
|------|------|
| `/mcp list` | 列出所有 MCP 服务器 |
| `/mcp connect <name>` | 连接服务器 |
| `/mcp disconnect <name>` | 断开服务器 |
| `/mcp tools <name>` | 查看服务器提供的工具 |
