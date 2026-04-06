<
# Claude Code Python MVP

基于 Claude Code 架构设计的 Python 实现,遵循严格的隔离原则,提供最小化可行产品(MVP)。

## 📋 目录

- [快速开始](#快速开始)
- [项目结构](#项目结构)
- [核心功能](#核心功能)
- [架构文档](#架构文档)
- [开发指南](#开发指南)

## 🚀 快速开始

### 1. 环境准备

```bash
# 确保 Python 3.10+
python --version

# 安装依赖
pip install -r requirements.txt
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

#### OpenAI

```bash
# Windows PowerShell
$env:OPENAI_API_KEY="sk-your-openai-key"

# Linux/Mac
export OPENAI_API_KEY="sk-your-openai-key"
```

### 3. 运行第一个示例

```bash
# 使用 GLM-4-Plus (推荐)
python cli.py --model glm-4-plus "你好,请介绍一下自己"

# 读取文件
python cli.py --model glm-4-plus "读取 README.md 的内容"

# 使用 auto 模式
python cli.py --mode auto "创建 hello.txt 并写入 'Hello World'"
```

## 📁 项目结构

```
opencode/
├── core/                    # 核心引擎
│   ├── agent_loop.py        # TAOR 循环
│   ├── message.py           # 消息管理
│   └── context.py           # 上下文加载
├── tools/                   # 工具系统
│   ├── registry.py          # 工具注册表
│   └── builtin/             # 内置工具
├── permissions/             # 权限管理
│   └── manager.py           # 权限管理器
├── config/                  # 配置管理
│   ├── loader.py            # 配置加载器
│   └── defaults.yaml        # 默认配置
├── docs/                    # 架构文档
│   ├── 01-architecture-overview.md
│   ├── 02-agent-loop-implementation.md
│   ├── 03-tools-and-permissions.md
│   └── 04-context-and-config.md
├── tests/                   # 单元测试
├── cli.py                   # CLI 入口
├── requirements.txt         # 依赖包
└── README.md                # 本文档
```

## ✨ 核心功能

- ✅ **Agent Loop** - 完整的 TAOR 循环(Think-Act-Observe-Repeat)
- ✅ **工具系统** - 可扩展的工具注册表(JSON Schema)
- ✅ **权限管理** - 4 种模式(normal/auto/plan/bypass)
- ✅ **上下文管理** - CLAUDE.md 加载 + 技术栈检测
- ✅ **配置系统** - YAML 配置 + 环境变量覆盖

## 📖 架构文档

本项目的详细架构设计分为 4 个专题文档:

1. **[MVP 架构总览与快速启动](docs/01-architecture-overview.md)**
   - 项目定位与设计哲学
   - 整体架构图
   - 技术选型说明
   - 快速启动指南

2. **[Agent Loop 核心实现](docs/02-agent-loop-implementation.md)**
   - Agent Loop 完整代码
   - 消息管理系统
   - 系统提示词组装
   - 错误处理与重试

3. **[工具系统与权限管理](docs/03-tools-and-permissions.md)**
   - 工具注册表设计
   - 内置工具实现
   - 权限管理器(三道防线)
   - 工具扩展指南

4. **[上下文管理与配置系统](docs/04-context-and-config.md)**
   - CLAUDE.md 加载机制
   - YAML 配置系统
   - 环境变量优先级
   - 最佳实践

## 🛠️ 开发指南

### 添加工具

```python
# 1. 实现 handler
def my_tool_handler(param: str) -> str:
    return f"Result: {param}"

# 2. 注册到 TOOL_REGISTRY
from tools.registry import register_tool

register_tool("my_tool", {
    "description": "我的工具",
    "parameters": {
        "type": "object",
        "properties": {
            "param": {"type": "string"}
        },
        "required": ["param"]
    },
    "handler": my_tool_handler,
    "permission_level": "read"
})
```

### 运行测试

```bash
pytest tests/ -v --cov=opencode
```

### 代码格式化

```bash
black opencode/
```

## 🔒 安全注意事项

- ⚠️ **不要提交 API 密钥到 Git** - 使用环境变量或 `.gitignore`
- ⚠️ **谨慎使用 bypass 模式** - 仅在可信环境中使用
- ⚠️ **命令执行有风险** - normal 模式下会要求确认

## 📝 许可证

本项目仅供学习和研究使用。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request!

---

**版本:** v0.1.0 (MVP)  
**最后更新:** 2026-04-05

