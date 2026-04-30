# MVP 架构总览与快速启动

## 1. 项目定位与设计哲学

### 1.1 项目背景

本项目是基于 **Claude Code** TypeScript 源码设计的 Python 实现版本,遵循严格的隔离原则:

- ✅ Python 代码完全位于 `opencode/` 目录
- ✅ 与 `src/` 和 `vendor/` 目录的 TypeScript 代码完全隔离
- ✅ 仅复用接口定义和协议格式(JSON Schema),不复制业务逻辑
- ✅ 采用独立的共享协议文件而非直接移植 TypeScript 类型

### 1.2 设计哲学

#### "运行时越笨,架构越稳定"

这是 Claude Code 的核心设计理念,也是本项目的指导原则:

```
智能下沉到模型 → 框架保持确定性 → 系统更易维护和调试
```

**具体体现:**
- Agent Loop 核心逻辑仅约 50 行代码
- 把复杂决策交给 LLM,框架只负责流程编排
- 避免在代码中硬编码业务规则

#### 最小化可行产品(MVP)策略

我们选择先实现最核心的功能,后续逐步扩展:

| 阶段 | 目标 | 时间估算 |
|------|------|---------|
| Phase 1 | Agent Loop 核心循环 | 第 1 周 |
| Phase 2 | 工具系统(4个基础工具) | 第 2 周 |
| Phase 3 | 权限管理(4种模式) | 第 3 周 |
| Phase 4 | 上下文管理与配置系统 | 第 4 周 |
| Phase 5 | 测试与文档完善 | 第 5 周 |

---

## 2. 整体架构图

### 2.1 目录结构

```
opencode/
├── core/                    # 核心引擎层
│   ├── __init__.py
│   ├── agent_loop.py        # TAOR 循环实现(~150行)
│   ├── message.py           # 消息模型与管理
│   └── context.py           # 上下文加载器(OPENCODE.md)
│
├── tools/                   # 工具系统层
│   ├── __init__.py
│   ├── registry.py          # 工具注册表
│   ├── base.py              # 工具基类(ABC)
│   ├── executor.py          # 工具执行引擎
│   └── builtin/             # 内置工具
│       ├── __init__.py
│       ├── read_file.py     # 读取文件
│       ├── write_file.py    # 写入文件
│       ├── run_command.py   # 执行命令
│       └── list_directory.py # 列出目录
│
├── permissions/             # 权限管理层
│   ├── __init__.py
│   ├── manager.py           # 权限管理器
│   └── rules.py             # 规则引擎(黑名单/白名单)
│
├── config/                  # 配置管理层
│   ├── __init__.py
│   ├── loader.py            # YAML 配置加载器
│   └── defaults.yaml        # 默认配置
│
├── tests/                   # 单元测试
│   ├── test_agent_loop.py
│   ├── test_tools.py
│   └── test_permissions.py
│
├── docs/                    # 架构文档
│   ├── 01-architecture-overview.md      # 本文档
│   ├── 02-agent-loop-implementation.md  # Agent Loop 详解
│   ├── 03-tools-and-permissions.md      # 工具与权限详解
│   └── 04-context-and-config.md         # 上下文与配置详解
│
├── cli.py                   # CLI 入口(~80行)
├── requirements.txt         # Python 依赖
└── README.md                # 快速开始指南
```

### 2.2 组件交互图

```
用户输入 (CLI)
    │
    ▼
┌─────────────────────┐
│   Agent Loop        │ ◄── 核心控制器
│  (core/agent_loop)  │
└─────────┬───────────┘
          │
          ├─► 加载上下文 (core/context.py)
          │       └─► .opencode/OPENCODE.md
          │
          ├─► 组装提示词 (agent_loop._build_system_prompt)
          │       ├─ 角色定义
          │       ├─ 项目约定
          │       ├─ 工具描述
          │       └─ 安全规则
          │
          ├─► 调用 LLM API (OpenAI SDK)
          │       └─► 流式响应解析
          │
          ├─► 检查工具调用?
          │     │
          │     ├─ 无工具调用 ──► 返回结果,结束
          │     │
          │     └─ 有工具调用 ──┐
          │                     ▼
          │           ┌─────────────────────┐
          │           │  工具执行引擎        │
          │           │ (tools/executor.py)  │
          │           └─────────┬───────────┘
          │                     │
          │                     ├─► 查找工具注册表 (tools/registry.py)
          │                     │
          │                     ├─► 权限检查 (permissions/manager.py)
          │                     │       ├─ Plan 模式拦截
          │                     │       ├─ 黑名单检查
          │                     │       └─ 用户确认(normal 模式)
          │                     │
          │                     └─► 执行工具 handler
          │                             ├─ read_file
          │                             ├─ write_file
          │                             ├─ run_command
          │                             └─ list_directory
          │
          └─► 工具结果封装为 UserMessage
                └─► 追加到消息历史
                      └─► 继续循环(回到 LLM 调用)
```

