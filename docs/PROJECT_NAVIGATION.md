# 📖 项目导航 - Claude Code Python MVP

欢迎使用 Claude Code Python MVP! 本文档帮助你快速找到所需资源。

---

## 🚀 快速开始

### 我是新用户,想立即运行

👉 阅读 [QUICKSTART.md](QUICKSTART.md) - 5分钟上手指南

```bash
cd opencode
pip install -r requirements.txt
export OPENAI_API_KEY="your-key"
python cli.py --mode bypass "列出当前目录"
```

### 我想了解项目架构

👉 阅读 [docs/01-architecture-overview.md](docs/01-architecture-overview.md) - MVP 架构总览

### 我想查看完成情况

👉 阅读 [COMPLETION_REPORT.md](COMPLETION_REPORT.md) - 实施完成报告

---

## 📚 文档索引

### 核心架构文档 (必读)

| 文档 | 内容 | 行数 | 适合人群 |
|------|------|------|----------|
| [01-architecture-overview.md](docs/01-architecture-overview.md) | MVP 定位、架构图、快速启动 | 450 | 所有人 |
| [02-agent-loop-implementation.md](docs/02-agent-loop-implementation.md) | Agent Loop 完整实现代码 | 813 | 开发者 |
| [03-tools-and-permissions.md](docs/03-tools-and-permissions.md) | 工具系统和权限管理 | 1179 | 开发者 |
| [04-context-and-config.md](docs/04-context-and-config.md) | 上下文管理和配置系统 | 1151 | 开发者 |

### 辅助文档

| 文档 | 用途 |
|------|------|
| [README.md](README.md) | 项目说明和使用指南 |
| [QUICKSTART.md](QUICKSTART.md) | 5分钟快速开始 |
| [COMPLETION_REPORT.md](COMPLETION_REPORT.md) | 实施完成总结 |
| [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) | 详细实施过程 |
| [PROGRESS.md](PROGRESS.md) | 进度跟踪(历史) |

---

## 💻 代码模块

### 核心模块

| 文件 | 功能 | 行数 | 说明 |
|------|------|------|------|
| `core/agent_loop.py` | Agent Loop 引擎 | 258 | **核心!** TAOR 循环实现 |
| `core/context.py` | 上下文加载器 | 215 | OPENCODE.md 和技术栈检测 |
| `core/message.py` | 消息管理 | 106 | 消息创建和验证 |

### 工具系统

| 文件 | 功能 | 说明 |
|------|------|------|
| `tools/registry.py` | 工具注册表 | 集中管理所有工具 |
| `tools/builtin/read_file.py` | 读取文件 | 文件大小限制 100KB |
| `tools/builtin/write_file.py` | 写入文件 | 自动创建目录 |
| `tools/builtin/run_command.py` | 执行命令 | 超时控制 30秒 |
| `tools/builtin/list_directory.py` | 列出目录 | 文件/目录分类 |

### 权限管理

| 文件 | 功能 | 说明 |
|------|------|------|
| `permissions/manager.py` | 权限管理器 | 三道防线 + 4种模式 |

### CLI 入口

| 文件 | 功能 |
|------|------|
| `cli.py` | 命令行接口,参数解析,日志配置 |

---

## 🎯 按任务查找

### 我想...

**运行程序**
→ [QUICKSTART.md](QUICKSTART.md) → 第3节"运行测试"

**理解 Agent Loop 工作原理**
→ [docs/02-agent-loop-implementation.md](docs/02-agent-loop-implementation.md) → 第2节"核心设计"

**添加新工具**
→ [docs/03-tools-and-permissions.md](docs/03-tools-and-permissions.md) → 第4节"扩展指南"

**修改权限策略**
→ [docs/03-tools-and-permissions.md](docs/03-tools-and-permissions.md) → 第3节"权限管理器"

**配置 API 密钥**
→ [QUICKSTART.md](QUICKSTART.md) → 第2节"配置 API 密钥"

**查看项目结构**
→ 阅读本文档 → "代码模块"部分

**了解与 Claude Code 的对应关系**
→ [COMPLETION_REPORT.md](COMPLETION_REPORT.md) → "与 Claude Code 源码的对应关系"

---

## 🔍 按问题查找

