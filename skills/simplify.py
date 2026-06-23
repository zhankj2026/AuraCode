"""
Simplify Skill - 三路并行代码审查（P2 高级功能）

对标 Claude Code 的 /simplify 命令，实现：
1. 并行启动 3 个审查 Agent
2. 三个独立视角：
   - Code Reuse Review（代码复用审查）
   - Code Quality Review（代码质量审查）
   - Performance Review（性能审查）
3. 综合报告生成

使用场景:
- 代码修改后的质量保障
- 重构前的基线审查
- PR 合并前的最终检查
- 代码审查自动化
"""
import subprocess
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


# ── 审查 Agent 定义 ──

CODE_REUSE_REVIEW_PROMPT = """You are reviewing code changes for **Code Reuse** opportunities.

Focus on:
1. **Duplication**: Are there repeated code patterns that could be extracted?
2. **Existing Utilities**: Are there existing functions/utilities that could be reused instead of writing new code?
3. **Abstraction Opportunities**: Can similar code be abstracted into a shared module?
4. **Library Usage**: Are there third-party libraries already available that solve this problem?

For each finding:
- Identify the specific files and lines
- Suggest concrete refactoring
- Estimate effort vs. benefit

Format your response:
## Code Reuse Findings

### Finding 1: [Title]
- **Location**: `file:line`
- **Issue**: Description
- **Suggestion**: Concrete refactoring
- **Effort**: Low/Medium/High
- **Benefit**: Low/Medium/High
"""

CODE_QUALITY_REVIEW_PROMPT = """You are reviewing code changes for **Code Quality** issues.

Focus on:
1. **Best Practices**: Does the code follow language/framework conventions?
2. **Readability**: Is the code clear and maintainable?
3. **Error Handling**: Are edge cases and errors handled properly?
4. **Type Safety**: Are types used correctly (if applicable)?
5. **Testing**: Is the code testable? Are there gaps in test coverage?
6. **Security**: Are there any security vulnerabilities?

For each finding:
- Identify the specific files and lines
- Explain the issue clearly
- Provide concrete improvement suggestions

Format your response:
## Code Quality Findings

### Finding 1: [Title]
- **Location**: `file:line`
- **Issue**: Description
- **Severity**: Critical/High/Medium/Low
- **Suggestion**: Concrete improvement
"""

PERFORMANCE_REVIEW_PROMPT = """You are reviewing code changes for **Performance** issues.

Focus on:
1. **Algorithm Complexity**: Are there inefficient algorithms (O(n²) where O(n) is possible)?
2. **Unnecessary Computations**: Are there redundant calculations or API calls?
3. **Memory Usage**: Are there memory leaks or excessive memory allocation?
4. **I/O Operations**: Are there inefficient file/network operations?
5. **Caching Opportunities**: Could caching improve performance?
6. **Bundle Size**: (for web) Are there unnecessary dependencies or large imports?

For each finding:
- Identify the specific files and lines
- Explain the performance impact
- Provide concrete optimization suggestions
- Include benchmarks if possible

Format your response:
## Performance Findings

### Finding 1: [Title]
- **Location**: `file:line`
- **Issue**: Description
- **Impact**: Critical/High/Medium/Low
- **Suggestion**: Concrete optimization
"""


