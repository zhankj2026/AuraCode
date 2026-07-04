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
Commit 命令 - AI 智能生成 Git 提交

功能:
- 分析当前 Git 变更（staged + unstaged）
- 参考最近提交风格
- 使用 AI 生成规范的 commit message
- 自动 stage 文件并创建提交

安全规则:
- 不会 amend 已有提交
- 不会提交可能包含秘密的文件
- 不会跳过 hooks
- 不会使用交互式 git 命令
"""

import subprocess
import re
from commands.registry import register_command

# 危险文件模式（可能包含秘密）
SECRET_FILE_PATTERNS = [
    r'\.env$',
    r'\.env\..+',
    r'credentials\.json$',
    r'secrets?\.(json|ya?ml|toml)$',
    r'\.npmrc$',
    r'\.pypirc$',
    r'.*private.*key.*',
    r'\.aws/credentials$',
]

COMMIT_SYSTEM_PROMPT = """你是一个专业的 Git 提交助手。根据代码变更生成规范的 commit message。

规则:
1. 分析所有 staged 变更，生成准确描述变更内容的 commit message
2. 参考最近的历史提交，遵循该仓库的提交风格
3. message 应简洁（1-2句），侧重"为什么"而非"是什么"
4. 使用以下类型前缀: feat(新功能), fix(修复), refactor(重构), test(测试), docs(文档), chore(维护)
5. 如果没有变更，说明"没有需要提交的内容"

输出格式（仅输出 commit message 本身，不要任何解释或代码块标记）:
type: 简短描述