### 常见问题

**Q: 如何安装依赖?**
→ [QUICKSTART.md](QUICKSTART.md) → 第1节

**Q: 提示未设置 API Key?**
→ [QUICKSTART.md](QUICKSTART.md) → 常见问题 Q1

**Q: 工具执行总是需要确认?**
→ [QUICKSTART.md](QUICKSTART.md) → 常见问题 Q2

**Q: 如何查看执行日志?**
→ [QUICKSTART.md](QUICKSTART.md) → 常见问题 Q4

**Q: 如何扩展新功能?**
→ [docs/01-architecture-overview.md](docs/01-architecture-overview.md) → 第6节"扩展示例"

**Q: 支持哪些模型?**
→ 任何 OpenAI 兼容的模型(gpt-4o, gpt-3.5-turbo, 本地模型等)

---

## 📂 目录结构

```
opencode/
├── 📄 核心文档
│   ├── README.md                    # 项目说明
│   ├── QUICKSTART.md                # 快速开始 ⭐
│   ├── COMPLETION_REPORT.md         # 完成报告 ⭐
│   └── ...其他辅助文档
│
├── 📚 架构文档 (docs/)
│   ├── 01-architecture-overview.md      # 架构总览 ⭐⭐⭐
│   ├── 02-agent-loop-implementation.md  # Agent Loop 实现 ⭐⭐⭐
│   ├── 03-tools-and-permissions.md      # 工具和权限 ⭐⭐⭐
│   └── 04-context-and-config.md         # 上下文和配置 ⭐⭐
│
├── 💻 代码模块
│   ├── core/                          # 核心模块
│   │   ├── agent_loop.py              # Agent Loop 引擎 ⭐⭐⭐
│   │   ├── context.py                 # 上下文加载器
│   │   └── message.py                 # 消息管理
│   │
│   ├── tools/                         # 工具系统
│   │   ├── registry.py                # 工具注册表 ⭐⭐
│   │   └── builtin/                   # 内置工具
│   │       ├── read_file.py           # 读文件
│   │       ├── write_file.py          # 写文件
│   │       ├── run_command.py         # 执行命令
│   │       └── list_directory.py      # 列目录
│   │
│   ├── permissions/                   # 权限管理
│   │   └── manager.py                 # 权限管理器 ⭐⭐
│   │
│   └── cli.py                         # CLI 入口 ⭐
│
└── ⚙️ 配置文件
    ├── requirements.txt               # Python 依赖
    ├── config.example.yaml            # 配置示例
    └── .gitignore                     # Git 忽略规则
```

---

## 🎓 学习路径

### 初学者路径

1. **第1天**: 运行示例
   - 阅读 [QUICKSTART.md](QUICKSTART.md)
   - 安装依赖并运行第一个命令
   
2. **第2天**: 理解架构
   - 阅读 [docs/01-architecture-overview.md](docs/01-architecture-overview.md)
   - 了解整体设计
   
3. **第3天**: 深入核心
   - 阅读 [docs/02-agent-loop-implementation.md](docs/02-agent-loop-implementation.md)
   - 理解 Agent Loop 工作流程

### 开发者路径

1. **研究代码**
   - 从 `core/agent_loop.py` 开始
   - 查看工具实现 `tools/builtin/`
   
2. **扩展功能**
   - 参考 [docs/03-tools-and-permissions.md](docs/03-tools-and-permissions.md) 添加工具
   - 修改 `permissions/manager.py` 调整权限策略
   
3. **优化改进**
   - 添加单元测试
   - 性能优化
   - 新功能开发

---

## 🔗 外部资源

- **Claude Code 源码**: `../src/` (TypeScript 版本)
- **需求文档**: `opencode.md` (原始需求)
- **OpenAI SDK 文档**: https://platform.openai.com/docs

---

## 💡 提示

- ⭐ 标记表示重要文档/文件,建议优先阅读
- 所有代码都有详细的 docstring 注释
- 架构文档包含完整的代码示例和解释
- 遇到问题先查看 [QUICKSTART.md](QUICKSTART.md) 的"常见问题"部分

---

**祝你使用愉快!** 🎉

有任何问题,请参考对应的架构文档或提交 Issue。