---

## 3. 技术选型说明

### 3.1 核心技术栈

| 组件 | 选择 | 版本要求 | 理由 |
|------|------|---------|------|
| **运行时** | Python | 3.10+ | 类型注解成熟,async/await 支持完善 |
| **LLM SDK** | OpenAI | 1.0+ | 兼容 Anthropic/AWS Bedrock/本地模型 |
| **配置格式** | YAML | PyYAML 6.0+ | 人类可读,易于维护 |
| **数据验证** | 原生 dict | - | 减少依赖,与 JSON Schema 原生对齐 |
| **测试框架** | pytest | 7.0+ | 生态丰富,插件众多 |

### 3.2 为什么不选择某些技术?

#### ❌ 不使用 Pydantic

**原因:**
- 增加 ~15MB 安装包体积
- 工具定义需要额外转换为 JSON Schema
- MVP 阶段简单 dict 足够

**对比:**
```python
# 方案 A: 原生 dict (采用)
TOOL_SCHEMA = {
    "type": "object",
    "properties": {"path": {"type": "string"}},
    "required": ["path"]
}

# 方案 B: Pydantic (未采用)
from pydantic import BaseModel

class ReadFileInput(BaseModel):
    path: str
    
    def to_json_schema(self):
        return self.model_json_schema()  # 额外转换开销
```

#### ❌ 不使用 asyncio (MVP 阶段)

**原因:**
- 简化并发控制逻辑
- 避免竞态条件(特别是文件写入)
- 后续可轻松升级

**扩展路径:**
```python
# Phase 2 扩展: 只读工具并行执行
import asyncio

if all(t.permission_level == "read" for t in tool_calls):
    results = await asyncio.gather(*[execute(t) for t in tool_calls])
else:
    results = [await execute(t) for t in tool_calls]  # 串行
```

#### ❌ 不使用 Click/Typer (CLI 框架)

**原因:**
- MVP 阶段仅需简单参数解析
- argparse 是标准库,零依赖
- 后续可扩展为 Typer

---

## 4. 快速启动指南

### 4.1 环境准备

```bash
# 1. 确保 Python 3.10+
python --version
# Python 3.10.12

# 2. 进入 opencode 目录
cd opencode

# 3. 安装依赖
pip install -r requirements.txt
```

### 4.2 配置 API 密钥

```bash
# 方式 1: 环境变量(推荐)
export OPENAI_API_KEY="sk-your-api-key"

# 方式 2: 写入 config.yaml
cat > config.yaml << EOF
llm:
  api_key: "sk-your-api-key"
  model: "gpt-4o"
EOF
```

### 4.3 运行第一个示例

```bash
# 示例 1: 简单对话
python cli.py "你好,请介绍一下自己"

# 示例 2: 读取文件
python cli.py "读取 README.md 文件的内容"

# 示例 3: 列出目录
python cli.py "列出当前目录下的所有文件"

# 示例 4: 使用 auto 模式(自动批准文件读写)
python cli.py --mode auto "创建 hello.txt 并写入 'Hello World'"
```

### 4.4 预期输出

```
> python cli.py "列出当前目录"

🤖 Assistant: 我来帮你列出当前目录的文件。

🔧 Tool Call: list_directory(path=".")
✅ Tool Result: 
README.md
cli.py
requirements.txt
...

🤖 Assistant: 当前目录下有以下文件:
- README.md
- cli.py
- requirements.txt
...

任务完成!
```

---

## 5. 与完整版 Claude Code 对照

### 5.1 功能对照表

| 组件 | Claude Code TS | Python MVP | 差异说明 | 扩展路径 |
|------|---------------|-----------|---------|---------|
| **Agent Loop** | ✅ 完整 | ✅ 完整 | 核心逻辑一致 | - |
| **工具数量** | 40+ | 4 | MVP 精简 | 按需添加 |
| **工具执行** | 并行/串行混合 | 全串行 | 简化并发控制 | 引入 asyncio.gather |
| **提示词层数** | 7 层 | 4 层 | 合并部分层级 | 动态注入扩展点 |
| **权限模式** | 4 种 | 4 种 | ✅ 完整 | - |
| **上下文压缩** | Auto-Compact | ❌ | MVP 暂不实现 | 摘要算法 |
| **记忆系统** | RAG + 向量库 | ❌ | MVP 暂不实现 | Chroma/Qdrant |
| **MCP 集成** | ✅ | ❌ | 预留接口 | MCP 协议客户端 |
| **多 Agent** | ✅ | ❌ | MVP 暂不实现 | 子 Agent 调度 |
| **流式 UI** | React Terminal | ❌ | CLI 文本输出 | Rich/tui 框架 |

