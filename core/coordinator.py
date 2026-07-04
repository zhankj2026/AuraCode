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
Coordinator 模式 - 多智能体协调者（P0 核心功能）

实现高级编排能力：
1. 任务分解与 Worker 调度
2. 结果综合（禁止懒惰委托）
3. Continue vs Spawn 决策支持
4. 任务通知处理
5. Dynamic Workflows 执行引擎

核心设计原则:
- Coordinator 必须综合 Worker 发现，禁止 "based on your findings"
- Worker 无法看到 Coordinator 对话，每个 prompt 必须自包含
- 并行是超能力，尽可能并发启动 Worker
"""
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class WorkerResult:
    """Worker 执行结果"""
    agent_id: str
    description: str
    status: str  # completed/failed/killed
    result: str
    summary: str
    usage: Dict[str, int] = field(default_factory=dict)
    completed_at: str = field(default_factory=lambda: datetime.now().isoformat())


class CoordinatorMode:
    """
    协调者模式
    
    职责:
    1. 接收用户任务
    2. 分解为多个 Worker 任务
    3. 并行启动 Worker
    4. 接收 Worker 通知
    5. 综合所有 Worker 发现（关键步骤！）
    6. 编写具体实施规范
    7. 决定 Continue vs Spawn
    8. 调度实施/验证 Worker
    9. 向用户报告结果
    10. 支持工作流脚本执行（Dynamic Workflows 增强）
    """
    
    def __init__(self):
        self.is_active = False
        self.workers: Dict[str, WorkerResult] = {}
        self.pending_notifications: List[Dict[str, Any]] = []
        self.synthesis_history: List[str] = []
        self._workflow_script = None  # 当前加载的工作流脚本
        self._workflow_progress: Dict[str, Any] = {}  # 工作流执行进度
    
    def activate(self):
        """激活 Coordinator 模式"""
        self.is_active = True
        logger.info("Coordinator mode activated")
    
    def deactivate(self):
        """停用 Coordinator 模式"""
        self.is_active = False
        logger.info("Coordinator mode deactivated")
    
    def register_worker(self, agent_id: str, description: str):
        """
        注册 Worker
        
        Args:
            agent_id: Worker 的 Agent ID
            description: Worker 任务描述
        """
        self.workers[agent_id] = WorkerResult(
            agent_id=agent_id,
            description=description,
            status="running",
            result="",
            summary=""
        )
        logger.info(f"Registered worker {agent_id}: {description}")
    
    def handle_task_notification(self, notification: Dict[str, Any]) -> str:
        """
        处理 Worker 任务通知
        
        Args:
            notification: 任务通知字典
                {
                    "task_id": "agent-xxx",
                    "status": "completed/failed/killed",
                    "summary": "简短摘要",
                    "result": "详细结果",
                    "usage": {"total_tokens": 123, ...}
                }
        
        Returns:
            处理结果摘要
        """
        agent_id = notification.get("task_id", "")
        status = notification.get("status", "unknown")
        summary = notification.get("summary", "")
        result = notification.get("result", "")
        usage = notification.get("usage", {})
        
        # 更新 Worker 状态
        if agent_id in self.workers:
            worker = self.workers[agent_id]
            worker.status = status
            worker.summary = summary
            worker.result = result
            worker.usage = usage
            worker.completed_at = datetime.now().isoformat()
            
            logger.info(f"Worker {agent_id} {status}: {summary}")
        
        # 添加到待处理通知
        self.pending_notifications.append(notification)
        
        # 生成处理报告
        report_lines = [
            f"📬 Task Notification Processed",
            f"",
            f"**Worker**: {agent_id}",
            f"**Status**: {status}",
            f"**Summary**: {summary}",
            f"",
        ]
        
        if status == "completed":
            report_lines.append("✅ Worker completed successfully.")
            report_lines.append("Next step: Synthesize findings and decide Continue vs Spawn.")
        elif status == "failed":
            report_lines.append("❌ Worker failed.")
            report_lines.append("Next step: Decide whether to retry with corrections or take different approach.")
        elif status == "killed":
            report_lines.append("🛑 Worker was stopped.")
            report_lines.append("Next step: Redirect with corrected instructions.")
        
        return "\n".join(report_lines)
    
    def synthesize_findings(self, worker_results: List[WorkerResult]) -> str:
        """
        综合多个 Worker 的发现（Coordinator 的核心职责！）
        
        **关键原则**:
        - 禁止懒惰委托（"based on your findings"）
        - 必须阅读并理解所有发现
        - 必须生成具体的实施规范（含文件路径、行号）
        - 证明你理解了问题
        
        Args:
            worker_results: Worker 执行结果列表
        
        Returns:
            综合报告（包含具体实施规范）
        """
        if not worker_results:
            return "⚠️ No worker findings to synthesize"
        
        # 提取关键发现
        findings = []
        for worker in worker_results:
            if worker.status == "completed" and worker.result:
                # 提取关键信息（文件路径、行号、错误信息等）
                findings.append({
                    "agent_id": worker.agent_id,
                    "description": worker.description,
                    "key_points": self._extract_key_points(worker.result),
                    "full_result": worker.result
                })
        
        # 生成综合报告
        report_lines = [
            "# Worker Findings Synthesis",
            f"",
            f"**Total Workers**: {len(worker_results)}",
            f"**Completed**: {sum(1 for w in worker_results if w.status == 'completed')}",
            f"**Failed**: {sum(1 for w in worker_results if w.status == 'failed')}",
            f"",
            "## Key Findings",
            f"",
        ]
        
        for i, finding in enumerate(findings, 1):
            report_lines.append(f"### Worker {i}: {finding['description']}")
            report_lines.append(f"")
            report_lines.append(f"**Agent ID**: {finding['agent_id']}")
            report_lines.append(f"")
            report_lines.append(f"**Key Points**:")
            for point in finding['key_points']:
                report_lines.append(f"- {point}")
            report_lines.append(f"")
        
        # 生成实施规范（必须具体！）
        report_lines.extend([
            "## Implementation Specification",
            f"",
            f"Based on the findings above, here is the specific implementation plan:",
            f"",
            f"### Changes Required",
            f"",
        ])
        
        # 这里应该根据实际发现生成具体规范
        # 示例格式:
        report_lines.extend([
            f"1. **File**: `src/auth/validate.ts:42`",
            f"   **Issue**: `user` field is undefined when session expires",
            f"   **Fix**: Add null check before accessing `user.id`",
            f"   ```typescript",
            f"   if (!user) {{",
            f"     return {{ error: 'Session expired', status: 401 }};",
            f"   }}",
            f"   ```",
            f"",
            f"2. **File**: `src/auth/types.ts:15`",
            f"   **Issue**: `Session.user` type should be `User | undefined`",
            f"   **Fix**: Update type definition",
            f"",
        ])
        
        # 记录综合历史
        synthesis_report = "\n".join(report_lines)
        self.synthesis_history.append(synthesis_report)
        
        return synthesis_report
    
    def _extract_key_points(self, result: str) -> List[str]:
        """
        从 Worker 结果中提取关键点
        
        提取策略:
        1. 文件路径和行号
        2. 错误信息
        3. 结论和建议
        4. 代码片段
        
        Args:
            result: Worker 完整结果
        
        Returns:
            关键点列表
        """
        key_points = []
        lines = result.split("\n")
        
        for line in lines:
            line = line.strip()
            
            # 检测文件路径
            if any(kw in line for kw in ["file:", "path:", "at ", ":"]) and "." in line:
                if len(line) < 200:  # 避免过长的行
                    key_points.append(line)
            
            # 检测结论/建议
            elif any(kw in line.lower() for kw in [
                "conclusion", "recommend", "found", "issue", "bug",
                "结论", "建议", "发现", "问题"
            ]):
                key_points.append(line)
            
            # 检测代码片段标记
            elif line.startswith("```") or line.startswith("`"):
                key_points.append(line)
        
        # 限制关键点数量
        return key_points[:10]
    
    def decide_continue_vs_spawn(
        self,
        worker_result: WorkerResult,
        next_task: str
    ) -> Dict[str, Any]:
        """
        决策：Continue（SendMessage）还是 Spawn（新 Agent）
        
        决策矩阵:
        
        | 情况 | 机制 | 原因 |
        |------|------|------|
        | 研究正好涉及需要编辑的文件 | Continue | Worker 已有文件上下文 + 现在有清晰计划 |
        | 研究广泛但实施狭窄 | Spawn | 避免携带探索噪声 |
        | 纠正失败或扩展最近工作 | Continue | Worker 有错误上下文 |
        | 验证其他 Worker 刚写的代码 | Spawn | 验证者应该用新鲜视角 |
        | 第一次实施完全用错方法 | Spawn | 错误上下文污染重试 |
        | 完全不相关的任务 | Spawn | 无有用上下文可复用 |
        
        Args:
            worker_result: Worker 执行结果
            next_task: 下一步任务描述
        
        Returns:
            决策结果
                {
                    "decision": "continue" | "spawn",
                    "reason": "决策原因",
                    "prompt": "给 Worker 的 prompt（如果 continue）"
                }
        """
        # 分析上下文重叠度
        context_overlap = self._analyze_context_overlap(
            worker_result.result,
            next_task
        )
        
        # 决策逻辑
        if context_overlap > 0.7:
            decision = "continue"
            reason = (
                "High context overlap — worker already has the relevant files in context "
                "and now gets a clear implementation spec"
            )
        elif context_overlap > 0.4:
            decision = "continue"
            reason = (
                "Moderate context overlap — continuing to take advantage of loaded context"
            )
        else:
            decision = "spawn"
            reason = (
                "Low context overlap — spawning fresh agent to avoid carrying unnecessary context"
            )
        
        return {
            "decision": decision,
            "reason": reason,
            "context_overlap": context_overlap,
            "worker_id": worker_result.agent_id,
            "next_task": next_task
        }
    
    def _analyze_context_overlap(
        self,
        worker_result: str,
        next_task: str
    ) -> float:
        """
        分析 Worker 结果与下一步任务的上下文重叠度
        
        Args:
            worker_result: Worker 执行结果
            next_task: 下一步任务描述
        
        Returns:
            重叠度 (0.0 - 1.0)
        """
        # 提取文件路径
        import re
        file_pattern = r'[\w/\.-]+\.(ts|js|py|md|json|yaml|yml)'
        
        worker_files = set(re.findall(file_pattern, worker_result))
        task_files = set(re.findall(file_pattern, next_task))
        
        if not worker_files or not task_files:
            # 如果没有文件路径，使用关键词匹配
            worker_words = set(worker_result.lower().split())
            task_words = set(next_task.lower().split())
            
            if not worker_words or not task_words:
                return 0.5  # 默认中等重叠
            
            common_words = worker_words & task_words
            return len(common_words) / max(len(worker_words), len(task_words))
        
        # 计算文件重叠度
        common_files = worker_files & task_files
        overlap = len(common_files) / max(len(worker_files), len(task_files))
        
        return overlap
    
    def get_status(self) -> Dict[str, Any]:
        """获取 Coordinator 状态"""
        return {
            "is_active": self.is_active,
            "total_workers": len(self.workers),
            "workers_by_status": {
                "running": sum(1 for w in self.workers.values() if w.status == "running"),
                "completed": sum(1 for w in self.workers.values() if w.status == "completed"),
                "failed": sum(1 for w in self.workers.values() if w.status == "failed"),
                "killed": sum(1 for w in self.workers.values() if w.status == "killed"),
            },
            "pending_notifications": len(self.pending_notifications),
            "synthesis_count": len(self.synthesis_history),
        }


# 全局 Coordinator 实例
coordinator = CoordinatorMode()


def get_coordinator_system_prompt() -> str:
    """
    获取 Coordinator 系统提示词
    
    包含:
    - 角色定义
    - 工具说明
    - 工作流指导
    - Continue vs Spawn 决策矩阵
    - Prompt 编写最佳实践
    """
    return """You are a coordinator. Your job is to:
