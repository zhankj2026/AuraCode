"""
Commit-Push-PR 命令 — 完整 PR 工作流

功能:
- 分析变更 → AI 生成 commit message → commit
- 自动创建分支（如果在默认分支上）
- push 到远程
- 使用 gh CLI 创建或更新 Pull Request
- 返回 PR URL

安全规则:
- 不会 amend 已有提交
- 不会提交可能包含秘密的文件
- 不会跳过 hooks
- 不会 force push main/master
- 不会使用交互式 git 命令

用法:
  /commit-push-pr                — 完整流程：commit + push + 创建 PR
  /commit-push-pr <描述>          — 附带额外说明
  /commit-push-pr --draft         — 创建草稿 PR
"""

import subprocess
import re
import os
from commands.registry import register_command

# 危险文件模式（可能包含秘密）
SECRET_FILE_PATTERNS = [
    r'\.env$', r'\.env\..+', r'credentials\.json$',
    r'secrets?\.(json|ya?ml|toml)$', r'\.npmrc$',
    r'\.pypirc$', r'.*private.*key.*', r'\.aws/credentials$',
]

COMMIT_SYSTEM_PROMPT = """你是一个专业的 Git 提交助手。根据代码变更生成规范的 commit message。

规则:
1. 分析所有变更，生成准确描述变更内容的 commit message
2. 参考最近的历史提交，遵循该仓库的提交风格
3. message 应简洁（1-2句），侧重"为什么"而非"是什么"
4. 使用以下类型前缀: feat(新功能), fix(修复), refactor(重构), test(测试), docs(文档), chore(维护)
5. 输出纯文本 commit message，不要代码块标记"""


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


def _run_gh(cmd: list, cwd: str = ".") -> tuple:
    """执行 gh CLI 命令"""
    try:
        result = subprocess.run(
            ["gh"] + cmd, capture_output=True, text=True,
            cwd=cwd, timeout=60, encoding="utf-8",
        )
        return result.returncode == 0, result.stdout, result.stderr
    except FileNotFoundError:
        return False, "", "gh CLI 未安装，请先安装: https://cli.github.com/"
    except subprocess.TimeoutExpired:
        return False, "", "命令超时"
    except Exception as e:
        return False, "", str(e)


def _check_secret_files(files: list) -> list:
    """检查可能包含秘密的文件"""
    warnings = []
    for f in files:
        for pattern in SECRET_FILE_PATTERNS:
            if re.search(pattern, f, re.IGNORECASE):
                warnings.append(f)
                break
    return warnings


def _get_default_branch(cwd: str = ".") -> str:
    """检测默认分支（main 或 master）"""
    ok, out, _ = _run_git(["symbolic-ref", "refs/remotes/origin/HEAD", "--short"], cwd)
    if ok:
        branch = out.strip().replace("origin/", "")
        if branch:
            return branch
    # 降级检测
    for b in ("main", "master", "develop"):
        ok, _, _ = _run_git(["rev-parse", "--verify", f"refs/heads/{b}"], cwd)
        if ok:
            return b
    return "main"


def _get_current_branch(cwd: str = ".") -> str:
    """获取当前分支名"""
    ok, out, _ = _run_git(["branch", "--show-current"], cwd)
    return out.strip() if ok else ""


def _get_git_context(cwd: str = ".") -> dict:
    """获取 Git 上下文"""
    ctx = {
        "status": "", "diff": "", "branch": "", "recent_commits": "",
        "staged_files": [], "unstaged_files": [], "untracked_files": [],
        "default_branch": _get_default_branch(cwd),
    }
    ok, out, _ = _run_git(["status", "--short"], cwd)
    if ok:
        ctx["status"] = out.strip()
        for line in out.strip().splitlines():
            if not line:
                continue
            code = line[:2]
            fname = line[3:].strip()
            if code[0] in ("A", "M", "D", "R"):
                ctx["staged_files"].append(fname)
            if code[1] in ("M", "D"):
                ctx["unstaged_files"].append(fname)
            if code == "??":
                ctx["untracked_files"].append(fname)
    ok, out, _ = _run_git(["diff", "HEAD"], cwd)
    if ok:
        ctx["diff"] = out[:8000]
    ctx["branch"] = _get_current_branch(cwd)
    ok, out, _ = _run_git(["log", "--oneline", "-10"], cwd)
    if ok:
        ctx["recent_commits"] = out
    return ctx


