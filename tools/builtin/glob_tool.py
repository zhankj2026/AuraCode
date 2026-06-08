"""
Glob 工具 - 使用 Glob 模式快速查找文件

参考 Claude Code GlobTool 设计，支持标准 glob 模式，
结果按修改时间排序（最新优先）。
"""

import os
import fnmatch
from pathlib import Path
from typing import Optional, List
from tools.registry import register_tool


# 默认忽略的目录（提升搜索性能，避免扫描无用路径）
DEFAULT_IGNORE_DIRS = {
    '.git', '.hg', '.svn',
    'node_modules', '__pycache__', '.venv', 'venv', 'env',
    '.mypy_cache', '.pytest_cache', '.tox', '.nox',
    'dist', 'build', '.next', '.nuxt', '.cache',
    '.idea', '.vscode', '.vs',
    'site-packages', '.eggs', '.egg-info',
    'coverage', '.nyc_output',
}


def _walk_glob(
    root: Path,
    pattern: str,
    max_depth: int,
    max_results: int,
    ignore_dirs: set,
    include_dirs: bool,
) -> List[tuple]:
    """
    递归遍历目录，收集匹配 glob 模式的文件。

    Returns:
        [(mtime, path_str), ...] 元组列表
    """
    results = []
    parts = pattern.split('/')

    def _match(path: Path, depth: int, pat_parts: List[str]):
        if len(results) >= max_results:
            return
        if depth > max_depth:
            return

        if not pat_parts:
            # 模式已完全匹配
            try:
                mtime = path.stat().st_mtime
            except OSError:
                return
            results.append((mtime, str(path)))
            return

        head, *rest = pat_parts

        if head == '**':
            # ** 匹配任意层目录
            # 情况1：当前路径匹配 **，继续往下匹配 rest
            _match(path, depth, rest)
            # 情况2：** 向下遍历一层
            if depth < max_depth:
                try:
                    for entry in sorted(path.iterdir()):
                        if entry.name.startswith('.') and entry.name in ignore_dirs:
                            continue
                        if entry.name in ignore_dirs:
                            continue
                        if entry.is_dir() and not entry.is_symlink():
                            _match(entry, depth + 1, pat_parts)  # 保持 ** 模式
                        elif not rest:
                            # ** 是最后一段，匹配文件
                            _match(entry, depth + 1, [])
                except PermissionError:
                    pass
        else:
            # 普通模式段（含 * ? [] 等）
            try:
                for entry in sorted(path.iterdir()):
                    if not fnmatch.fnmatch(entry.name, head):
                        continue
                    if entry.name in ignore_dirs and entry.is_dir() and not entry.is_symlink():
                        continue
                    if rest:
                        if entry.is_dir() and not entry.is_symlink():
                            _match(entry, depth + 1, rest)
                    else:
                        if include_dirs or entry.is_file():
                            _match(entry, depth + 1, [])
            except PermissionError:
                pass

    _match(root, 0, parts)
    return results


def glob_handler(
    pattern: str,
    path: str = ".",
    max_depth: int = 10,
    max_results: int = 200,
    include_dirs: bool = False,
) -> str:
    """
    使用 Glob 模式查找文件

    支持标准 glob 模式，结果按修改时间排序（最新文件优先）。

    常用模式示例：
    - "**/*.py"          所有 Python 文件
    - "src/**/*.ts"      src 目录下所有 TypeScript 文件
    - "tests/**/test_*.py"  测试文件
    - "**/config.json"   任意层级的 config.json
    - "*.md"             当前目录 Markdown 文件

    Args:
        pattern: Glob 模式（支持 ** * ? []）
        path: 搜索起始路径
        max_depth: 最大搜索深度
        max_results: 最大返回数量
        include_dirs: 是否包含目录（默认只返回文件）

    Returns:
        匹配文件列表（按修改时间降序）
    """
    try:
        root = Path(path).resolve()
        if not root.exists():
            return f"错误: 路径不存在: {path}"
        if not root.is_dir():
            return f"错误: 路径不是目录: {path}"

        if not pattern:
            return "错误: pattern 不能为空"

        # 如果 pattern 是绝对路径，提取根目录
        if os.path.isabs(pattern):
            # 找到第一个含通配符的路径段之前的部分作为根
            p = Path(pattern)
            parts = p.parts
            root_parts = []
            glob_parts = []
            found_glob = False
            for part in parts:
                if not found_glob and not any(c in part for c in '*?[]'):
                    root_parts.append(part)
                else:
                    found_glob = True
                    glob_parts.append(part)
            if root_parts:
                root = Path(*root_parts)
            pattern = '/'.join(glob_parts)

        matches = _walk_glob(
            root=root,
            pattern=pattern.replace('\\', '/'),
            max_depth=max_depth,
            max_results=max_results,
            ignore_dirs=DEFAULT_IGNORE_DIRS,
            include_dirs=include_dirs,
        )

        if not matches:
            return f"未找到匹配 '{pattern}' 的文件（搜索路径: {root}）"

        # 按修改时间降序排列（最新优先）
        matches.sort(key=lambda x: x[0], reverse=True)

        lines = []
        total = len(matches)
        for mtime, fpath in matches[:max_results]:
            lines.append(fpath)

        result = f"找到 {total} 个匹配文件:\n\n" + "\n".join(lines)

        if total > max_results:
            result += f"\n\n... (还有 {total - max_results} 个未显示)"

        return result

    except Exception as e:
        return f"错误: {str(e)}"


register_tool("glob", {
    "description": (
        "快速文件模式匹配工具，支持任意代码库规模。\n"
        "支持 glob 模式如 '**/*.py' 或 'src/**/*.ts'。\n"
        "返回结果按修改时间排序（最新优先）。\n"
        "适用于需要按文件名模式查找文件的场景。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": (
                    "Glob 模式，如 '**/*.py', 'src/**/*.ts', '*.json'。"
                    "支持 ** (任意层目录), * (通配), ? (单字符), [] (字符集)。"
                )
            },
            "path": {
                "type": "string",
                "description": "搜索起始路径（默认为当前目录）",
                "default": "."
            },
            "max_depth": {
                "type": "integer",
                "description": "最大搜索深度",
                "default": 10
            },
            "max_results": {
                "type": "integer",
                "description": "最大返回结果数",
                "default": 200
            },
            "include_dirs": {
                "type": "boolean",
                "description": "是否包含目录（默认只返回文件）",
                "default": False
            }
        },
        "required": ["pattern"]
    },
    "handler": glob_handler,
    "permission_level": "read"
})