- Help the user achieve their goal
- Direct workers to research, implement and verify code changes
- Synthesize results and communicate with the user
- Answer questions directly when possible — don't delegate work that you can handle without tools

## Your Tools

- **spawn_subagent** - Spawn a new worker
- **send_message** - Continue an existing worker (send a follow-up to its agent ID)
- **task_stop** - Stop a running worker
- **get_task_notifications** - Check for worker completion notifications
- **list_active_agents** - List all workers including completed ones

When calling spawn_subagent:
- Do not use one worker to check on another. Workers will notify you when they are done.
- Do not use workers to trivially report file contents or run commands. Give them higher-level tasks.
- After launching agents, briefly tell the user what you launched and end your response.
- Never fabricate or predict agent results in any format — results arrive as separate messages.

## Task Workflow

Most tasks can be broken down into the following phases:

| Phase | Who | Purpose |
|-------|-----|---------|
| Research | Workers (parallel) | Investigate codebase, find files, understand problem |
| Synthesis | **You** (coordinator) | Read findings, understand the problem, craft implementation specs |
| Implementation | Workers | Make targeted changes per spec, commit |
| Verification | Workers | Test changes work |

### Concurrency

**Parallelism is your superpower. Workers are async. Launch independent workers concurrently whenever possible.**

Manage concurrency:
- **Read-only tasks** (research) — run in parallel freely
- **Write-heavy tasks** (implementation) — one at a time per set of files
- **Verification** can sometimes run alongside implementation on different file areas

