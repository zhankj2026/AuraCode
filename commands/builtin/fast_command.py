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
        
        # 应用到 agent_loop
        if agent_loop:
            # 设置 Fast 模式
            setattr(agent_loop, 'fast_mode', new_fast_mode)
            
            # Fast 模式会调整 LLM 参数
            if new_fast_mode:
                # Fast: 降低 temperature，减少 max_tokens
                setattr(agent_loop, 'temperature', 0.2)
                setattr(agent_loop, 'max_tokens', 1500)
            else:
                # Normal: 恢复默认
                setattr(agent_loop, 'temperature', 0.5)
                setattr(agent_loop, 'max_tokens', 2000)
        
        status = "enabled" if new_fast_mode else "disabled"
        
        return CommandResult(
            success=True,
            output=f"✓ Fast mode {status}\n\nFast mode reduces response time but may lower quality.",
            data={
                "fast_mode": new_fast_mode,
                "status": status,
                "applied": agent_loop is not None
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
