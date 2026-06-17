# 工具系统

OpenCode 内置 53 个工具，由 AI 代理在对话过程中自动调用。你无需手动调用工具，AI 会根据你的需求自动选择并执行。

---

## 工具分类

### 文件操作

| 工具 | 说明 |
|------|------|
| `read_file` | 读取文件内容，支持指定行范围 |
| `write_file` | 写入/创建文件 |
| `replace_in_file` | 精确文本替换（先搜索后替换）|
| `undo_edit` | 撤销上一步编辑操作 |
| `notebook_edit` | Jupyter Notebook 单元格编辑 |
| `analyze_file` | 文件结构与内容分析 |

### 代码搜索

| 工具 | 说明 |
|------|------|
| `find` | 文件内容正则搜索 |
| `glob` | Glob 模式文件匹配（`**/*.py` 等）|
| `grep` | 高性能内容搜索（基于 ripgrep）|
| `list_directory` | 目录结构浏览 |
| `lsp` | LSP 协议 — 跳转定义、查找引用、获取诊断 |
| `tool_search` | 工具发现与搜索（不确定工具名时使用）|

### 终端执行

| 工具 | 说明 |
|------|------|
| `run_command` | Shell 命令执行（支持超时、后台、工作目录）|
| `run_powershell` | Windows PowerShell 执行 |
| `run_tests` | 项目测试运行 |
| `repl` | 交互式 Python REPL |
| `lint` | 代码规范检查 |

### 智能代理

| 工具 | 说明 |
|------|------|
| `spawn_subagent` | 创建子代理（独立上下文，可并行）|
| `join_subagent` | 等待子代理完成并获取结果 |
| `list_subagents` | 列出活跃子代理 |
| `subagent_stats` | 子代理执行统计 |
| `list_agent_types` | 可用代理类型列表 |
| `plan_agent` | 计划模式代理（只读分析）|

### 任务管理

| 工具 | 说明 |
|------|------|
| `task_create` | 创建任务 |
| `task_list` | 列出任务 |
| `task_update` | 更新任务状态 |
| `todo_write` | 任务进度可视化 |

### 计划模式

| 工具 | 说明 |
|------|------|
| `enter_plan_mode` | 进入计划模式（只读，不执行修改）|
| `exit_plan_mode` | 退出计划模式，恢复执行 |

### Git Worktree

| 工具 | 说明 |
|------|------|
| `enter_worktree` | 进入 Git Worktree 隔离工作区 |
| `exit_worktree` | 退出 Worktree 并合并变更 |

### 定时任务

| 工具 | 说明 |
|------|------|
| `cron_create` | 创建定时任务（Cron 表达式）|
| `cron_delete` | 删除定时任务 |
| `cron_list` | 列出所有定时任务 |

### 记忆系统

| 工具 | 说明 |
|------|------|
| `save_memory` | 保存记忆条目 |
| `load_memory` | 加载记忆 |
| `search_memories` | 语义搜索记忆 |
| `list_memories` | 列出记忆索引 |
| `get_memory_summary` | 获取记忆摘要 |
| `get_relevant_memories` | LLM 驱动的相关记忆召回 |
| `delete_memory` | 删除记忆 |

### 技能系统

| 工具 | 说明 |
|------|------|
| `activate_skill` | 激活领域技能 |
| `deactivate_skill` | 停用领域技能 |
| `get_active_skills` | 获取已激活技能 |
| `list_skills` | 列出所有可用技能 |
| `show_available_skills` | 展示技能详情 |

### 网络与外部

| 工具 | 说明 |
|------|------|
| `web_fetch` | 获取网页内容并分析（支持提取正文）|
| `web_search` | 网络搜索 |

### 交互与配置

| 工具 | 说明 |
|------|------|
| `ask_user` | 向用户提问（支持多选和自定义输入）|
| `brief` | 简洁模式切换（减少输出）|
| `config` | 运行时配置读写 |
| `edit_history` | 编辑对话历史 |
| `sleep` | 等待/延迟 |

---

## 工具增强

OpenCode 对所有工具调用提供统一增强（由 `ToolEnhancer` 驱动）：

| 功能 | 说明 |
|------|------|
| **结果摘要** | 大型工具输出自动生成摘要 |
| **自动重试** | 幂等工具（读文件、搜索等）失败后自动重试 |
| **输出裁剪** | 超大 diff 只保留修改区域 ±N 行 |

---

## 使用追踪

通过 `/tools` 命令查看工具使用统计：

```
> /tools

工具使用统计 (本次会话):
  read_file      12 次  成功 100%  平均 0.3s
  run_command     5 次  成功  80%  平均 1.2s
  write_file      3 次  成功 100%  平均 0.1s
  ...
```

---

## 相关文档

- [命令参考](commands.md)
- [技能系统](skills.md)
- [MCP 协议集成](mcp.md) — 通过 MCP 扩展更多工具
