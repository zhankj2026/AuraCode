"""
Init 命令 - 初始化项目文档 OPENCODE.md

功能:
- 分析代码库结构、语言、框架
- 使用 AI 生成项目文档 OPENCODE.md
- 包含构建/测试/规范等关键信息
- 帮助 AI 快速理解项目上下文

用法:
  /init              分析并生成 OPENCODE.md
  /init --force      强制覆盖已有的 OPENCODE.md
"""

import os
import subprocess
from commands.registry import register_command


# 需要检查的关键文件
KEY_FILES = [
    # 包管理 / manifest
    "package.json", "Cargo.toml", "pyproject.toml", "setup.py",
    "go.mod", "pom.xml", "requirements.txt", "Pipfile",
    # 构建配置
    "Makefile", "CMakeLists.txt", "build.gradle", "build.gradle.kts",
    # CI/CD
    ".github/workflows/ci.yml", ".github/workflows/main.yml",
    ".gitlab-ci.yml", "Jenkinsfile",
    # 代码规范
    ".eslintrc", ".eslintrc.js", ".prettierrc", "ruff.toml",
    ".golangci.yml", "rustfmt.toml",
    # README
    "README.md", "README.rst",
    # 现有 AI 配置
    "CLAUDE.md", "OPENCODE.md", ".cursorrules",
    ".cursor/rules", ".github/copilot-instructions.md",
]

INIT_SYSTEM_PROMPT = """你是一个代码库文档专家。请分析以下项目信息，创建一份精炼的 OPENCODE.md 文件。

OPENCODE.md 是给 AI 编程助手（如 OpenCode、Claude Code）使用的项目指南，帮助 AI 快速理解项目。

规则:
1. 只包含 AI 不知道就无法正确工作的信息
2. 不要重复 README 中已有的明显内容
3. 不要列出每个文件，AI 可以自己探索
4. 重点包括：非标准命令、特殊约定、架构决策、测试技巧

输出格式（Markdown，仅输出文件内容）:
# OPENCODE.md

This file provides guidance to AI coding assistants when working with code in this repository.

## Build / Test Commands
（项目特有的构建、测试、lint 命令）

## Architecture
（高层架构，需要跨文件理解的"大图"）

## Code Style
（与语言默认规范不同的约定）

## Gotchas
（非明显的坑、环境变量、特殊配置）
"""


def _explore_project(cwd: str = ".") -> dict:
    """探索项目结构，收集关键信息"""
    info = {
        "files_found": [],
        "dir_structure": "",
        "languages": set(),
        "frameworks": set(),
        "has_git": False,
        "git_remote": "",
        "readme_content": "",
        "manifest_content": {},
        "existing_ai_config": {},
    }

    # 检查关键文件
    for f in KEY_FILES:
        path = os.path.join(cwd, f)
        if os.path.exists(path):
            info["files_found"].append(f)
            # 读取部分内容
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as fp:
                    content = fp.read(2000)
                    if f in ("README.md", "README.rst"):
                        info["readme_content"] = content
                    elif f in ("CLAUDE.md", "OPENCODE.md"):
                        info["existing_ai_config"][f] = content
                    elif f in ("package.json", "pyproject.toml", "Cargo.toml",
                               "go.mod", "requirements.txt"):
                        info["manifest_content"][f] = content
            except Exception:
                pass

    # 推断语言
    lang_extensions = {
        ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
        ".go": "Go", ".rs": "Rust", ".java": "Java",
        ".cpp": "C++", ".c": "C", ".rb": "Ruby",
        ".php": "PHP", ".kt": "Kotlin", ".swift": "Swift",
    }
    try:
        for root, dirs, files in os.walk(cwd):
            # 跳过隐藏目录和 node_modules
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "__pycache__", "target", "dist")]
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in lang_extensions:
                    info["languages"].add(lang_extensions[ext])
            if root.count(os.sep) - cwd.count(os.sep) > 2:
                break  # 限制深度
    except Exception:
        pass

    # 目录结构（前3层）
    try:
        result = subprocess.run(
            ["find" if os.name != "nt" else "dir", "/b", "/s"],
            capture_output=True, text=True, cwd=cwd, timeout=10
        )
        if result.returncode == 0:
            all_items = result.stdout.strip().splitlines()
            # 只显示前50个
            info["dir_structure"] = "\n".join(all_items[:50])
            if len(all_items) > 50:
                info["dir_structure"] += f"\n... (共 {len(all_items)} 项)"
    except Exception:
        # fallback：简单列出顶层
        try:
            items = os.listdir(cwd)
            info["dir_structure"] = "\n".join(items[:30])
        except Exception:
            pass

    # Git 信息
    try:
        result = subprocess.run(
            ["git", "remote", "-v"],
            capture_output=True, text=True, cwd=cwd, timeout=5
        )
        if result.returncode == 0:
            info["has_git"] = True
            info["git_remote"] = result.stdout.splitlines()[0] if result.stdout else ""
    except Exception:
        pass

    return info


