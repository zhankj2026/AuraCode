"""
上下文加载器

负责加载 AURACODE.md 文件、检测技术栈和项目结构,
为 Agent Loop 提供项目相关的上下文信息。
"""

import os
import glob
from typing import Optional, List


def load_project_context(project_root: str = ".") -> str:
    """
    加载项目上下文(AURACODE.md + 技术栈检测)
    
    Args:
        project_root: 项目根目录路径
        
    Returns:
        格式化的上下文字符串,如果无上下文则返回空字符串
    """
    context_parts = []
    
    # 1. 加载 AURACODE.md
    AURACODE_md_content = load_AURACODE_md(project_root)
    if AURACODE_md_content:
        context_parts.append(f"## 项目约定\n\n{AURACODE_md_content}")
    
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


def load_AURACODE_md(project_root: str) -> Optional[str]:
    """
    加载 AURACODE.md 文件
    
    搜索路径:
    1. {project_root}/.auracode/AURACODE.md
    2. {project_root}/AURACODE.md (备选)
    
    Args:
        project_root: 项目根目录
        
    Returns:
        文件内容,如果不存在则返回 None
    """
    # 优先搜索 .auracode/ 目录
    AURACODE_dir_path = os.path.join(project_root, ".auracode", "AURACODE.md")
    if os.path.exists(AURACODE_dir_path):
        try:
            with open(AURACODE_dir_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    return content
        except Exception as e:
            print(f"⚠️  读取 AURACODE.md 失败: {e}")
    
    # 备选: 根目录下的 AURACODE.md
    root_path = os.path.join(project_root, "AURACODE.md")
    if os.path.exists(root_path):
        try:
            with open(root_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    return content
        except Exception as e:
            print(f"⚠️  读取 AURACODE.md 失败: {e}")
    
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


def detect_project_structure(
    project_root: str,
    max_depth: int = 2,
    max_items_per_level: int = 20
) -> Optional[str]:
    """
    检测项目结构（递归显示目录树）

    Args:
        project_root: 项目根目录
        max_depth: 最大递归深度（默认 2 层）
        max_items_per_level: 每层最多显示的文件数（默认 20）

    Returns:
        项目结构描述（树形结构）
    """
    def _should_ignore(name: str) -> bool:
        """判断是否应该忽略该文件/目录"""
        ignore_patterns = [
            # 版本控制
            ".git", ".svn", ".hg",
            # 依赖目录
            "node_modules", "__pycache__", "venv", ".venv", "env",
            "dist", "build", "target", "bin", "obj",
            # IDE
            ".idea", ".vscode", ".eclipse",
            # 临时文件
            "*.pyc", "*.pyo", ".DS_Store", "Thumbs.db",
            # 其他
            ".cache", ".pytest_cache", ".coverage",
        ]
        # 检查是否匹配忽略模式
        for pattern in ignore_patterns:
            if pattern.startswith("*"):
                # 通配符匹配
                if name.endswith(pattern[1:]):
                    return True
            elif name == pattern:
                return True
        return False

    def _scan_directory(
        path: str,
        prefix: str = "",
        depth: int = 0
    ) -> List[str]:
        """
        递归扫描目录

        Args:
            path: 当前目录路径
            prefix: 树形前缀
            depth: 当前深度

        Returns:
            目录树行列表
        """
        if depth > max_depth:
            return []

        try:
            items = os.listdir(path)
        except (PermissionError, OSError):
            return []

        # 过滤和排序
        dirs = []
        files = []

        for item in items:
            if _should_ignore(item):
                continue

            full_path = os.path.join(path, item)
            if os.path.isdir(full_path):
                dirs.append(item)
            else:
                files.append(item)

        # 限制数量
        dirs = sorted(dirs)[:max_items_per_level]
        files = sorted(files)[:max_items_per_level]

        lines = []

        # 添加目录
        for i, dir_name in enumerate(dirs):
            is_last = (i == len(dirs) - 1) and not files
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{dir_name}/")

            # 递归子目录
            child_prefix = prefix + ("    " if is_last else "│   ")
            child_path = os.path.join(path, dir_name)
            lines.extend(_scan_directory(child_path, child_prefix, depth + 1))

        # 添加文件
        for i, file_name in enumerate(files):
            is_last = i == len(files) - 1
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{file_name}")

        return lines

    try:
        # 生成目录树
        tree_lines = _scan_directory(project_root)

        if not tree_lines:
            return None

        # 组装输出
        output = [f"项目结构 ({project_root}):", ""]
        output.append(f".")
        output.extend(tree_lines)

        # 添加省略提示
        total_items = len(os.listdir(project_root))
        visible_items = len([i for i in os.listdir(project_root) if not _should_ignore(i)])
        if visible_items > max_items_per_level:
            output.append(f"...")
            output.append(f"(仅显示前 {max_items_per_level} 项，部分项已省略)")

        return "\n".join(output)

    except Exception as e:
        return None
