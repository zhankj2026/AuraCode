# OpenCode - AI 编程助手

基于 Claude Code 架构设计的 Python 实现，提供生产级 AI 编程助手的核心功能。支持多轮对话、命令执行、远程控制、多智能体协作等能力。

## 特性概览

| 功能 | 说明 |
|------|------|
| **TAOR 循环** | Think-Act-Observe-Repeat 智能体循环 |
| **22+ 工具** | 文件操作、搜索、代码分析、命令执行等 |
| **18+ 命令** | Git 提交、压缩历史、任务规划、代码审查等 |
| **7 技能** | 简化代码、验证变更、调试诊断、批量变更等 |
| **Bridge 远程控制** | REST API + WebSocket 多会话远程控制 |
| **MCP 协议** | Model Context Protocol 集成，支持外部工具服务 |
| **权限管理** | 4 级权限控制 (normal/auto/plan/bypass) |
| **插件系统** | 动态加载插件扩展功能 |
| **钩子系统** | 工具执行前后插入自定义逻辑 |
| **记忆系统** | 持久化用户/项目/反馈记忆 |
| **Subagent** | 并行多智能体任务执行 |

## 快速开始

### 1. 环境准备

```bash
# Python 3.10+
python --version

# 安装所有依赖
pip install -r requirements.txt
```

### 2. 配置 API 密钥

```bash
# Windows PowerShell
$env:OPENAI_API_KEY="your-api-key"
$env:OPENAI_BASE_URL="https://open.bigmodel.cn/api/paas/v4"

# Linux/Mac
export OPENAI_API_KEY="your-api-key"
export OPENAI_BASE_URL="https://open.bigmodel.cn/api/paas/v4"
```

**支持的 LLM**: 智谱 GLM (推荐) / OpenAI GPT / 任何 OpenAI 兼容接口

### 3. 启动

```bash
# 方式 1: 多轮对话模式（推荐）
python cli.py

# 方式 2: 带初始问题启动
python cli.py "帮我分析这个项目"

# 方式 3: 命令模式（单次执行）
python cli.py --command status

# 方式 4: Bridge 远程控制模式
python cli.py --bridge --bridge-port 8765
```

---

## 功能详解

### 一、对话模式命令

在多轮对话中使用 `/` 前缀调用命令：

```bash
python cli.py    # 启动对话模式
```

| 命令 | 说明 | 示例 |
|------|------|------|
| `/help` | 显示帮助信息 | `/help` |
| `/status` | 查看系统状态（模型/token/迭代次数） | `/status` |
| `/clear` | 清空对话历史 | `/clear` |
| `/exit` | 退出 | `/exit` |

#### 编程辅助命令

| 命令 | 说明 | 用法 |
|------|------|------|
| `/commit` | AI 智能生成 Git 提交 | `/commit` |
| `/compact` | 压缩对话历史，保留摘要 | `/compact` |
| `/plan` | 任务规划模式（先计划再执行） | `/plan 重构用户认证模块` |
| `/diff` | 查看 Git 代码变更 | `/diff` `/diff --stat` |
| `/context` | 查看上下文使用情况 | `/context` |
| `/init` | AI 分析代码库生成 OPENCODE.md | `/init` |

#### 代码质量命令

| 命令 | 说明 | 用法 |
|------|------|------|
| `/simplify` | 审查代码复用/质量/效率 | `/simplify` |
| `/verify` | 验证代码变更是否按预期工作 | `/verify` |
| `/debug` | 调试诊断当前会话问题 | `/debug` |
| `/batch` | 大规模并行变更编排 | `/batch 为所有API添加错误处理` |
| `/update-config` | 管理配置（LLM/权限/钩子） | `/update-config` |

#### 系统管理命令

