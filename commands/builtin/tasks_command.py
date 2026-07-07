#!/usr/bin/env python3
"""
任务命令 - 显示当前任务状态

功能：
- 列出活跃任务
- 显示任务进度
- 显示任务统计
"""

from typing import Any, Dict, List

from ..base import CommandContext, CommandResult, LocalCommand


class TasksCommand(LocalCommand):
    """任务命令"""
    
    name = "tasks"
    description = "显示当前任务状态"
    aliases = []
    
    async def execute(self, args: str, context: CommandContext) -> CommandResult:
        """执行任务命令"""
        
        # 从上下文获取任务列表
        agent_loop = getattr(context, 'agent_loop', None)
        
        if not agent_loop:
            return CommandResult(
                success=True,
                output="No active agent loop",
                data={"tasks": [], "count": 0}
            )
        
        # 获取任务管理器
        task_manager = getattr(agent_loop, 'task_manager', None)
        
        if not task_manager:
            return CommandResult(
                success=True,
                output="No task manager available",
                data={"tasks": [], "count": 0}
            )
        
        # 获取任务列表
        tasks = []
        
        # 活跃任务
        active_tasks = getattr(task_manager, 'active_tasks', [])
        for task in active_tasks:
            tasks.append({
                "id": task.get("id"),
                "description": task.get("description"),
                "status": "active",
                "progress": task.get("progress", 0)
            })
        
        # 已完成任务
        completed_tasks = getattr(task_manager, 'completed_tasks', [])
        for task in completed_tasks:
            tasks.append({
                "id": task.get("id"),
                "description": task.get("description"),
                "status": "completed"
            })
        
        if not tasks:
            return CommandResult(
                success=True,
                output="No tasks found",
                data={"tasks": [], "count": 0}
            )
        
        # 格式化输出
        output_lines = [f"Tasks ({len(tasks)}):"]
        output_lines.append("")
        
        for i, task in enumerate(tasks, 1):
            status_icon = "✓" if task["status"] == "completed" else "⚡"
            line = f"{i}. {status_icon} {task['description']}"
            if task.get("progress"):
                line += f" ({task['progress']}%)"
            output_lines.append(line)
        
        output = "\n".join(output_lines)
        
        return CommandResult(
            success=True,
            output=output,
            data={
                "tasks": tasks,
                "count": len(tasks)
            }
        )
    
    async def execute_non_interactive(
        self, args: str, context: CommandContext
    ) -> Dict[str, Any]:
        """非交互模式执行"""
        result = await self.execute(args, context)
        return {
            "type": "text",
            "value": result.output,
            "data": result.data
        }


# 注册命令
def register():
    """注册命令到全局注册表"""
    from ..registry import command_registry
    command_registry.register(TasksCommand())
