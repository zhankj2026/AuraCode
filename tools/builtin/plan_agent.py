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
规划 Agent 工具

只读模式，用于探索代码库并设计实现方案。
严格禁止任何文件修改操作。
"""

import os
from tools.registry import register_tool


def plan_agent_handler(task: str, perspective: str = "practical") -> str:
    """
    启动只读规划 Agent 来设计实现方案

    这是一个规划模式的子代理，具有以下特点：
    - 只读模式：不能创建、修改或删除文件
    - 探索代码库：使用 read_file、grep、find 等工具
    - 设计方案：基于探索结果设计实现策略
    - 输出计划：提供分步实现策略和关键文件列表

    Args:
        task: 需要规划的任务描述
        perspective: 设计视角 (practical/architectural/research)
            - practical: 实用主义，快速实现
            - architectural: 架构优先，考虑扩展性
            - research: 深入研究，全面分析

    Returns:
        规划结果，包含实现策略和关键文件列表
    """
    # 检查是否允许运行规划子代理
    # 在实际实现中，这里会启动一个独立的 Agent Loop
    # 为了简化，这里返回一个提示

    return f"""📋 规划 Agent 已启动

任务: {task}
视角: {perspective}

⚠️ 注意: 这是一个只读规划 Agent
- ✅ 允许: read_file, grep, find, list_directory
- ❌ 禁止: write_file, replace_in_file, run_command(危险操作)

规划 Agent 正在分析任务...
（完整实现需要启动独立的子 Agent Loop）"""


register_tool("plan_agent", {
    "description": """启动只读规划 Agent 来设计实现方案。

规划 Agent 专门用于探索代码库并设计实现策略：
- 只读模式：严格禁止任何文件修改
- 深入探索：分析现有代码模式和架构
- 设计方案：提供分步实现策略
- 识别依赖：找出关键文件和潜在挑战

适用于：需要仔细规划的非平凡实现任务""",
    "parameters": {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "需要规划的任务描述，详细说明要实现什么功能"
            },
            "perspective": {
                "type": "string",
                "enum": ["practical", "architectural", "research"],
                "description": "设计视角：practical(实用快速), architectural(架构优先), research(深入研究)",
                "default": "practical"
            }
        },
        "required": ["task"]
    },
    "handler": plan_agent_handler,
    "permission_level": "read"
})
