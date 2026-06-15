"""
Review 命令 — AI 代码审查

对当前工作区的 Git 变更进行 AI 驱动的代码审查，
输出结构化报告（严重性/类别/建议）。
集成 CodeAnalyzer 进行变更影响分析。
"""
import os
import subprocess
from commands.registry import register_command


def review_handler(args: list, loop=None) -> str:
    """
    审查当前工作区的未提交变更。

    用法:
        /review           — 审查所有暂存+未暂存变更
        /review --staged  — 仅审查暂存变更
        /review <file>    — 审查指定文件
    """
    # 解析参数
    staged_only = "--staged" in args
    target_file = None
    for a in args:
        if not a.startswith("-"):
            target_file = a
            break

    lines = []
    lines.append("=" * 60)
    lines.append("🔍 代码审查报告")
    lines.append("=" * 60)

    # 1. 获取变更
    try:
        if target_file:
            if not os.path.exists(target_file):
                return f"错误: 文件不存在: {target_file}"
            diff_output = _get_file_diff(target_file)
            lines.append(f"\n审查文件: {target_file}")
        elif staged_only:
            diff_output = _run_git("diff", "--cached")
            lines.append("\n审查范围: 暂存变更 (--staged)")
        else:
            diff_output = _run_git("diff") + "\n" + _run_git("diff", "--cached")
            lines.append("\n审查范围: 所有未提交变更")

        if not diff_output.strip():
            lines.append("\n✅ 无变更需要审查")
            return "\n".join(lines)

    except Exception as e:
        return f"错误: 无法获取 Git 变更: {e}"

    # 2. 解析变更统计
    stats = _parse_diff_stats(diff_output)
    lines.append(f"变更统计: {stats['files']} 文件, +{stats['additions']}/-{stats['deletions']}")
    lines.append("")

    # 3. 本地规则审查（不依赖 LLM）
    issues = _local_review(diff_output)

    if not issues:
        lines.append("✅ 未发现问题（本地规则检查通过）")
    else:
        # 按严重性分组
        critical = [i for i in issues if i["severity"] == "critical"]
        warning = [i for i in issues if i["severity"] == "warning"]
        info = [i for i in issues if i["severity"] == "info"]

        if critical:
            lines.append(f"🔴 严重问题 ({len(critical)}):")
            for i in critical:
                lines.append(f"  • [{i['category']}] {i['message']}")
        if warning:
            lines.append(f"🟡 警告 ({len(warning)}):")
            for i in warning:
                lines.append(f"  • [{i['category']}] {i['message']}")
        if info:
            lines.append(f"🔵 建议 ({len(info)}):")
            for i in info:
                lines.append(f"  • [{i['category']}] {i['message']}")

    # 4. 变更影响分析 (CodeAnalyzer 集成)
    try:
        from core.code_analyzer import CodeAnalyzer
        project_root = os.getcwd()
        analyzer = CodeAnalyzer(project_root=project_root)
        graph = analyzer.build_dependency_graph()

        # 获取变更文件列表
        changed_files = list(stats.get("_changed_files", set()))
        if not changed_files:
            # 从 diff 中提取文件名
            changed_files = _extract_changed_files(diff_output)

        if changed_files and graph:
            impact = analyzer.analyze_impact(changed_files)
            if impact:
                lines.append("")
                lines.append("─" * 40)
                lines.append("📊 变更影响分析:")
                report = analyzer.generate_impact_report(changed_files)
                lines.append(report)
    except ImportError:
        pass  # CodeAnalyzer 不可用时跳过
    except Exception as e:
        lines.append(f"\n⚠️ 影响分析失败: {e}")

    # 5. 如果 LLM 可用，进行 AI 审查
    if loop:
        lines.append("")
        lines.append("─" * 40)
        lines.append("🤖 AI 深度审查:")
        ai_review = _ai_review(loop, diff_output, stats)
        lines.append(ai_review)

    lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)