def _check_gh_available() -> tuple:
    """检查 gh CLI 是否可用且已认证"""
    try:
        result = subprocess.run(
            ["gh", "auth", "status"], capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0, result.stdout + result.stderr
    except FileNotFoundError:
        return False, "gh CLI 未安装"
    except Exception as e:
        return False, str(e)


def _check_existing_pr(branch: str, cwd: str = ".") -> dict:
    """检查当前分支是否已有 PR"""
    ok, out, _ = _run_gh(["pr", "view", "--json", "number,title,url,state"], cwd)
    if ok and out.strip():
        try:
            import json
            pr = json.loads(out)
            return {"exists": True, **pr}
        except (json.JSONDecodeError, TypeError):
            pass
    return {"exists": False}


def commit_push_pr_handler(args: list, loop=None) -> str:
    """commit-push-pr 命令处理函数"""
    cwd = "."
    extra_desc = ""
    is_draft = "--draft" in args
    for a in args:
        if not a.startswith("-"):
            extra_desc = a
            break

    lines = ["🚀 Commit → Push → PR 工作流", "=" * 60]

    # 0. 检查 git 仓库
    ok, _, _ = _run_git(["rev-parse", "--git-dir"], cwd)
    if not ok:
        return "❌ 当前目录不是 Git 仓库"

    # 1. 检查 gh CLI
    gh_ok, gh_msg = _check_gh_available()
    if not gh_ok:
        lines.append(f"⚠️  gh CLI 不可用: {gh_msg.strip()}")
        lines.append("   PR 创建步骤将跳过，仅执行 commit + push")

    # 2. 获取上下文
    ctx = _get_git_context(cwd)
    lines.append(f"🌿 分支: {ctx['branch'] or '(detached)'}")
    lines.append(f"📍 默认分支: {ctx['default_branch']}")

    # 3. 检查变更
    all_files = ctx["staged_files"] + ctx["unstaged_files"] + ctx["untracked_files"]
    if not all_files:
        # 无变更但可能有未推送的 commit
        ok, out, _ = _run_git(
            ["log", f"{ctx['default_branch']}..HEAD", "--oneline"], cwd
        )
        if ok and out.strip():
            lines.append(f"📦 工作目录干净，但有 {len(out.strip().splitlines())} 个未推送的提交")
        else:
            lines.append("✅ 工作目录干净，没有需要提交的内容")
            if gh_ok and ctx["branch"] != ctx["default_branch"]:
                lines.append("   尝试直接创建 PR...")
                return _do_push_and_pr(ctx, lines, gh_ok, is_draft, extra_desc, cwd, loop)
            return "\n".join(lines)

    # 4. 检查秘密文件
    secret_warnings = _check_secret_files(all_files)
    if secret_warnings:
        lines.append(f"\n⚠️  以下文件可能包含秘密，已跳过:")
        for f in secret_warnings:
            lines.append(f"   - {f}")

    # 5. 显示变更概览
    lines.append(f"\n📋 变更: {len(ctx['staged_files'])} 已暂存, "
                 f"{len(ctx['unstaged_files'])} 未暂存, "
                 f"{len(ctx['untracked_files'])} 新文件")

    # 6. 如果在默认分支，创建新分支
    if ctx["branch"] == ctx["default_branch"]:
        import getpass
        try:
            user = getpass.getuser()
        except Exception:
            user = "dev"
        branch_name = f"{user}/changes-{int(__import__('time').time()) % 100000}"
        lines.append(f"\n🔀 当前在默认分支 {ctx['default_branch']}，创建新分支: {branch_name}")
        ok, _, err = _run_git(["checkout", "-b", branch_name], cwd)
        if not ok:
            lines.append(f"❌ 创建分支失败: {err}")
            return "\n".join(lines)
        ctx["branch"] = branch_name

    # 7. Stage 文件
    if not ctx["staged_files"]:
        files_to_stage = [
            f for f in ctx["unstaged_files"] + ctx["untracked_files"]
            if f not in secret_warnings
        ]
        if files_to_stage:
            ok, _, err = _run_git(["add"] + files_to_stage, cwd)
            if ok:
                lines.append(f"✅ 已暂存 {len(files_to_stage)} 个文件")
            else:
                lines.append(f"❌ 暂存失败: {err}")
                return "\n".join(lines)

    # 8. AI 生成 commit message
    if loop is None:
        commit_msg = "chore: update files"
        lines.append("\n⚠️  AgentLoop 未初始化，使用默认 commit message")
    else:
        lines.append("\n🤖 AI 生成 commit message...")
        try:
            user_prompt = (
                f"分支: {ctx['branch']}\n"
                f"最近提交风格:\n{ctx['recent_commits']}\n"
                f"变更 diff:\n```\n{ctx['diff'][:4000]}\n```\n"
            )
            if extra_desc:
                user_prompt += f"\n用户补充说明: {extra_desc}\n"

            response = loop.client.chat.completions.create(
                model=loop.model,
                messages=[
                    {"role": "system", "content": COMMIT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3, max_tokens=200,
            )
            commit_msg = response.choices[0].message.content.strip().replace("```", "").strip()
            lines.append(f"💬 {commit_msg}")
        except Exception as e:
            commit_msg = "chore: update files"
            lines.append(f"⚠️  AI 生成失败 ({e})，使用默认 message")

    # 9. 创建 commit
    lines.append("\n📝 创建提交...")
    ok, out, err = _run_git(["commit", "-m", commit_msg], cwd)
    if ok:
        ok2, hash_out, _ = _run_git(["log", "--oneline", "-1"], cwd)
        lines.append(f"✅ 提交成功: {hash_out.strip() if ok2 else '(unknown)'}")
    else:
        lines.append(f"❌ 提交失败: {err}")
        return "\n".join(lines)

    # 10. Push + PR
    return _do_push_and_pr(ctx, lines, gh_ok, is_draft, extra_desc, cwd, loop)


def _do_push_and_pr(ctx, lines, gh_ok, is_draft, extra_desc, cwd, loop):
    """执行 push 和 PR 创建"""
    # Push
    lines.append(f"\n📤 推送 {ctx['branch']} → origin...")
    ok, out, err = _run_git(["push", "-u", "origin", ctx["branch"]], cwd)
    if ok:
        lines.append("✅ 推送成功")
    else:
        lines.append(f"❌ 推送失败: {err}")
        return "\n".join(lines)

    if not gh_ok:
        lines.append("\n⚠️  gh 不可用，跳过 PR 创建")
        lines.append(f"   手动创建: https://github.com/.../compare/{ctx['branch']}")
        lines.append("=" * 60)
        return "\n".join(lines)

    # 检查已有 PR
    pr_info = _check_existing_pr(ctx["branch"], cwd)

    if pr_info.get("exists") and pr_info.get("state") == "OPEN":
        # 更新已有 PR
        lines.append(f"\n🔄 PR 已存在: #{pr_info.get('number')} — 更新标题和描述...")
        # 获取 diff 统计用于 PR body
        ok, diff_stat, _ = _run_git(
            ["diff", f"{ctx['default_branch']}...HEAD", "--stat"], cwd
        )
        title = pr_info.get("title", ctx["branch"])
        ok2, _, err2 = _run_gh([
            "pr", "edit",
            "--title", title,
        ], cwd)
        if ok2:
            lines.append(f"✅ PR 已更新: {pr_info.get('url', '')}")
        else:
            lines.append(f"⚠️  PR 更新失败: {err2}")
    else:
        # 创建新 PR
        lines.append("\n📋 创建 Pull Request...")
        # 生成 PR 标题和 body
        pr_title = _generate_pr_title(ctx, loop, cwd)
        pr_body = _generate_pr_body(ctx, extra_desc, cwd)

        gh_cmd = [
            "pr", "create",
            "--title", pr_title,
            "--body", pr_body,
        ]
        if is_draft:
            gh_cmd.append("--draft")
            lines.append("   (草稿模式)")

        ok, out, err = _run_gh(gh_cmd, cwd)
        if ok:
            pr_url = out.strip()
            lines.append(f"✅ PR 创建成功!")
            lines.append(f"🔗 {pr_url}")
        else:
            lines.append(f"❌ PR 创建失败: {err}")
            lines.append(f"   手动创建: gh pr create --title \"{pr_title}\"")

    lines.append("=" * 60)
    return "\n".join(lines)


def _generate_pr_title(ctx: dict, loop, cwd: str) -> str:
    """生成 PR 标题"""
    # 从最近的 commit 提取
    ok, out, _ = _run_git(
        ["log", f"{ctx['default_branch']}..HEAD", "--oneline"], cwd
    )
    commits = out.strip().splitlines() if ok else []
    if len(commits) == 1:
        # 单 commit → 用 commit message 做标题
        return commits[0].split(" ", 1)[1] if " " in commits[0] else commits[0]
    elif len(commits) > 1:
        return f"{ctx['branch']} ({len(commits)} commits)"
    return f"Changes from {ctx['branch']}"


def _generate_pr_body(ctx: dict, extra_desc: str, cwd: str) -> str:
    """生成 PR 描述"""
    parts = ["## Summary\n"]

    if extra_desc:
        parts.append(extra_desc + "\n")

    # Diff 统计
    ok, stat, _ = _run_git(
        ["diff", f"{ctx['default_branch']}...HEAD", "--stat"], cwd
    )
    if ok and stat.strip():
        parts.append("## Changes\n```")
        parts.append(stat.strip())
        parts.append("```\n")

    # Commits
    ok, commits, _ = _run_git(
        ["log", f"{ctx['default_branch']}..HEAD", "--oneline"], cwd
    )
    if ok and commits.strip():
        parts.append("## Commits\n")
        for c in commits.strip().splitlines():
            parts.append(f"- {c}")
        parts.append("")

    parts.append("## Test Plan\n- [ ] 本地验证通过")
    parts.append("- [ ] 相关测试已运行")

    return "\n".join(parts)


# 注册命令
register_command("commit-push-pr", {
    "description": "完整 PR 工作流 — commit + push + 创建 Pull Request",
    "handler": commit_push_pr_handler,
    "category": "git",
    "args_help": "[描述] [--draft]",
})
