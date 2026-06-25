# 命令参考

在对话模式中输入 `/命令名` 即可执行。AuraCode 内置 46 条命令，覆盖开发全流程。

---

## 核心交互

| 命令 | 说明 |
|------|------|
| `/help` (`?`) | 查看所有可用命令及简要说明 |
| `/status` | 当前会话状态（模型、Token、迭代次数、费用）|
| `/clear` | 清空对话历史，重新开始 |
| `/compact` | LLM 驱动压缩对话历史，保留关键摘要 |
| `/context` | Token 分布可视化与上下文使用情况 |
| `/cost` | 会话费用追踪（按模型独立计价）|
| `/model <name>` | 运行时切换模型，支持历史回滚 |
| `/new` | 创建新会话 |
| `/reset` | 重置当前会话 |

---

## Git 工作流

| 命令 | 说明 |
|------|------|
| `/commit` | AI 分析当前变更，智能生成 Git 提交信息并执行 |
| `/diff` | 查看 Git 暂存区与工作区差异 |
| `/review` | 代码审查 — 变更影响分析 + 依赖图展示 |
| `/security-review` | 安全漏洞扫描 — 16 类检查规则 + 严重性分级 |
| `/worktree` | Git Worktree 隔离工作区管理 |

### 示例

```
> /commit

分析变更:
  - 修改 src/auth.py (添加 JWT 验证)
  - 新增 src/middleware.py

建议提交信息:
  feat(auth): 添加 JWT Token 验证中间件

是否提交? [Y/n]
```

```
> /security-review

扫描结果:
  🔴 高危 (1): src/auth.py:45 - 硬编码密钥
  🟡 中危 (2): src/api.py:12 - 未验证的 URL 重定向
  🟢 低危 (3): src/db.py:8 - SQL 拼接（已参数化）
```

---

## 会话管理

| 命令 | 说明 |
|------|------|
| `/resume` | 恢复历史会话（含离开摘要）|
| `/history` | 会话历史列表与全文搜索 |
| `/rewind` | 会话回退 — Checkpoint 撤销上 N 轮对话 |
| `/export` | 导出对话为 Markdown / JSON 文件 |
| `/plan` | 进入任务规划模式 — 分步计划制定与追踪 |

### 示例

```
> /resume --all

会话历史 (共 15 条):
  #1  2024-01-15  重构 auth 模块      12轮  $0.08
  #2  2024-01-14  修复分页 bug         5轮  $0.03
  ...

输入编号恢复。
```

---

## 代码质量

| 命令 | 说明 |
|------|------|
| `/analyze` | 项目级代码分析（结构、复杂度、依赖）|
| `/lint` | 代码规范检查 |
| `/test` | 运行项目测试 |
| `/benchmark` | 性能基准测试与历史对比 |
| `/verify` | 验证代码变更是否正确（Skill）|
| `/simplify` | 三路并行代码审查与简化建议（Skill）|
| `/debug` | 调试会话问题诊断（Skill）|
| `/doctor` | 环境诊断与健康检查 |

### 示例

```
> /benchmark

运行基准测试...
  ✅ test_query   1.23s (上次: 1.45s, ↓15%)
  ⚠️ test_parse   3.89s (上次: 2.10s, ↑85%)
  ✅ test_save    0.54s (上次: 0.52s, +4%)
```

---

## 系统管理

| 命令 | 说明 |
|------|------|
| `/config-edit` | 运行时热编辑配置文件（立即生效）|
| `/permissions` | 权限规则管理（查看/添加/移除/模式切换）|
| `/hooks` | Hook 管理 — 配置查看、执行日志、热重载 |
| `/plugins` | 插件系统管理（列表/启用/禁用）|
| `/mcp` | MCP 服务器管理（连接/断开/工具列表）|
| `/memory` | 记忆管理（查看/搜索/编辑/删除/导出）|
| `/tools` | 工具使用统计与调用追踪 |
| `/init` | 初始化项目文档 `AURACODE.md` |

### 示例

```
> /permissions

当前模式: normal

Allow 规则:
  ✅ read_file:*
  ✅ run_command:git *

Deny 规则:
  ❌ run_command:rm -rf
  ❌ run_command:sudo *

用法: /permissions add allow "write_file:src/*"
```

---

## 代理与技能

| 命令 | 说明 |
|------|------|
| `/skills` | 列出所有可用技能 |
| `/activate <name>` | 激活领域技能 |
| `/deactivate <name>` | 停用领域技能 |
| `/active` | 查看已激活的技能 |
| `/subagents` | 子代理管理（列表/统计/终止）|
| `/bridge` | Bridge 远程控制管理 |
| `/cron` | 定时任务管理 |
| `/batch` | 大规模并行变更编排（Skill）|

### 示例

```
> /activate git-workflow

✅ 技能 'git-workflow' 已激活
  描述: Git 工作流规范
  触发: 涉及 Git 操作时
```

---

## 其他

| 命令 | 说明 |
|------|------|
| `/tips` | 功能发现提示（展示你还未使用的功能）|
| `/update-config` | 配置管理（Hooks/权限/环境变量）|
