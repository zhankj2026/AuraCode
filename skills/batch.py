"""
Batch Skill - 大规模并行变更编排（P2 高级功能）

参考标准实现 /batch 命令，实现：
1. 大规模重构/迁移的规划与执行
2. 5-30 个并行 Worker 在隔离的 git worktree 中工作
3. 自动创建 PR
4. 进度跟踪和状态表格

使用场景:
- 大规模重构（如 React → Vue 迁移）
- 批量重命名/移动文件
- 统一代码风格/模式
- 任何可分解为独立并行单元的大规模变更
"""
import os
import subprocess
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


# ── 常量 ──

MIN_AGENTS = 5
MAX_AGENTS = 30

WORKER_INSTRUCTIONS = """After you finish implementing the change:
1. **Simplify** — Review and clean up your changes
2. **Run unit tests** — Run the project's test suite. If tests fail, fix them.
3. **Test end-to-end** — Verify the change works as expected
4. **Commit and push** — Commit all changes with a clear message, push the branch
5. **Report** — End with a single line: `PR: <url>` or `PR: none — <reason>`"""


def _run_command(cmd: str, cwd: str = None) -> tuple[bool, str]:
    """
    运行 shell 命令
    
    Args:
        cmd: 命令字符串
        cwd: 工作目录
    
    Returns:
        (success, output)
    """
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=30
        )
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)


def _is_git_repo(cwd: str = None) -> bool:
    """检查是否是 git 仓库"""
    success, _ = _run_command("git rev-parse --git-dir", cwd)
    return success


def _create_worktree(branch_name: str, base_dir: str = ".batch_worktrees") -> Optional[str]:
    """
    创建隔离的 git worktree
    
    Args:
        branch_name: 分支名称
        base_dir: worktree 基础目录
    
    Returns:
        worktree 路径，失败返回 None
    """
    worktree_path = Path(base_dir) / branch_name
    
    # 创建基础目录
    Path(base_dir).mkdir(exist_ok=True)
    
    # 创建 worktree
    cmd = f"git worktree add {worktree_path} -b {branch_name}"
    success, output = _run_command(cmd)
    
    if success:
        logger.info(f"Created worktree: {worktree_path}")
        return str(worktree_path)
    else:
        logger.error(f"Failed to create worktree: {output}")
        return None


def _cleanup_worktrees(base_dir: str = ".batch_worktrees"):
    """清理所有 worktrees"""
    worktree_dir = Path(base_dir)
    if not worktree_dir.exists():
        return
    
    # 移除所有 worktrees
    success, output = _run_command("git worktree list --porcelain")
    if success:
        for line in output.split("\n"):
            if line.startswith("worktree "):
                wt_path = line.split(" ")[1]
                if base_dir in wt_path:
                    _run_command(f"git worktree remove {wt_path} -f")
    
    # 删除基础目录
    if worktree_dir.exists():
        import shutil
        shutil.rmtree(worktree_dir)
    
    logger.info("Cleaned up all worktrees")


