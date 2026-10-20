# AuraCode 桌面客户端（Electron + React）

在已有 AuraCode Python 后端（`Bridge` 服务）之上套一层桌面壳，提供类 Codex / WorkBuddy 的体验。
**不改动任何 Python 代码**——主进程只是 `spawn` 已有的 `python cli.py --bridge`，renderer 通过 loopback + 随机 token 调 REST / WS。

## 架构

```
┌──────────────────────────────────────────────────────────┐
│  Electron 主进程 (src/main)                                │
│   - 生成随机 token + 端口，spawn `python cli.py --bridge`  │
│   - 轮询 /api/status 等待就绪                              │
│   - 通过 IPC 把 {host,port,token} 下发给渲染进程           │
└───────────────┬──────────────────────────────────────────┘
                │ IPC (bridge:config)
┌───────────────▼──────────────────────────────────────────┐
│  Preload (contextIsolation) 暴露 window.auracode          │
└───────────────┬──────────────────────────────────────────┘
                │ fetch / WebSocket → 127.0.0.1:<port>
┌───────────────▼──────────────────────────────────────────┐
│  AuraCode Bridge 后端 (既有 Python，不在本目录)           │
│   REST  /api/sessions · /message · /permission · /files   │
│   WS    /ws/events · /ws/sessions/{id}/events             │
└──────────────────────────────────────────────────────────┘
```

## 开发

前置：Node 18+，且本机可运行 `python cli.py --bridge`（需安装 AuraCode 的 Python 依赖）。

```bash
cd desktop
npm install
npm run dev
```

主进程会自动定位包含 `cli.py` 的 AuraCode 根目录（默认向上级目录探测）。
可用环境变量覆盖：

- `AURACODE_ROOT`：Python 工程根目录（含 cli.py）
- `AURACODE_PYTHON`：python 可执行文件（默认 `python` / `python3`）
- `AURACODE_PORT`：监听端口（默认 8765）
- `AURACODE_HOST`：绑定地址（默认 127.0.0.1）

## 打包（Windows NSIS）

```bash
npm run package
```

> 生产环境需把 portable Python 随应用分发（electron-builder 的 `extraResources` + `asarUnpack`），
> 并在主进程 `backend.ts` 里把 `AURACODE_PYTHON` 指向 `resources/` 内的解释器。本骨架默认复用系统 Python。

## 目录

```
desktop/
  src/main/       主进程：后端生命周期 + IPC
  src/preload/    仅暴露最小 API 给渲染进程
  src/renderer/   React UI（活动栏 / 侧栏 / 主区 / 右栏 / 设置 / 权限弹窗）
    src/api/       BridgeClient（REST+WS）与类型
    src/state/     轻量全局 store
    src/components 各 UI 组件
```

## 已实现的最小闭环

- 启动后端 → 连接 → 自动建/选会话
- 对话：发送消息、流式接收 `assistant_message` / `text_chunk`、`tool_call` / `tool_result` 事件卡片
- 权限：后端 `permission_request` 自动弹确认框，回复 `allow/deny`
- 文件：资源树列出、打开为编辑器 Tab、编辑/保存（调后端文件接口）
- 设置：分类导航页（通用/外观/快捷键/模型/技能/MCP/权限/数据管理）
- 工作区：顶栏下拉选择历史工作区 / 临时会话 / 新建 / 打开本地文件夹
