# Subagent 使用指南

## 概述

Subagent 系统提供独立工作区来并行执行任务，实现上下文隔离、结果压缩和并行执行。

## 核心价值

1. **隔离**: 探索过程留在独立窗口，主会话只拿回结论
2. **压缩**: 返回结构化摘要，不返回完整执行日志
3. **并行**: 可同时运行多个独立调查任务

## 可用的 Agent 类型

| 类型 | 图标 | 用途 | 使用场景 |
|------|------|------|----------|
| `explore` | 🔍 | 代码探索 | 需要广泛搜索代码库（>3次查询） |
| `plan` | 📋 | 制定计划 | 实施新功能前的架构分析 |
| `review` | 👀 | 代码审查 | 检查代码质量、安全和可维护性 |
| `impact` | 🎯 | 影响分析 | 分析 API/Schema 变更的影响范围 |
| `diagnose` | 🔧 | 测试诊断 | 分析测试失败原因 |
| `general` | 🤖 | 通用任务 | 其他独立任务 |

## 工具使用

### spawn_subagent

创建并运行一个 subagent：

```python
# 基本用法
spawn_subagent(
    task="搜索所有使用 AuthService 的文件",
    agent_type="explore"
)

# 使用 fork 模式（继承父会话上下文）
spawn_subagent(
    task="基于当前讨论分析影响范围",
    agent_type="impact",
    fork_mode=True
)

# 同步运行（等待完成）
result = spawn_subagent(
    task="审查最近的代码修改",
    agent_type="review",
    run_in_background=False
)
```

### join_subagent

获取 subagent 结果：

```python
# 等待并获取结果
result = join_subagent(agent_id="abc123")

# 设置超时
result = join_subagent(agent_id="abc123", timeout=30)
```

### list_subagents

列出所有 subagent：

```python
# 列出所有
list_subagents()

# 按状态过滤
list_subagents(status="running")
list_subagents(status="completed")
```

### subagent_stats

获取统计信息：

```python
subagent_stats()
```

### list_agent_types

查看可用的 agent 类型：

```python
list_agent_types()
```

## 使用场景

### 场景 1: 代码探索

当你需要广泛探索代码库时：

```python
# 不推荐：在主会话中进行大量搜索
grep("AuthService", ".")
grep("AuthService", "./src")
grep("login", "./src")
# ... 更多搜索

# 推荐：使用 explore agent
spawn_subagent(
    task="找到所有与用户认证相关的文件和函数，包括 AuthService、login、authenticate 等",
    agent_type="explore"
)
```

### 场景 2: 实施前规划

```python
# 在实施新功能前
spawn_subagent(
    task="分析如何添加用户权限系统，需要修改哪些文件，有哪些依赖和风险",
    agent_type="plan"
)
```

### 场景 3: 代码审查

```python
# 代码修改后
spawn_subagent(
    task="审查最近的 git diff 修改，检查安全性、性能和可维护性问题",
    agent_type="review"
)
```

### 场景 4: 影响分析

```python
# 修改 API 前
spawn_subagent(
    task="分析修改 User.create() 接口的影响，包括所有调用方和测试",
    agent_type="impact"
)
```

### 场景 5: 并行调查

```python
# 同时运行多个独立调查
spawn_subagent(
    task="检查前端组件的认证实现",
    agent_type="explore"
)

spawn_subagent(
    task="检查后端 API 的认证实现",
    agent_type="explore"
)

spawn_subagent(
    task="检查数据库模型的认证相关字段",
    agent_type="explore"
)
```

## Fork 模式

Fork 模式让 subagent 继承父会话的完整上下文：

```python
# Fresh 模式（默认）：只有任务描述
spawn_subagent(
    task="搜索配置文件",
    agent_type="explore",
    fork_mode=False  # 默认
)

# Fork 模式：继承父会话的所有上下文
spawn_subagent(
    task="基于当前项目理解，分析架构变更",
    agent_type="plan",
    fork_mode=True
)
```

**何时使用 Fork 模式**：
- ✅ 需要大量背景信息的复杂任务
- ✅ 并行验证同一父会话的多个分支方案
- ❌ 简单搜索或独立任务（用 fresh 模式）

## Agent 定义文件

Agent 类型通过 `.claude/agents/*.md` 文件定义：

```markdown
---
name: explore
description: 搜索和理解代码库，不做修改
tools: Read, Grep, Glob
model: sonnet
---

You are a code exploration specialist.

When invoked:
1. Use Grep/Glob to find relevant files
2. Read only the most relevant files
3. Return structured findings
```

可以添加自定义 agent：

1. 创建 `.claude/agents/my_agent.md`
2. 定义 frontmatter 和提示词
3. 使用 `agent_type="my_agent"` 调用

## 输出格式

Subagent 返回压缩后的结构化结果：

```
# Subagent 执行摘要

**任务**: 搜索认证相关文件
**原始输出**: 50000 字符
**压缩后**: 1500 字符
**压缩率**: 97.0%

---

### Key Findings
- AuthService 位于 `src/auth/service.py`
- 使用 MongoDB 存储会话
- ...

### Relevant Files
| File Path | Purpose |
|-----------|---------|
| `src/auth/service.py` | 认证服务实现 |
| `src/middleware/auth.py` | 认证中间件 |
```

## 命令行使用

```bash
# 查看 subagent 状态
/subagents
/subagents list
/subagents stats
/subagents types
```

## 最佳实践

1. **明确任务描述**：越具体的任务描述，越好的结果
2. **选择正确的类型**：根据任务选择合适的 agent_type
3. **合理使用并行**：只有真正独立的任务才并行执行
4. **检查结果**：使用 `join_subagent` 或查看输出文件获取结果
5. **清理资源**：定期清理已完成的 subagent 记录

## 注意事项

- Subagent 在独立线程中运行，有最大并发数限制（默认 5）
- 输出文件保存在 `.subagent_output/{agent_id}.md`
- Fork 模式会复制父会话上下文，可能增加 token 使用
- 如果没有设置 OPENAI_API_KEY，subagent 会使用 mock 执行
