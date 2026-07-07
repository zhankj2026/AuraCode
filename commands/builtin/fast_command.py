#!/usr/bin/env python3
"""
快速模式命令 - 切换快速模式

功能：
- 启用/禁用快速模式
- 减少响应延迟
- 可能降低响应质量
"""

from typing import Any, Dict

from ..base import CommandContext, CommandResult, LocalCommand


class FastCommand(LocalCommand):
    """快速模式命令"""
    
    name = "fast"
    description = "切换快速模式"
    aliases = []
    
    async def execute(self, args: str, context: CommandContext) -> CommandResult:
        """执行快速模式命令"""
        
        # 获取当前状态
        agent_loop = getattr(context, 'agent_loop', None)
        current_fast_mode = False
        
        if agent_loop:
            current_fast_mode = getattr(agent_loop, 'fast_mode', False)
        
        # 切换状态
        new_fast_mode = not current_fast_mode
        
        # TODO: 实际应用到 agent_loop
        
        status = "enabled" if new_fast_mode else "disabled"
        
        return CommandResult(
            success=True,
            output=f"Fast mode {status}",
            data={
                "fast_mode": new_fast_mode,
                "status": status
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
    command_registry.register(FastCommand())
