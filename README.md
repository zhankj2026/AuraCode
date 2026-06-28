# AuraCode — AI 编程智能体

> Python 实现的全功能 AI 编程助手，支持 **56 种内置工具**、**54 条交互命令**、**7 项领域技能**，具备 MCP 协议完整实现、Bridge 远程控制与企业级安全策略。

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-50%2B%20passing-brightgreen.svg)](tests/)

---

## ✨ 核心特性

| 维度 | 能力 |
|------|------|
| **内置工具** | 56 个 — 文件读写、代码搜索、LSP 智能、Shell 执行、Web 搜索、子代理协同等 |
| **交互命令** | 54 条 — Git 工作流、会话管理、调试诊断、安全审查、目录切换、命令执行等 |
| **领域技能** | 7 个内置 + 用户自定义 — 按需激活，渐进式披露，节省 Token |
| **错误恢复** | 6 层纵深防御 — Fallback 模型 → Prompt 压缩 → 截断恢复 → Hook 兜底 → 预算控制 → 图片剥离 |
| **MCP 协议** | 完整实现 — Client + Server 模式 + MCPB 格式 + 企业安全策略 + 健康检查 |
| **Bridge 远程控制** | REST + WebSocket — 多会话管理、实时事件推送、远程审批、文件浏览 |
| **子代理系统** | 多代理并行 — 独立上下文、结果聚合、类型定制、协同工作 |
| **记忆系统** | LLM 驱动召回 — 新鲜度衰减、语义搜索、跨会话持久化、自动提取 |
| **权限管理** | 4 级模式 — Normal / Auto / Plan / Bypass + 参数级 allow/deny 规则 |
| **钩子系统** | 10+ 事件类型 — 配置驱动、优先级排序、短路机制、热重载 |
| **插件系统** | 生命周期管理 — 自动发现、依赖解析、Marketplace、插件间通信 |

---

## 🚀 快速开始

### 环境要求

- Python 3.10+
- pip
- Git（可选，用于 Git 相关命令）

### 安装

```bash
cd auracode
pip install -r requirements.txt
```

### 配置

```bash
cp config.example.yaml config.yaml
# 编辑 config.yaml，填入你的 LLM API Key
```

**核心配置示例**：

```yaml
llm:
  provider: openai            # OpenAI 兼容接口
  model: glm-4-plus           # 模型名称
  base_url: https://open.bigmodel.cn/api/paas/v4
  api_key: ${OPENAI_API_KEY}  # 推荐使用环境变量
  max_tokens: 4096
  temperature: 0.2

permissions:
  mode: normal                # normal | auto | plan | bypass
  allow_rules:
    - "read_file:*"
    - "run_command:git status"
  deny_rules:
    - "run_command:rm -rf"
    - "run_command:sudo"

agent:
  max_iterations: 20
  context_window: 200000
```

### 启动

```bash
# 对话模式
python cli.py
python cli.py "帮我分析这个项目"

# 命令模式
python cli.py -c analyze .
python cli.py -c status

# Bridge 远程控制模式
python cli.py --bridge
python cli.py --bridge --bridge-port 9000
```

---

## 📖 CLI 参数参考

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `prompt` | 初始输入（对话模式） | - |
| `--mode` | 权限模式: `normal` / `auto` / `plan` / `bypass` | `normal` |
| `--model` | LLM 模型名称 | `glm-4.7` |
| `--base-url` | API Base URL | 环境变量 `OPENAI_BASE_URL` |
| `--max-iterations` | 最大迭代次数 | `20` |
| `-c, --command` | 命令模式执行 | - |
| `-v, --verbose` | 显示详细日志 | `false` |
| `--bridge` | 启动 Bridge 远程控制 | `false` |
| `--bridge-port` | Bridge 端口 | `8765` |
| `--bridge-host` | Bridge 绑定地址 | `127.0.0.1` |
| `--bridge-max-sessions` | Bridge 最大会话数 | `5` |
| `--bridge-token` | Bridge 认证 Token | 自动生成 |

---

## 🎯 命令大全（54 条）

在对话模式中输入 `/命令名` 即可执行。

