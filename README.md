# Claude Code Python MVP

基于 Claude Code 架构设计的 Python 实现，提供生产级 AI 编程助手的核心功能。

## 特性

- **TAOR 循环**: Think-Act-Observe-Repeat 智能体循环
- **工具系统**: 17+ 内置工具，支持文件操作、命令执行、代码分析
- **权限管理**: 多级权限控制 (normal/auto/plan/bypass)
- **插件系统**: 动态加载插件，扩展功能
- **钩子系统**: 在工具执行前后插入自定义逻辑
- **技能系统**: 渐进式披露，按需注入领域知识
- **Subagent**: 并行任务执行，支持多智能体协作

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

```bash
# 基本使用
python cli.py "帮我分析这个项目的结构"

# 指定模型
python cli.py "重构这个函数" --model glm-4-plus

# 自动模式（无需确认）
python cli.py "运行测试" --mode auto
```

## 项目结构

```
opencode/
├── cli.py                 # CLI 入口
├── core/                  # 核心实现
│   ├── agent_loop.py     # TAOR 循环
│   ├── context.py        # 项目上下文
│   ├── message.py        # 消息处理
│   └── subagent.py       # Subagent 管理
├── tools/                 # 工具系统
│   ├── registry.py       # 工具注册表
│   └── builtin/          # 内置工具 (17+)
│       ├── read_file.py
│       ├── write_file.py
│       ├── run_command.py
│       ├── subagent.py
│       └── skill_tools.py
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
│   └── demos/            # 演示文件
└── docs/                  # 文档
    ├── code.md           # 完整开发记录
    ├── USAGE_GUIDE.md    # 使用指南
    └── SKILL_*.md        # 技能系统文档
```

## 核心功能

### 1. 工具系统

17+ 内置工具，涵盖：

- **文件操作**: read_file, write_file, list_directory
- **搜索分析**: grep, find, analyze_file
- **代码编辑**: replace_in_file, undo_edit
- **质量检查**: lint, run_tests
- **命令执行**: run_command
- **智能体**: spawn_subagent, plan_agent
- **技能管理**: activate_skill, list_skills

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

### 3. 插件系统

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

### 4. 钩子系统

在工具执行的不同阶段插入自定义逻辑：

```python
# PreToolUse: 工具执行前
# PostToolUse: 工具执行后
# PostToolUseFailure: 工具失败时
hook_manager.register_hook("PreToolUse", my_hook)
```

### 5. Subagent 系统

并行执行多个任务：

```python
# 创建并行任务
spawn_subagent(task="分析代码结构")
spawn_subagent(task="生成测试用例")

# 获取结果
join_subagent(agent_id="...")
```

## 文档

- [完整使用指南](docs/USAGE_GUIDE.md)
- [开发文档](docs/code.md)
- [技能系统设计](docs/SKILL_FINAL_DESIGN.md)
- [插件开发指南](docs/01-architecture-overview.md)

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

# 演示
python demos/demo_tools.py
python demos/demo_skills.py
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
    "active_skills": [],  # 默认激活的技能
}
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
