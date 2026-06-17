# 对话交互

OpenCode 的核心交互方式是多轮对话。AI 代理在每一轮中会分析你的需求，自动调用合适的工具完成任务，并将结果呈现给你。

---

## 工作模式

OpenCode 提供三种启动模式：

### 对话模式（默认）

```bash
python cli.py
python cli.py "你的问题"
```

进入交互式 REPL，持续对话直到完成目标。

### 命令模式

```bash
python cli.py -c <command> [args...]
```

执行单条命令后退出，适合脚本与 CI/CD 集成。

### Bridge 远程控制模式

```bash
python cli.py --bridge --bridge-port 9000
```

启动 REST + WebSocket 服务，可从浏览器或其他客户端远程操控。详见 [Bridge 远程控制](../advanced/bridge.md)。

---

## 对话循环

OpenCode 采用 **TAOR 循环**（Think → Act → Observe → Repeat）：

```
用户提问
  ↓
[Think]  AI 分析需求，规划下一步
  ↓
[Act]    调用工具（读文件/搜索/写文件/执行命令...）
  ↓
[Observe] 观察工具结果
  ↓
[Repeat]  重复直到任务完成，返回最终结果
```

每一轮迭代都会消耗 Token，默认最多 20 轮（可配置）。

---

## 流式输出

AI 回复默认以流式方式逐字显示，无需等待完整响应。可通过 `/model` 命令切换模型。

---

## 上下文管理

对话过程中，所有消息（用户输入 + AI 回复 + 工具结果）共同构成上下文窗口。

| 命令 | 作用 |
|------|------|
| `/context` | 查看当前 Token 分布与使用情况 |
| `/compact` | LLM 驱动压缩历史，保留关键摘要 |
| `/clear` | 清空对话历史，重新开始 |

### 自动压缩

当上下文接近窗口上限（默认 200,000 Token）时，OpenCode 会自动触发压缩：
- 旧的工具结果被裁剪（只保留关键变更区域）
- 早期对话被压缩为摘要
- base64 图片被剥离

---

## 会话持久化

每次对话结束后自动保存，可通过 `/resume` 恢复：

```
> /resume

最近会话:
  1. 2024-01-15 14:30 - 重构 auth 模块 (12 轮, $0.08)
  2. 2024-01-15 10:15 - 修复 bug #234 (5 轮, $0.03)

输入编号恢复，或 /resume --all 查看全部
```

会话文件存储在 `~/.opencode/sessions/`。

---

## 会话回退

如果 AI 的某步操作不符合预期，可以回退到之前的检查点：

```
> /rewind

已回退到检查点 #3（撤销最近 2 轮对话）
```

---

## CLI 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `prompt` | 初始输入 | - |
| `--mode` | 权限模式: `normal` / `auto` / `plan` / `bypass` | `normal` |
| `--model` | LLM 模型名称 | `glm-4.7` |
| `--base-url` | API Base URL | 环境变量 |
| `--max-iterations` | 最大迭代次数 | `20` |
| `-c, --command` | 命令模式 | - |
| `-v, --verbose` | 显示详细日志 | `false` |
| `--bridge` | 启动 Bridge 服务 | `false` |
| `--bridge-port` | Bridge 端口 | `8765` |
| `--bridge-host` | Bridge 绑定地址 | `127.0.0.1` |

---

## 相关命令

| 命令 | 说明 |
|------|------|
| `/status` | 当前会话状态 |
| `/cost` | 会话费用追踪 |
| `/model` | 切换模型 |
| `/export` | 导出对话为文件 |
| `/history` | 会话历史管理 |
