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
Goal 命令 - 目标驱动的 Loop

功能:
- 定义可验证的成功条件
- 自动执行 → 验证 → 调整循环
- 直到条件满足或超时

用法:
  /goal <目标描述>           启动目标驱动 Loop
  /goal status              查看当前 Loop 状态
  /goal stop                停止当前 Loop
  /goal list                列出历史 Loop

示例:
  /goal 所有测试通过且 lint 干净
  /goal 代码覆盖率 > 80%
  /goal 没有 TypeScript 类型错误
"""

import time
import threading
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from enum import Enum

from commands.registry import register_command
from core.validator import get_validator, ValidationResult

logger = logging.getLogger(__name__)


class GoalState(Enum):
    """Loop 状态"""
    PENDING = "pending"      # 等待启动
    RUNNING = "running"      # 运行中
    PAUSED = "paused"        # 暂停
    COMPLETED = "completed"  # 已完成（目标达成）
    FAILED = "failed"        # 失败（超时或无法达成）
    STOPPED = "stopped"      # 手动停止


@dataclass
class GoalAttempt:
    """单次尝试记录"""
    attempt_num: int
    timestamp: datetime
    action: str
    validation_result: Optional[ValidationResult] = None
    success: bool = False
    error: Optional[str] = None
    duration_ms: int = 0


@dataclass
class GoalLoop:
    """目标驱动 Loop"""
    goal_id: str
    goal_description: str
    success_criteria: str
    state: GoalState = GoalState.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    max_attempts: int = 10
    timeout_seconds: int = 600  # 10 分钟
    current_attempt: int = 0
    attempts: List[GoalAttempt] = field(default_factory=list)
    
    last_error: Optional[str] = None
    summary: Optional[str] = None
    
    def progress(self) -> float:
        """计算进度 (0.0 ~ 1.0)"""
        if self.state == GoalState.COMPLETED:
            return 1.0
        if self.state == GoalState.FAILED:
            return 0.0
        if self.max_attempts > 0:
            return self.current_attempt / self.max_attempts
        return 0.0
    
    def is_timeout(self) -> bool:
        """检查是否超时"""
        if self.started_at is None:
            return False
        elapsed = (datetime.now() - self.started_at).total_seconds()
        return elapsed > self.timeout_seconds
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "goal_id": self.goal_id,
            "goal_description": self.goal_description,
            "success_criteria": self.success_criteria,
            "state": self.state.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "max_attempts": self.max_attempts,
            "current_attempt": self.current_attempt,
            "progress": self.progress(),
            "last_error": self.last_error,
        }


# 全局 Loop 状态
_active_loops: Dict[str, GoalLoop] = {}
_loop_history: List[GoalLoop] = []
_loop_lock = threading.Lock()


def _generate_goal_id() -> str:
    """生成 Loop ID"""
    import uuid
    return f"goal_{uuid.uuid4().hex[:8]}"


def _parse_goal(description: str) -> tuple:
    """
    解析目标描述，提取成功条件
    
    Returns:
        (goal_description, success_criteria)
    """
    # 简单的规则提取
    criteria = description
    
    # 如果是测试相关
    if "测试" in description or "test" in description.lower():
        criteria = "所有测试通过"
    
    # 如果是 lint 相关
    if "lint" in description.lower():
        criteria = "Lint 检查无错误"
    
    # 如果是类型相关
    if "类型" in description or "type" in description.lower():
        criteria = "类型检查通过"
    
    return description, criteria


def _validate_goal(goal: GoalLoop, loop=None) -> ValidationResult:
    """
    验证目标是否达成
    
    Args:
        goal: 目标 Loop
        loop: AgentLoop 实例
    
    Returns:
        ValidationResult
    """
    validator = get_validator()
    
    # 根据目标描述决定验证策略
    desc_lower = goal.goal_description.lower()
    
    if "测试" in desc_lower or "test" in desc_lower:
        # 运行测试验证
        return validator.validate(run_tests=True)
    
    elif "lint" in desc_lower:
        # 只运行 lint
        return validator.validate(run_tests=False)
    
    elif "类型" in desc_lower or "type" in desc_lower:
        # 类型检查
        return validator.validate(run_tests=False)
    
    else:
        # 完整验证
        return validator.validate(run_tests=True)


def _run_goal_loop(goal: GoalLoop, agent_loop=None, callback: Optional[Callable] = None):
    """
    执行目标驱动 Loop
    
    Args:
        goal: 目标 Loop
        agent_loop: AgentLoop 实例
        callback: 状态变更回调
    """
    goal.state = GoalState.RUNNING
    goal.started_at = datetime.now()
    
    if callback:
        callback(goal)
    
    logger.info(f"[Goal] Starting loop {goal.goal_id}: {goal.goal_description}")
    
    while goal.current_attempt < goal.max_attempts:
        # 检查超时
        if goal.is_timeout():
            goal.state = GoalState.FAILED
            goal.last_error = "超时"
            logger.warning(f"[Goal] Loop {goal.goal_id} timeout")
            break
        
        # 执行一次尝试
        goal.current_attempt += 1
        attempt = GoalAttempt(
            attempt_num=goal.current_attempt,
            timestamp=datetime.now(),
            action=f"尝试 #{goal.current_attempt}"
        )
        
        start_time = time.time()
        
        try:
            # 1. 执行验证
            logger.info(f"[Goal] Attempt {goal.current_attempt}: validating...")
            validation_result = _validate_goal(goal, agent_loop)
            attempt.validation_result = validation_result
            
            # 2. 检查是否达成目标
            if validation_result.passed:
                attempt.success = True
                goal.state = GoalState.COMPLETED
                goal.completed_at = datetime.now()
                goal.summary = f"在第 {goal.current_attempt} 次尝试后达成目标"
                logger.info(f"[Goal] Loop {goal.goal_id} completed: {goal.summary}")
                break
            else:
                # 3. 未达成，记录错误并继续
                attempt.success = False
                attempt.error = "; ".join(validation_result.errors[:3])
                goal.last_error = attempt.error
                
                # 如果有 AgentLoop，让它尝试修复
                if agent_loop:
                    logger.info(f"[Goal] Attempt {goal.current_attempt} failed, asking AI to fix...")
                    fix_prompt = _generate_fix_prompt(goal, validation_result)
                    try:
                        agent_loop.run(fix_prompt)
                    except Exception as e:
                        logger.error(f"[Goal] Fix attempt failed: {e}")
            
        except Exception as e:
            attempt.error = str(e)
            logger.error(f"[Goal] Attempt {goal.current_attempt} error: {e}")
        
        attempt.duration_ms = int((time.time() - start_time) * 1000)
        goal.attempts.append(attempt)
        
        if callback:
            callback(goal)
        
        # 短暂暂停避免过于频繁
        time.sleep(1)
    
    # Loop 结束
    if goal.state == GoalState.RUNNING:
        if goal.current_attempt >= goal.max_attempts:
            goal.state = GoalState.FAILED
            goal.last_error = f"达到最大尝试次数 ({goal.max_attempts})"
        goal.completed_at = datetime.now()
    
    if callback:
        callback(goal)
    
    # 保存到历史
    with _loop_lock:
        _loop_history.append(goal)
        if goal.goal_id in _active_loops:
            del _active_loops[goal.goal_id]


def _generate_fix_prompt(goal: GoalLoop, validation_result: ValidationResult) -> str:
    """生成修复提示"""
    errors = validation_result.errors[:5]
    
    prompt = f"""目标: {goal.goal_description}