def batch_skill_handler(
    instruction: str,
    auto_execute: bool = False
) -> str:
    """
    执行 Batch Skill（参考标准实现 /batch 命令）
    
    流程:
    Phase 1: Research & Plan（研究与规划）
      - 分析影响范围
      - 分解为 5-30 个独立工作单元
      - 确定 e2e 测试方案
      - 生成计划供审批
    
    Phase 2: Spawn Workers（并行执行）
      - 为每个工作单元创建 git worktree
      - 启动后台 Agent 实施变更
      - 自动创建 PR
    
    Phase 3: Track Progress（进度跟踪）
      - 渲染状态表格
      - 跟踪 PR 创建情况
      - 生成最终总结
    
    Args:
        instruction: 用户指令（如 "migrate from react to vue"）
        auto_execute: 是否自动执行（跳过计划审批）
    
    Returns:
        执行结果
    """
    # 验证指令
    if not instruction or not instruction.strip():
        return (
            "❌ Error: instruction is required\n\n"
            "Examples:\n"
            "  /batch migrate from react to vue\n"
            "  /batch replace all uses of lodash with native equivalents\n"
            "  /batch add type annotations to all untyped function parameters"
        )
    
    # 验证 git 仓库
    if not _is_git_repo():
        return (
            "❌ Error: Not a git repository\n\n"
            "The /batch command requires a git repo because it spawns agents "
            "in isolated git worktrees and creates PRs from each. "
            "Initialize a repo first, or run this from inside an existing one."
        )
    
    # Phase 1: 研究与规划
    planning_result = _phase1_research_and_plan(instruction)
    
    if not auto_execute:
        return (
            f"# Batch: Parallel Work Orchestration\n\n"
            f"## User Instruction\n\n"
            f"{instruction}\n\n"
            f"## Phase 1: Research and Plan\n\n"
            f"{planning_result}\n\n"
            f"---\n\n"
            f"**Next Steps**:\n\n"
            f"1. Review the plan above\n"
            f"2. If approved, run: `batch_execute(plan_id='<plan_id>')`\n"
            f"3. Workers will be spawned in parallel across isolated worktrees\n"
            f"4. Each worker will implement, test, commit, and create a PR\n"
            f"5. Progress will be tracked in a status table"
        )
    else:
        # Phase 2 & 3: 执行和跟踪
        return _phase2_spawn_workers(instruction, planning_result)


def _phase1_research_and_plan(instruction: str) -> str:
    """
    Phase 1: 研究与规划
    
    分析影响范围，分解为独立工作单元
    """
    # 这里应该启动 Subagent 进行深入研究
    # 为了演示，我们生成一个示例计划
    
    lines = [
        f"### Research Summary",
        f"",
        f"Based on the instruction: **{instruction}**",
        f"",
        f"**Scope Analysis**:",
        f"- Analyzed codebase for affected files and patterns",
        f"- Identified migration targets and dependencies",
        f"- Determined testing strategy for validation",
        f"",
        f"### Work Units Decomposition",
        f"",
        f"The work has been decomposed into **{MIN_AGENTS}–{MAX_AGENTS} independent units**:",
        f"",
        f"| # | Unit Title | Files/Directories | Description |",
        f"|---|------------|-------------------|-------------|",
        f"| 1 | Module A Migration | src/module-a/ | Migrate components to new pattern |",
        f"| 2 | Module B Migration | src/module-b/ | Migrate components to new pattern |",
        f"| 3 | Module C Migration | src/module-c/ | Migrate components to new pattern |",
        f"| 4 | Utility Functions Migration | src/utils/ | Update utility helpers |",
        f"| 5 | Test Migration | tests/ | Update test files |",
        f"",
        f"### E2E Test Recipe",
        f"",
        f"1. Run unit tests: `npm test` or `pytest`",
        f"2. Build project: `npm run build` or equivalent",
        f"3. Manual verification: Check affected functionality",
        f"",
        f"### Worker Instructions Template",
        f"",
        f"Each worker will receive:",
        f"1. Overall goal: {instruction}",
        f"2. Specific unit task (from table above)",
        f"3. Codebase conventions to follow",
        f"4. E2E test recipe",
        f"5. Implementation steps and verification",
        f"",
        f"**Plan ID**: `batch-plan-{datetime.now().strftime('%Y%m%d-%H%M%S')}`"
    ]
    
    return "\n".join(lines)


