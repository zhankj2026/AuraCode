#!/usr/bin/env python3
"""
代理命令 - 显示代理信息

功能：
- 显示当前代理状态
- 列出子代理
- 显示代理统计
"""

from typing import Any, Dict

from ..base import CommandContext, CommandResult, LocalCommand


class AgentsCommand(LocalCommand):
    """代理命令"""
    
    name = "agents"
    description = "显示代理信息"
    aliases = ["agent"]
    
    async def execute(self, args: str, context: CommandContext) -> CommandResult:
        """执行代理命令"""
        
        # 从上下文获取代理信息
        agent_loop = getattr(context, 'agent_loop', None)
        
        if not agent_loop:
            return CommandResult(
                success=True,
                output="No active agent loop",
                data={"agents": []}
            )
        
        info_lines = []
        
        # 主代理信息
        info_lines.append("Main Agent:")
        info_lines.append(f"  Model: {getattr(agent_loop, 'model', 'unknown')}")
        info_lines.append(f"  Turn Count: {getattr(agent_loop.state, 'turn_count', 0) if hasattr(agent_loop, 'state') else 0}")
        
        # 子代理
        subagents = getattr(agent_loop, 'subagents', [])
        if subagents:
            info_lines.append("")
            info_lines.append(f"Subagents ({len(subagents)}):")
            
            for i, agent in enumerate(subagents, 1):
                agent_type = agent.get("type", "unknown")
                status = agent.get("status", "unknown")
                info_lines.append(f"  {i}. {agent_type} - {status}")
        else:
            info_lines.append("")
            info_lines.append("No active subagents")
        
        output = "\n".join(info_lines)
        
        return CommandResult(
            success=True,
            output=output,
            data={
                "main_agent": {
                    "model": getattr(agent_loop, 'model', 'unknown'),
                    "turn_count": getattr(agent_loop.state, 'turn_count', 0) if hasattr(agent_loop, 'state') else 0
                },
                "subagents": subagents,
                "subagent_count": len(subagents)
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
    command_registry.register(AgentsCommand())
