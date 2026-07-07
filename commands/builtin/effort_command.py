#!/usr/bin/env python3
"""
努力程度命令 - 设置响应努力程度

功能：
- 设置 low/medium/high
- 影响响应深度和详细程度
"""

from typing import Any, Dict

from ..base import CommandContext, CommandResult, LocalCommand


class EffortCommand(LocalCommand):
    """努力程度命令"""
    
    name = "effort"
    description = "设置响应努力程度"
    aliases = []
    
    VALID_LEVELS = ["low", "medium", "high"]
    
    async def execute(self, args: str, context: CommandContext) -> CommandResult:
        """执行努力程度命令"""
        
        level = args.strip().lower() if args else ""
        
        if not level:
            # 显示当前设置
            agent_loop = getattr(context, 'agent_loop', None)
            current_effort = "medium"
            
            if agent_loop:
                current_effort = getattr(agent_loop, 'effort_level', 'medium')
            
            return CommandResult(
                success=True,
                output=f"Current effort level: {current_effort}\n\nUsage: /effort <low|medium|high>",
                data={
                    "current": current_effort
                }
            )
        
        if level not in self.VALID_LEVELS:
            return CommandResult(
                success=False,
                output=f"Invalid effort level: {level}\n\nValid levels: {', '.join(self.VALID_LEVELS)}"
            )
        
        # 应用到 agent_loop
        agent_loop = getattr(context, 'agent_loop', None)
        if agent_loop:
            # 设置 effort_level 属性
            setattr(agent_loop, 'effort_level', level)
            
            # 根据 effort 调整 LLM 参数
            if level == "low":
                # 快速响应，减少思考
                setattr(agent_loop, 'temperature', 0.3)
                setattr(agent_loop, 'max_tokens', 1000)
            elif level == "medium":
                # 平衡模式
                setattr(agent_loop, 'temperature', 0.5)
                setattr(agent_loop, 'max_tokens', 2000)
            elif level == "high":
                # 深度思考
                setattr(agent_loop, 'temperature', 0.7)
                setattr(agent_loop, 'max_tokens', 4000)
        
        return CommandResult(
            success=True,
            output=f"✓ Effort level set to: {level}\n\nThis will affect response depth and detail level.",
            data={
                "effort": level,
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
    command_registry.register(EffortCommand())