### 5.2 代码量对比

| 模块 | Claude Code TS | Python MVP | 压缩比 |
|------|---------------|-----------|-------|
| Agent Loop | ~500 行 | ~150 行 | 3.3x |
| 工具系统 | ~5000 行 | ~300 行 | 16.7x |
| 权限管理 | ~2000 行 | ~150 行 | 13.3x |
| 配置系统 | ~1000 行 | ~100 行 | 10x |
| **总计** | **~8500 行** | **~700 行** | **12.1x** |

> 💡 **说明:** Python MVP 通过精简功能和去除 UI 层,实现了 12 倍的代码量压缩,同时保留了核心架构。

---

## 6. 核心设计原则

### 6.1 隔离原则

**严格禁止:**
- ❌ 从 `src/` 或 `vendor/` 导入任何 TypeScript 代码
- ❌ 复制 TypeScript 的业务逻辑实现
- ❌ 使用 TypeScript 风格的类型定义(如 `interface`, `type alias`)

**允许的做法:**
- ✅ 复用 JSON Schema 格式的协议定义
- ✅ 参考 Claude Code 的架构设计思路
- ✅ 使用独立的 `.md` 文档描述接口规范

### 6.2 可扩展性原则

**设计目标:**
- 添加工具只需 3 步: 实现 handler → 注册到 `TOOL_REGISTRY` → 更新文档
- 更换 LLM 提供商只需修改 `config.yaml`,无需改代码
- 权限规则支持通配符匹配(如 `run_command:git *`)

**示例: 添加 grep 工具**
```python
# 1. 实现 handler (tools/builtin/grep.py)
def grep_handler(pattern: str, path: str = ".") -> str:
    import subprocess
    result = subprocess.run(
        ["grep", "-r", pattern, path],
        capture_output=True, text=True, timeout=10
    )
    return result.stdout

# 2. 注册到 TOOL_REGISTRY (tools/registry.py)
TOOL_REGISTRY["grep"] = {
    "description": "递归搜索文件内容",
    "parameters": {
        "type": "object",
        "properties": {
            "pattern": {"type": "string"},
            "path": {"type": "string", "default": "."}
        },
        "required": ["pattern"]
    },
    "handler": grep_handler,
    "permission_level": "read"
}

# 3. 更新文档 (docs/03-tools-and-permissions.md)
# 添加工具说明和使用示例
```

### 6.3 安全性原则

**三道防线:**
1. **Plan 模式拦截** - 禁止所有修改操作
2. **黑名单检查** - 拦截危险命令(`rm -rf /`, `sudo` 等)
3. **用户确认** - normal 模式下需手动批准

**最佳实践:**
- 命令超时限制(默认 30 秒)
- 工具输出截断(超过 500 行自动截断)
- 最大迭代次数限制(默认 20 次)

---

## 7. 下一步行动

### 立即执行

1. **阅读后续文档**
   - [文档 2: Agent Loop 核心实现](./02-agent-loop-implementation.md)
   - [文档 3: 工具系统与权限管理](./03-tools-and-permissions.md)
   - [文档 4: 上下文管理与配置系统](./04-context-and-config.md)

2. **实施 Phase 1: Agent Loop 核心**
   ```bash
   # 创建核心文件
   touch core/agent_loop.py core/message.py
   # 实现 TAOR 循环(参考文档 2)
   ```

3. **运行端到端测试**
   ```bash
   python cli.py "你好"
   ```

### 本周目标

- ✅ 完成 4 个专题文档编写
- ⏳ 实现 Agent Loop 核心循环
- ⏳ 集成 OpenAI SDK
- ⏳ 完成首次端到端测试

---

## 附录: 常见问题

### Q1: 为什么选择 OpenAI SDK 而不是直接调用 Anthropic API?

**A:** OpenAI SDK 已成为事实标准,且支持多后端:
```python
# 切换到 Anthropic
client = OpenAI(
    api_key=os.environ["ANTHROPIC_API_KEY"],
    base_url="https://api.anthropic.com/v1"
)

# 切换到本地模型(Ollama)
client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama"
)
```

### Q2: MVP 版本能否处理复杂任务?

**A:** 可以,但有限制:
- ✅ 简单文件操作、代码分析、命令执行
- ⚠️ 长对话可能超出上下文窗口(无自动压缩)
- ❌ 无法并行执行多个工具(效率较低)

### Q3: 如何贡献代码?

**A:** 
1. Fork 仓库
2. 创建分支 (`git checkout -b feature/my-tool`)
3. 实现功能 + 编写测试
4. 提交 PR 并描述变更

---

**文档版本:** v1.0  
**最后更新:** 2026-04-05  
**维护者:** Claude Code Python MVP Team
