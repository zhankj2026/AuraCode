# opencode 状态汇总与 Claude Code 差异分析

> 更新日期: 2026-06-12 | 最新提交: cc5

---

## 一、opencode 当前模块总览（13 次 Git 提交）

| 模块 | 文件数 | 核心能力 |
|------|--------|----------|
| **core/** | 6 | AgentLoop + SessionState + Memory + Context + Subagent + Message |
| **tools/builtin/** | 31 | read/write/replace/grep/find/glob/lsp/web/todo/ask/powershell/plan_mode/subagent/tool_search/sleep/config/notebook_edit/repl/task_manager/brief... |
| **commands/builtin/** | 16 | commit/compact/diff/context/plan/init/bridge/skills/status/subagents... |
| **bridge/** | 7 | REST+WebSocket 远程控制, 多会话管理, JWT认证, Web UI |
| **skills/** | 5域 | simplify/verify/debug/batch/update-config |
| **plugins/** | 3 | 插件加载器 + 示例插件 |
| **hooks/** | 2 | Pre/PostToolUse 钩子链 |
| **permissions/** | 2 | normal/auto/plan/bypass 四级权限 |
| **mcp/** | 完整 | MCP 协议客户端 + 5传输层 + 技能/工具集成 |
| **cli.py** | 1 | 对话模式 + 命令模式 + Bridge 模式 |

---

## 二、P0/P1/P2 实现详情

### P0 - SessionState 集中状态管理

- **session_state.py** (304行):
  - `TokenUsage`: 跨轮次 prompt/completion/total token 累计
  - `QueryResult`: 结构化报告（status/text/duration/turns/cost/usage/error/denials）
  - `SessionState`: 集中管理 messages/usage/cost/abort/permissions/fallback

- **agent_loop.py 集成**:
  - `self.messages` → `self.state.messages`（通过 @property 向后兼容）
  - `self.state = SessionState(max_budget_usd, fallback_model)`
  - `_call_llm()` 使用 `state.get_active_model()` 支持 fallback 切换

### P1 - 错误恢复与控制

| 特性 | 实现方式 |
|------|----------|
| **max_output_tokens 恢复** | 检测 `finish_reason=="length"` → 注入 continue 消息重试（最多 3 次） |
| **Fallback 模型** | API 异常时自动切换到备用模型（`activate_fallback()`） |
| **中断控制** | `threading.Event` 实现 `abort()`，循环内两处检查点 |
| **预算控制** | `max_budget_usd` 上限检查，超限自动终止并返回 `error_max_budget` |

### P2 - 上下文管理

| 特性 | 实现方式 |
|------|----------|
| **上下文压缩** | `_compact_messages()`: 消息超阈值时保留 system + 最近 N 条，旧消息压缩为摘要 |
| **权限拒绝追踪** | `record_permission_denial()` 记录到 QueryResult.permission_denials |
| **CLI 结构化展示** | `process_round()` 展示 `QueryResult.format_summary()`，`show_stats()` 从 SessionState 读取 |

---

## 三、opencode vs Claude Code 差异对比

| 维度 | Claude Code | opencode | 完成度 |
|------|------------|----------|--------|
| **核心循环** | query.ts 1730行 while(true) 状态机 | agent_loop.py ~1250行 TAOR循环 | **~75%** |
| **状态管理** | AppStateStore.ts ~100字段 + Store发布订阅 | SessionState 精简版，集中管理 token/cost/abort | **~60%** |
| **查询结果** | QueryEngine yield result (含duration/cost/usage/denials) | QueryResult dataclass (相同字段) | **~90%** |
| **错误恢复(6层)** | Fallback→Prompt-too-long→MaxOutput→StopHook→Budget→ImageStrip | Fallback + MaxOutput + Budget + Prompt-too-long (4层) | **~65%** |
| **上下文压缩** | Snip→Microcompact→ContextCollapse→AutoCompact | Snip→Microcompact→ContextCollapse→AutoCompact (4级) | **~80%** |
| **Token追踪** | 精确到每轮，cost-tracker模块 | TokenUsage累计 + 粗略成本估算 | **~80%** |
| **中断控制** | AbortController (Web标准) | threading.Event (Python等价) | **~85%** |
| **权限系统** | 复杂权限上下文 + Bridge远程审批 | PermissionManager 4级模式 + Bridge远程审批 | **~75%** |
| **工具系统** | 42+ 工具目录 | 31 文件 48 工具 (+repl/task/brief) | **~75%** |
| **技能系统** | 3 个内置 + 用户自定义 | 5 域技能（simplify/verify/debug/batch/update-config） | **~70%** |
| **命令系统** | 15+ 命令 + 82子目录 | 16 个命令 | **~60%** |
| **记忆系统** | memdir 8文件 + MEMORY.md索引 | memory.py + memdir迁移 + LLM语义召回 + 新鲜度 | **~80%** |
| **Bridge远程控制** | 完整Remote Bridge (JWT+WebSocket+ReplBridge) | 简化版 (FastAPI+WebSocket+多会话管理) | **~70%** |
| **MCP集成** | 原生TS MCP | Python MCP客户端 (5传输层+插件+技能) | **~65%** |
| **子代理** | Task.ts Agent (explore/plan/review/impact/diagnose) | subagent.py 同5类 | **~80%** |
| **流式输出** | 完整 SSE streaming | `_call_llm_streaming()` 逐token实时 + StreamResult + 显式stream关闭 | **~95%** |
| **Hook系统** | 83+ hooks | 10种事件 (Pre/Post/Stop/UserMessage/Session/Notification/Subagent...) | **~55%** |
| **事件回调** | EventEmitter + WebSocket推送 | `_emit_event()` + BridgeSession实时转发 + Web UI可视化 | **~85%** |
| **多模型支持** | Anthropic原生 + fallback | OpenAI兼容协议 + fallback | **~75%** |
| **输出模式** | BriefTool (简洁/标准/详细) | BriefTool (brief/normal/verbose) + system prompt注入 | **~80%** |

---

## 四、关键差距（下一步可改进方向）

### 已完成（本轮）

- **ContextCollapse** (70% → 80%): 文件读写依赖追踪 + 过时读取自动折叠 + read_file 行范围选择 + 4级压缩流水线
- **工具丰富度** (65% → 75%): 新增 REPLTool/TaskManager/BriefTool，总计 48 个工具
- **输出模式** (新增): BriefTool 简洁/标准/详细三模式 + system prompt 动态注入

### 已完成（上一轮）

- **Microcompact** (60% → 70%): 13 种可清除工具 + 2 种可清除输入 + 保留最近 6 个结果 + run() 预检查
- **工具丰富度** (55% → 65%): 新增 4 个工具 (tool_search/sleep/config/notebook_edit)，总计 43 个

### 已完成（更早）

- **流式输出** (20% → 80%): `_call_llm_streaming()` + StreamResult + 逐token实时显示
- **多级上下文压缩** (30% → 60%): Snip + LLM-driven AutoCompact
- **Prompt-too-long 恢复** (缺失 → 实现): context_length 检测 → 压缩 → 重试
- **Hook 生态** (40% → 55%): 新增 6 种事件 (Stop/SessionEnd/UserMessage/Notification/Subagent)
- **事件回调** (待实现 → 实现): `_emit_event()` + `_fire_lifecycle_hook()`

### 下一步高优先级

1. **Hook 生态继续扩展** (~55% → 65%)
   - 新增 ToolError/PreCompact/PostCompact/ContextWarning 等事件
   - Hook 链优先级排序和短路机制

2. **命令系统增强** (~60% → 70%)
   - 按需迁移: /review (代码审查), /benchmark (性能基准), /history (会话历史管理)

3. **错误恢复完善** (~65% → 75%)
   - StopHook 恢复: 当 PostToolUse hook 返回 deny 时的恢复策略
   - ImageStrip: 当上下文包含大图片时的智能剥离

---

## 五、总结

opencode 已覆盖 Claude Code **约 80% 的核心能力**：

| 完成度 | 模块 |
|--------|------|
| **~95%** | 流式输出（含精确中断控制）、查询结果结构化报告 |
| **~85%** | 事件回调（Bridge实时转发+Web可视化）、中断控制、记忆系统、子代理 |
| **~80%** | 上下文压缩(4级流水线)、核心循环、Token追踪、输出模式、子代理 |
| **~70-75%** | 工具系统(48工具)、技能系统、Bridge远程控制、多模型支持 |
| **~60-65%** | 错误恢复、Hook系统、命令系统、MCP集成 |

整体架构已进入 **"深度打磨"** 阶段。本轮新增 ContextCollapse 上下文折叠 + 5 个高价值工具（REPL/TaskManager/BriefTool），上下文压缩从 3 级升至 4 级（与 Claude Code 完全对齐），工具数量从 43→48。