| 命令 | 说明 | 用法 |
|------|------|------|
| `/skills` | 列出可用技能 | `/skills` |
| `/activate` | 激活技能 | `/activate python-standards` |
| `/deactivate` | 停用技能 | `/deactivate python-standards` |
| `/subagents` | 管理子智能体 | `/subagents list` |
| `/plugins` | 查看插件信息 | `/plugins` |
| `/bridge` | 远程控制服务器管理 | `/bridge start` `/bridge status` |
| `/analyze` | 分析代码文件 | `/analyze .` |
| `/test` | 运行测试 | `/test` |
| `/lint` | 代码检查 | `/lint` |

### 二、22+ 内置工具

AI 自动调用的工具，无需手动操作：

**文件操作**
- `read_file` - 读取文件内容
- `write_file` - 写入文件
- `list_directory` - 列出目录
- `replace_in_file` - 替换文件内容
- `undo_edit` - 撤销编辑
- `edit_history` - 查看编辑历史

**搜索分析**
- `grep` - 正则搜索文件内容
- `find` - 按名称查找文件
- `analyze_file` - AI 分析文件

**命令执行**
- `run_command` - 执行系统命令
- `lint` - 代码语法检查
- `run_tests` - 运行测试套件

**智能体**
- `spawn_subagent` - 创建并行子智能体
- `join_subagent` - 获取子智能体结果
- `list_subagents` - 列出子智能体
- `plan_agent` - 规划智能体

**技能管理**
- `list_skills` / `show_available_skills` - 查看技能
- `activate_skill` / `deactivate_skill` - 激活/停用
- `get_active_skills` - 已激活技能

**记忆系统**
- `save_memory` / `load_memory` / `search_memories` - 持久化记忆

### 三、7 个技能

技能是按需注入的领域知识，激活后 AI 会遵循相关规范：

| 技能 | 说明 | 激活方式 |
|------|------|----------|
| `python-standards` | Python 编码规范和最佳实践 | `/activate python-standards` |
| `git-workflow` | Git 工作流规范 | `/activate git-workflow` |
| `simplify` | 代码审查与简化（三路并行 review） | `/simplify` |
| `verify` | 验证代码变更是否正常工作 | `/verify` |
| `debug` | 调试会话问题诊断 | `/debug` |
| `batch` | 大规模并行变更编排 | `/batch` |
| `update-config` | 配置管理 | `/update-config` |

### 四、权限管理

4 种权限模式控制工具执行的安全级别：

| 模式 | 说明 |
|------|------|
| `normal` | 文件写入和命令执行均需确认 |
| `auto` | 文件操作自动通过，仅命令需确认 |
| `plan` | 只读模式，不允许修改文件 |
| `bypass` | 全部自动通过（谨慎使用） |

```bash
# 指定权限模式启动
python cli.py --mode auto "执行一些文件操作"

# 配置文件 config.yaml
permissions:
  mode: auto
  allow_rules:
    - "run_command:ls"
    - "run_command:git status"
  deny_rules:
    - "run_command:rm -rf"
    - "run_command:sudo"
```

### 五、Bridge 远程控制

通过 REST API + WebSocket 实现多会话远程控制：

```bash
# 启动 Bridge 服务器
python cli.py --bridge --bridge-port 8765 --bridge-token my-secret

# 或在对话模式中
/bridge start --port 8765
/bridge status
/bridge stop
```

**API 端点**:

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/sessions` | 创建新会话 |
| GET | `/api/sessions` | 列出所有会话 |
| GET | `/api/sessions/{id}` | 获取会话详情 |
| POST | `/api/sessions/{id}/message` | 发送消息 |
| POST | `/api/sessions/{id}/permission` | 回复权限请求 |
| POST | `/api/sessions/{id}/stop` | 停止会话 |
| DELETE | `/api/sessions/{id}` | 删除会话 |
| GET | `/api/status` | 服务器状态 |
| WS | `/ws/events` | 全局事件流 |
| WS | `/ws/sessions/{id}/events` | 单会话事件流 |

**测试页面**: 用浏览器打开 `bridge/test_bridge.html` 即可交互测试

```bash
# 使用 curl 测试
curl -X POST http://127.0.0.1:8765/api/sessions \
  -H "Authorization: Bearer my-secret" \
  -H "Content-Type: application/json" \
  -d '{"work_dir": ".", "model": "glm-4-plus"}'