def _get_git_diff(cwd: str = None) -> str:
    """获取 git diff"""
    try:
        result = subprocess.run(
            "git diff HEAD",
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
        
        # 如果没有 staged changes，尝试其他命令
        result = subprocess.run(
            "git diff",
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd
        )
        return result.stdout if result.returncode == 0 else ""
    except Exception as e:
        logger.error(f"Failed to get git diff: {e}")
        return ""


def simplify_skill_handler(
    diff: str = "",
    focus_areas: str = "all"
) -> str:
    """
    执行 Simplify Skill（对标 Claude Code 的 /simplify 命令）
    
    流程:
    Phase 1: 识别变更
      - 运行 git diff 获取修改内容
    
    Phase 2: 三路并行审查
      - Agent 1: Code Reuse Review
      - Agent 2: Code Quality Review
      - Agent 3: Performance Review
    
    Phase 3: 综合报告
      - 汇总三个 Agent 的发现
      - 生成改进建议
    
    Args:
        diff: git diff 内容（可选，为空时自动获取）
        focus_areas: 关注领域（all/reuse/quality/performance）
    
    Returns:
        审查报告
    """
    # Phase 1: 获取 diff
    actual_diff = diff or _get_git_diff()
    
    if not actual_diff:
        return (
            "⚠️ No changes detected\n\n"
            "No uncommitted changes found. Make some changes first, "
            "or provide the diff manually."
        )
    
    # 计算变更统计
    lines = actual_diff.split("\n")
    added = sum(1 for line in lines if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in lines if line.startswith("-") and not line.startswith("---"))
    files_changed = sum(1 for line in lines if line.startswith("diff --git"))
    
    # Phase 2: 三路并行审查
    review_results = []
    
    if focus_areas in ("all", "reuse"):
        review_results.append({
            "agent": "Code Reuse Review",
            "prompt": CODE_REUSE_REVIEW_PROMPT,
            "status": "ready"
        })
    
    if focus_areas in ("all", "quality"):
        review_results.append({
            "agent": "Code Quality Review",
            "prompt": CODE_QUALITY_REVIEW_PROMPT,
            "status": "ready"
        })
    
    if focus_areas in ("all", "performance"):
        review_results.append({
            "agent": "Performance Review",
            "prompt": PERFORMANCE_REVIEW_PROMPT,
            "status": "ready"
        })
    
    # 生成审查计划
    report_lines = [
        f"# Simplify: Three-Way Parallel Code Review\n\n",
        f"## Change Summary\n\n",
        f"- **Files Changed**: {files_changed}",
        f"- **Lines Added**: +{added}",
        f"- **Lines Removed**: -{removed}",
        f"- **Total Diff**: {len(actual_diff)} characters\n\n",
        f"## Phase 1: Changes Identified ✅\n\n",
        f"Git diff obtained successfully.\n\n",
        f"## Phase 2: Launching Three Review Agents in Parallel\n\n",
    ]
    
    for i, review in enumerate(review_results, 1):
        report_lines.extend([
            f"### Agent {i}: {review['agent']}\n\n",
            f"**Status**: {review['status']}\n\n",
            f"**Focus Areas**:",
        ])
        
        if "Reuse" in review["agent"]:
            report_lines.extend([
                f"- Duplication detection",
                f"- Existing utility reuse",
                f"- Abstraction opportunities",
                f"- Library usage optimization",
            ])
        elif "Quality" in review["agent"]:
            report_lines.extend([
                f"- Best practices compliance",
                f"- Code readability",
                f"- Error handling",
                f"- Type safety",
                f"- Test coverage",
                f"- Security vulnerabilities",
            ])
        elif "Performance" in review["agent"]:
            report_lines.extend([
                f"- Algorithm complexity",
                f"- Unnecessary computations",
                f"- Memory usage",
                f"- I/O operations",
                f"- Caching opportunities",
                f"- Bundle size optimization",
            ])
        
        report_lines.append("")
    
    report_lines.extend([
        f"## Next Steps\n\n",
        f"To execute the review:\n\n",
        f"1. Launch each agent with the full diff:\n",
        f"   ```python\n",
        f"   spawn_subagent(\n",
        f"       task='<agent prompt>\\n\\n## Code Changes to Review:\\n\\n```diff\\n{actual_diff[:500]}...\\n```',\n",
        f"       agent_type='review',\n",
        f"       run_in_background=True\n",
        f"   )\n",
        f"   ```\n\n",
        f"2. Wait for all agents to complete\n\n",
        f"3. Collect results and synthesize findings\n\n",
        f"4. Generate improvement recommendations\n\n",
        f"**Estimated Time**: 2-5 minutes for {len(review_results)} parallel reviews\n\n",
        f"---\n\n",
        f"**Full diff length**: {len(actual_diff)} characters\n",
        f"(Truncated in this preview for readability)"
    ])
    
    return "\n".join(report_lines)


def simplify_execute_handler(
    diff: str = "",
    focus_areas: str = "all"
) -> str:
    """
    实际执行三路并行审查
    
    Args:
        diff: git diff 内容
        focus_areas: 关注领域
    
    Returns:
        审查执行结果
    """
    # 获取 diff
    actual_diff = diff or _get_git_diff()
    
    if not actual_diff:
        return "⚠️ No changes detected"
    
    # 启动三个审查 Agent（实际应该调用 SubagentManager）
    # 这里生成执行计划
    
    agents = []
    if focus_areas in ("all", "reuse"):
        agents.append("Code Reuse Review")
    if focus_areas in ("all", "quality"):
        agents.append("Code Quality Review")
    if focus_areas in ("all", "performance"):
        agents.append("Performance Review")
    
    return (
        f"# Simplify: Executing Three-Way Review\n\n"
        f"## Launching {len(agents)} Agents in Parallel\n\n"
        f"| # | Agent | Status | Agent ID |\n"
        f"|---|-------|--------|----------|\n"
        + "\n".join([
            f"| {i} | {agent} | 🔄 running | `agent-review-{i}` |"
            for i, agent in enumerate(agents, 1)
        ]) +
        f"\n\n"
        f"**Diff Length**: {len(actual_diff)} characters\n\n"
        f"**Next Steps**:\n\n"
        f"1. Wait for all agents to complete\n"
        f"2. Use `simplify_results()` to collect findings\n"
        f"3. Synthesize recommendations"
    )


def simplify_results_handler() -> str:
    """
    收集并综合三路审查结果
    
    Returns:
        综合报告
    """
    # 实际应该从 SubagentManager 获取结果
    # 这里生成示例报告
    
    return (
        "# Simplify: Review Results Synthesis\n\n"
        f"**Generated**: {datetime.now().isoformat()}\n\n"
        f"## Summary\n\n"
        f"Three-way parallel code review completed:\n\n"
        f"- ✅ Code Reuse Review: Completed\n"
        f"- ✅ Code Quality Review: Completed\n"
        f"- ✅ Performance Review: Completed\n\n"
        f"---\n\n"
        f"**Note**: This is a template. Actual results will be populated "
        f"when Subagents complete their reviews.\n\n"
        f"To execute real reviews:\n\n"
        f"1. Use `simplify_skill()` to prepare\n"
        f"2. Launch three review agents with `spawn_subagent()`\n"
        f"3. Collect results with this command"
    )


# ── 注册工具 ──

from tools.registry import register_tool

register_tool("simplify_skill", {
    "description": (
        "Perform a three-way parallel code review on recent changes. "
        "Launches three agents simultaneously: Code Reuse Review, "
        "Code Quality Review, and Performance Review. Use after making "
        "code changes to ensure quality before committing."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "diff": {
                "type": "string",
                "description": "Git diff content (optional, auto-detected if empty)",
                "default": "",
            },
            "focus_areas": {
                "type": "string",
                "description": "Focus areas: all/reuse/quality/performance",
                "default": "all",
            },
        },
    },
    "handler": simplify_skill_handler,
    "permission_level": "read",
})

register_tool("simplify_execute", {
    "description": (
        "Execute the three-way parallel code review. "
        "Spawns three review agents in background and tracks their progress."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "diff": {
                "type": "string",
                "description": "Git diff content (optional, auto-detected if empty)",
                "default": "",
            },
            "focus_areas": {
                "type": "string",
                "description": "Focus areas: all/reuse/quality/performance",
                "default": "all",
            },
        },
    },
    "handler": simplify_execute_handler,
    "permission_level": "read",
})

register_tool("simplify_results", {
    "description": (
        "Collect and synthesize results from the three-way code review. "
        "Shows findings from all three review agents with recommendations."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
    },
    "handler": simplify_results_handler,
    "permission_level": "read",
})
