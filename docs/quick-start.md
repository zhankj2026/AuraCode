# 快速开始

本文带你用 5 分钟完成 OpenCode 的安装与首次使用，体验核心交互能力。

---

## 1. 安装

### 环境要求

- Python 3.10+
- pip

### 安装步骤

```bash
# 进入 opencode 目录
cd opencode

# 安装依赖
pip install -r requirements.txt
```

---

## 2. 配置 API Key

OpenCode 需要一个 LLM API Key 才能运行。推荐两种方式：

### 方式一：环境变量（推荐）

```bash
# Linux/macOS
export OPENAI_API_KEY="your-api-key-here"

# Windows PowerShell
$env:OPENAI_API_KEY = "your-api-key-here"
```

### 方式二：写入配置文件

```bash
# 复制配置模板
cp config.example.yaml config.yaml
```

编辑 `config.yaml`，填入 API 信息：

```yaml
llm:
  provider: openai
  model: glm-4.7
  base_url: https://open.bigmodel.cn/api/paas/v4
  max_tokens: 4096
  temperature: 0.2
```

---

## 3. 启动对话

### 多轮对话模式

```bash
# 直接启动
python cli.py

# 带初始提问启动
python cli.py "帮我分析这个项目的目录结构"
```

启动后进入交互界面，直接输入问题即可：

```
> 帮我找出项目中所有的 Python 文件，并统计数量
```

AI 会自动调用工具（`glob`、`run_command` 等）完成任务并返回结果。

### 命令模式

无需进入交互界面，直接执行单条命令：

```bash
# 分析项目
python cli.py -c analyze .

# 查看状态
python cli.py -c status
```

---

## 4. 使用斜杠命令

在对话模式中输入 `/` 开头的命令可触发特殊功能：

| 命令 | 作用 |
|------|------|
| `/help` | 查看所有可用命令 |
| `/status` | 查看当前会话状态（Token 用量、模型等）|
| `/cost` | 查看本次会话费用 |
| `/clear` | 清空对话历史，重新开始 |
| `/compact` | 压缩对话历史，保留关键摘要 |
| `/commit` | AI 分析变更并生成 Git 提交 |
| `/model` | 运行时切换模型 |

示例：

```
> /status

会话状态:
  模型: glm-4.7
  Token: 已用 3,200 / 200,000
  迭代: 2/20
  费用: $0.012
```

---

## 5. 权限控制

默认使用 `normal` 模式，危险操作（如执行 Shell 命令）会弹出确认提示。

```bash
# 使用自动模式（自动批准安全操作）
python cli.py --mode auto

# 使用只读计划模式（不执行任何修改）
python cli.py --mode plan
```

详见 [权限管理](user-guide/permissions.md)。

---

## 6. 下一步

完成基本体验后，可以深入了解各项功能：

- [对话交互](user-guide/chat.md) — 了解完整的对话交互机制
- [工具系统](user-guide/tools.md) — 探索 53 个内置工具
- [命令参考](user-guide/commands.md) — 46 条命令完整说明
- [Bridge 远程控制](advanced/bridge.md) — 从浏览器远程操控

---

## 常见问题

**Q: 如何更换模型？**
A: 运行时使用 `/model <模型名>` 切换，或修改 `config.yaml` 中的 `llm.model`。

**Q: 遇到 429 Too Many Requests 怎么办？**
A: OpenCode 内置指数退避重试（最多 5 次），一般无需手动处理。可配置 Fallback 模型作为备选。

**Q: 如何保存会话？**
A: 会话自动持久化到 `~/.opencode/sessions/`，下次用 `/resume` 恢复。
