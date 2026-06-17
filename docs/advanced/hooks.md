# 钩子系统

钩子（Hooks）是配置驱动的事件回调机制，让你在 AI 操作的关键节点插入自定义逻辑。

---

## 事件类型

| 事件 | 触发时机 |
|------|----------|
| `PreToolUse` | 工具调用前（可拦截）|
| `PostToolUse` | 工具调用后 |
| `Stop` | 代理循环结束 |
| `ToolError` | 工具执行出错 |
| `UserMessage` | 用户消息接收 |
| `PreCompact` | 上下文压缩前 |
| `PostCompact` | 上下文压缩后 |
| `ContextWarning` | 上下文窗口接近上限 |

---

## 配置方式

### 项目级配置（`.opencode/hooks.yaml`）

```yaml
hooks:
  PreToolUse:
    - command: "echo 'About to use tool: $TOOL_NAME'"
      filter: "run_command"     # 只匹配 run_command 工具
      priority: 10              # 优先级（数字越大越先执行）

  PostToolUse:
    - command: "black $FILE_PATH"
      filter: "write_file"      # 写 Python 文件后自动格式化
      matcher: "\\.py$"         # 正则匹配文件路径

  Stop:
    - command: "notify-send 'OpenCode task completed'"
```

### 运行时注册（插件方式）

插件可通过 `get_hooks()` 方法注册钩子：

```python
def get_hooks(self):
    return [
        {
            "event": "PostToolUse",
            "handler": self._after_write,
            "matcher": "write_file"
        }
    ]
```

---

## 特性

### 优先级排序

通过 `priority` 控制执行顺序，数字越大越先执行：

```yaml
hooks:
  PreToolUse:
    - command: "echo first"
      priority: 100
    - command: "echo second"
      priority: 50
```

### 短路机制

`PreToolUse` 钩子返回非零退出码时，后续钩子和工具调用均被跳过：

```yaml
hooks:
  PreToolUse:
    - command: "test -f $FILE_PATH"    # 文件不存在时阻止操作
      filter: "read_file"
      short_circuit: true              # 启用短路
```

### 错误隔离

单个钩子出错不影响其他钩子和主流程，错误会被记录但不中断执行。

### 文件监听热重载

修改 `.opencode/hooks.yaml` 后自动重载，无需重启。

---

## 环境变量

钩子执行时可访问以下环境变量：

| 变量 | 说明 |
|------|------|
| `$TOOL_NAME` | 当前工具名称 |
| `$TOOL_INPUT` | 工具输入（JSON）|
| `$FILE_PATH` | 操作的文件路径（如适用）|
| `$SESSION_ID` | 当前会话 ID |

---

## 管理命令

```
> /hooks

已注册 Hook (5 个):

  PreToolUse (2):
    1. [priority=100] echo 'About to use tool'  filter: run_command
    2. [priority=50]  validate.py               filter: write_file

  PostToolUse (2):
    1. black $FILE_PATH                         filter: write_file, matcher: \.py$
    2. log_hook.py                              filter: *

  Stop (1):
    1. notify-send 'Task completed'

> /hooks log

最近 Hook 执行日志:
  14:30:01  PreToolUse   run_command  ✅ 0.01s
  14:30:02  PostToolUse  write_file   ✅ 0.45s  (black 格式化)
  14:30:05  Stop                      ✅ 0.00s
```

---

## 相关命令

| 命令 | 说明 |
|------|------|
| `/hooks` | 查看已注册钩子 |
| `/hooks log` | 查看执行日志 |
| `/hooks reload` | 手动重新加载配置 |