curl -X POST http://127.0.0.1:8765/api/sessions/{id}/message \
  -H "Authorization: Bearer my-secret" \
  -H "Content-Type: application/json" \
  -d '{"content": "分析项目结构"}'
```

### 六、MCP 协议集成

支持 Model Context Protocol，可连接外部工具服务器：

```yaml
# config.yaml 中配置 MCP 服务器
mcp:
  servers:
    - name: my-server
      transport: stdio  # stdio/http/websocket
      command: python my_mcp_server.py
```

**支持能力**:
- 4 种传输协议: stdio / HTTP / WebSocket / SSE
- 工具适配: MCP 工具自动转为 OpenCode 工具
- 资源访问: 列出/读取 MCP 服务器资源
- OAuth 认证: 支持 OAuth 2.0 认证流程

### 七、Subagent 并行任务

创建多个子智能体并行执行任务：

```bash
# AI 会自动使用 subagent 工具
# 示例对话：
> "同时分析 src/ 和 tests/ 目录的代码质量"
# AI 会 spawn 两个 subagent 并行分析
```

**相关工具**: `spawn_subagent` / `join_subagent` / `list_subagents` / `subagent_stats`

### 八、记忆系统

仿 Claude Code 设计，持久化 4 种记忆类型：

| 类型 | 说明 |
|------|------|
| `user` | 用户角色、偏好、知识背景 |
| `feedback` | 用户反馈（有效/无效方法） |
| `project` | 项目目标、状态 |
| `reference` | 外部文档/系统参考 |

**相关工具**: `save_memory` / `load_memory` / `search_memories`

### 九、插件系统

动态加载插件扩展功能：

```python
# plugins/example_autoformat.py
class AutoFormatPlugin(ToolPlugin):
    name = "auto-format"
    
    def get_tools(self):
        return [...]    # 插件提供的工具
    
    def get_hooks(self):
        return [...]    # 插件提供的钩子
```

查看已加载插件: `/plugins`

### 十、钩子系统

在工具执行的不同阶段插入自定义逻辑：

```python
# PreToolUse:    工具执行前
# PostToolUse:   工具执行后
# PostToolUseFailure: 工具失败时
hook_manager.register_hook("PreToolUse", my_hook)
```

---

## CLI 参数参考

```bash
python cli.py [prompt] [选项]

参数:
  prompt                  初始问题/指令

选项:
  --mode {normal,auto,plan,bypass}  权限模式 (默认: normal)
  --model MODEL                     LLM 模型 (默认: glm-4.7)
  --base-url URL                    API Base URL
  --max-iterations N                最大迭代次数 (默认: 20)
  --command CMD [ARGS ...]          命令模式: 单次执行命令
  --verbose                         显示详细日志
  
  # Bridge 远程控制
  --bridge                          启动 Bridge 服务器模式
  --bridge-port PORT                Bridge 端口 (默认: 8765)
  --bridge-host HOST                Bridge 地址 (默认: 127.0.0.1)
  --bridge-max-sessions N           最大会话数 (默认: 5)
  --bridge-token TOKEN              认证 Token (默认自动生成)
```

## 配置文件

`config.yaml` 完整配置项：

```yaml
llm:
  provider: openai
  model: glm-4.7
  base_url: https://open.bigmodel.cn/api/paas/v4
  max_tokens: 4096
  temperature: 0.2

permissions:
  mode: normal
  allow_rules:
    - "run_command:ls"
    - "run_command:git status"
  deny_rules:
    - "run_command:rm -rf"
    - "run_command:sudo"

agent:
  max_iterations: 20
  context_window: 200000

context:
  load_claude_md: true
  max_files_read: 10

logging:
  level: DEBUG
