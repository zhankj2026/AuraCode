"""
subagent 工具 - 创建和管理并行子 Agent (增强版)

改进:
- 支持 agent_type (explore/plan/review/impact/diagnose)
- 支持 fork_mode (继承父会话上下文)
- 改进的结果压缩
- 更清晰的工具描述
"""

from core.subagent import subagent_manager
from tools.registry import register_tool


def spawn_subagent_handler(
    task: str,
    model: str = "glm-4-plus",
    agent_type: str = "general",
    run_in_background: bool = True,
    fork_mode: bool = False
) -> str:
    """
    创建子 Agent 并行执行任务

    Args:
        task: 任务描述
        model: 使用的模型名称
        agent_type: Agent 类型
                  - explore: 代码探索，适合广泛搜索 (>3次查询)
                  - plan: 制定计划，适合实施前的架构分析
                  - review: 代码审查，检查质量和安全
                  - impact: 影响分析，检查变更波及范围
                  - diagnose: 测试诊断，分析失败原因
                  - general: 通用任务
        run_in_background: 是否后台运行
        fork_mode: 是否继承父会话上下文（适合需要背景的任务）

    Returns:
        Subagent 状态信息
    """
    try:
        # 验证 agent_type
        available_types = subagent_manager.get_available_agent_types()
        if agent_type != "general" and agent_type not in available_types:
            return f"⚠️ 警告: 未知的 agent_type '{agent_type}'\n\n" \
                   f"可用类型: {', '.join(available_types)}\n" \
                   f"将使用 'general' 类型代替"

        handle = subagent_manager.spawn_subagent(
            task=task,
            model=model,
            agent_type=agent_type,
            run_in_background=run_in_background,
            fork_mode=fork_mode
        )

        output_file = f".subagent_output/{handle.agent_id}.md"

        if run_in_background:
            mode_desc = "Fork 模式" if fork_mode else "Fresh 模式"
            return (
                f"✅ Subagent 已启动\n\n"
                f"**Agent ID**: {handle.agent_id}\n"
                f"**类型**: {handle.agent_type}\n"
                f"**任务**: {task[:100]}{'...' if len(task) > 100 else ''}\n"
                f"**模型**: {model}\n"
                f"**模式**: {mode_desc}\n"
                f"**状态**: 运行中\n\n"
                f"**输出文件**: {output_file}\n\n"
                f"使用以下工具获取结果:\n"
                f"- `join_subagent(agent_id='{handle.agent_id}')` - 等待并获取结果\n"
                f"- `list_subagents()` - 查看所有运行中的 agent"
            )
        else:
            # 同步运行，等待完成
            result = subagent_manager.join_subagent(handle.agent_id)
            return f"✅ Subagent 执行完成\n\n{result}"

    except RuntimeError as e:
        return f"❌ 无法创建 Subagent\n\n{str(e)}"
    except Exception as e:
        return f"❌ Subagent 创建失败\n\n错误: {str(e)}"


def join_subagent_handler(agent_id: str, timeout: int = None) -> str:
    """
    等待 Subagent 完成并获取结果

    Args:
        agent_id: Agent ID
        timeout: 超时时间(秒)，默认无限等待

    Returns:
        Subagent 执行结果
    """
    try:
        result = subagent_manager.join_subagent(agent_id, timeout=timeout)
        return result

    except KeyError:
        return f"❌ 错误: 未找到 Subagent {agent_id}\n\n使用 `list_subagents()` 查看可用的 Agent"
    except TimeoutError:
        return f"⏱️ Subagent {agent_id} 执行超时({timeout}秒)\n\nAgent 仍在后台运行，可以稍后再次查询"
    except Exception as e:
        return f"❌ 获取 Subagent 结果失败\n\n错误: {str(e)}"


def list_subagents_handler(status: str = None) -> str:
    """
    列出所有 Subagent

    Args:
        status: 可选，过滤状态 (running/completed/failed/cancelled)

    Returns:
        Subagent 列表
    """
    try:
        agents = subagent_manager.list_agents(status=status)

        if not agents:
            return f"{'没有' if not status else f\"没有状态为 '{status}' 的\"} Subagent"

        # 格式化输出
        lines = [f"📋 Subagent 列表 (共 {len(agents)} 个):", ""]

        for agent in agents:
            status_icon = {
                'running': '🔄',
                'completed': '✅',
                'failed': '❌',
                'cancelled': '⛔'
            }.get(agent['status'], '❓')

            # Agent 类型图标
            type_icon = {
                'explore': '🔍',
                'plan': '📋',
                'review': '👀',
                'impact': '🎯',
                'diagnose': '🔧',
                'general': '🤖'
            }.get(agent['agent_type'], '📦')

            fork_badge = " [Fork]" if agent.get('fork_mode') else ""

            lines.append(f"{status_icon} **{agent['agent_id']}** {type_icon} {fork_badge}")
            lines.append(f"   类型: {agent['agent_type']}")
            lines.append(f"   任务: {agent['task']}")
            lines.append(f"   模型: {agent['model']}")
            lines.append(f"   状态: {agent['status']}")

            if agent.get('created_at'):
                lines.append(f"   创建: {agent['created_at']}")

            if agent.get('result_preview'):
                preview = agent['result_preview']
                if len(preview) > 100:
                    preview = preview[:100] + "..."
                lines.append(f"   预览: {preview}")

            lines.append("")

        return "\n".join(lines)

    except Exception as e:
        return f"❌ 获取 Subagent 列表失败\n\n错误: {str(e)}"