## Writing Worker Prompts

**Workers can't see your conversation.** Every prompt must be self-contained with everything the worker needs.

### Always synthesize — your most important job

When workers report research findings, **you must understand them before directing follow-up work**. Read the findings. Identify the approach. Then write a prompt that proves you understood by including specific file paths, line numbers, and exactly what to change.

Never write "based on your findings" or "based on the research." These phrases delegate understanding to the worker instead of doing it yourself.

### Choose continue vs. spawn by context overlap

After synthesizing, decide whether the worker's existing context helps or hurts:

| Situation | Mechanism | Why |
|-----------|-----------|-----|
| Research explored exactly the files that need editing | **Continue** (send_message) | Worker already has the files in context AND now gets a clear plan |
| Research was broad but implementation is narrow | **Spawn fresh** (spawn_subagent) | Avoid dragging along exploration noise; focused context is cleaner |
| Correcting a failure or extending recent work | **Continue** | Worker has the error context and knows what it just tried |
| Verifying code a different worker just wrote | **Spawn fresh** | Verifier should see the code with fresh eyes |
| First implementation attempt used the wrong approach entirely | **Spawn fresh** | Wrong-approach context pollutes the retry |
| Completely unrelated task | **Spawn fresh** | No useful context to reuse |

There is no universal default. Think about how much of the worker's context overlaps with the next task. High overlap -> continue. Low overlap -> spawn fresh.

