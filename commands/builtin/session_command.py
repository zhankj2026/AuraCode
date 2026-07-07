#!/usr/bin/env python3
"""
会话命令 - 显示当前会话信息

功能：
- 显示会话 ID
- 显示会话状态
- 显示远程会话 URL（如有）
"""

from typing import Any, Dict

from ..base import CommandContext, CommandResult, LocalCommand


class SessionCommand(LocalCommand):
    """会话命令"""
    
    name = "session"
    description = "显示当前会话信息"
    aliases = []
    
    async def execute(self, args: str, context: CommandContext) -> CommandResult:
        """执行会话命令"""
        
        # 获取会话信息
        session_id = getattr(context, 'session_id', None)
        agent_loop = getattr(context, 'agent_loop', None)
        
        info_lines = []
        
        # 会话 ID
        if session_id:
            info_lines.append(f"Session ID: {session_id}")
        else:
            info_lines.append("Session ID: (not set)")
        
        # 从 agent_loop 获取更多信息
        if agent_loop:
            # 会话状态
            state = getattr(agent_loop, 'state', None)
            if state:
                info_lines.append(f"Turn Count: {state.turn_count}")
                info_lines.append(f"Total Cost: ${state.total_cost_usd:.4f}")
                info_lines.append(f"Total Tokens: {state.total_usage.total_tokens}")
            
            # 远程会话 URL
            remote_url = getattr(agent_loop, 'remote_session_url', None)
            if remote_url:
                info_lines.append(f"Remote URL: {remote_url}")
        
        # 工作目录
        work_dir = getattr(context, 'work_dir', None)
        if work_dir:
            info_lines.append(f"Work Directory: {work_dir}")
        
        output = "\n".join(info_lines)
        
        return CommandResult(
            success=True,
            output=output,
            data={
                "session_id": session_id,
                "work_dir": work_dir
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
    command_registry.register(SessionCommand())
