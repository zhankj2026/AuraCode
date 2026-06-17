# 架构总览

opencode 是一个基于 TAOR（Think-Act-Observe-Repeat）循环设计的 AI 编程助手，使用 Python 实现。本文档描述其整体架构、模块划分和数据流。

---

## 目录结构

```
opencode/
├── cli.py                # CLI 入口：参数解析 + 主循环
├── config.yaml           # 用户配置文件
├── requirements.txt      # Python 依赖
│
├── core/                 # 核心引擎
│   ├── agent_loop.py     # AgentLoop — TAOR 循环主体
│   ├── session_state.py  # SessionState — 会话状态管理
│   ├── context.py        # 项目上下文加载（OPENCODE.md + 技术栈检测）
│   ├── memory.py         # 记忆系统（MEMORY.md 管理 + LLM 驱动召回）
│   ├── message.py        # 消息格式化
│   ├── subagent.py       # 子代理（并行任务分派）
│   └── tool_enhancer.py  # 工具增强（自动摘要 + 幂等重试 + 输出裁剪）
│
├── tools/                # 工具系统
│   ├── registry.py       # TOOL_REGISTRY 全局注册表
│   ├── __init__.py       # 工具自动注册
│   └── builtin/          # 内置工具（50+ 个）
│       ├── read_file.py
│       ├── write_file.py
│       ├── run_command.py
│       ├── search_content.py
│       └── ...
│
├── commands/             # 命令系统
│   ├── base.py           # Command 抽象基类
│   ├── registry.py       # 命令注册表
│   └── builtin/          # 内置命令（40+ 个）
│       ├── commit.py
│       ├── compact.py
│       ├── model.py
│       └── ...
│
├── plugins/              # 插件系统
│   ├── base.py           # ToolPlugin 抽象基类
│   ├── builtin.py        # 内置插件注册表
│   ├── loader.py         # 四源插件加载器
│   └── registry.py       # PluginManifest 清单管理
│
├── hooks/                # 钩子系统
│   └── manager.py        # HookManager — 事件分发 + 优先级 + 短路
│
├── skills/               # 技能系统
│   ├── loader.py         # SkillManager — 三源技能加载
│   ├── context.py        # SkillContext 单例（AgentLoop ↔ 工具桥接）
│   └── <skill>/          # 内置技能目录
│
├── permissions/          # 权限系统
│   └── manager.py        # PermissionManager — 四级模式 + allow/deny
│
├── mcp/                  # MCP 协议集成
│   ├── client/           # MCP 客户端
│   ├── config/           # MCP 服务器配置
│   ├── transport/        # 传输层（stdio / SSE / WebSocket）
│   ├── tools/            # MCP 工具适配器
│   └── plugins/          # MCP 插件桥接
│
├── bridge/               # Bridge 远程控制
│   ├── session.py        # BridgeSession — 远程会话
│   ├── server.py         # FastAPI REST + WebSocket 服务器
│   ├── manager.py        # 多会话管理器
│   ├── types.py          # 类型定义
│   └── config.py         # Bridge 配置
│
├── services/             # 持久化服务
│   ├── session_store.py  # 会话持久化（JSON 日志）
│   ├── history_log.py    # 全局交互历史（JSONL）
│   ├── settings_store.py # 用户设置持久化
│   ├── file_history.py   # 文件修改备份
│   └── ...
│
├── config/               # 配置系统
│   └── __init__.py       # 配置加载/合并
│
└── docs/                 # 项目文档
    ├── index.md
    ├── quick-start.md
    ├── user-guide/
    ├── advanced/
    └── development/
```

---

## 核心数据流

```
用户输入
  │
  ▼
cli.py ──────────────────────────────────────────┐
  │                                               │
  ▼                                               │
AgentLoop.run()                                   │
  │                                               │
  ├─ 构建 System Prompt                           │
  │   ├─ 角色定义                                  │
  │   ├─ 项目上下文 (OPENCODE.md)                  │
  │   ├─ 记忆注入 (MEMORY.md)                      │
  │   └─ 技能激活提示                              │
  │                                               │
  ├─ TAOR 循环 ──────────────────────────────────┐│
  │   │                                           ││
  │   ├─ Think: _call_llm_streaming()             ││
  │   │   ├─ OpenAI API 流式调用                   ││
  │   │   ├─ 实时输出到终端                         ││
  │   │   └─ 累积工具调用                          ││
  │   │                                           ││
  │   ├─ Act: _execute_tool()                     ││
  │   │   ├─ PreToolUse Hook                      ││
  │   │   ├─ PermissionManager 权限检查            ││
  │   │   ├─ 工具执行 (TOOL_REGISTRY)              ││
  │   │   ├─ ToolEnhancer 增强                     ││
  │   │   └─ PostToolUse Hook                     ││
  │   │                                           ││
  │   ├─ Observe: 工具结果追加到消息历史            ││
  │   │                                           ││
  │   └─ Repeat: 继续循环或退出                     ││
  │                                               ││
  ├─ 错误恢复                                      ││
  │   ├─ API 级重试 (8 次)                         ││
  │   ├─ 轮次级重试 (1 次)                         ││
  │   ├─ 上下文压缩 + 重试                         ││
  │   └─ Fallback 模型                             ││
  │                                               ││
  └─ 返回 QueryResult ◄───────────────────────────┘│
                                                    │
  ◄─────────────────────────────────────────────────┘
  展示结果 / 保存会话
```