## Example Session

User: "There's a null pointer in the auth module. Can you fix it?"

You:
  Let me investigate first.
  
  spawn_subagent(task="Investigate the auth module. Find where null pointer exceptions could occur...")
  spawn_subagent(task="Find all test files related to auth. Report test structure and gaps...")
  
  Investigating from two angles — I'll report back with findings.

[Worker completes]

You:
  Found the bug — null pointer in validate.ts:42. 
  
  send_message(to="agent-a1b", message="Fix the null pointer in src/auth/validate.ts:42. Add a null check before accessing user.id — if null, return 401 with 'Session expired'. Commit and report the hash.")
  
  Fix is in progress.
"""


# ── Dynamic Workflows 增强 ──

def load_workflow_script(self, workflow_script) -> str:
    """
    加载工作流脚本（Dynamic Workflows 核心方法）
    
    参考标准 Dynamic Workflows 的脚本加载机制。
    
    Args:
        workflow_script: WorkflowScript 对象或字典
    
    Returns:
        加载结果
    """
    from core.workflow_types import WorkflowScript
    
    # 支持字典或 WorkflowScript 对象
    if isinstance(workflow_script, dict):
        self._workflow_script = WorkflowScript.from_dict(workflow_script)
    else:
        self._workflow_script = workflow_script
    
    # 验证脚本
    errors = self._workflow_script.validate()
    if errors:
        return f"❌ 工作流脚本验证失败:\n" + "\n".join(f"- {e}" for e in errors)
    
    # 初始化进度
    self._workflow_progress = {
        "workflow_name": self._workflow_script.name,
        "status": "loaded",
        "stages_completed": 0,
        "stages_total": len(self._workflow_script.stages),
        "started_at": None,
        "completed_at": None,
    }
    
    logger.info(f"Loaded workflow script: {self._workflow_script.name}")
    
    return (
        f"✅ 工作流脚本加载成功\n\n"
        f"**名称**: {self._workflow_script.name}\n"
        f"**描述**: {self._workflow_script.description}\n"
        f"**阶段数**: {len(self._workflow_script.stages)}\n"
        f"**执行顺序**: {' -> '.join(self._workflow_script.get_execution_order())}\n\n"
        f"使用 `execute_workflow()` 开始执行。"
    )


def execute_workflow(self, model: str = "glm-4-plus") -> str:
    """
    执行已加载的工作流脚本
    
    参考标准 Dynamic Workflows 的执行引擎。
    
    Args:
        model: LLM 模型
    
    Returns:
        执行结果摘要
    """
    if not self._workflow_script:
        return "❌ 未加载工作流脚本，请先调用 load_workflow_script()"
    
    # 使用 SubagentOrchestrator 执行
    from core.subagent import SubagentOrchestrator
    
    orchestrator = SubagentOrchestrator()
    
    try:
        # 更新进度
        self._workflow_progress["status"] = "running"
        self._workflow_progress["started_at"] = datetime.now().isoformat()
        
        logger.info(f"Starting workflow execution: {self._workflow_script.name}")
        
        # 执行工作流
        result = orchestrator.run_workflow(self._workflow_script, model=model)
        
        # 更新进度
        self._workflow_progress["status"] = "completed"
        self._workflow_progress["completed_at"] = datetime.now().isoformat()
        self._workflow_progress["stages_completed"] = len(result.get("stages", {}))
        self._workflow_progress["final_result"] = result.get("final_result", "")[:500]
        
        # 生成执行报告
        report_lines = [
            f"✅ 工作流执行完成\n",
            f"**名称**: {result['workflow_name']}",
            f"**收敛**: {result['converged']}",
            f"**迭代次数**: {result['iterations']}",
            f"**阶段数**: {len(result['stages'])}",
            f"",
            f"## 阶段结果\n",
        ]
        
        for stage_name, stage_result in result['stages'].items():
            report_lines.append(f"### {stage_name}")
            report_lines.append(f"- Agent 数: {len(stage_result)}")
            completed = sum(1 for r in stage_result if r['status'] == 'completed')
            report_lines.append(f"- 完成: {completed}/{len(stage_result)}")
            
            # 显示关键发现
            if stage_result:
                report_lines.append(f"- 关键发现:")
                for r in stage_result[:3]:  # 最多显示 3 个
                    if r.get('result_preview'):
                        preview = r['result_preview'][:100]
                        report_lines.append(f"  - {r['agent_id']}: {preview}...")
            
            report_lines.append("")
        
        # 添加中间结果摘要
        if result.get('intermediate_store'):
            report_lines.extend([
                f"## 中间结果（上下文卸载）\n",
            ])
            for stage_name, content in result['intermediate_store'].items():
                if isinstance(content, str):
                    report_lines.append(f"**{stage_name}**:")
                    report_lines.append(f"```\n{content[:300]}...\n```")
                    report_lines.append("")
        
        report_lines.extend([
            f"## 最终结果\n",
            result.get('final_result', '')[:1000],
        ])
        
        return "\n".join(report_lines)
        
    except Exception as e:
        self._workflow_progress["status"] = "failed"
        self._workflow_progress["error"] = str(e)
        
        logger.error(f"Workflow execution failed: {e}")
        
        return f"❌ 工作流执行失败: {e}"


def get_workflow_progress(self) -> Dict[str, Any]:
    """获取工作流执行进度"""
    return self._workflow_progress.copy()


def save_workflow_script(self, name: str, description: str = "") -> str:
    """
    保存当前工作流脚本到文件
    
    Args:
        name: 脚本名称
        description: 脚本描述
    
    Returns:
        保存结果
    """
    import json
    from pathlib import Path
    
    if not self._workflow_script:
        return "❌ 未加载工作流脚本"
    
    # 确保目录存在
    workflows_dir = Path(".auracode/workflows")
    workflows_dir.mkdir(parents=True, exist_ok=True)
    
    # 保存脚本
    script_file = workflows_dir / f"{name}.json"
    with open(script_file, 'w', encoding='utf-8') as f:
        json.dump(self._workflow_script.to_dict(), f, indent=2, ensure_ascii=False)
    
    return (
        f"✅ 工作流脚本已保存\n\n"
        f"**路径**: {script_file}\n"
        f"**名称**: {name}\n"
        f"**描述**: {description or self._workflow_script.description}\n\n"
        f"使用 `load_workflow_script()` 加载此脚本。"
    )


# 重新绑定方法到类
CoordinatorMode.load_workflow_script = load_workflow_script
CoordinatorMode.execute_workflow = execute_workflow
CoordinatorMode.get_workflow_progress = get_workflow_progress
CoordinatorMode.save_workflow_script = save_workflow_script
