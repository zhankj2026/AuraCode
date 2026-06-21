---
name: debug
description: 调试和诊断当前会话中的问题，分析错误日志和异常行为
trigger: 当用户遇到错误、异常行为或需要诊断问题时激活，或用户主动调用 /debug
when_to_use: 当遇到错误、异常行为或需要诊断问题时主动激活
argument_hint: "[error description or log content]"
---

# Debug: 会话问题诊断

帮助诊断当前 opencode 会话中遇到的问题。系统性分析错误、异常行为和配置问题。

## 诊断流程

### Step 1: 收集信息

**1.1 确认问题描述**
- 用户描述了什么问题？
- 是否有错误消息或堆栈跟踪？
- 问题是在什么操作时发生的？

**1.2 检查项目环境**
```bash
# Python 版本
python --version

# 已安装的包
pip list 2>/dev/null || pip3 list

# 检查 opencode 配置
cat opencode/config.yaml 2>/dev/null || echo "No config.yaml found"
```

**1.3 检查 Git 状态**
```bash
git status
git log --oneline -5
```

### Step 2: 分析常见错误模式

**Python 导入错误:**
- 检查 `sys.path` 是否包含项目根目录
- 检查 `__init__.py` 文件是否缺失
- 检查包名拼写和大小写

**API 调用失败:**
- 检查 API 密钥是否配置（`OPENAI_API_KEY` 环境变量）
- 检查网络连接
- 检查模型名称是否正确
- 检查 rate limit 是否超限

**工具执行失败:**
- 检查工具是否在注册表中（`/skills list`）
- 检查权限管理器配置
- 检查命令是否可在 shell 中执行

**配置问题:**
- 检查 `config.yaml` 的 YAML 语法是否合法
- 检查必要字段是否完整（model, api_key 等）
- 检查插件/钩子配置是否冲突

### Step 3: 系统性排查

按优先级逐一排查：

1. **语法和导入问题** — 尝试 `python -c "import your_module"`
2. **依赖问题** — 检查 `requirements.txt` 是否完整，运行 `pip install -r requirements.txt`
3. **权限问题** — 检查文件/目录权限
4. **端口/地址冲突** — 如果是服务，检查端口是否被占用
5. **版本兼容性** — 检查 Python 版本和依赖版本是否匹配

### Step 4: 提供修复方案

对每个发现的问题：

1. **解释根因** — 为什么会出现这个问题
2. **提供修复命令** — 可以直接执行的具体命令
3. **预防措施** — 如何避免再次出现

## 日志分析

如果用户开启了 `--verbose` 模式，日志会包含 DEBUG 级别信息：

```bash
# 查看最近的日志输出（stderr）
# 在 --verbose 模式下重新运行以捕获完整日志

# 常见的日志级别
# DEBUG - 详细调试信息
# INFO - 一般信息（skill 加载、工具注册等）
# WARNING - 潜在问题（配置缺失、降级行为）
# ERROR - 明确的错误（API 调用失败、文件不存在）
```

## 常见 opencode 问题速查

| 问题 | 可能原因 | 快速修复 |
|------|---------|---------|
| "API 调用失败" | 未配置 API Key | `export OPENAI_API_KEY=sk-...` |
| "工具未找到" | 工具未注册 | 检查 `tools/builtin/__init__.py` |
| "Skill 加载失败" | SKILL.md 格式错误 | 检查 frontmatter YAML 语法 |
| "权限被拒绝" | 权限管理器拦截 | 检查 `permissions/manager.py` 配置 |
| "模型不可用" | 模型名称错误 | 检查 `config.yaml` 的 model 字段 |
| "命令未找到" | 命令未注册 | 检查 `commands/builtin/__init__.py` |
| "插件加载失败" | 插件接口不匹配 | 检查 `plugins/base.py` 的 ToolPlugin 基类 |

## 调试原则

1. **重现问题** — 先确认问题可以稳定重现
2. **最小化复现** — 找到触发问题的最小操作序列
3. **对比正常工作时的状态** — 什么变了？
4. **一次修一个问题** — 避免多个修改互相干扰
5. **验证修复** — 修复后确认问题消失且无副作用
