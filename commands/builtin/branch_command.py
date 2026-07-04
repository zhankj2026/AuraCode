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
Branch 命令 — 从当前对话创建 Git 分支

功能:
- 从当前对话点创建新的 Git 分支（对话分叉）
- 支持分支命名和基于指定提交创建
- 自动切换工作目录到新分支
- 显示分支状态和切换确认

用法:
  /branch              — 交互式创建分支
  /branch <name>       — 创建指定名称的分支
  /branch --list       — 列出所有本地分支
  /branch --switch <n> — 切换到指定分支
"""

import subprocess
import os
import re
from commands.registry import register_command


def _run_git(cmd: list, cwd: str = ".") -> tuple:
    """执行 git 命令，返回 (success, stdout, stderr)"""
    try:
        result = subprocess.run(
            ["git"] + cmd, capture_output=True, text=True,
            cwd=cwd, timeout=30, encoding="utf-8",
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "命令超时"
    except Exception as e:
        return False, "", str(e)


def _sanitize_branch_name(name: str) -> str:
    """清理分支名称，确保合法"""
    name = name.strip().lower()
    name = re.sub(r'[^a-z0-9._/\-]', '-', name)
    name = re.sub(r'-+', '-', name).strip('-')
    return name[:64] if name else "new-branch"


def branch_handler(args: list, loop=None) -> str:
    """branch 命令处理函数"""
    cwd = "."

    # 检查 git 仓库
    ok, _, _ = _run_git(["rev-parse", "--git-dir"], cwd)
    if not ok:
        return "❌ 当前目录不是 Git 仓库"

    lines = ["🌿 Git 分支管理", "=" * 60]

    # 解析参数
    if "--list" in args or "-l" in args:
        return _list_branches(cwd)

    if "--switch" in args or "-s" in args:
        idx = next((i for i, a in enumerate(args) if a in ("--switch", "-s")), -1)
        if idx >= 0 and idx + 1 < len(args):
            return _switch_branch(args[idx + 1], cwd)
        return "❌ 请指定分支名称: /branch --switch <name>"

    if "--delete" in args or "-d" in args:
        idx = next((i for i, a in enumerate(args) if a in ("--delete", "-d")), -1)
        if idx >= 0 and idx + 1 < len(args):
            return _delete_branch(args[idx + 1], cwd)
        return "❌ 请指定分支名称: /branch --delete <name>"

    # 创建分支
    branch_name = None
    for a in args:
        if not a.startswith("-"):
            branch_name = a
            break

    if not branch_name:
        # 无参数 → 显示当前状态 + 提示
        return _show_branch_status(cwd)

    return _create_branch(branch_name, cwd)


def _show_branch_status(cwd: str) -> str:
    """显示当前分支状态"""
    lines = ["🌿 Git 分支状态", "=" * 60]

    # 当前分支
    ok, out, _ = _run_git(["branch", "--show-current"], cwd)
    current = out.strip() if ok else "(detached)"
    lines.append(f"当前分支: {current}")

    # 分支列表
    ok, out, _ = _run_git(["branch", "-v", "--no-color"], cwd)
    if ok and out.strip():
        lines.append("\n本地分支:")
        for line in out.strip().splitlines():
            prefix = "→" if line.startswith("*") else " "
            lines.append(f"  {prefix} {line[2:]}")

    # 远程分支
    ok, out, _ = _run_git(["branch", "-r", "--no-color"], cwd)
    if ok and out.strip():
        remotes = [l.strip() for l in out.strip().splitlines()
                   if "HEAD" not in l]
        if remotes:
            lines.append(f"\n远程分支 ({len(remotes)}):")
            for r in remotes[:10]:
                lines.append(f"  • {r}")
            if len(remotes) > 10:
                lines.append(f"  ... 还有 {len(remotes) - 10} 个")

    lines.append(f"\n用法:")
    lines.append(f"  /branch <name>       创建并切换到新分支")
    lines.append(f"  /branch --list       列出所有分支")
    lines.append(f"  /branch --switch <n> 切换到指定分支")
    lines.append(f"  /branch --delete <n> 删除指定分支")
    lines.append("=" * 60)
    return "\n".join(lines)


def _create_branch(name: str, cwd: str) -> str:
    """创建并切换到新分支"""
    safe_name = _sanitize_branch_name(name)
    lines = [f"🌿 创建分支: {safe_name}", "=" * 60]

    # 当前分支
    ok, out, _ = _run_git(["branch", "--show-current"], cwd)
    current = out.strip() if ok else "(unknown)"
    lines.append(f"基于分支: {current}")

    # 检查工作区是否干净
    ok, out, _ = _run_git(["status", "--short"], cwd)
    if ok and out.strip():
        lines.append("⚠️  工作区有未提交的变更，建议先提交或暂存")

    # 创建分支
    ok, out, err = _run_git(["checkout", "-b", safe_name], cwd)
    if ok:
        lines.append(f"✅ 分支已创建并切换: {safe_name}")
        # 显示 HEAD
        ok2, hash_out, _ = _run_git(["log", "--oneline", "-1"], cwd)
        if ok2:
            lines.append(f"📍 HEAD: {hash_out.strip()}")
    else:
        if "already exists" in err:
            lines.append(f"⚠️  分支 {safe_name} 已存在，尝试切换...")
            ok2, _, err2 = _run_git(["checkout", safe_name], cwd)
            if ok2:
                lines.append(f"✅ 已切换到分支: {safe_name}")
            else:
                lines.append(f"❌ 切换失败: {err2}")
        else:
            lines.append(f"❌ 创建分支失败: {err}")

    lines.append("=" * 60)
    return "\n".join(lines)


def _list_branches(cwd: str) -> str:
    """列出所有分支"""
    lines = ["🌿 分支列表", "=" * 60]

    # 本地分支
    ok, out, _ = _run_git(["branch", "-v", "--no-color"], cwd)
    if ok and out.strip():
        lines.append("\n本地分支:")
        for line in out.strip().splitlines():
            prefix = "→" if line.startswith("*") else " "
            lines.append(f"  {prefix} {line[2:]}")

    # 远程分支
    ok, out, _ = _run_git(["branch", "-r", "--no-color"], cwd)
    if ok and out.strip():
        remotes = [l.strip() for l in out.strip().splitlines()
                   if "HEAD" not in l]
        if remotes:
            lines.append(f"\n远程分支 ({len(remotes)}):")
            for r in remotes[:20]:
                lines.append(f"  • {r}")
            if len(remotes) > 20:
                lines.append(f"  ... 还有 {len(remotes) - 20} 个")

    lines.append("=" * 60)
    return "\n".join(lines)


def _switch_branch(name: str, cwd: str) -> str:
    """切换到指定分支"""
    ok, out, err = _run_git(["checkout", name], cwd)
    if ok:
        return f"✅ 已切换到分支: {name}"
    else:
        return f"❌ 切换失败: {err}"


def _delete_branch(name: str, cwd: str) -> str:
    """删除指定分支"""
    # 先检查是否在目标分支上
    ok, out, _ = _run_git(["branch", "--show-current"], cwd)
    if ok and out.strip() == name:
        return f"❌ 无法删除当前分支 ({name})，请先切换到其他分支"

    ok, out, err = _run_git(["branch", "-d", name], cwd)
    if ok:
        return f"✅ 分支已删除: {name}"
    else:
        # 尝试强制删除
        if "not fully merged" in err:
            return (f"⚠️  分支 {name} 有未合并的变更。"
                    f"使用 git branch -D 强制删除（本命令不自动执行）")
        return f"❌ 删除失败: {err}"


# 注册命令
register_command("branch", {
    "description": "Git 分支管理 — 创建/切换/列出/删除分支",
    "handler": branch_handler,
    "category": "git",
    "args_help": "[name] | --list | --switch <n> | --delete <n>",
})

