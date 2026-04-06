"""执行命令工具"""
import subprocess
import platform
from tools.registry import register_tool


def run_command_handler(command: str) -> str:
    """执行 Shell 命令"""
    if platform.system() == "Windows":
        shell = True
    else:
        shell = True
    
    result = subprocess.run(
        command,
        shell=shell,
        capture_output=True,
        text=True,
        timeout=30
    )
    
    output = ""
    if result.stdout:
        output += result.stdout
    if result.stderr:
        if output:
            output += "\n--- STDERR ---\n"
        output += result.stderr
    
    if result.returncode != 0:
        output += f"\n--- EXIT CODE: {result.returncode} ---"
    
    return output


register_tool("run_command", {
    "description": "执行 Shell 命令",
    "parameters": {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "要执行的命令"}
        },
        "required": ["command"]
    },
    "handler": run_command_handler,
    "permission_level": "execute"
})