验证失败，请修复以下问题:
"""
    for i, error in enumerate(errors, 1):
        prompt += f"{i}. {error}\n"
    
    prompt += """
请分析错误原因并修复代码，确保满足目标条件。
"""
    return prompt


def goal_handler(args: list, loop=None) -> str:
    """goal 命令处理函数"""
    lines = []
    
    if not args:
        return _show_goal_help()
    
    subcmd = args[0].lower()
    
    # /goal status - 查看当前 Loop 状态
    if subcmd == "status":
        return _show_goal_status()
    
    # /goal stop - 停止当前 Loop
    if subcmd == "stop":
        return _stop_goal()
    
    # /goal list - 列出历史
    if subcmd == "list":
        return _list_goal_history()
    
    # /goal <目标描述> - 启动新 Loop
    goal_description = " ".join(args)
    return _start_goal(goal_description, loop)


def _show_goal_help() -> str:
    """显示帮助"""
    return """🎯 Goal 命令 - 目标驱动的 Loop

用法:
  /goal <目标描述>     启动目标驱动 Loop
  /goal status        查看当前 Loop 状态
  /goal stop          停止当前 Loop
  /goal list          列出历史 Loop

示例:
  /goal 所有测试通过且 lint 干净
  /goal 代码没有类型错误
  /goal 所有验证通过

