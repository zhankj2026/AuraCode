#!/usr/bin/env python3
"""
顺便提及命令 - 在对话中添加额外说明

功能：
- 添加临时上下文
- 不影响主对话流程
"""

from typing import Any, Dict

from ..base import CommandContext, CommandResult, LocalCommand


class BtwCommand(LocalCommand):
    """顺便提及命令"""
    
    name = "btw"
    description = "顺便提及（添加额外说明）"
    aliases = []
    
    async def execute(self, args: str, context: CommandContext) -> CommandResult:
        """执行顺便提及命令"""
        
        if not args or not args.strip():
            return CommandResult(
                success=False,
                output="Usage: /btw <message>\n\nAdd a side note or additional context to the conversation."
            )
        
        message = args.strip()
        
        # 存储侧边消息到会话历史
        # 这些消息会作为系统消息添加到对话中
        agent_loop = getattr(context, 'agent_loop', None)
        if agent_loop:
            # 添加到消息历史（作为系统消息）
            if hasattr(agent_loop, 'state') and hasattr(agent_loop.state, 'messages'):
                agent_loop.state.messages.append({
                    "role": "system",
                    "content": f"[Side note] {message}",
                    "type": "side_note"
                })
        
        return CommandResult(
            success=True,
            output=f"✓ Noted: {message}\n\nThis side note has been added to the conversation context.",
            data={
                "message": message,
                "noted": True,
                "added_to_context": agent_loop is not None
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
    command_registry.register(BtwCommand())