def init_handler(args: list, loop=None) -> str:
    """init 命令处理函数"""
    lines = []
    lines.append("📝 初始化项目文档 (OPENCODE.md)")
    lines.append("=" * 60)

    force = "--force" in args
    cwd = "."

    # 检查是否已存在
    existing_files = []
    for f in ("OPENCODE.md", "CLAUDE.md"):
        if os.path.exists(os.path.join(cwd, f)):
            existing_files.append(f)

    if existing_files and not force:
        lines.append(f"ℹ️  已存在: {', '.join(existing_files)}")
        lines.append("   使用 /init --force 覆盖并重新生成")
        return "\n".join(lines)

    # 探索项目
    lines.append("🔍 正在分析项目结构...")
    info = _explore_project(cwd)

    lines.append(f"   检测到语言: {', '.join(info['languages']) or '未知'}")
    lines.append(f"   关键文件: {len(info['files_found'])} 个")
    if info["has_git"]:
        lines.append(f"   Git: ✅ ({info['git_remote'][:50]})")

    if loop is None:
        lines.append("\n⚠️  AgentLoop 未初始化，无法使用 AI 生成文档")
        lines.append("   将生成基础模板...")
        # 生成基础模板
        content = _generate_basic_template(info)
    else:
        lines.append("🤖 正在使用 AI 生成项目文档...")
        try:
            # 构建 AI 提示
            user_prompt = (
                f"项目信息：\n"
                f"- 检测到的语言: {', '.join(info['languages'])}\n"
                f"- 关键文件: {', '.join(info['files_found'])}\n"
                f"- 目录结构（部分）:\n{info['dir_structure'][:2000]}\n\n"
            )

            if info["readme_content"]:
                user_prompt += f"README.md 内容:\n{info['readme_content'][:2000]}\n\n"

            for fname, content in info["manifest_content"].items():
                user_prompt += f"{fname} 内容:\n{content[:1000]}\n\n"

            if info["existing_ai_config"]:
                for fname, content in info["existing_ai_config"].items():
                    user_prompt += f"现有 {fname} 内容（供参考改进）:\n{content[:1000]}\n\n"

            user_prompt += "请基于以上信息，创建一份精炼的 OPENCODE.md 文件。"

            response = loop.client.chat.completions.create(
                model=loop.model,
                messages=[
                    {"role": "system", "content": INIT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                max_tokens=2000
            )
            content = response.choices[0].message.content.strip()

        except Exception as e:
            lines.append(f"⚠️  AI 生成失败 ({e})，使用基础模板")
            content = _generate_basic_template(info)

    # 写入文件
    output_path = os.path.join(cwd, "OPENCODE.md")
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        lines.append(f"\n✅ 已生成: {output_path}")
        lines.append(f"   大小: {len(content)} 字符")
        lines.append("\n📄 内容预览:")
        lines.append("-" * 40)
        preview = content[:600]
        lines.append(preview)
        if len(content) > 600:
            lines.append("...")
        lines.append("-" * 40)
    except Exception as e:
        lines.append(f"\n❌ 写入文件失败: {e}")

    lines.append("=" * 60)
    return "\n".join(lines)


def _generate_basic_template(info: dict) -> str:
    """无 AI 时生成基础模板"""
    langs = ", ".join(info["languages"]) if info["languages"] else "未检测"
    return f"""# OPENCODE.md

This file provides guidance to AI coding assistants when working with code in this repository.

## Project Overview

- **Languages**: {langs}
- **Key files found**: {", ".join(info["files_found"][:10]) or "none detected"}

## Build / Test Commands

<!-- TODO: Add project-specific build and test commands -->
- Build: `make build` or equivalent
- Test: `make test` or equivalent
- Lint: `make lint` or equivalent

## Architecture

<!-- TODO: Describe the high-level architecture here -->

## Code Style

<!-- TODO: Add non-default style conventions here -->

## Gotchas

<!-- TODO: Add non-obvious notes here -->
"""


register_command("init", {
    "description": "初始化 OPENCODE.md 项目文档 - AI 分析代码库生成指南",
    "handler": init_handler,
    "category": "tools",
    "args_help": "[--force]"
})
