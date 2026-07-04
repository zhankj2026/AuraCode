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
Plan 命令 - 任务规划模式

功能:
- 启用/切换规划模式（plan mode）
- 在规划模式下，AI 先制定详细计划再执行
- 可指定任务描述生成计划
- 查看当前计划的步骤和进度

用法:
  /plan                  切换规划模式开关
  /plan <任务描述>        针对特定任务生成计划
  /plan show             查看当前计划
  /plan next             标记当前步骤完成，进入下一步
"""

import json
from commands.registry import register_command

PLAN_SYSTEM_PROMPT = """你是一个任务规划专家。请为以下任务制定详细的执行计划。

规划规则:
1. 先分析任务需求和现有代码结构
2. 将任务分解为具体可执行的步骤
3. 每个步骤要明确：做什么、改哪些文件、如何验证
4. 考虑边界情况和潜在风险
5. 步骤数量控制在 3-10 个

输出格式（Markdown，仅输出计划内容）:
## 任务计划：<标题>

### 背景分析
- 现状：...
- 目标：...

### 执行步骤

1. **[步骤名]**
   - 操作：具体做什么
   - 文件：涉及哪些文件
   - 验证：如何确认完成

2. **[步骤名]**
   ...

### 风险点
- ...
"""


# 当前活跃计划（模块级状态）
_current_plan = {
    "active": False,
    "mode_on": False,
    "task": "",
    "steps": [],
    "current_step": 0,
    "plan_text": ""
}


def _parse_plan_steps(plan_text: str) -> list:
    """从计划文本中提取步骤列表"""
    steps = []
    in_steps = False
    current_step = ""
    for line in plan_text.splitlines():
        line = line.strip()
        if "执行步骤" in line or "Steps" in line.lower():
            in_steps = True
            continue
        if in_steps:
            # 检测步骤开始（数字. 或 - ** 开头）
            if line and (line[0].isdigit() or line.startswith("- **") or line.startswith("* **")):
                if current_step:
                    steps.append(current_step.strip())
                current_step = line
            elif current_step and line:
                current_step += "\n  " + line
            elif line.startswith("### ") and not "步骤" in line:
                # 新 section 开始，步骤部分结束
                if current_step:
                    steps.append(current_step.strip())
                break
    if current_step:
        steps.append(current_step.strip())
    return steps


def plan_handler(args: list, loop=None) -> str:
    """plan 命令处理函数"""
    lines = []

    # 无参数：切换模式
    if not args:
        _current_plan["mode_on"] = not _current_plan["mode_on"]
        state = "✅ 已启用" if _current_plan["mode_on"] else "⭕ 已关闭"
        lines.append(f"📋 规划模式: {state}")
        if _current_plan["mode_on"]:
            lines.append("   后续任务将先制定计划再执行")
            lines.append("   使用 /plan <任务描述> 生成具体计划")
        return "\n".join(lines)

    subcmd = args[0].lower()

    # /plan show - 查看当前计划
    if subcmd == "show":
        if not _current_plan["plan_text"]:
            return "📋 当前没有活跃计划\n使用 /plan <任务描述> 创建计划"
        lines.append("📋 当前计划")
        lines.append("=" * 60)
        lines.append(f"任务: {_current_plan['task']}")
        lines.append(f"进度: 步骤 {_current_plan['current_step']}/{len(_current_plan['steps'])}")
        lines.append("")
        lines.append(_current_plan["plan_text"])
        return "\n".join(lines)

    # /plan next - 推进到下一步
    if subcmd == "next":
        if not _current_plan["steps"]:
            return "📋 当前没有活跃计划"
        _current_plan["current_step"] = min(
            _current_plan["current_step"] + 1,
            len(_current_plan["steps"])
        )
        step_num = _current_plan["current_step"]
        total = len(_current_plan["steps"])
        lines.append(f"✅ 已推进到步骤 {step_num}/{total}")
        if step_num <= total:
            lines.append(f"当前步骤:\n{_current_plan['steps'][step_num-1]}")
        if step_num >= total:
            lines.append("\n🎉 所有步骤已完成！")
        return "\n".join(lines)

    # /plan <任务描述> - 生成新计划
    if loop is None:
        return "❌ AgentLoop 未初始化，无法生成计划"

    task_description = " ".join(args)
    lines.append("📋 任务规划")
    lines.append("=" * 60)
    lines.append(f"任务: {task_description}")
    lines.append("🤖 正在分析并生成计划...")

    try:
        # 收集项目上下文
        context_info = ""
        if loop.messages:
            # 取最近的对话作为上下文
            recent = [m for m in loop.messages[-6:] if m.get("content")]
            context_info = "\n".join(
                f"[{m.get('role','')}]: {str(m.get('content',''))[:300]}"
                for m in recent
            )

        user_prompt = (
            f"请为以下任务制定执行计划：\n\n"
            f"任务：{task_description}\n\n"
        )
        if context_info:
            user_prompt += f"最近的对话上下文：\n{context_info}\n\n"
        user_prompt += "请生成详细的分步执行计划。"

        response = loop.client.chat.completions.create(
            model=loop.model,
            messages=[
                {"role": "system", "content": PLAN_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2,
            max_tokens=1500
        )
        plan_text = response.choices[0].message.content.strip()

        # 解析步骤
        steps = _parse_plan_steps(plan_text)

        # 保存计划状态
        _current_plan.update({
            "active": True,
            "mode_on": True,
            "task": task_description,
            "steps": steps,
            "current_step": 1,
            "plan_text": plan_text
        })

        lines.append("\n" + plan_text)
        if steps:
            lines.append(f"\n📌 共 {len(steps)} 个步骤，当前: 步骤 1")
            lines.append(f"   使用 /plan next 推进到下一步")
            lines.append(f"   使用 /plan show 查看完整计划")

    except Exception as e:
        lines.append(f"❌ 生成计划失败: {e}")

    lines.append("=" * 60)
    return "\n".join(lines)


register_command("plan", {
    "description": "任务规划模式 - 先制定计划再执行，支持分步推进",
    "handler": plan_handler,
    "category": "system",
    "args_help": "[任务描述|show|next]"
})
