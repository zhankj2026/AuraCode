# AuraCode — AI 编程智能体

AuraCode 是一款基于 Python 实现的全功能 AI 编程助手。它通过增强上下文工程与智能体无缝结合，全面理解你的代码库，并以系统化方式推进开发任务。AuraCode 提供**对话模式**、**命令模式**与 **Bridge 远程控制**三种工作方式，涵盖代码生成、智能搜索、多文件修改、自动测试、安全审查等完整开发场景。

---

## 核心能力

| 维度 | 说明 |
|------|------|
| **53 个内置工具** | 文件读写、代码搜索、LSP 智能、终端执行、Web 搜索、子代理协同等 |
| **46 条交互命令** | 涵盖 Git 工作流、会话管理、调试诊断、安全审查、性能基准等 |
| **7 项领域技能** | 按需激活的领域知识包，渐进式披露，节省 Token |
| **MCP 协议集成** | 完整客户端 — 服务器自动发现、动态工具注册、调用链追踪 |
| **Bridge 远程控制** | REST + WebSocket — 多会话管理、实时事件推送、远程审批 |
| **记忆系统** | LLM 驱动召回 — 新鲜度衰减、语义搜索、跨会话持久化 |
| **6 层错误恢复** | 纵深防御 — Fallback 模型 → Prompt 压缩 → 截断恢复 → Hook 兜底 |

---

## 快速导航

### 入门

- [快速开始](quick-start.md) — 5 分钟内完成安装并体验核心功能
- [对话交互](user-guide/chat.md) — 了解对话模式与基本交互

### 用户指南

- [命令参考](user-guide/commands.md) — 46 条命令完整说明
- [工具系统](user-guide/tools.md) — 53 个内置工具分类介绍
- [技能系统](user-guide/skills.md) — 领域技能激活与自定义
- [记忆系统](user-guide/memory.md) — 跨会话持久化记忆
- [权限管理](user-guide/permissions.md) — 四级权限模式与规则配置
- [MCP 协议集成](user-guide/mcp.md) — 连接外部工具与服务

### 高级功能

- [Bridge 远程控制](advanced/bridge.md) — WebSocket 实时操控与多会话管理
- [钩子系统](advanced/hooks.md) — 配置驱动的事件钩子
- [插件系统](advanced/plugins.md) — 插件生命周期管理
- [错误恢复机制](advanced/error-recovery.md) — 6 层纵深防御体系

### 开发

- [架构总览](development/architecture.md) — 项目结构与模块关系

---

## 支持的 LLM

AuraCode 通过 OpenAI 兼容接口对接各类大语言模型：

| 提供商 | 模型示例 | 说明 |
|--------|----------|------|
| 智谱 AI | `glm-4-plus`, `glm-4.7`, `glm-4.5-air` | 推荐，中文能力强 |
| OpenAI | `gpt-4o`, `gpt-4-turbo` | 需科学上网 |
| 其他 | 任意 OpenAI 兼容 API | 通过 `base_url` 配置 |

---

## 系统要求

- Python 3.10+
- pip
- 支持 Windows / macOS / Linux

---

## 许可证

[Apache License 2.0](https://github.com/auracode/auracode/blob/main/LICENSE)
