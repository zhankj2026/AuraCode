# Claude Code Python MVP

基于 Claude Code 架构设计的 Python 实现，提供生产级 AI 编程助手的核心功能。

## 特性

- **TAOR 循环**: Think-Act-Observe-Repeat 智能体循环
- **工具系统**: 22+ 内置工具，支持文件操作、命令执行、代码分析
- **权限管理**: 多级权限控制 (normal/auto/plan/bypass)
- **插件系统**: 动态加载插件，扩展功能
- **钩子系统**: 在工具执行前后插入自定义逻辑
- **技能系统**: 渐进式披露，按需注入领域知识
- **Subagent**: 并行任务执行，支持多智能体协作
- **记忆系统**: 仿 Claude Code 设计，持久化用户/项目/反馈记忆
- **命令系统**: 12+ 内置命令，支持对话和命令两种模式

## 快速开始

### 1. 环境准备

```bash
# 确保 Python 3.10+
python --version

# 安装依赖
pip install openai
```

### 2. 配置 API 密钥

#### 智谱 GLM (推荐)

```bash
# Windows PowerShell
$env:OPENAI_API_KEY="your-zhipu-api-key"
$env:OPENAI_BASE_URL="https://open.bigmodel.cn/api/paas/v4"

# Linux/Mac
export OPENAI_API_KEY="your-zhipu-api-key"
export OPENAI_BASE_URL="https://open.bigmodel.cn/api/paas/v4"
```

**获取 API Key**: https://open.bigmodel.cn/

### 3. 运行

#### 多轮对话模式（推荐）

```bash
# 启动交互式对话
python cli.py

# 带初始问题启动
python cli.py "帮我分析这个项目"

# 对话中可用的命令
> /help          # 显示帮助
> /skills        # 列出技能
> /activate python-standards  # 激活技能
> /clear         # 清空历史
> /status        # 查看状态
> /exit          # 退出
```

#### 命令模式

```bash
# 分析代码
python cli.py --command analyze .

# 运行测试
python cli.py --command test

# 管理技能
python cli.py --command skills activate python-standards

# 查看状态
python cli.py --command status

# 查看帮助
python cli.py --command help
```

**详细文档**: 
- [多轮对话模式](docs/CHAT_MODE.md)
- [命令模式文档](docs/COMMAND_MODE.md)

## 项目结构

```
opencode/
├── cli.py                 # CLI 入口 (双模式: 对话/命令)
├── core/                  # 核心实现
│   ├── agent_loop.py     # TAOR 循环
│   ├── context.py        # 项目上下文
│   ├── message.py        # 消息处理
│   ├── subagent.py       # Subagent 管理
│   └── memory.py         # 记忆系统
├── tools/                 # 工具系统
│   ├── registry.py       # 工具注册表
│   └── builtin/          # 内置工具 (22+)
│       ├── read_file.py
│       ├── write_file.py
│       ├── run_command.py
│       ├── list_directory.py
│       ├── grep.py
│       ├── find.py
│       ├── analyze_file.py
│       ├── replace_in_file.py
│       ├── undo_edit.py
│       ├── lint.py
│       ├── run_tests.py
│       ├── subagent.py
│       ├── plan_agent.py
│       ├── skill_tools.py
│       └── memory_tools.py
├── commands/              # 命令系统 (12+ 内置命令)
│   ├── registry.py       # 命令注册表
│   ├── base.py           # 命令基类
│   └── builtin/          # 内置命令
│       ├── help_command.py
│       ├── status_command.py
│       ├── skills_command.py
│       ├── plugins_command.py
│       ├── analyze_command.py
│       ├── test_command.py
│       ├── lint_command.py
│       └── subagents_command.py
├── permissions/           # 权限管理
│   └── manager.py
├── plugins/               # 插件系统
│   ├── base.py
│   ├── loader.py
│   └── example_autoformat.py
├── hooks/                 # 钩子系统
│   └── manager.py
├── skills/                # 技能系统
│   ├── context.py        # 技能上下文
│   ├── loader.py         # 技能管理器
│   ├── python-standards/ # Python 编码规范
│   └── git-workflow/     # Git 工作流
├── tests/                 # 测试文件
│   ├── test_phase*.py    # Phase 测试
│   ├── test_integration.py
│   ├── test_hooks_execution.py
│   ├── test_skill_*.py
│   └── demos/            # 演示文件
└── docs/                  # 文档
    ├── QUICKSTART.md     # 快速开始指南
    ├── USAGE_GUIDE.md    # 完整使用指南
    ├── COMMAND_MODE.md   # 命令模式文档
    ├── CHAT_MODE.md      # 对话模式文档
    ├── code.md           # 完整开发记录
    └── SKILL_*.md        # 技能系统文档
```

## 核心功能

### 1. 工具系统 (22+ 内置工具)

