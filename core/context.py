"""
上下文加载器

负责加载 CLAUDE.md 文件、检测技术栈和项目结构,
为 Agent Loop 提供项目相关的上下文信息。
"""

import os
import glob
from typing import Optional, List


def load_project_context(project_root: str = ".") -> str:
    """
    加载项目上下文(CLAUDE.md + 技术栈检测)
    
    Args:
        project_root: 项目根目录路径
        
    Returns:
        格式化的上下文字符串,如果无上下文则返回空字符串
    """
    context_parts = []
    
    # 1. 加载 CLAUDE.md
    claude_md_content = load_claude_md(project_root)
    if claude_md_content:
        context_parts.append(f"## 项目约定\n\n{claude_md_content}")
    
    # 2. 检测技术栈
    tech_stack = detect_tech_stack(project_root)
    if tech_stack:
        context_parts.append(f"## 技术栈\n\n{tech_stack}")
    
    # 3. 检测项目结构
    project_structure = detect_project_structure(project_root)
    if project_structure:
        context_parts.append(f"## 项目结构\n\n{project_structure}")
    
    # 合并所有部分
    if context_parts:
        return "\n\n".join(context_parts)
    
    return ""


def load_claude_md(project_root: str) -> Optional[str]:
    """
    加载 CLAUDE.md 文件
    
    搜索路径:
    1. {project_root}/.claude/CLAUDE.md
    2. {project_root}/CLAUDE.md (备选)
    
    Args:
        project_root: 项目根目录
        
    Returns:
        文件内容,如果不存在则返回 None
    """
    # 优先搜索 .claude/ 目录
    claude_dir_path = os.path.join(project_root, ".claude", "CLAUDE.md")
    if os.path.exists(claude_dir_path):
        try:
            with open(claude_dir_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    return content
        except Exception as e:
            print(f"⚠️  读取 CLAUDE.md 失败: {e}")
    
    # 备选: 根目录下的 CLAUDE.md
    root_path = os.path.join(project_root, "CLAUDE.md")
    if os.path.exists(root_path):
        try:
            with open(root_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    return content
        except Exception as e:
            print(f"⚠️  读取 CLAUDE.md 失败: {e}")
    
    return None


def detect_tech_stack(project_root: str) -> Optional[str]:
    """
    自动检测项目技术栈
    
    通过检测标志性文件判断项目类型:
    - requirements.txt / setup.py → Python
    - package.json → Node.js/JavaScript
    - go.mod → Go
    - pom.xml / build.gradle → Java
    - Cargo.toml → Rust
    - Gemfile → Ruby
    - composer.json → PHP
    
    Args:
        project_root: 项目根目录
        
    Returns:
        技术栈描述字符串,如果无法检测则返回 None
    """
    indicators = {
        # Python
        "requirements.txt": "Python 项目 (使用 pip 管理依赖)",
        "setup.py": "Python 项目 (使用 setuptools)",
        "pyproject.toml": "Python 项目 (使用 Poetry 或 PEP 517)",
        "Pipfile": "Python 项目 (使用 Pipenv)",
        
        # JavaScript/TypeScript
        "package.json": "Node.js/JavaScript 项目",
        "tsconfig.json": "TypeScript 项目",
        "next.config.js": "Next.js 项目",
        "nuxt.config.js": "Nuxt.js 项目",
        
        # Go
        "go.mod": "Go 项目",
        
        # Java
        "pom.xml": "Java/Maven 项目",
        "build.gradle": "Java/Gradle 项目",
        
        # Rust
        "Cargo.toml": "Rust 项目",
        
        # Ruby
        "Gemfile": "Ruby 项目",
        
        # PHP
        "composer.json": "PHP 项目",
        
        # .NET
        "*.csproj": ".NET/C# 项目",
        
        # Docker
        "Dockerfile": "使用 Docker 容器化",
        "docker-compose.yml": "使用 Docker Compose",
    }
    
    detected = []
    
    for filename, description in indicators.items():
        # 处理通配符
        if "*" in filename:
            pattern = os.path.join(project_root, filename)
            if glob.glob(pattern):
                detected.append(f"- {description}")
        else:
            filepath = os.path.join(project_root, filename)
            if os.path.exists(filepath):
                detected.append(f"- {description}")
    
    return "\n".join(detected) if detected else None


def detect_project_structure(project_root: str) -> Optional[str]:
    """
    检测项目结构(顶层目录)
    
    Args:
        project_root: 项目根目录
        
    Returns:
        项目结构描述
    """
    try:
        items = os.listdir(project_root)
        
        # 过滤隐藏文件和常见忽略项
        ignore_prefixes = [".", "__", "node_modules", "venv", ".git"]
        visible_items = [
            item for item in items 
            if not any(item.startswith(p) for p in ignore_prefixes)
        ]
        
        # 分类
        dirs = []
        files = []
        
        for item in visible_items:
            full_path = os.path.join(project_root, item)
            if os.path.isdir(full_path):
                dirs.append(item + "/")
            else:
                files.append(item)
        
        # 只显示重要的目录和文件
        important_dirs = [d for d in dirs if d in [
            "src/", "lib/", "app/", "tests/", "docs/", 
            "config/", "scripts/", "tools/"
        ]]
        
        important_files = [f for f in files if f in [
            "README.md", "LICENSE", "Makefile", "CHANGELOG.md"
        ]]
        
        output_parts = []
        
        if important_dirs:
            output_parts.append("主要目录:")
            for d in sorted(important_dirs):
                output_parts.append(f"  - {d}")
        
        if important_files:
            output_parts.append("\n重要文件:")
            for f in sorted(important_files):
                output_parts.append(f"  - {f}")
        
        return "\n".join(output_parts) if output_parts else None
    
    except Exception:
        return None