### 核心交互

| 命令 | 说明 |
|------|------|
| `/help` (`?`) | 查看所有可用命令 |
| `/status` | 当前会话状态概览 |
| `/clear` | 清空对话历史 |
| `/compact` | LLM 驱动压缩对话历史，保留关键摘要 |
| `/context` | Token 分布可视化与上下文使用情况 |
| `/cost` | 会话费用追踪（按模型独立计价） |
| `/model` | 运行时模型切换与历史回滚 |
| `/settings` | 用户设置管理 |

### 目录与命令执行

| 命令 | 说明 |
|------|------|
| `/cd [path]` | 切换工作目录（支持绝对/相对路径、`cd -` 返回） |
| `/pwd` | 显示当前工作目录 |
| `/exec <cmd>` | 执行 Shell/CMD 命令（支持超时、后台执行） |
| `/run <cmd>` | 同 `/exec` |
| `/shell <cmd>` | 同 `/exec` |

### Git 工作流

| 命令 | 说明 |
|------|------|
| `/commit` | AI 智能分析变更并生成 Git 提交 |
| `/commit-push-pr` | 完整 PR 工作流（commit → push → gh pr create） |
| `/branch` | 从当前对话创建 Git 分支 |
| `/diff` | 查看 Git 暂存/未暂存差异 |
| `/review` | 代码审查 — 变更影响分析 + 依赖图展示 |
| `/security-review` | 安全漏洞扫描 — 16 类检查 + 严重性分级 |
| `/worktree` | Git Worktree 隔离工作区管理 |

### 会话管理

| 命令 | 说明 |
|------|------|
| `/resume` | 恢复历史会话（含离开摘要） |
| `/history` | 会话历史管理与搜索 |
| `/rewind` | 会话回退 — Checkpoint 撤销 |
| `/export` | 对话导出为 Markdown / JSON |
| `/plan` | 任务规划模式 — 分步计划制定与追踪 |
| `/init` | 初始化项目文档 AURACODE.md |

### 代码质量

| 命令 | 说明 |
|------|------|
| `/analyze` | 项目级代码分析 |
| `/lint` | 代码规范检查 |
| `/test` | 运行项目测试 |
| `/benchmark` | 性能基准测试与对比 |
| `/verify` | 验证代码变更是否正确 |
| `/simplify` | 三路并行代码审查与简化建议 |
| `/debug` | 调试会话问题诊断 |
| `/doctor` | 环境诊断与健康检查 |

### 系统管理

| 命令 | 说明 |
|------|------|
| `/config-edit` | 运行时配置热编辑 |
| `/permissions` | 权限规则管理（查看/添加/移除/模式切换） |
| `/hooks` | Hook 管理 — 配置查看、执行日志、热重载 |
| `/plugins` | 插件系统管理（安装/卸载/搜索/Marketplace） |
| `/mcp` | MCP 服务器管理 — 连接/断开/工具列表/状态 |
| `/memory` | 记忆管理 — 查看/搜索/编辑/删除/导出 |
| `/tools` | 工具使用统计与追踪 |

### 代理与技能

| 命令 | 说明 |
|------|------|
| `/skills` | 技能系统管理 |
| `/activate` | 激活领域技能 |
| `/deactivate` | 停用领域技能 |
| `/active` | 查看已激活技能 |
| `/subagents` | 子代理管理 — 列表/统计/终止 |
| `/bridge` | Bridge 远程控制管理 |
| `/cron` | 定时任务管理 |
| `/batch` | 大规模并行变更编排 |

### 其他

| 命令 | 说明 |
|------|------|
| `/tips` | 功能发现提示 |
| `/update-config` | 配置管理（Hooks/权限/环境变量） |

---

## 🛠️ 内置工具（56 个）

### 文件操作（6 个）
`read_file` · `write_file` · `replace_in_file` · `undo_edit` · `notebook_edit` · `analyze_file`

### 代码搜索（6 个）
`find` · `glob` · `grep` · `list_directory` · `lsp` · `tool_search`

### 终端执行（5 个）
`run_command` · `run_powershell` · `run_tests` · `repl` · `lint`

