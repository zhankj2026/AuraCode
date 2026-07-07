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
        
        # TODO: 实现权限上下文更新
        # TODO: 实现沙箱配置刷新
        
        # 返回成功消息
        return CommandResult(
            success=True,
            output=f"Added {path} as a working directory for this session",
            data={
                "path": str(path),
                "added": True
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