def _extract_changed_files(diff: str) -> list:
    """从 diff 输出中提取变更文件列表"""
    files = []
    for line in diff.splitlines():
        if line.startswith("diff --git"):
            parts = line.split(" b/")
            if len(parts) > 1:
                files.append(parts[-1])
    return files


def _run_git(*args) -> str:
    """执行 git 命令"""
    result = subprocess.run(
        ["git"] + list(args),
        capture_output=True, text=True, timeout=30,
        encoding="utf-8", errors="replace",
    )
    return result.stdout


def _get_file_diff(path: str) -> str:
    """获取单文件 diff"""
    diff = _run_git("diff", "--", path)
    if not diff.strip():
        diff = _run_git("diff", "--cached", "--", path)
    if not diff.strip():
        # 未跟踪文件 → 读取内容
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            lines = content.splitlines()
            diff = f"--- /dev/null\n+++ b/{path}\n"
            diff += "\n".join(f"+{l}" for l in lines[:200])
        except Exception:
            diff = ""
    return diff


def _parse_diff_stats(diff: str) -> dict:
    """解析 diff 统计"""
    files = set()
    additions = 0
    deletions = 0
    for line in diff.splitlines():
        if line.startswith("diff --git"):
            parts = line.split(" b/")
            if len(parts) > 1:
                files.add(parts[-1])
        elif line.startswith("+") and not line.startswith("+++"):
            additions += 1
        elif line.startswith("-") and not line.startswith("---"):
            deletions += 1
    return {"files": len(files), "additions": additions, "deletions": deletions}


def _local_review(diff: str) -> list:
    """本地规则审查（不依赖 LLM）"""
    issues = []
    for line in diff.splitlines():
        if not line.startswith("+") or line.startswith("+++"):
            continue

        content = line[1:]  # 去掉 + 前缀

        # 安全检查
        if any(pat in content.lower() for pat in ["password", "secret", "api_key", "token"]):
            if "=" in content or ":" in content:
                issues.append({
                    "severity": "critical",
                    "category": "security",
                    "message": f"可能包含硬编码密钥: {content.strip()[:80]}",
                })

        # TODO/FIXME/HACK 标记
        for marker in ["TODO", "FIXME", "HACK", "XXX"]:
            if marker in content.upper():
                issues.append({
                    "severity": "info",
                    "category": "maintenance",
                    "message": f"代码标记 {marker}: {content.strip()[:80]}",
                })

        # 过长行
        if len(content) > 200:
            issues.append({
                "severity": "info",
                "category": "style",
                "message": f"行过长 ({len(content)} 字符): {content.strip()[:60]}...",
            })

        # print 语句（Python）
        if content.strip().startswith("print(") or content.strip().startswith("console.log"):
            issues.append({
                "severity": "warning",
                "category": "debug",
                "message": f"调试输出残留: {content.strip()[:80]}",
            })

    return issues


def _ai_review(loop, diff: str, stats: dict) -> str:
    """使用 LLM 进行 AI 深度审查"""
    try:
        prompt = (
            f"请审查以下代码变更（{stats['files']} 文件, "
            f"+{stats['additions']}/-{stats['deletions']}）。\n\n"
            f"```diff\n{diff[:4000]}\n```\n\n"
            "请用中文输出：\n"
            "1. 变更概述（1-2 句话）\n"
            "2. 潜在问题（bug/安全/性能/可维护性）\n"
            "3. 改进建议\n"
            "格式要求：简洁，使用 emoji 标记严重性。"
        )
        result = loop.run(prompt)
        return result.text or "（AI 审查无输出）"
    except Exception as e:
        return f"AI 审查失败: {e}"


register_command("review", {
    "description": "AI 代码审查（审查 Git 变更中的问题）",
    "handler": review_handler,
    "category": "analysis",
    "args_help": "[--staged] [file]  审查暂存变更或指定文件",
})