---

## 模块关系

```
                    ┌──────────┐
                    │  cli.py  │
                    └────┬─────┘
                         │
                    ┌────▼─────┐
              ┌─────│ AgentLoop │──────┐
              │     └────┬─────┘      │
              │          │            │
     ┌────────▼──┐  ┌───▼────┐  ┌───▼────────┐
     │ Session   │  │ Tools  │  │ Extensions │
     │ State     │  │        │  │            │
     └───────────┘  └───┬────┘  └──┬───┬──┬─┘
                        │     ┌────┘   │  │
                   ┌────▼───┐ │   ┌────┘  └────┐
                   │Registry│ │   │             │
                   └────────┘ │   │             │
                         ┌────▼┐ ┌▼─────┐ ┌────▼───┐
                         │Hooks│ │Skills│ │Plugins │
                         └─────┘ └──────┘ └────────┘
```

---

## 核心模块详解

### AgentLoop (`core/agent_loop.py`)

系统的核心引擎，约 2300 行代码，职责包括：

- **TAOR 循环**：Think → Act → Observe → Repeat
- **LLM 调用**：流式/同步 API 调用 + 智能重试
- **工具执行**：解析 LLM 工具调用 → 权限检查 → 执行 → 返回结果
- **上下文管理**：消息历史维护 + 自动压缩 + 记忆注入
- **事件发射**：`_emit_event()` 供 Bridge 订阅
- **错误恢复**：四层恢复机制（详见 [错误恢复](../advanced/error-recovery.md)）

### SessionState (`core/session_state.py`)

集中式会话状态管理：

- `messages` — 对话消息历史
- `token_usage` — Token 用量累计
- `cost_tracker` — 费用追踪（每模型独立定价）
- `turn_count` — 轮次计数
- `abort_requested` — 中断控制
- `active_model` — 当前活跃模型（支持 Fallback）
- `on_change` — 状态变更回调（发布/订阅）

### ToolRegistry (`tools/registry.py`)

全局工具注册表：

- `register_tool(name, definition)` — 注册工具
- `get_tool_schemas()` — 获取所有工具的 JSON Schema（传给 LLM）
- `execute_tool(name, arguments)` — 执行工具

50+ 内置工具覆盖：文件操作、代码搜索、Shell 执行、Web 搜索、LSP、Notebook 等。

### HookManager (`hooks/manager.py`)

事件驱动的钩子系统：

- 事件类型：`PreToolUse`, `PostToolUse`, `Stop`, `ToolError`, `UserMessage`, `PreCompact`, `PostCompact`, `ContextWarning`
- 支持优先级排序和短路机制
- 配置文件驱动 + 热重载

### SkillManager (`skills/loader.py`)

三源技能加载：

- **内置技能**：`skills/` 目录下的技能包
- **项目技能**：`.opencode/skills/` 目录
- **用户技能**：`~/.opencode/skills/` 目录

技能通过 `SkillContext` 单例桥接 AgentLoop 和工具系统。

### PermissionManager (`permissions/manager.py`)

四级权限模式：

- `normal` — 写操作需用户确认
- `auto` — 自动批准所有操作
- `plan` — 只读模式，禁止写操作
- `bypass` — 跳过所有检查

支持 allow/deny 规则 + glob 模式匹配。

---

## 运行模式

### CLI 模式

```
python -m opencode.cli
```

终端交互，用户在命令行中输入消息，AgentLoop 处理后流式输出。

### Bridge 模式

```
python -m opencode.cli --bridge
```

启动 FastAPI 服务器，通过 REST API + WebSocket 提供远程控制能力。Web UI 可实时查看执行过程。

---

## 扩展点

| 扩展点 | 机制 | 入口 |
|--------|------|------|
| 新工具 | 继承 `ToolPlugin` 或直接 `register_tool()` | `tools/builtin/` 或插件 |
| 新命令 | 继承 `Command` 基类 | `commands/builtin/` |
| 新技能 | 创建 `SKILL.md` 元数据 | `skills/` 目录 |
| 新钩子 | 配置文件或插件 `get_hooks()` | `.opencode/hooks.yaml` |
| 新插件 | 继承 `ToolPlugin` | `plugins/` 或 `register_builtin_plugin()` |
| MCP 服务器 | `mcp/config/` 配置 | `config.yaml` 的 `mcp_servers` |

---

## 配置层级

配置从多个来源合并，优先级从高到低：

1. CLI 参数 (`--model`, `--permission-mode`)
2. 项目配置 (`.opencode/config.yaml`)
3. 用户配置 (`~/.opencode/config.yaml` 或 `config.yaml`)
4. 环境变量 (`OPENAI_API_KEY`, `OPENAI_BASE_URL`)
5. 内置默认值

---

## 技术栈

| 组件 | 技术 |
|------|------|
| 语言 | Python 3.10+ |
| LLM SDK | openai (兼容 OpenAI API 协议) |
| Web 框架 | FastAPI (Bridge 服务器) |
| 通信协议 | WebSocket + REST (Bridge) |
| MCP 传输 | stdio / SSE / WebSocket |
| 持久化 | JSON / JSONL 文件 |
| 包管理 | pip + requirements.txt |
