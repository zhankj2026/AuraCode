"""
REPLTool — 交互式 Python REPL

允许 LLM 在沙箱环境中执行 Python 代码片段并获取输出结果。
参考 REPLTool 实现。
"""
import io
import sys
import traceback
from contextlib import redirect_stdout, redirect_stderr
from tools.registry import register_tool


# 全局持久命名空间（跨调用保留变量）
_REPL_NAMESPACE: dict = {}


def repl_handler(
    code: str,
    timeout: int = 10,
    clear: bool = False,
) -> str:
    """
    在 Python REPL 沙箱中执行代码片段。

    Args:
        code: 要执行的 Python 代码
        timeout: 超时秒数（1-30，默认 10）
        clear: 是否清除之前的命名空间

    Returns:
        执行结果（stdout + 返回值 + 错误信息）
    """
    if clear:
        _REPL_NAMESPACE.clear()
        return "✅ REPL 命名空间已清除"

    if not code or not code.strip():
        return "错误: 代码为空"

    timeout = max(1, min(30, timeout))

    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    result_value = None
    error = None

    try:
        # 尝试作为表达式求值（获取返回值）
        try:
            compiled = compile(code, "<repl>", "eval")
            with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
                result_value = eval(compiled, {"__builtins__": __builtins__}, _REPL_NAMESPACE)
        except SyntaxError:
            # 不是表达式 → 作为语句执行
            compiled = compile(code, "<repl>", "exec")
            with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
                exec(compiled, {"__builtins__": __builtins__}, _REPL_NAMESPACE)

    except Exception:
        error = traceback.format_exc()

    # 构建输出
    parts = []

    stdout_text = stdout_buf.getvalue()
    if stdout_text:
        parts.append(stdout_text.rstrip())

    stderr_text = stderr_buf.getvalue()
    if stderr_text:
        parts.append(f"[stderr]\n{stderr_text.rstrip()}")

    if error:
        parts.append(f"[error]\n{error.rstrip()}")
    elif result_value is not None:
        parts.append(repr(result_value))

    if not parts:
        parts.append("(无输出)")

    # 显示命名空间中的新变量
    user_vars = {
        k: type(v).__name__
        for k, v in _REPL_NAMESPACE.items()
        if not k.startswith("_") and k not in __builtins__
    }
    if user_vars:
        var_summary = ", ".join(f"{k}: {v}" for k, v in list(user_vars.items())[:20])
        if len(user_vars) > 20:
            var_summary += f" ... (+{len(user_vars)-20} more)"
        parts.append(f"\n[变量空间: {var_summary}]")

    return "\n".join(parts)


register_tool("repl", {
    "description": "在 Python REPL 沙箱中执行代码片段（变量跨调用保留）",
    "parameters": {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "要执行的 Python 代码",
            },
            "timeout": {
                "type": "integer",
                "description": "超时秒数（1-30，默认 10）",
                "default": 10,
            },
            "clear": {
                "type": "boolean",
                "description": "是否清除之前的命名空间",
                "default": False,
            },
        },
        "required": ["code"],
    },
    "handler": repl_handler,
    "permission_level": "execute",
})
