"""
lint 工具 - 运行静态检查

基于 code.md Phase 3 实现
参考: 第 5.1 节
"""

import os
import subprocess
from tools.registry import register_tool


def _detect_language(path: str) -> str:
    """
    自动检测编程语言
    
    Args:
        path: 文件路径或目录路径
    
    Returns:
        语言类型: python/javascript/typescript/unknown
    """
    if path and os.path.isfile(path):
        ext = os.path.splitext(path)[1].lower()
        lang_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.jsx': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
        }
        return lang_map.get(ext, 'unknown')
    
    # 目录:检查是否存在特定配置文件
    if path and os.path.isdir(path):
        if os.path.exists(os.path.join(path, 'package.json')):
            # 检查是否有 TypeScript
            ts_files = [f for f in os.listdir(path) if f.endswith(('.ts', '.tsx'))]
            if ts_files:
                return 'typescript'
            return 'javascript'
        
        # 检查 Python 项目
        py_files = [f for f in os.listdir(path) if f.endswith('.py')]
        if py_files or os.path.exists(os.path.join(path, 'requirements.txt')):
            return 'python'
    
    return 'python'  # 默认 Python


def lint_handler(
    path: str = None,
    language: str = None,
    fix: bool = False
) -> str:
    """
    运行静态检查
    
    Args:
        path: 要检查的文件或目录路径,默认为当前目录
        language: 编程语言(python/javascript/typescript),默认自动检测
        fix: 是否自动修复可修复的问题
    
    Returns:
        检查结果
    """
    try:
        # 默认路径
        if not path:
            path = '.'
        
        # 自动检测语言
        if not language:
            language = _detect_language(path)
        
        # 构建命令
        if language == 'python':
            cmd = ['ruff', 'check']
            if fix:
                cmd.append('--fix')
            cmd.append(path)
            
        elif language == 'javascript':
            cmd = ['npx', 'eslint']
            if fix:
                cmd.append('--fix')
            cmd.append(path)
            
        elif language == 'typescript':
            cmd = ['npx', 'eslint', '--ext', '.ts,.tsx']
            if fix:
                cmd.append('--fix')
            cmd.append(path)
            
        else:
            return f"❌ 不支持的语言: {language}\n\n支持的语言: python, javascript, typescript"
        
        # 执行检查
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=os.getcwd()
        )
        
        output = result.stdout or result.stderr
        
        # 分析结果
        if result.returncode == 0:
            if not output or output.strip() == '':
                return f"✅ 静态检查通过\n\n语言: {language}\n路径: {path}\n\n无问题"
            else:
                return f"✅ 静态检查通过\n\n语言: {language}\n路径: {path}\n\n{output}"
        else:
            # 有问题
            lines = output.splitlines()
            
            # 限制输出
            if len(lines) > 200:
                output = '\n'.join(lines[:200])
                output += f'\n\n... (共 {len(lines)} 行,显示前 200 行)'
            
            return f"❌ 发现问题\n\n语言: {language}\n路径: {path}\n\n{output}"
    
    except subprocess.TimeoutExpired:
        return f"❌ 静态检查超时(60秒)\n\n路径: {path or '.'}"
    
    except FileNotFoundError as e:
        # 工具未安装
        tool_name = 'ruff' if language == 'python' else 'eslint'
        return f"❌ 未找到 {tool_name} 工具\n\n请先安装:\n- Python: pip install ruff\n- JavaScript/TypeScript: npm install -g eslint"
    
    except Exception as e:
        return f"❌ 静态检查失败\n\n错误: {str(e)}"


# 注册工具
register_tool("lint", {
    "description": "运行静态代码检查(ruff/eslint),支持自动修复",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "要检查的文件或目录路径",
                "default": "."
            },
            "language": {
                "type": "string",
                "description": "编程语言(python/javascript/typescript),默认自动检测",
                "enum": ["python", "javascript", "typescript"]
            },
            "fix": {
                "type": "boolean",
                "description": "是否自动修复可修复的问题",
                "default": False
            }
        },
        "required": []
    },
    "handler": lint_handler,
    "permission_level": "read"
})