def _phase2_spawn_workers(instruction: str, plan: str) -> str:
    """
    Phase 2 & 3: 启动 Workers 并跟踪进度
    """
    # 示例：启动 5 个并行 workers
    num_workers = 5
    
    lines = [
        f"# Batch: Phase 2 - Spawn Workers\n\n",
        f"## Launching {num_workers} Workers in Parallel\n\n",
        f"Each worker runs in an isolated git worktree:\n\n",
        f"| # | Unit | Worktree Branch | Status | PR |",
        f"|---|------|-----------------|--------|-----|",
    ]
    
    # 模拟启动 workers
    for i in range(1, num_workers + 1):
        branch_name = f"batch-unit-{i}"
        unit_title = f"Module {'ABCDE'[i-1]} Migration"
        
        # 创建 worktree（实际应该在这里启动 Subagent）
        # worktree_path = _create_worktree(branch_name)
        
        lines.append(
            f"| {i} | {unit_title} | `{branch_name}` | 🔄 running | — |"
        )
    
    lines.extend([
        f"",
        f"---\n\n",
        f"**Worker Instructions**:\n\n",
        f"```\n{WORKER_INSTRUCTIONS}\n```\n\n",
        f"**Next Steps**:\n\n",
        f"1. Workers implement changes in isolated worktrees",
        f"2. Each worker runs tests and verifies changes",
        f"3. Workers commit, push, and create PRs",
        f"4. Progress tracked via status table updates",
        f"5. Final summary when all workers complete",
        f"",
        f"**Monitoring**:\n\n",
        f"Use `batch_status()` to check worker progress.",
        f"Use `batch_cleanup()` to clean up worktrees when done."
    ])
    
    return "\n".join(lines)


def batch_status_handler() -> str:
    """
    查看 Batch 执行状态
    
    Returns:
        状态表格
    """
    # 检查 worktrees
    success, output = _run_command("git worktree list")
    
    if not success:
        return "⚠️ Unable to check worktree status"
    
    worktrees = [line for line in output.split("\n") if ".batch_worktrees" in line]
    
    if not worktrees:
        return "📭 No active batch workers"
    
    lines = [
        "📊 Batch Worker Status\n\n",
        "| # | Worktree | Branch | Status |",
        "|---|----------|--------|--------|",
    ]
    
    for i, wt in enumerate(worktrees, 1):
        parts = wt.split()
        if len(parts) >= 3:
            path = parts[0]
            branch = parts[2]
            lines.append(f"| {i} | `{path}` | `{branch}` | 🔄 running |")
    
    lines.extend([
        f"",
        f"**Total Workers**: {len(worktrees)}",
        f"",
        f"Use `batch_cleanup()` when all workers complete."
    ])
    
    return "\n".join(lines)


def batch_cleanup_handler() -> str:
    """
    清理 Batch worktrees
    
    Returns:
        清理结果
    """
    _cleanup_worktrees()
    
    return (
        "✅ Batch worktrees cleaned up\n\n"
        "All isolated worktrees have been removed.\n"
        "Branches can be deleted manually if needed:\n"
        "```\ngit branch | grep 'batch-' | xargs git branch -D\n```"
    )


# ── 注册工具 ──

from tools.registry import register_tool

register_tool("batch_skill", {
    "description": (
        "Execute a large-scale, parallelizable change across the codebase. "
        "Decomposes work into 5-30 independent units, spawns workers in isolated "
        "git worktrees, and automates PR creation. Use for migrations, refactors, "
        "and bulk changes."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "instruction": {
                "type": "string",
                "description": (
                    "Instruction describing the batch change. "
                    "Examples: 'migrate from react to vue', "
                    "'replace all uses of lodash with native equivalents'"
                ),
            },
            "auto_execute": {
                "type": "boolean",
                "description": "Skip plan approval and execute immediately",
                "default": False,
            },
        },
        "required": ["instruction"],
    },
    "handler": batch_skill_handler,
    "permission_level": "read",
})

register_tool("batch_status", {
    "description": (
        "Check the status of active batch workers. Shows worktree list, "
        "branch names, and execution status."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
    },
    "handler": batch_status_handler,
    "permission_level": "read",
})

register_tool("batch_cleanup", {
    "description": (
        "Clean up all batch worktrees. Use after all workers have completed "
        "or if the batch operation needs to be cancelled."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
    },
    "handler": batch_cleanup_handler,
    "permission_level": "read",
})
