---
name: stuck
description: 诊断卡死、缓慢或无响应的 auracode 会话，分析进程状态和资源使用
trigger: 用户主动调用 /stuck
when_to_use: 当用户感觉 auracode 会话卡住、无响应或运行缓慢时主动激活
argument_hint: "[PID or symptom description]"
---

# Stuck: 诊断卡死/缓慢的 auracode 会话

调查当前机器上卡死或运行缓慢的 auracode 进程，输出诊断报告。

## 目标

找到卡住或异常的 auracode 进程，分析原因并提供诊断信息。**仅诊断，不终止进程。**

## 卡死信号

以下迹象表明会话可能有问题：

| 信号 | 含义 | 如何检测 |
|------|------|---------|
| **CPU ≥90% 持续** | 可能是无限循环 | 间隔 1-2s 采样两次确认 |
| **进程状态 D（不可中断睡眠）** | I/O 挂起 | `ps` 输出的 state 列首字符 |
| **进程状态 T（已停止）** | 用户可能误按 Ctrl+Z | `ps` 输出 |
| **进程状态 Z（僵尸）** | 父进程未回收 | `ps` 输出 |
| **RSS ≥4GB** | 内存泄漏导致卡顿 | `ps` 的 RSS 列 |
| **挂起的子进程** | 卡住的 git/shell 子进程冻结父进程 | `pgrep -lP <pid>` |

## 调查步骤

### Step 1: 列出所有 auracode 进程

**macOS/Linux:**
```bash
ps -axo pid=,pcpu=,rss=,etime=,state=,comm=,command= | grep -E 'python.*auracode' | grep -v grep
```

**Windows (PowerShell):**
```powershell
Get-Process python* | Where-Object { $_.CommandLine -like '*auracode*' } |
  Select-Object Id, CPU, WorkingSet64, StartTime, State
```

**成功标准**: 获取所有 auracode 相关进程的 PID、CPU、内存、运行时间。

### Step 2: 分析可疑进程

对每个可疑进程，深入检查：

```bash
# 子进程（可能卡住的 git/shell）
pgrep -lP <pid>

# 如果高 CPU：间隔 1-2s 再采样一次确认
ps -p <pid> -o pcpu=,rss=,state=,etime=

# 如果子进程看起来挂起，查看其完整命令行
ps -p <child_pid> -o command=
```

**Windows (PowerShell):**
```powershell
# 查看子进程
Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq $PID } |
  Select-Object ProcessId, Name, CommandLine
```

**成功标准**: 识别出具体哪个进程/子进程异常，以及异常原因。

### Step 3: 检查 Bridge 会话状态（如适用）

如果 auracode 使用 Bridge 模式，检查 WebSocket 连接状态：

```bash
# 检查 Bridge 服务器端口
netstat -an | grep -E '(8765|8766)'

# 检查最近的会话日志
ls -la ~/.auracode/sessions/ | tail -5
```

**成功标准**: 确认 Bridge 连接是否正常。

### Step 4: 输出诊断报告

```
## 诊断报告

### 进程概况
| PID | CPU% | RSS | 状态 | 运行时间 | 命令 |
|-----|------|-----|------|---------|------|
| ... | ... | ... | ... | ... | ... |

### 发现的问题
- [问题描述]: [具体 PID、CPU%、子进程等]

### 可能的原因
- [分析]: [为什么出现这个问题]

### 建议操作
- [建议]: [用户可以做什么来恢复]
```

如果所有进程都健康，直接告知用户——不要制造不存在的问题。

**成功标准**: 用户获得清晰的诊断结论和建议操作。

## 注意事项

1. **不要终止任何进程** — 这是纯诊断工具
2. **如果用户给了参数（PID 或症状），优先调查那里**
3. **二次采样确认** — 高 CPU 需要两次采样确认不是瞬时峰值
4. **检查子进程** — 卡住的 `git`、`python` 子进程是常见根因

## 常见问题速查

| 症状 | 可能原因 | 建议 |
|------|---------|------|
| 完全无响应 | API 调用超时或网络问题 | 检查网络连接，等待超时重试 |
| 响应极慢 | 上下文过大导致 token 超限 | 使用 `/compact` 压缩对话 |
| CPU 持续 100% | 无限循环或 Shell 命令卡住 | 检查是否有 `run_command` 在执行长命令 |
| 内存持续增长 | 大型 diff 或文件读取未裁剪 | 重启会话 |
| Bridge 断连 | WebSocket 超时 | 刷新浏览器页面重连 |
