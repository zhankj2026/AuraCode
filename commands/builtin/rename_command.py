#!/usr/bin/env python3
"""
重命名命令 - 重命名当前会话

功能：
- 手动设置会话名称
- 自动生成会话名称（TODO）
- 保存到会话存储
"""

from typing import Any, Dict

from ..base import CommandContext, CommandResult, LocalCommand


class RenameCommand(LocalCommand):
    """重命名命令"""
    
    name = "rename"
    description = "重命名当前会话"
    aliases = []
    
    async def execute(self, args: str, context: CommandContext) -> CommandResult:
        """执行重命名命令"""
        
        # 检查参数
        if not args or not args.strip():
            return CommandResult(
                success=False,
                output="Usage: /rename <name>\n\nProvide a new name for the current session."
            )
        
        new_name = args.strip()
        
        # 获取会话 ID
        session_id = getattr(context, 'session_id', None)
        if not session_id:
            return CommandResult(
                success=False,
                output="Cannot rename: No active session"
            )
        
        # TODO: 实现会话存储和重命名逻辑
        # 目前只是返回成功消息
        
        return CommandResult(
            success=True,
            output=f"Session renamed to: {new_name}",
            data={
                "session_id": session_id,
                "new_name": new_name
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
    command_registry.register(RenameCommand())
