#!/usr/bin/env python3
"""
退出命令 - 优雅退出 AgentLoop

功能：
- 随机告别消息
- 清理资源
- 保存会话状态
"""

import random
from typing import Any, Dict

from ..base import CommandContext, CommandResult, LocalCommand


class ExitCommand(LocalCommand):
    """退出命令"""
    
    name = "exit"
    description = "退出 AuraCode"
    aliases = ["quit", "q"]
    
    # 告别消息列表
    GOODBYE_MESSAGES = [
        "Goodbye!",
        "See ya!",
        "Bye!",
        "Catch you later!",
        "再见！",
        "下次见！",
    ]
    
    def get_random_goodbye(self) -> str:
        """随机获取告别消息"""
        return random.choice(self.GOODBYE_MESSAGES)
    
    async def execute(self, args: str, context: CommandContext) -> CommandResult:
        """执行退出命令"""
        
        # 获取告别消息
        goodbye = self.get_random_goodbye()
        
        # 返回退出信号
        return CommandResult(
            success=True,
            output=goodbye,
            data={
                "should_exit": True,
                "message": goodbye
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
            "should_exit": True
        }


# 注册命令
def register():
    """注册命令到全局注册表"""
    from ..registry import command_registry
    command_registry.register(ExitCommand())