```

## 项目结构

```
opencode/
├── cli.py                  # CLI 入口（对话/命令/Bridge 三种模式）
├── config.yaml             # 配置文件
├── requirements.txt        # 依赖
├── core/                   # 核心实现
│   ├── agent_loop.py       #   TAOR 循环引擎
│   ├── context.py          #   项目上下文
│   ├── subagent.py         #   Subagent 管理
│   ├── memory.py           #   记忆系统
│   └── message.py          #   消息处理
├── tools/builtin/          # 22+ 内置工具
│   ├── read_file.py        #   读文件
│   ├── write_file.py       #   写文件
│   ├── run_command.py      #   执行命令
│   ├── grep.py             #   正则搜索
│   ├── find.py             #   文件查找
│   ├── replace_in_file.py  #   内容替换
│   ├── analyze_file.py     #   AI 分析
│   ├── lint.py             #   代码检查
│   ├── run_tests.py        #   运行测试
│   ├── subagent.py         #   子智能体
│   ├── plan_agent.py       #   规划智能体
│   ├── skill_tools.py      #   技能工具
│   ├── memory_tools.py     #   记忆工具
│   └── undo_edit.py        #   撤销编辑
├── commands/builtin/       # 18+ 命令
│   ├── commit_command.py   #   AI Git 提交
│   ├── compact_command.py  #   压缩对话历史
│   ├── plan_command.py     #   任务规划
│   ├── diff_command.py     #   查看变更
│   ├── context_command.py  #   上下文统计
│   ├── init_command.py     #   生成项目文档
│   ├── bridge_command.py   #   远程控制
│   ├── skill_commands.py   #   simplify/verify/debug/batch
│   └── subagents_command.py#   子智能体管理
├── bridge/                 # 远程控制模块
│   ├── server.py           #   FastAPI 服务器
│   ├── session.py          #   Bridge 会话
│   ├── manager.py          #   多会话管理
│   ├── types.py            #   类型定义
│   └── test_bridge.html    #   测试页面
├── mcp/                    # MCP 协议集成
│   ├── client/             #   MCP 客户端
│   ├── transport/          #   传输层
│   ├── tools/              #   工具适配
│   ├── auth/               #   OAuth 认证
│   └── config/             #   配置管理
├── skills/                 # 7 个技能
│   ├── python-standards/   #   Python 编码规范
│   ├── git-workflow/       #   Git 工作流
│   ├── simplify/           #   代码简化审查
│   ├── verify/             #   变更验证
│   ├── debug/              #   调试诊断
│   ├── batch/              #   批量变更
│   └── update-config/      #   配置管理
├── permissions/            # 权限管理
├── plugins/                # 插件系统
├── hooks/                  # 钩子系统
└── tests/                  # 测试套件
```

## 测试

```bash
cd tests
python test_phase1_tools.py      # 基础工具
python test_phase2_complete.py   # 文件编辑
python test_phase3_tools.py      # 质量检查
python test_integration.py       # 集成测试
python test_hooks_execution.py   # 钩子系统
python test_skill_tools.py       # 技能工具
python test_memory_system.py     # 记忆系统
```

## 支持的 LLM

### 智谱 GLM (推荐)

```bash
export OPENAI_API_KEY="your-key"
export OPENAI_BASE_URL="https://open.bigmodel.cn/api/paas/v4"
# 模型: glm-4-plus / glm-4.7 / glm-4-air / glm-4-flash
```

### OpenAI

```bash
export OPENAI_API_KEY="sk-your-key"
# 模型: gpt-4o / gpt-4-turbo / gpt-3.5-turbo
```

### 其他兼容接口

任何兼容 OpenAI API 的服务均可使用，只需设置 `base_url` 和 `api_key`。

## 开发路线图

- [x] Phase 1: 基础工具系统
- [x] Phase 2: 文件编辑工具
- [x] Phase 3: 质量检查工具
- [x] Phase 4: 插件和钩子系统
- [x] Phase 5: 技能系统
- [x] Phase 6: Subagent 系统
- [x] Phase 7: 编程辅助命令 (commit/compact/plan/diff/context/init)
- [x] Phase 8: 高级技能 (simplify/verify/debug/batch/update-config)
- [x] Phase 9: Bridge 多会话远程控制
- [x] Phase 10: MCP 协议集成

## 许可证

MIT License
