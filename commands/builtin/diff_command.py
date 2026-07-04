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
Diff 命令 - 查看 Git 变更差异

功能:
- 显示未提交的代码变更（staged + unstaged）
- 支持按文件过滤
- 显示变更统计概览
- 可选显示与某个提交的差异

用法:
  /diff              显示所有未提交变更
  /diff <文件路径>    仅显示指定文件的变更
  /diff --staged     仅显示已暂存的变更
  /diff --stat       仅显示统计摘要
"""

import subprocess
from commands.registry import register_command


def _run_git(cmd: list, cwd: str = ".") -> tuple:
    """执行 git 命令"""
    try:
        result = subprocess.run(
            ["git"] + cmd,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=30,
            encoding="utf-8"
        )
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)


def _colorize_diff(diff_text: str) -> str:
    """为 diff 输出添加颜色标记（文本标记）"""
    lines = diff_text.splitlines()
    result = []
    for line in lines:
        if line.startswith("+++") or line.startswith("---"):
            result.append(f"  {line}")
        elif line.startswith("+"):
            result.append(f"  🟢 {line[1:]}")
        elif line.startswith("-"):
            result.append(f"  🔴 {line[1:]}")
        elif line.startswith("@@"):
            result.append(f"  ⚡ {line}")
        elif line.startswith("diff ") or line.startswith("index "):
            result.append(f"  📄 {line}")
        else:
            result.append(f"  {line}")
    return "\n".join(result)


def diff_handler(args: list, loop=None) -> str:
    """diff 命令处理函数"""
    cwd = "."

    # 检查是否在 git 仓库
    ok, _, _ = _run_git(["rev-parse", "--git-dir"], cwd)
    if not ok:
        return "❌ 当前目录不是 Git 仓库"

    lines = []
    lines.append("🔍 Git Diff - 代码变更")
    lines.append("=" * 60)

    # 解析参数
    show_staged_only = "--staged" in args or "--cached" in args
    show_stat_only = "--stat" in args
    filter_file = None
    for arg in args:
        if not arg.startswith("--"):
            filter_file = arg
            break

    # 获取当前分支
    ok, branch, _ = _run_git(["branch", "--show-current"], cwd)
    if ok:
        lines.append(f"🌿 分支: {branch.strip()}")

    # 获取状态概览
    ok, status_out, _ = _run_git(["status", "--short"], cwd)
    if ok and status_out.strip():
        staged_count = sum(1 for l in status_out.splitlines() if l and l[0] not in " ?")
        unstaged_count = sum(1 for l in status_out.splitlines() if l and len(l) > 1 and l[1] in "MD")
        untracked_count = sum(1 for l in status_out.splitlines() if l.startswith("??"))
        lines.append(f"📊 变更: {staged_count} 已暂存 / {unstaged_count} 未暂存 / {untracked_count} 新文件")
    else:
        lines.append("✅ 工作目录干净，没有变更")
        return "\n".join(lines)

    lines.append("-" * 60)

    # 构建 diff 命令
    diff_cmd = ["diff"]
    if show_staged_only:
        diff_cmd.extend(["--cached"])
    else:
        diff_cmd.append("HEAD")

    if show_stat_only:
        diff_cmd.append("--stat")
    else:
        diff_cmd.extend(["--color=never"])

    if filter_file:
        diff_cmd.extend(["--", filter_file])

    ok, diff_out, err = _run_git(diff_cmd, cwd)

    if not ok:
        lines.append(f"❌ 获取 diff 失败: {err}")
        return "\n".join(lines)

    if not diff_out.strip():
        lines.append("✅ 没有匹配的变更")
        return "\n".join(lines)

    if show_stat_only:
        lines.append("\n📊 变更统计:")
        lines.append(diff_out)
    else:
        lines.append("\n📝 变更详情:")
        # 截断过长的 diff
        diff_lines = diff_out.splitlines()
        max_lines = 100
        if len(diff_lines) > max_lines:
            colored = _colorize_diff("\n".join(diff_lines[:max_lines]))
            lines.append(colored)
            lines.append(f"\n  ... (截断 {len(diff_lines) - max_lines} 行，完整内容请使用 git diff 命令)")
        else:
            lines.append(_colorize_diff(diff_out))

    # 如果有未跟踪的文件，也列出
    if not show_staged_only and not filter_file:
        ok, untracked, _ = _run_git(["ls-files", "--others", "--exclude-standard"], cwd)
        if ok and untracked.strip():
            lines.append("\n❓ 新文件（未跟踪）:")
            for f in untracked.strip().splitlines()[:10]:
                lines.append(f"   + {f}")
            total_untracked = len(untracked.strip().splitlines())
            if total_untracked > 10:
                lines.append(f"   ... 共 {total_untracked} 个新文件")

    lines.append("=" * 60)
    return "\n".join(lines)


register_command("diff", {
    "description": "查看 Git 代码变更 - 支持过滤文件和统计模式",
    "handler": diff_handler,
    "category": "tools",
    "args_help": "[文件路径|--staged|--stat]"
})