- **文件操作**: read_file, write_file, list_directory
- **搜索分析**: grep, find, analyze_file
- **代码编辑**: replace_in_file, undo_edit
- **质量检查**: lint, run_tests
- **命令执行**: run_command
- **智能体**: spawn_subagent, plan_agent
- **技能管理**: activate_skill, list_skills
- **记忆管理**: save_memory, load_memory, search_memories

### 2. 技能系统

渐进式披露设计，按需注入领域知识：

```python
# 可用技能列表（元数据，始终显示）
## 可用技能
- python-standards: Python 编码规范 [未激活]
- git-workflow: Git 工作流规范 [未激活]

# 激活后注入完整内容
activate_skill("python-standards")
```

### 3. 记忆系统

仿 Claude Code 设计，支持 4 种记忆类型：

- **user**: 用户角色、偏好、知识背景
- **feedback**: 用户反馈指导（有效/无效方法）
- **project**: 项目目标、截止日期、状态
- **reference**: 外部系统参考（Bug 追踪、文档等）

### 4. 插件系统

动态加载插件，扩展功能：

```python
class MyPlugin(ToolPlugin):
    @property
    def name(self):
        return "my-plugin"

    def get_tools(self):
        return [...]  # 插件提供的工具

    def get_hooks(self):
        return [...]  # 插件提供的钩子
```

### 5. 钩子系统

在工具执行的不同阶段插入自定义逻辑：

```python
# PreToolUse: 工具执行前
# PostToolUse: 工具执行后
# PostToolUseFailure: 工具失败时
hook_manager.register_hook("PreToolUse", my_hook)
```

### 6. Subagent 系统

并行执行多个任务：

```python
# 创建并行任务
spawn_subagent(task="分析代码结构")
spawn_subagent(task="生成测试用例")

# 获取结果
join_subagent(agent_id="...")
```

### 7. 命令系统

12+ 内置命令，支持对话模式和命令模式：

```bash
# 对话模式中使用
> /help          # 显示帮助
> /skills        # 列出技能
> /activate python-standards  # 激活技能
> /status        # 查看状态
> /clear         # 清空历史
> /exit          # 退出

# 命令模式
python cli.py --command analyze .
python cli.py --command skills activate python-standards
python cli.py --command status
```

## 文档

- [快速开始指南](docs/QUICKSTART.md) - 5 分钟上手指南
- [完整使用指南](docs/USAGE_GUIDE.md) - 详细功能说明
- [对话模式文档](docs/CHAT_MODE.md) - 多轮对话模式
- [命令模式文档](docs/COMMAND_MODE.md) - 命令模式详解
- [开发文档](docs/code.md) - 完整开发记录
- [技能系统设计](docs/SKILL_FINAL_DESIGN.md) - 技能系统详解
- [插件开发指南](docs/01-architecture-overview.md) - 架构概览

## 测试

```bash
# 运行所有测试
cd tests
python test_phase1_tools.py
python test_phase2_complete.py
python test_phase3_tools.py
python test_phase4_tools.py
python test_phase5_tools.py
python test_phase6_tools.py

# 集成测试
python test_integration.py
python test_hooks_execution.py
python test_skill_tools.py
python test_skill_metadata.py
python test_command_mode.py
python test_chat_mode.py
python test_memory_system.py

# 演示
python demos/demo_tools.py
python demos/demo_skills.py
python demos/demo_memory_system.py
```

## 配置选项

```python
config = {
    # LLM 配置
    "api_key": "...",
    "base_url": "...",
    "model": "glm-4-plus",

    # Agent 配置
    "max_iterations": 20,
    "permission_mode": "normal",  # normal/auto/plan/bypass

    # 扩展系统
    "enable_plugins": True,
    "enable_hooks": True,
    "enable_skills": True,
    "enable_memory": True,
    "active_skills": [],  # 默认激活的技能

    # 记忆系统
    "memory_dir": ".claude/memory",  # 记忆存储目录
}
```

## 支持的 LLM

### 智谱 GLM (推荐)

```bash
# 环境变量配置
export OPENAI_API_KEY="your-zhipu-api-key"
export OPENAI_BASE_URL="https://open.bigmodel.cn/api/paas/v4"

# 可用模型
# glm-4-plus - 最强性能 (推荐)
# glm-4 - 标准版
# glm-4-air - 快速响应
# glm-4-flash - 超快速度
# glm-4.7 - 最新版
```

**获取 API Key**: https://open.bigmodel.cn/

### OpenAI

```bash
# 环境变量配置
export OPENAI_API_KEY="sk-your-api-key"

# 可用模型
# gpt-4o - 最新 GPT-4 模型
# gpt-4-turbo - GPT-4 Turbo
# gpt-3.5-turbo - 经济实惠
```

## 开发路线图

- [x] Phase 1: 基础工具系统
- [x] Phase 2: 文件编辑工具
- [x] Phase 3: 质量检查工具
- [x] Phase 4: 插件和钩子系统
- [x] Phase 5: 技能系统
- [x] Phase 6: Subagent 系统
- [ ] Phase 7: 高级功能（规划中）

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可证

MIT License
