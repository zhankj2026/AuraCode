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
Workflow Tools - Dynamic Workflows 工具集（Phase 3）

提供 4 个核心工具：
1. dynamic_workflow: 动态生成并执行工作流
2. workflow_status: 查看工作流进度
3. save_workflow: 保存工作流脚本
4. execute_saved_workflow: 执行已保存的工作流

参考标准Dynamic Workflows 的用户接口。
"""
import logging
from typing import Dict, Any, Optional
from tools.registry import register_tool

logger = logging.getLogger(__name__)


def dynamic_workflow_handler(
    task: str,
    auto_approve: bool = False,
    save_script: bool = False
) -> str:
    """
    动态生成并执行工作流（参考标准Dynamic Workflows）
    
    流程:
    1. LLM 分析任务，生成工作流脚本
    2. 验证脚本正确性
    3. 用户审批（auto_approve=False 时）
    4. 执行工作流
    5. 保存脚本（save_script=True 时）
    
    Args:
        task: 任务描述（如 "audit all API endpoints for auth checks"）
        auto_approve: 自动审批脚本（跳过用户确认）
        save_script: 是否保存脚本供后续复用
    
    Returns:
        执行结果
    
    示例:
        dynamic_workflow(
            task="审计 src/routes/ 下所有 API endpoint 的认证检查",
            auto_approve=False,
            save_script=True
        )
    """
    from core.coordinator import coordinator
    from core.workflow_generator import generate_workflow_script
    import json
    
    # Phase 1: 使用 WorkflowScriptGenerator 生成脚本
    try:
        workflow_script = generate_workflow_script(task)
        workflow_template = workflow_script.to_dict()
    except Exception as e:
        logger.error(f"Failed to generate workflow: {e}")
        return f"❌ 工作流生成失败: {e}"
    
    # Phase 2: 验证脚本
    errors = workflow_script.validate()
    if errors:
        return (
            f"❌ 生成的工作流脚本存在错误\n\n"
            f"**任务**: {task}\n\n"
            f"**错误列表**:\n" + 
            "\n".join([f"- {err}" for err in errors])
        )
    
    # 如果没有自动审批，显示脚本供用户确认
    if not auto_approve:
        script_preview = json.dumps(workflow_template, indent=2, ensure_ascii=False)
        return (
            f"📋 工作流脚本已生成\n\n"
            f"**任务**: {task}\n\n"
            f"**脚本预览**:\n```json\n{script_preview[:500]}...\n```\n\n"
            f"**下一步**:\n"
            f"1. 审批脚本：设置 `auto_approve=True` 执行\n"
            f"2. 保存脚本：设置 `save_script=True` 供后续复用\n"
            f"3. 直接执行：设置 `auto_approve=True, save_script=True`"
        )
    
    # Phase 3: 加载并执行工作流
    coordinator.activate()
    
    try:
        # 加载脚本
        load_result = coordinator.load_workflow_script(workflow_template)
        
        # 检查加载是否成功
        if "❌" in load_result:
            return load_result
        
        # 执行工作流（model=None → 继承当前会话模型）
        execute_result = coordinator.execute_workflow(model=None)
        
        # 如果需要保存脚本
        if save_script:
            workflow_name = workflow_template["name"]
            save_result = coordinator.save_workflow_script(
                workflow_name,
                task
            )
            execute_result += f"\n\n{save_result}"
        
        return execute_result
        
    except Exception as e:
        return f"❌ 工作流执行失败: {e}"


def workflow_status_handler(workflow_id: str = "") -> str:
    """
    查看工作流进度
    
    Args:
        workflow_id: 工作流 ID（可选，为空显示所有）
    
    Returns:
        进度信息
    
    示例:
        workflow_status()  # 查看所有
        workflow_status(workflow_id="api-audit")  # 查看指定
    """
    from core.coordinator import coordinator
    from pathlib import Path
    import json
    
    # 查看当前 Coordinator 的工作流
    progress = coordinator.get_workflow_progress()
    
    if not progress or progress.get("status") is None:
        return "📭 当前没有活跃的工作流"
    
    # 构建进度报告
    lines = [
        f"📊 工作流进度\n\n",
        f"**名称**: {progress.get('workflow_name', 'Unknown')}",
        f"**状态**: {progress.get('status', 'unknown')}",
        f"**阶段**: {progress.get('stages_completed', 0)}/{progress.get('stages_total', 0)}",
    ]
    
    if progress.get("started_at"):
        lines.append(f"**开始时间**: {progress['started_at']}")
    
    if progress.get("completed_at"):
        lines.append(f"**完成时间**: {progress['completed_at']}")
    
    if progress.get("error"):
        lines.append(f"\n❌ **错误**: {progress['error']}")
    
    if progress.get("final_result"):
        lines.append(f"\n**最终结果**:\n{progress['final_result'][:500]}")
    
    # 查看已保存的工作流脚本
    workflows_dir = Path(".auracode/workflows")
    if workflows_dir.exists():
        saved_workflows = list(workflows_dir.glob("*.json"))
        if saved_workflows:
            lines.append(f"\n📁 已保存的工作流脚本 ({len(saved_workflows)} 个):")
            for wf_file in saved_workflows:
                if not workflow_id or workflow_id in wf_file.stem:
                    with open(wf_file, 'r', encoding='utf-8') as f:
                        wf_data = json.load(f)
                    lines.append(f"  - `{wf_file.stem}`: {wf_data.get('description', '')[:50]}")
    
    return "\n".join(lines)


def save_workflow_handler(
    name: str,
    description: str = ""
) -> str:
    """
    保存当前工作流脚本
    
    Args:
        name: 工作流名称
        description: 工作流描述
    
    Returns:
        保存结果
    
    示例:
        save_workflow(
            name="api-auth-audit",
            description="审计 API endpoint 的认证检查"
        )
    """
    from core.coordinator import coordinator
    
    if not coordinator._workflow_script:
        return (
            "❌ 当前没有加载的工作流脚本\n\n"
            "请先执行 `dynamic_workflow()` 或 `load_workflow_script()` 加载工作流。"
        )
    
    # 保存脚本
    return coordinator.save_workflow_script(name, description)


def execute_saved_workflow_handler(
    name: str,
    model: str = None
) -> str:
    """
    执行已保存的工作流脚本
    
    Args:
        name: 工作流名称（或文件路径）
        model: LLM 模型
    
    Returns:
        执行结果
    
    示例:
        execute_saved_workflow(name="api-auth-audit")
    """
    from core.coordinator import coordinator
    from pathlib import Path
    import json
    
    # 查找脚本文件
    workflows_dir = Path(".auracode/workflows")
    
    # 尝试作为文件名或名称
    script_file = workflows_dir / f"{name}.json"
    if not script_file.exists():
        # 搜索匹配的文件
        matching_files = list(workflows_dir.glob(f"*{name}*.json"))
        if matching_files:
            script_file = matching_files[0]
        else:
            return f"❌ 未找到工作流脚本: {name}\n\n使用 `workflow_status()` 查看已保存的脚本。"
    
    # 加载脚本
    with open(script_file, 'r', encoding='utf-8') as f:
        workflow_data = json.load(f)
    
    # 加载到 Coordinator
    coordinator.activate()
    load_result = coordinator.load_workflow_script(workflow_data)
    
    # 检查加载是否成功
    if "❌" in load_result:
        return load_result
    
    # 执行工作流
    try:
        execute_result = coordinator.execute_workflow(model=model)
        return execute_result
    except Exception as e:
        return f"❌ 工作流执行失败: {e}"


# ── 注册工具 ──

register_tool("dynamic_workflow", {
    "description": (
        "Generate and execute a dynamic workflow for complex tasks. "
        "Automatically creates a multi-stage workflow script with parallel agents, "
        "cross-validation, and convergence checking. Use for large-scale audits, "
        "migrations, research, and security reviews."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": (
                    "Task description. Examples: "
                    "'audit all API endpoints for auth checks', "
                    "'migrate from React to Vue', "
                    "'find all security vulnerabilities'"
                ),
            },
            "auto_approve": {
                "type": "boolean",
                "description": "Auto-approve the generated script without review",
                "default": False,
            },
            "save_script": {
                "type": "boolean",
                "description": "Save the script for future reuse",
                "default": False,
            },
        },
        "required": ["task"],
    },
    "handler": dynamic_workflow_handler,
    "permission_level": "read",
})

register_tool("workflow_status", {
    "description": (
        "Check the progress of running or completed workflows. "
        "Shows stage status, agent status, and intermediate results. "
        "Also lists saved workflow scripts."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "workflow_id": {
                "type": "string",
                "description": "Workflow ID or name (optional, shows all if empty)",
                "default": "",
            },
        },
    },
    "handler": workflow_status_handler,
    "permission_level": "read",
})

register_tool("save_workflow", {
    "description": (
        "Save the current workflow script for future reuse. "
        "Converts the script into a reusable command that can be "
        "executed with execute_saved_workflow()."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Workflow name (used as filename)",
            },
            "description": {
                "type": "string",
                "description": "Workflow description",
                "default": "",
            },
        },
        "required": ["name"],
    },
    "handler": save_workflow_handler,
    "permission_level": "read",
})

register_tool("execute_saved_workflow", {
    "description": (
        "Execute a previously saved workflow script by name. "
        "Use for repeating previously defined workflows without "
        "regenerating the script."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Workflow name or script filename",
            },
            "model": {
                "type": "string",
                "description": "LLM model to use (留空继承当前会话模型)",
            },
        },
        "required": ["name"],
    },
    "handler": execute_saved_workflow_handler,
    "permission_level": "read",
})