def subagent_stats_handler() -> str:
    """
    获取 Subagent 统计信息

    Returns:
        统计信息
    """
    try:
        stats = subagent_manager.get_stats()
        available_types = subagent_manager.get_available_agent_types()

        lines = [
            "📊 Subagent 统计",
            "",
            f"总计: {stats['total']}",
            f"🔄 运行中: {stats['running']}",
            f"✅ 已完成: {stats['completed']}",
            f"❌ 失败: {stats['failed']}",
            f"⛔ 已取消: {stats['cancelled']}",
            "",
            f"📦 可用的 Agent 类型 ({len(available_types)}):",
        ]

        for agent_type in available_types:
            if agent_type == "general":
                lines.append(f"  - {agent_type}: 通用任务")
            else:
                agent_def = subagent_manager.get_agent_definition(agent_type)
                desc = agent_def.get('description', '无描述')[:60] if agent_def else '未找到定义'
                lines.append(f"  - {agent_type}: {desc}")

        return "\n".join(lines)

    except Exception as e:
        return f"❌ 获取统计信息失败\n\n错误: {str(e)}"


def list_agent_types_handler() -> str:
    """
    列出所有可用的 Agent 类型及其描述

    Returns:
        Agent 类型列表
    """
    try:
        available_types = subagent_manager.get_available_agent_types()

        lines = ["🤖 可用的 Agent 类型", ""]

        for agent_type in available_types:
            if agent_type == "general":
                lines.append(f"### general")
                lines.append("通用 Agent，适用于各种任务")
                lines.append("")
            else:
                agent_def = subagent_manager.get_agent_definition(agent_type)
                if agent_def:
                    lines.append(f"### {agent_type}")
                    lines.append(f"{agent_def.get('description', '无描述')}")
                    lines.append(f"**工具**: {', '.join(agent_def.get('tools', []))}")
                    lines.append(f"**模型**: {agent_def.get('model', 'sonnet')}")
                    lines.append("")

        return "\n".join(lines)

    except Exception as e:
        return f"❌ 获取 Agent 类型失败\n\n错误: {str(e)}"


# 注册工具
register_tool("spawn_subagent", {
    "description": """创建独立工作区子代理，并行执行任务。

**何时使用**:
- 需要大量搜索/读取但结果只需简单摘要
- 并行执行多个独立调查任务
- 隔离会产生噪音的探索过程

**Agent 类型**:
- explore: 代码探索（>3次查询时使用）
- plan: 制定实施计划
- review: 代码审查
- impact: 影响分析
- diagnose: 测试诊断
- general: 通用任务

**不推荐用于**:
- 需要频繁来回讨论的任务
- 与主任务共享大量中间状态的场景

返回结构化结论，非完整执行日志。
""",
    "parameters": {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "任务描述，越具体越好"
            },
            "model": {
                "type": "string",
                "description": "使用的模型名称",
                "default": "glm-4-plus"
            },
            "agent_type": {
                "type": "string",
                "description": "Agent 类型 (explore/plan/review/impact/diagnose/general)",
                "enum": ["explore", "plan", "review", "impact", "diagnose", "general"],
                "default": "general"
            },
            "run_in_background": {
                "type": "boolean",
                "description": "是否后台运行",
                "default": True
            },
            "fork_mode": {
                "type": "boolean",
                "description": "是否继承父会话上下文",
                "default": False
            }
        },
        "required": ["task"]
    },
    "handler": spawn_subagent_handler,
    "permission_level": "execute"
})

register_tool("join_subagent", {
    "description": "等待 Subagent 完成并获取结果",
    "parameters": {
        "type": "object",
        "properties": {
            "agent_id": {
                "type": "string",
                "description": "Agent ID"
            },
            "timeout": {
                "type": "integer",
                "description": "超时时间(秒)，默认无限等待",
                "default": None
            }
        },
        "required": ["agent_id"]
    },
    "handler": join_subagent_handler,
    "permission_level": "read"
})

register_tool("list_subagents", {
    "description": "列出所有 Subagent",
    "parameters": {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "description": "过滤状态 (running/completed/failed/cancelled)",
                "enum": ["running", "completed", "failed", "cancelled"]
            }
        },
        "required": []
    },
    "handler": list_subagents_handler,
    "permission_level": "read"
})

register_tool("subagent_stats", {
    "description": "获取 Subagent 统计信息",
    "parameters": {
        "type": "object",
        "properties": {},
        "required": []
    },
    "handler": subagent_stats_handler,
    "permission_level": "read"
})

register_tool("list_agent_types", {
    "description": "列出所有可用的 Agent 类型及其描述",
    "parameters": {
        "type": "object",
        "properties": {},
        "required": []
    },
    "handler": list_agent_types_handler,
    "permission_level": "read"
})
