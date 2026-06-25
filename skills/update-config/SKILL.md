---
name: update-config
description: 管理 auracode 配置，包括 LLM 设置、权限规则、钩子、日志等
trigger: 当用户需要修改项目配置、添加权限规则、配置钩子时激活，或用户主动调用 /update-config
when_to_use: 当需要修改 config.yaml、权限规则、钩子配置或 LLM 设置时主动激活
argument_hint: "<what to configure>"
---

# Update Config: auracode 配置管理

修改 auracode 的 `config.yaml` 配置文件，管理 LLM 设置、权限规则、钩子系统等。

## CRITICAL: 先读后写

**修改配置前，必须先读取现有 config.yaml 文件。** 合并新旧配置，不要替换整个文件。

## 配置文件位置

| 文件 | 用途 |
|------|------|
| `auracode/config.yaml` | 主配置文件 |
| `auracode/config.example.yaml` | 配置模板参考 |

## 配置结构详解

### LLM 配置

```yaml
llm:
  provider: openai           # LLM 提供商（使用 OpenAI 兼容接口）
  model: gpt-4o             # 模型名称
  base_url: https://api.openai.com/v1  # API 基础 URL
  api_key: "sk-..."         # API Key（推荐通过环境变量设置）
  max_tokens: 4096          # 最大输出 token 数
  temperature: 0.2          # 温度（越低越确定性）
```

**常用模型配置示例:**

```yaml
# OpenAI
llm:
  provider: openai
  model: gpt-4o
  base_url: https://api.openai.com/v1

# 智谱 GLM
llm:
  provider: openai
  model: glm-4.7
  base_url: https://open.bigmodel.cn/api/paas/v4

# 本地 Ollama
llm:
  provider: openai
  model: llama3
  base_url: http://localhost:11434/v1
```

### 权限配置

```yaml
permissions:
  mode: normal    # normal | auto | plan | bypass
  
  allow_rules:    # 自动允许的工具操作
    - "run_command:ls"
    - "run_command:git status"
    - "run_command:git diff"
    - "read_file:*"
  
  deny_rules:     # 始终拒绝的工具操作
    - "run_command:rm -rf"
    - "run_command:sudo"
    - "run_command:chmod 777"
```

**权限规则语法:**
- 精确匹配: `"run_command:git status"`
- 前缀通配: `"run_command:git *"` — 匹配所有 git 命令
- 工具通配: `"read_file:*"` — 匹配所有文件读取

**权限模式说明:**
| 模式 | 行为 |
|------|------|
| `normal` | 默认模式，按规则判断 |
| `auto` | 自动允许所有操作 |
| `plan` | 只规划不执行 |
| `bypass` | 跳过所有权限检查 |

### Agent 配置

```yaml
agent:
  max_iterations: 20        # 最大迭代次数（TAOR 循环上限）
  context_window: 200000    # 上下文窗口大小（token）
```

### 上下文配置

```yaml
context:
  load_claude_md: true      # 是否加载 CLAUDE.md
  max_files_read: 10        # 单次最大文件读取数
```

### 日志配置

```yaml
logging:
  level: DEBUG    # DEBUG | INFO | WARNING | ERROR
```

也可通过 `--verbose` 命令行参数启用 DEBUG 日志。

## 钩子系统 (Hooks)

auracode 支持 4 种钩子事件，通过 `hooks/manager.py` 管理：

| 事件 | 触发时机 | 用途 |
|------|---------|------|
| `PreToolUse` | 工具执行前 | 参数校验、权限预检、输入修改 |
| `PostToolUse` | 工具执行后 | 自动格式化、日志记录、结果验证 |
| `SessionStart` | 会话开始 | 初始化环境、加载额外上下文 |
| `PostToolUseFailure` | 工具执行失败 | 错误通知、自动重试、降级处理 |

### 钩子注册方式（Python 代码）

```python
from hooks.manager import HookManager

hook_manager = HookManager()

# 注册 PostToolUse 钩子
def auto_format(result, tool_name, **kwargs):
    """工具执行后自动格式化"""
    if tool_name in ('write_file', 'edit_file'):
        file_path = kwargs.get('file_path', '')
        if file_path.endswith('.py'):
            import subprocess
            subprocess.run(['black', file_path], check=False)
    return HookResult(allow=True)

hook_manager.register_hook(
    "PostToolUse",
    auto_format,
    matcher="write_file|edit_file"
)
```

### 常见钩子模式

**自动格式化 Python 文件:**
```python
def format_python(result, tool_name, **kwargs):
    file_path = kwargs.get('file_path', '')
    if file_path.endswith('.py'):
        import subprocess
        subprocess.run(['black', file_path], check=False)
        subprocess.run(['ruff', 'check', '--fix', file_path], check=False)
    return HookResult(allow=True)
```

**记录所有命令执行:**
```python
def log_commands(result, tool_name, **kwargs):
    if tool_name == 'run_command':
        command = kwargs.get('command', '')
        with open('.auracode_command_log.txt', 'a') as f:
            f.write(f"{datetime.now()}: {command}\n")
    return HookResult(allow=True)
```

**阻止危险操作:**
```python
def block_dangerous(result, tool_name, **kwargs):
    command = kwargs.get('command', '')
    dangerous = ['rm -rf', 'DROP TABLE', 'format']
    if any(d in command for d in dangerous):
        return HookResult(allow=False, block_reason=f"危险操作: {command}")
    return HookResult(allow=True)
```

## 配置修改工作流

1. **读取现有配置** — `cat auracode/config.yaml`
2. **理解用户意图** — 需要修改什么？
3. **合并变更** — 保留现有配置，只修改目标部分
4. **验证 YAML 语法** — 确保格式正确
5. **确认变更** — 告诉用户修改了什么

## 常见配置操作

### 添加权限规则
```yaml
# 读取现有 allow_rules，追加新规则
permissions:
  allow_rules:
    - "run_command:ls"          # 现有
    - "run_command:git status"  # 现有
    - "run_command:npm test"    # 新增
```

### 切换模型
```yaml
llm:
  model: gpt-4o-mini  # 改为更便宜的模型
```

### 调整 Agent 行为
```yaml
agent:
  max_iterations: 50  # 增加迭代次数上限
```

## 常见错误

1. **YAML 缩进错误** — YAML 严格要求缩进，使用空格不用 Tab
2. **替换而非合并** — 修改权限时不要覆盖已有规则
3. **API Key 硬编码** — 推荐使用环境变量 `OPENAI_API_KEY`
4. **忘记验证** — 修改后检查 YAML 语法是否合法