### 智能代理（6 个）
`spawn_subagent` · `join_subagent` · `list_subagents` · `subagent_stats` · `list_agent_types` · `plan_agent`

### 任务管理（4 个）
`task_create` · `task_list` · `task_update` · `todo_write`

### 计划模式（2 个）
`enter_plan_mode` · `exit_plan_mode`

### Git Worktree（2 个）
`enter_worktree` · `exit_worktree`

### 定时任务（3 个）
`cron_create` · `cron_delete` · `cron_list`

### 记忆系统（7 个）
`save_memory` · `load_memory` · `search_memories` · `list_memories` · `get_memory_summary` · `get_relevant_memories` · `delete_memory`

### 技能系统（5 个）
`activate_skill` · `deactivate_skill` · `get_active_skills` · `list_skills` · `show_available_skills`

### 网络与外部（2 个）
`web_fetch` · `web_search`

### 交互与配置（5 个）
`ask_user` · `brief` · `config` · `edit_history` · `sleep`

### 其他（3 个）
`task_get` · `task_stop` · `tool_search`

---

## 🎓 技能系统

技能是按需激活的领域知识包，激活后注入系统提示词，指导 AI 遵循特定领域的最佳实践。

### 内置技能

| 技能 | 说明 | 触发场景 |
|------|------|----------|
| `git-workflow` | Git 工作流规范 | 涉及 Git 操作时 |
| `python-standards` | Python 编码规范 | Python 项目开发时 |
| `simplify` | 代码审查与简化 | 三路并行审查代码 |
| `verify` | 变更验证 | 验证代码修改正确性 |
| `debug` | 调试诊断 | 排查会话问题 |
| `batch` | 并行变更编排 | 大规模跨文件修改 |
| `update-config` | 配置管理 | Hooks/权限/环境配置 |

### 自定义技能

支持项目级和用户级自定义技能，自动发现与加载：

```
# 项目级（跟随仓库）
.auracode/skills/my-skill/SKILL.md

# 用户级（全局）
~/.auracode/skills/my-skill/SKILL.md
```

**SKILL.md 格式**：

```markdown
---
name: my-skill
description: 我的自定义技能
trigger: 当需要执行特定任务时
---

# My Skill

详细的技能指导内容...
```

---

## 🔌 MCP 协议集成

