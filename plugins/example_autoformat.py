#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2026 zhankj
#
# This source code is licensed under the [ Apache-2.0] license.
# For the full license text, please refer to the LICENSE file in the root directory.
#
# Author: zhankj <creating2018@aliyun.com>
# Project Homepage: http://www.auracode.top
#

"""
示例插件 - 自动格式化

演示如何实现一个完整的插件
"""

import os
import subprocess
from typing import List, Dict, Any
from plugins.base import ToolPlugin


class AutoFormatPlugin(ToolPlugin):
    """
    自动格式化插件
    
    在写入 Python 文件后自动运行 black 格式化
    """
    
    @property
    def name(self) -> str:
        return "auto-format"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "自动格式化 Python 文件(使用 black)"
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """不提供额外工具"""
        return []
    
    def get_hooks(self) -> List[Dict[str, Any]]:
        """注册 PostToolUse 钩子"""
        return [
            {
                "event": "PostToolUse",
                "handler": self._format_after_write,
                "matcher": "write_file"
            }
        ]
    
    def is_available(self) -> bool:
        """检查 black 是否已安装"""
        try:
            result = subprocess.run(
                ['black', '--version'],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False
    
    def initialize(self) -> bool:
        """初始化插件"""
        print(f"[OK] Plugin {self.name} enabled: Auto-format Python files")
        return True
    
    async def _format_after_write(self, **kwargs) -> 'HookResult':
        """
        写入文件后自动格式化
        
        Args:
            **kwargs: 包含 tool_name, input, output 等
        """
        from hooks.manager import HookResult
        
        try:
            # 获取文件路径
            tool_input = kwargs.get('input', {})
            filepath = tool_input.get('path', '')
            
            # 只处理 Python 文件
            if not filepath.endswith('.py'):
                return HookResult()
            
            # 检查文件是否存在
            if not os.path.exists(filepath):
                return HookResult()
            
            # 运行 black
            result = subprocess.run(
                ['black', filepath, '-q'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return HookResult(
                    additional_context=f"✅ 已自动格式化 {filepath}"
                )
            else:
                return HookResult(
                    additional_context=f"⚠️ 格式化失败: {filepath}"
                )
        
        except Exception as e:
            return HookResult(
                additional_context=f"⚠️ 格式化异常: {str(e)}"
            )