可选的详细描述（如有必要）"""


def _run_git(cmd: list, cwd: str = ".") -> tuple:
    """执行 git 命令，返回 (success, stdout, stderr)"""
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
    except subprocess.TimeoutExpired:
        return False, "", "命令超时"
    except Exception as e:
        return False, "", str(e)


def _check_secret_files(files: list) -> list:
    """检查文件列表中是否有可能包含秘密的文件"""
    warnings = []
    for f in files:
        for pattern in SECRET_FILE_PATTERNS:
            if re.search(pattern, f, re.IGNORECASE):
                warnings.append(f)
                break
    return warnings


def _get_git_context(cwd: str = ".") -> dict:
    """获取 Git 上下文信息"""
    context = {
        "status": "",
        "diff": "",
        "staged_diff": "",
        "branch": "",
        "recent_commits": "",
        "staged_files": [],
        "unstaged_files": [],
        "untracked_files": [],
    }

    # git status
    ok, out, _ = _run_git(["status", "--short"], cwd)
    if ok:
        context["status"] = out.strip()
        # 解析文件状态
        for line in out.strip().splitlines():
            if not line:
                continue
            status_code = line[:2]
            filename = line[3:].strip()
            if status_code[0] in ("A", "M", "D", "R"):
                context["staged_files"].append(filename)
            if status_code[1] in ("M", "D"):
                context["unstaged_files"].append(filename)
            if status_code == "??":
                context["untracked_files"].append(filename)

    # staged diff
    ok, out, _ = _run_git(["diff", "--cached", "--stat"], cwd)
    if ok:
        context["staged_diff"] = out

    # full diff (staged + unstaged)
    ok, out, _ = _run_git(["diff", "HEAD"], cwd)
    if ok:
        context["diff"] = out[:8000]  # 截断避免过长

    # 当前分支
    ok, out, _ = _run_git(["branch", "--show-current"], cwd)
    if ok:
        context["branch"] = out.strip()

    # 最近提交
    ok, out, _ = _run_git(["log", "--oneline", "-10"], cwd)
    if ok:
        context["recent_commits"] = out

    return context


def commit_handler(args: list, loop=None) -> str:
    """commit 命令处理函数"""
    cwd = "."

    # 检查是否在 git 仓库
    ok, _, _ = _run_git(["rev-parse", "--git-dir"], cwd)
    if not ok:
        return "❌ 当前目录不是 Git 仓库"

    lines = []
    lines.append("📦 Git Commit 助手")
    lines.append("=" * 60)

    # 1. 获取 Git 上下文
    ctx = _get_git_context(cwd)
    lines.append(f"🌿 分支: {ctx['branch'] or '(未知)'}")

    # 2. 检查是否有变更
    all_files = ctx["staged_files"] + ctx["unstaged_files"] + ctx["untracked_files"]
    if not all_files:
        lines.append("✅ 工作目录干净，没有需要提交的内容")
        return "\n".join(lines)

    # 3. 显示变更概览
    lines.append(f"\n📋 变更概览:")
    if ctx["staged_files"]:
        lines.append(f"   ✅ 已暂存: {len(ctx['staged_files'])} 个文件")
        for f in ctx["staged_files"][:5]:
            lines.append(f"      + {f}")
        if len(ctx["staged_files"]) > 5:
            lines.append(f"      ... 还有 {len(ctx['staged_files'])-5} 个")

    if ctx["unstaged_files"]:
        lines.append(f"   📝 未暂存: {len(ctx['unstaged_files'])} 个文件")
        for f in ctx["unstaged_files"][:5]:
            lines.append(f"      ~ {f}")

    if ctx["untracked_files"]:
        lines.append(f"   ❓ 新文件: {len(ctx['untracked_files'])} 个")
        for f in ctx["untracked_files"][:5]:
            lines.append(f"      ? {f}")

    # 4. 检查敏感文件
    secret_warnings = _check_secret_files(all_files)
    if secret_warnings:
        lines.append(f"\n⚠️  警告：以下文件可能包含秘密信息，建议不要提交：")
        for f in secret_warnings:
            lines.append(f"   - {f}")
        lines.append("   将跳过这些文件。")

    # 5. 如果没有 staged 文件，自动 stage 所有非秘密文件
    if not ctx["staged_files"]:
        files_to_stage = [
            f for f in ctx["unstaged_files"] + ctx["untracked_files"]
            if f not in secret_warnings
        ]
        if files_to_stage:
            ok, _, err = _run_git(["add"] + files_to_stage, cwd)
            if ok:
                lines.append(f"\n✅ 已自动暂存 {len(files_to_stage)} 个文件")
            else:
                lines.append(f"\n❌ 暂存文件失败: {err}")
                return "\n".join(lines)
        else:
            lines.append("\n没有可安全提交的文件")
            return "\n".join(lines)

    # 6. 使用 AI 生成 commit message
    if loop is None:
        lines.append("\n⚠️  AgentLoop 未初始化，使用默认 commit message")
        commit_msg = "chore: update files"
    else:
        lines.append("\n🤖 正在使用 AI 生成 commit message...")
        try:
            # 构建 AI 提示
            user_prompt = (
                f"当前分支: {ctx['branch']}\n\n"
                f"最近提交风格参考:\n{ctx['recent_commits']}\n\n"
                f"本次变更 diff:\n```\n{ctx['diff'][:4000]}\n```\n\n"
                f"请为这些变更生成一个 commit message。"
            )

            response = loop.client.chat.completions.create(
                model=loop.model,
                messages=[
                    {"role": "system", "content": COMMIT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=200
            )
            commit_msg = response.choices[0].message.content.strip()
            # 清理可能的代码块标记
            commit_msg = commit_msg.replace("```", "").strip()
            lines.append(f"💬 生成的 commit message:\n   {commit_msg}")

        except Exception as e:
            lines.append(f"⚠️  AI 生成失败 ({e})，使用默认 message")
            commit_msg = "chore: update files"

    # 7. 执行提交
    lines.append("\n📝 正在创建提交...")
    ok, out, err = _run_git(
        ["commit", "-m", commit_msg],
        cwd
    )

    if ok:
        lines.append(f"✅ 提交成功!")
        # 显示提交 hash
        ok2, hash_out, _ = _run_git(["log", "--oneline", "-1"], cwd)
        if ok2:
            lines.append(f"   {hash_out.strip()}")
    else:
        lines.append(f"❌ 提交失败: {err}")

    lines.append("=" * 60)
    return "\n".join(lines)


# 注册命令
register_command("commit", {
    "description": "AI 智能生成 Git 提交 - 分析变更并生成规范的 commit message",
    "handler": commit_handler,
    "category": "tools",
    "args_help": ""
})
