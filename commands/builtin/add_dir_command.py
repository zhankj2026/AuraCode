#!/usr/bin/env python3
"""
添加目录命令 - 添加工作目录

功能：
- 添加额外的工作目录
- 支持相对路径和绝对路径
- 可选保存到配置
"""

import os
from pathlib import Path
from typing import Any, Dict

from ..base import CommandContext, CommandResult, LocalCommand


class AddDirCommand(LocalCommand):
    """添加目录命令"""
    
    name = "add-dir"
    description = "添加工作目录"
    aliases = ["add-directory"]
    
    async def execute(self, args: str, context: CommandContext) -> CommandResult:
        """执行添加目录命令"""
        
        # 解析路径
        directory_path = args.strip() if args else ""
        
        if not directory_path:
            return CommandResult(
                success=False,
                output="Usage: /add-dir <path>\n\nProvide a directory path to add as a working directory."
            )
        
        # 转换为绝对路径
        path = Path(directory_path).resolve()
        
        # 验证路径
        if not path.exists():
            return CommandResult(
                success=False,
                output=f"Error: Directory does not exist: {path}"
            )
        
        if not path.is_dir():
            return CommandResult(
                success=False,
                output=f"Error: Path is not a directory: {path}"
            )
        
        # 更新权限上下文
        agent_loop = getattr(context, 'agent_loop', None)
        added_to_context = False
        
        if agent_loop:
            # 1. 添加到工作目录列表
            if hasattr(agent_loop, 'work_dirs'):
                if not isinstance(agent_loop.work_dirs, list):
                    agent_loop.work_dirs = []
                if str(path) not in [str(d) for d in agent_loop.work_dirs]:
                    agent_loop.work_dirs.append(str(path))
                    added_to_context = True
            
            # 2. TODO: 更新权限管理器（如果存在）
            # if hasattr(agent_loop, 'permission_manager'):
            #     agent_loop.permission_manager.add_directory(str(path))
            
            # 3. TODO: 更新沙箱配置（如果存在）
            # if hasattr(agent_loop, 'sandbox_manager'):
            #     agent_loop.sandbox_manager.add_allowed_directory(str(path))
        
        # 返回成功消息
        status_msg = f"Added {path} as a working directory"
        if added_to_context:
            status_msg += " for this session"
        
        return CommandResult(
            success=True,
            output=f"✓ {status_msg}\n\nUse /permissions to manage directory access.",
            data={
                "path": str(path),
                "added": True,
                "added_to_context": added_to_context
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
    command_registry.register(AddDirCommand())
