"""
subagent 工具 - 创建和管理并行子 Agent

基于 code.md Phase 6 实现
参考: 第 6.4 节
"""

from core.subagent import subagent_manager
from tools.registry import register_tool


def spawn_subagent_handler(
    task: str,
    model: str = "glm-4-plus",
    run_in_background: bool = True
) -> str:
    """
    创建子 Agent 并行执行任务
    
    Args:
        task: 任务描述
        model: 使用的模型名称
        run_in_background: 是否后台运行,默认 True
    
    Returns:
        Subagent 状态信息
    """
    try:
        handle = subagent_manager.spawn_subagent(
            task=task,
            model=model,
            run_in_background=run_in_background
        )
        
        if run_in_background:
            output_file = f".subagent_output/{handle.agent_id}.md"
            return (
                f"✅ Subagent 已启动\n\n"
                f"**Agent ID**: {handle.agent_id}\n"
                f"**任务**: {task}\n"
                f"**模型**: {model}\n"
                f"**状态**: 运行中\n"
                f"**输出文件**: {output_file}\n\n"
                f"使用 `join_subagent` 工具获取结果:\n"
                f"```python\n"
                f"join_subagent(agent_id='{handle.agent_id}')\n"
                f"```"
            )
        else:
            # 同步运行,等待完成
            result = subagent_manager.join_subagent(handle.agent_id)
            return f"✅ Subagent 执行完成\n\n{result}"
    
    except RuntimeError as e:
        return f"❌ 无法创建 Subagent\n\n{str(e)}"
    
    except Exception as e:
        return f"❌ Subagent 创建失败\n\n错误: {str(e)}"


def join_subagent_handler(agent_id: str, timeout: int = None) -> str:
    """
    获取 Subagent 结果
    
    Args:
        agent_id: Agent ID
        timeout: 超时时间(秒),默认无限等待
    
    Returns:
        Subagent 执行结果
    """
    try:
        result = subagent_manager.join_subagent(agent_id, timeout=timeout)
        return result
    
    except KeyError:
        return f"❌ 错误: 未找到 Subagent {agent_id}\n\n使用 `list_subagents` 查看可用的 Agent"
    
    except TimeoutError:
        return f"⏱️ Subagent {agent_id} 执行超时({timeout}秒)\n\nAgent 仍在后台运行,可以稍后再次查询"
    
    except Exception as e:
        return f"❌ 获取 Subagent 结果失败\n\n错误: {str(e)}"


def list_subagents_handler(status: str = None) -> str:
    """
    列出所有 Subagent
    
    Args:
        status: 可选,过滤状态(running/completed/failed)
    
    Returns:
        Subagent 列表
    """
    try:
        agents = subagent_manager.list_agents()
        
        if not agents:
            return "没有 Subagent"
        
        # 过滤状态
        if status:
            agents = [a for a in agents if a['status'] == status]
            if not agents:
                return f"没有状态为 '{status}' 的 Subagent"
        
        # 格式化输出
        lines = [f"Subagent 列表 (共 {len(agents)} 个):", ""]
        
        for agent in agents:
            status_icon = {
                'running': '🔄',
                'completed': '✅',
                'failed': '❌',
                'cancelled': '⛔'
            }.get(agent['status'], '❓')
            
            lines.append(f"{status_icon} **{agent['agent_id']}**")
            lines.append(f"   任务: {agent['task']}")
            lines.append(f"   模型: {agent['model']}")
            lines.append(f"   状态: {agent['status']}")
            lines.append(f"   创建: {agent['created_at']}")
            
            if agent.get('result_preview'):
                preview = agent['result_preview']
                lines.append(f"   预览: {preview}...")
            
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
        
        lines = [
            "Subagent 统计:",
            "",
            f"📊 总计: {stats['total']}",
            f"🔄 运行中: {stats['running']}",
            f"✅ 已完成: {stats['completed']}",
            f"❌ 失败: {stats['failed']}",
            f"⛔ 已取消: {stats['cancelled']}",
        ]
        
        return "\n".join(lines)
    
    except Exception as e:
        return f"❌ 获取统计信息失败\n\n错误: {str(e)}"


# 注册工具
register_tool("spawn_subagent", {
    "description": "创建子 Agent 并行执行任务",
    "parameters": {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "任务描述"
            },
            "model": {
                "type": "string",
                "description": "使用的模型名称",
                "default": "glm-4-plus"
            },
            "run_in_background": {
                "type": "boolean",
                "description": "是否后台运行",
                "default": True
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
                "description": "超时时间(秒)",
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
                "description": "过滤状态(running/completed/failed)",
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