完整实现 [Model Context Protocol](https://modelcontextprotocol.io/)，支持客户端和服务器双模式。

### MCP Client 模式

连接外部 MCP 服务器，扩展工具能力：

```yaml
# config.yaml
mcp:
  servers:
    postgres:
      command: "npx"
      args: ["-y", "@modelcontextprotocol/server-postgres"]
      transport: stdio
      env:
        DATABASE_URL: "${DATABASE_URL}"
```

**特性**：
- ✅ 自动发现 — 启动时扫描并连接配置的 MCP 服务器
- ✅ 动态注册 — MCP 工具自动注册到工具系统
- ✅ 调用链追踪 — 工具调用过程可观测
- ✅ 工具结果缓存 — TTL 缓存机制
- ✅ 热加载/卸载 — 运行时添加/移除服务器

**管理命令**：`/mcp list` · `/mcp connect <name>` · `/mcp disconnect <name>`

### MCP Server 模式

将 AuraCode 作为 MCP Server 运行，对外暴露内置工具：

```bash
python -m mcp.server --cwd . --debug
```

**特性**：
- ✅ JSON-RPC 2.0 协议支持
- ✅ StdioServerTransport
- ✅ 自动加载所有内置工具
- ✅ 工具调用代理机制

### MCPB 文件格式

支持 `.mcpb` bundle 格式，打包分发 MCP 服务器配置：

```json
{
  "name": "database-tools",
  "version": "1.0.0",
  "servers": {
    "postgres": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-postgres"],
      "env": {
        "DATABASE_URL": "${user:DATABASE_URL}"
      }
    }
  }
}
```

### 企业安全策略

支持允许列表/拒绝列表策略，控制哪些 MCP 服务器可以被加载：

```python
from mcp.security import McpSecurityPolicy, AllowedMcpServerEntry

policy = McpSecurityPolicy(
    allowlist=[
        AllowedMcpServerEntry(server_name="postgres"),
        AllowedMcpServerEntry(server_command=["npx", "-y", "@mcp/redis"]),
    ],
    denylist=[
        # 拒绝特定服务器
    ]
)
```

**匹配方式**：
- 服务器名称匹配
- 命令数组精确匹配
- URL 模式匹配（支持通配符）

### 健康检查机制

自动监控 MCP 服务器状态，支持自动重连：

**服务器状态分类**：
- ✅ `CONNECTED` — 已连接
- ❌ `FAILED` — 连接失败
- 🔐 `NEEDS_AUTH` — 需要认证
- ⏳ `PENDING` — 重连中
- ⛔ `DISABLED` — 已禁用

**特性**：
- 定期检查（可配置间隔）
- 自动重连（指数退避）
- 可用率统计
- 延迟监控
- 健康报告生成

---

## 🌐 Bridge 远程控制

基于 FastAPI 的 REST + WebSocket 远程控制服务，支持浏览器端实时操控。

```bash
# 启动 Bridge
python cli.py --bridge --bridge-port 9000 --bridge-max-sessions 10

# 指定认证 Token
python cli.py --bridge --bridge-token my-secret
```

**核心能力**：
- ✅ 多会话并行管理（最大会话数可配置）
- ✅ WebSocket 实时事件推送（工具调用、Token 消耗、错误通知）
- ✅ Token 认证机制
- ✅ 远程消息发送与命令执行
- ✅ 文件浏览 API
- ✅ 内置 Web UI（`bridge/test_bridge.html`）
- ✅ LLM 请求/响应网络监控

**REST API**：
- `POST /api/sessions` — 创建会话
- `POST /api/sessions/{id}/message` — 发送消息
- `GET /api/sessions` — 列出会话
- `POST /api/sessions/{id}/interrupt` — 中断会话
- `POST /api/sessions/{id}/model` — 切换模型
- `GET /api/files` — 浏览文件
- `GET /api/files/content` — 获取文件内容

**WebSocket**：
- `ws://host:port/ws?token=xxx` — 实时事件流

---

## 🔒 权限管理

四级权限模式，参数级 allow/deny 规则：

| 模式 | 说明 |
|------|------|
| `normal` | 默认模式 — 危险操作需确认 |
| `auto` | 自动模式 — 自动批准安全操作 |
| `plan` | 计划模式 — 只读分析，不执行修改 |
| `bypass` | 绕过模式 — 跳过所有权限检查 |

```yaml
permissions:
  mode: normal
  allow_rules:
    - "read_file:*"          # 允许读取所有文件
    - "run_command:git *"    # 允许所有 git 命令
  deny_rules:
    - "run_command:rm -rf"   # 禁止危险删除
    - "run_command:sudo *"   # 禁止 sudo
```

**管理命令**：`/permissions`

---

## 🪝 钩子系统

配置驱动的事件钩子，支持 10+ 事件类型：

| 事件 | 触发时机 |
|------|----------|
| `PreToolUse` | 工具调用前 |
| `PostToolUse` | 工具调用后 |
| `Stop` | 代理循环结束 |
| `ToolError` | 工具执行出错 |
| `UserMessage` | 用户消息接收 |
| `PreCompact` | 上下文压缩前 |
| `PostCompact` | 上下文压缩后 |
| `ContextWarning` | 上下文窗口警告 |

```yaml
# .auracode/hooks.yaml
hooks:
  PreToolUse:
    - command: "echo 'About to use tool'"
      filter: "run_command"
  Stop:
    - command: "notify-send 'Task completed'"
```

**特性**：优先级排序、短路机制、错误隔离、文件监听热重载。

**管理命令**：`/hooks`

---

## 🧩 插件系统

基于生命周期的插件架构：

```
plugins/
├── base.py              # 插件基类
├── loader.py            # 插件加载器
├── registry.py          # 插件注册中心
├── builtin.py           # 内置插件注册表
├── marketplace.py       # Marketplace 管理
├── plugin_installer.py  # 插件安装器
└── zip_cache.py         # Zip 缓存
```

**特性**：
- ✅ 自动发现 — 启动时扫描插件目录
- ✅ 依赖管理 — 插件间依赖声明与加载顺序
- ✅ 插件间通信 — 事件驱动的插件协作
- ✅ Marketplace — 插件市场支持
- ✅ 内置插件 — 用户设置持久化

**管理命令**：`/plugins`

---

## 🛡️ 错误恢复（6 层）

纵深防御体系，确保代理在各种异常下都能优雅恢复：

| 层级 | 机制 | 触发条件 |
|------|------|----------|
| 1 | **Fallback 模型** | 主模型不可用时自动切换备选模型 |
| 2 | **Prompt 压缩** | 上下文超长时压缩历史消息 + 裁剪旧工具结果 |
| 3 | **MaxOutput 恢复** | 输出被截断时自动续写 |
| 4 | **StopHook 兜底** | 代理异常停止时通过 Hook 提供恢复建议 |
| 5 | **Budget 控制** | Token 预算超限时终止并报告 |
| 6 | **ImageStrip 剥离** | 上下文过大时剥离 base64 图片 + 裁剪大型结果 |

---

## 📁 项目结构

```
auracode/
├── cli.py                    # CLI 入口（对话模式 + 命令模式 + Bridge 模式）
├── config.yaml               # 运行时配置
├── config.example.yaml       # 配置模板
├── requirements.txt          # Python 依赖
├── LICENSE                   # Apache 2.0 许可证
│
├── core/                     # 核心引擎
│   ├── agent_loop.py         #   TAOR 智能体循环（Think-Act-Observe-Repeat, 2638 行）
│   ├── session_state.py      #   会话状态（Token 追踪/成本/权限）
│   ├── session_store.py      #   会话持久化（JSON 日志/索引/分支）
│   ├── session_intelligence.py #  会话智能（自动索引/全文检索/分支持久化）
│   ├── context.py            #   上下文构建与管理
│   ├── memory.py             #   记忆系统（LLM 召回/新鲜度/扫描）
│   ├── auto_memory.py        #   自动记忆提取引擎
│   ├── message.py            #   消息数据结构
│   ├── subagent.py           #   子代理管理
│   ├── code_analyzer.py      #   代码分析（依赖图/影响分析）
│   ├── tool_enhancer.py      #   工具增强（结果摘要/自动重试/输出裁剪）
│   ├── tool_tracker.py       #   工具使用追踪
│   ├── coordinator.py        #   工作流协调器
│   └── workflow_types.py     #   工作流类型定义
│
├── tools/                    # 工具系统（56 个内置工具）
│   ├── registry.py           #   工具注册中心
│   └── builtin/              #   内置工具实现
│       ├── read_file.py      #     文件读取
│       ├── write_file.py     #     文件写入
│       ├── replace_in_file.py #    文本替换
│       ├── run_command.py    #     Shell 命令执行
│       ├── run_powershell.py #     PowerShell 执行
│       ├── glob_tool.py      #     Glob 搜索
│       ├── lsp_tool.py       #     LSP 代码智能
│       ├── web_fetch.py      #     网页获取
│       ├── web_search.py     #     网络搜索
│       └── ... (56 个工具)
│
├── commands/                 # 命令系统（54 条内置命令）
│   ├── registry.py           #   命令注册中心
│   ├── base.py               #   命令基类
│   └── builtin/              #   内置命令实现
│       ├── cd_command.py     #     目录切换
│       ├── exec_command.py   #     命令执行
│       ├── commit_command.py #     Git 提交
│       ├── review_command.py #     代码审查
│       ├── mcp_command.py    #     MCP 管理
│       └── ... (54 条命令)
│
├── skills/                   # 技能系统（7 个内置技能）
│   ├── loader.py             #   技能管理器（多源发现/渐进式披露）
│   ├── context.py            #   技能上下文注入
│   ├── builtin_skills.py     #   编程式技能注册
│   └── [内置技能目录]         #   7 个内置技能
│
├── mcp/                      # MCP 协议集成（完整实现）
│   ├── manager.py            #   MCP 管理器（热加载/注销/缓存）
│   ├── bundle.py             #   MCPB 文件格式支持
│   ├── health.py             #   健康检查机制
│   ├── security.py           #   企业安全策略
│   ├── server/               #   MCP Server 模式
│   ├── client/               #   协议客户端
│   ├── transport/            #   传输层（stdio/SSE/WebSocket/HTTP）
│   ├── tools/                #   MCP 工具适配
│   ├── config/               #   服务器配置
│   ├── auth/                 #   OAuth 认证
│   ├── plugins/              #   MCP 插件
│   └── skills/               #   MCP Skill 集成
│
├── bridge/                   # Bridge 远程控制
│   ├── server.py             #   FastAPI REST + WebSocket 服务
│   ├── session.py            #   Bridge 会话（事件回调/消息推送）
│   ├── manager.py            #   多会话管理
│   ├── auth.py               #   Token 认证
│   ├── types.py              #   类型定义
│   └── test_bridge.html      #   Web UI 控制面板
│
├── hooks/                    # 钩子系统
│   ├── manager.py            #   Hook 管理器（优先级/短路/隔离）
│   └── config_loader.py      #   配置加载与热重载
│
├── permissions/              # 权限管理
│   └── manager.py            #   权限管理器（规则匹配/审批队列）
│
├── plugins/                  # 插件系统
│   ├── base.py               #   插件基类
│   ├── loader.py             #   插件加载器
│   ├── registry.py           #   插件注册中心
│   ├── builtin.py            #   内置插件
│   ├── marketplace.py        #   Marketplace 管理
│   ├── plugin_installer.py   #   插件安装器
│   └── zip_cache.py          #   Zip 缓存
│
├── services/                 # 后台服务
│   ├── away_summary.py       #   离开摘要（LLM 生成回顾）
│   ├── diagnostic_tracker.py #   诊断追踪（LSP 错误基线/增量）
│   ├── tip_system.py         #   功能发现提示（冷却/历史/注册表）
│   ├── session_transcript.py #   会话转录（JSONL 增量）
│   ├── session_memory.py     #   会话记忆摘要
│   ├── project_store.py      #   项目级配置
│   ├── session_env.py        #   会话环境脚本
│   ├── task_store.py         #   任务持久化
│   ├── history_log.py        #   全局交互历史
│   ├── settings_store.py     #   用户设置
│   └── file_history.py       #   文件修改备份
│
├── config/                   # 配置管理
│   └── __init__.py           #   配置加载与验证
│
├── tests/                    # 测试套件（50+ 测试）
├── examples/                 # 使用示例
├── docs/                     # 用户文档
└── website/                  # 项目官网（静态站点）
```

---

## 🤖 支持的 LLM

AuraCode 通过 OpenAI 兼容接口对接各类 LLM：

| 提供商 | 模型示例 | 说明 |
|--------|----------|------|
| 智谱 AI | `glm-4-plus`, `glm-4.7`, `glm-4.5-air` | 推荐，中文能力强 |
| OpenAI | `gpt-4o`, `gpt-4-turbo` | 需科学上网 |
| 自定义 | 任意 OpenAI 兼容 API | 通过 `base_url` 配置 |

---

## 🔧 环境变量

| 变量 | 说明 |
|------|------|
| `OPENAI_API_KEY` | LLM API 密钥（必需） |
| `OPENAI_BASE_URL` | API Base URL（可选） |

---

## 📊 测试覆盖

项目包含 50+ 测试用例，覆盖核心功能：

```bash
# 运行所有测试
python -m pytest tests/ -v

# 运行特定测试
python -m pytest tests/test_cd_command.py -v
python -m pytest tests/test_exec_command.py -v
python -m pytest tests/test_phase3_mcp_advanced.py -v
```

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

## 📄 许可证

[Apache License 2.0](LICENSE)

---

## 📮 联系方式

- 📖 文档：`docs/` 目录
- 💬 问题反馈：GitHub Issues /Gitee Issues
- 🌟 项目地址：https://gitee.com/creating2018/auracode 
