# 错误恢复

opencode 实现了多层错误恢复机制，确保在 API 限流、网络故障、上下文溢出等场景下仍能正常工作。

---

## 架构总览

```
LLM 调用失败
  │
  ├── 第 1 层: API 级重试（_call_llm_streaming 内部，最多 8 次）
  │     ├── 速率限制 → Retry-After / 错误消息提取 / 平方根退避
  │     ├── 服务器过载 → 指数退避 1-32s
  │     └── 超时/连接 → 指数退避 + 抖动
  │
  ├── 第 2 层: 轮次级恢复（run() 循环内）
  │     ├── 上下文过长 → 压缩 + 重试
  │     ├── 瞬时网络错误 → 等待 10s + 重试 1 次
  │     └── 连续服务器错误 → Fallback 模型
  │
  ├── 第 3 层: 工具级恢复（_execute_tool 内）
  │     ├── StopHook 拦截 → 恢复提示引导替代方案
  │     ├── 幂等工具失败 → ToolEnhancer 自动重试
  │     └── 权限拒绝 → 记录 + 提示
  │
  └── 第 4 层: 输出恢复
        └── 输出截断 → 续写提示（最多 3 次）
```

---

## 第 1 层：API 级重试

`_call_llm_streaming()` 内部实现，对每次 LLM 调用自动重试。

### 参数

| 参数 | 值 | 说明 |
|------|-----|------|
| `max_retries` | 8 | 最大重试次数 |
| `MAX_BACKOFF_S` | 32s | 非速率限制退避上限 |
| `RATE_LIMIT_FLOOR_S` | 8s | 速率限制最低等待 |
| `RATE_LIMIT_CAP_S` | 60s | 速率限制最大等待 |

### 错误分类

`_classify_error()` 按优先级分类：

| 分类 | HTTP 状态码 | 说明 |
|------|-------------|------|
| `rate_limit` | 429 | 速率限制 |
| `server_overload` | 529 / 500+overloaded | 服务器过载 |
| `timeout` | 408, 409 | 请求超时 |
| `auth` | 401, 403 | 认证失败（不重试） |
| `server_error` | 5xx | 服务器内部错误 |
| `prompt_too_long` | — | 上下文溢出 |
| `connection` | — | 网络连接问题 |

分类优先级：HTTP 状态码 > 异常类型检查 > 关键词匹配。

### 退避策略

```
速率限制:
  1. Retry-After 响应头（+ 10% 抖动，上限 5 分钟）
  2. 错误消息中的等待时间提示（如 GLM "Xs 后重试"）
  3. 默认: 8 × √attempt 秒 + 0~5s 随机抖动

普通瞬时错误:
  2^(attempt-1) 秒 + 25% 随机抖动，上限 32s
  即: 1s → 2s → 4s → 8s → 16s → 32s
```

### 重试事件

每次重试都会发射 `api_retry` 事件，Bridge 可实时展示：

```python
self._emit_event("api_retry", {
    "attempt": attempt,
    "max_retries": max_retries,
    "wait_seconds": round(wait, 1),
    "error": str(e),
    "category": category,
    "is_rate_limit": category == 'rate_limit',
})
```

---

## 第 2 层：轮次级恢复

`run()` 方法的 TAOR 循环内处理，在单次 API 重试耗尽后介入。

### 上下文过长恢复

当 LLM 返回 `context_length_exceeded` 错误时：

1. 裁剪旧工具结果（`_snip_old_tool_results()`）
2. 压缩消息历史（`_compact_messages()`）
3. 自动重试当前轮次

压缩后仍然失败则返回错误结果，不会无限重试。

### 瞬时网络错误恢复

超时、连接断开、服务器 5xx 等瞬时错误：

- 等待 10 秒后重试当前轮次（最多 1 次）
- 速率限制 (429) 不在此层重试（第 1 层已有 8 次）

### Fallback 模型

连续服务器错误超过阈值时自动切换到备用模型：

```python
# 配置
config = {
    "model": "glm-4.7",
    "fallback_model": "glm-4-flash",  # 备用模型
}

# 触发条件: 连续 2 次 5xx 服务器错误
_MAX_CONSECUTIVE_SERVER_ERRORS = 2
```

切换后后续请求自动使用 fallback 模型，直到会话结束或手动切换。

---

## 第 3 层：工具级恢复

### StopHook 恢复提示

当 PreToolUse 钩子阻止工具执行时，返回恢复提示引导 LLM 尝试替代方案：

```
Tool 'run_command' was blocked by safety hook.
Reason: dangerous command detected.
Please try an alternative approach or ask the user for guidance.
```

LLM 收到提示后会自动选择其他方法完成任务。

### 幂等工具自动重试

`ToolEnhancer` 对幂等工具（如 `read_file`、`list_files`）自动重试：

```python
# 可重试工具列表
retryable_tools = [
    "read_file", "list_files", "search_content",
    "get_diagnostics", "web_fetch", "web_search",
]

# 重试策略
max_retries = 2
base_delay = 0.5s
backoff_factor = 2
```

非幂等工具（如 `write_file`、`run_command`）不自动重试，避免副作用。

### 工具输出裁剪

大型工具输出（如 diff 结果超过 4000 字符）自动裁剪未修改区域，保留关键变更部分。

---

## 第 4 层：输出截断恢复

当 LLM 输出达到 `max_tokens` 上限被截断时：

1. 向消息历史追加续写提示
2. LLM 从中断处继续，无需道歉或回顾
3. 最多恢复 3 次（`max_output_recovery_limit`）

续写提示：
```
Output token limit hit. Resume directly — no apology,
no recap. Pick up mid-thought if that is where the cut happened.
Break remaining work into smaller pieces.
```

---

## 会话持久化保护

无论何种错误，会话数据都会被安全保存：

- **CLI 模式**：`try/finally` 包裹 `run()`，异常时也保存会话
- **Bridge 模式**：`_run_loop` 的 `finally` 块自动保存会话
- 可通过 `/resume` 命令恢复中断的会话

---

## 事件通知

所有错误恢复过程都会发射事件，供 Bridge UI 和日志系统追踪：

| 事件 | 触发时机 | 关键字段 |
|------|----------|----------|
| `api_retry` | API 级重试 | attempt, wait_seconds, category |
| `turn_retry` | 轮次级重试 | turn, error, wait_seconds |
| `prompt_too_long_recovery` | 上下文压缩恢复 | messages_before |
| `fallback_model_activated` | Fallback 模型激活 | model, fallback_model |

---

## 配置项

通过 `config.yaml` 或构造函数调整恢复行为：

```yaml
model: glm-4.7                    # 主模型
fallback_model: glm-4-flash       # 备用模型
max_iterations: 20                # TAOR 最大迭代
max_output_recovery_limit: 3      # 输出截断恢复上限
context_compact_threshold: auto   # 压缩阈值（auto=动态计算）
```