Loop 会自动执行 → 验证 → 修复 → 再验证，直到目标达成或超时。
"""


def _start_goal(description: str, loop=None) -> str:
    """启动新的 Goal Loop"""
    goal_id = _generate_goal_id()
    goal_desc, criteria = _parse_goal(description)
    
    goal = GoalLoop(
        goal_id=goal_id,
        goal_description=goal_desc,
        success_criteria=criteria,
    )
    
    with _loop_lock:
        _active_loops[goal_id] = goal
    
    lines = [
        "🎯 启动目标驱动 Loop",
        "=" * 50,
        f"目标: {goal_desc}",
        f"成功条件: {criteria}",
        f"最大尝试: {goal.max_attempts} 次",
        f"超时时间: {goal.timeout_seconds} 秒",
        "",
        "🚀 Loop 启动中...",
        f"   使用 /goal status 查看进度",
        f"   使用 /goal stop 停止 Loop",
    ]
    
    # 在后台线程中运行 Loop
    def run_loop():
        _run_goal_loop(goal, loop)
    
    thread = threading.Thread(target=run_loop, daemon=True)
    thread.start()
    
    return "\n".join(lines)


def _show_goal_status() -> str:
    """显示当前 Loop 状态"""
    with _loop_lock:
        if not _active_loops:
            return "🎯 当前没有运行的 Loop\n使用 /goal <目标描述> 启动"
        
        lines = ["🎯 当前 Loop 状态", "=" * 50]
        
        for goal in _active_loops.values():
            state_icon = {
                GoalState.PENDING: "⏳",
                GoalState.RUNNING: "🔄",
                GoalState.PAUSED: "⏸️",
                GoalState.COMPLETED: "✅",
                GoalState.FAILED: "❌",
                GoalState.STOPPED: "🛑",
            }.get(goal.state, "?")
            
            lines.append(f"{state_icon} {goal.goal_id}")
            lines.append(f"   目标: {goal.goal_description}")
            lines.append(f"   状态: {goal.state.value}")
            lines.append(f"   进度: {goal.current_attempt}/{goal.max_attempts} ({goal.progress()*100:.0f}%)")
            
            if goal.last_error:
                lines.append(f"   最近错误: {goal.last_error[:50]}...")
            
            if goal.state == GoalState.COMPLETED:
                lines.append(f"   ✅ {goal.summary}")
            
            lines.append("")
        
        return "\n".join(lines)


def _stop_goal() -> str:
    """停止当前 Loop"""
    with _loop_lock:
        if not _active_loops:
            return "🎯 当前没有运行的 Loop"
        
        for goal in _active_loops.values():
            if goal.state == GoalState.RUNNING:
                goal.state = GoalState.STOPPED
                goal.completed_at = datetime.now()
                return f"🛑 Loop {goal.goal_id} 已停止"
        
        return "🎯 没有可停止的 Loop"


def _list_goal_history() -> str:
    """列出历史 Loop"""
    with _loop_lock:
        if not _loop_history:
            return "🎯 暂无历史 Loop 记录"
        
        lines = ["🎯 Loop 历史记录", "=" * 50]
        
        for goal in _loop_history[-10:]:  # 最近 10 个
            state_icon = {
                GoalState.COMPLETED: "✅",
                GoalState.FAILED: "❌",
                GoalState.STOPPED: "🛑",
            }.get(goal.state, "?")
            
            lines.append(f"{state_icon} {goal.goal_id}")
            lines.append(f"   目标: {goal.goal_description[:50]}...")
            lines.append(f"   尝试次数: {goal.current_attempt}")
            
            if goal.completed_at:
                duration = (goal.completed_at - goal.started_at).total_seconds()
                lines.append(f"   耗时: {duration:.1f}s")
            
            lines.append("")
        
        return "\n".join(lines)


register_command("goal", {
    "description": "目标驱动的 Loop - 自动执行直到目标达成",
    "handler": goal_handler,
    "category": "system",
    "args_help": "<目标描述>|status|stop|list"
})
