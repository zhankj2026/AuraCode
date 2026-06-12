"""
Sleep 工具 - 等待/延迟

参考 Claude Code SleepTool 设计，用于在异步操作间等待
（如等待服务器启动、文件生成、后台进程完成等）。
"""

import time
from tools.registry import register_tool


def sleep_handler(seconds: float = 1.0, reason: str = "") -> str:
    """
    暂停执行指定的时间

    Args:
        seconds: 等待秒数（0.1 ~ 60.0）
        reason: 等待原因（可选，用于日志）
    """
    # 限制范围
    seconds = max(0.1, min(60.0, seconds))

    start = time.time()
    time.sleep(seconds)
    elapsed = time.time() - start

    output = f"已等待 {elapsed:.1f} 秒"
    if reason:
        output += f"（原因: {reason}）"

    return output


register_tool("sleep", {
    "description": (
        "暂停执行指定的时间。用于等待异步操作完成，"
        "如等待服务器启动、后台进程结束、文件生成等。"
        "最大等待 60 秒。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "seconds": {
                "type": "number",
                "description": "等待秒数（0.1 ~ 60.0）",
                "default": 1.0,
            },
            "reason": {
                "type": "string",
                "description": "等待原因（可选）",
                "default": "",
            },
        },
        "required": ["seconds"],
    },
    "handler": sleep_handler,
    "permission_level": "read",
})
