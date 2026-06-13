"""
Export 命令 - 对话导出为文件

功能:
- 将当前对话历史导出为可读文本文件
- 支持 Markdown 格式
- 支持 JSON 格式（机器可读）
- 自动生成文件名（基于时间戳或首条消息）

用法:
  /export              导出为 Markdown（自动生成文件名）
  /export <filename>   导出到指定文件
  /export json         导出为 JSON 格式
  /export json <file>  导出 JSON 到指定文件
"""

import json
import os
import re
from datetime import datetime
from commands.registry import register_command


def _sanitize_filename(name: str, max_len: int = 50) -> str:
    """清理文件名（移除非法字符）"""
    clean = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', name)
    clean = re.sub(r'\s+', '_', clean.strip())
    return clean[:max_len]


def _extract_first_prompt(messages: list) -> str:
    """提取首条用户消息作为文件名素材"""
    for msg in messages:
        if msg.get("role") == "user":
            content = str(msg.get("content", ""))
            return content[:80] if content else ""
    return ""


def _format_as_markdown(messages: list) -> str:
    """将消息历史格式化为 Markdown"""
    lines = []
    lines.append(f"# opencode 对话记录")
    lines.append(f"")
    lines.append(f"> 导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"> 消息总数: {len(messages)}")
    lines.append(f"")
    lines.append("---")
    lines.append("")

    role_names = {
        "system": "系统",
        "user": "用户",
        "assistant": "助手",
        "tool": "工具结果",
    }

    msg_index = 0
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")

        # 跳过系统提示（太长且无意义）
        if role == "system" and len(str(content)) > 500:
            lines.append(f"### [{role_names.get(role, role)}]")
            lines.append(f"*(系统提示，{len(str(content))} 字符，已省略)*")
            lines.append("")
            continue

        msg_index += 1
        role_label = role_names.get(role, role)

        if role == "user":
            lines.append(f"### 👤 {role_label}")
        elif role == "assistant":
            lines.append(f"### 🤖 {role_label}")
        elif role == "tool":
            # 工具结果截断
            content_str = str(content)
            if len(content_str) > 2000:
                content_str = content_str[:1000] + f"\n\n... (截断，原始 {len(str(content))} 字符) ...\n\n" + content_str[-500:]
            lines.append(f"### 🔧 {role_label}")
            lines.append(f"```")
            lines.append(content_str)
            lines.append(f"```")
            lines.append("")
            continue
        else:
            lines.append(f"### [{role_label}]")

        if content:
            content_str = str(content)
            if len(content_str) > 5000:
                content_str = content_str[:2500] + f"\n\n... (截断，原始 {len(str(content))} 字符) ...\n\n" + content_str[-1000:]
            lines.append(content_str)

        # 处理工具调用
        tool_calls = msg.get("tool_calls", [])
        if tool_calls:
            lines.append("")
            lines.append("**调用工具:**")
            for tc in tool_calls:
                func = tc.get("function", {})
                name = func.get("name", "unknown")
                args_str = func.get("arguments", "{}")
                try:
                    args_obj = json.loads(args_str) if isinstance(args_str, str) else args_str
                    # 截断长参数
                    formatted = json.dumps(args_obj, ensure_ascii=False, indent=2)
                    if len(formatted) > 500:
                        formatted = formatted[:300] + "\n  ... (参数过长) ..."
                    lines.append(f"- `{name}`: ```json\n{formatted}\n  ```")
                except (json.JSONDecodeError, TypeError):
                    lines.append(f"- `{name}`: {args_str[:200]}")

        lines.append("")

    return "\n".join(lines)


def _format_as_json(messages: list, state=None) -> str:
    """将消息历史格式化为 JSON"""
    data = {
        "metadata": {
            "exported_at": datetime.now().isoformat(),
            "message_count": len(messages),
            "version": "opencode-1.0",
        },
        "messages": [],
    }

    # 添加会话状态信息
    if state:
        data["metadata"]["model"] = getattr(state, '_current_model', 'unknown')
        data["metadata"]["total_cost_usd"] = state.total_cost_usd
        data["metadata"]["total_tokens"] = state.total_usage.total_tokens
        data["metadata"]["turns"] = state.turn_count

    for msg in messages:
        entry = {
            "role": msg.get("role", "unknown"),
            "content": str(msg.get("content", "")),
        }
        # 工具调用
        tool_calls = msg.get("tool_calls", [])
        if tool_calls:
            entry["tool_calls"] = []
            for tc in tool_calls:
                func = tc.get("function", {})
                entry["tool_calls"].append({
                    "name": func.get("name", ""),
                    "arguments": func.get("arguments", ""),
                })
        # 工具调用 ID
        if msg.get("tool_call_id"):
            entry["tool_call_id"] = msg["tool_call_id"]

        data["messages"].append(entry)

    return json.dumps(data, ensure_ascii=False, indent=2)


def export_handler(args: list, loop=None) -> str:
    """export 命令处理函数"""
    if loop is None:
        return "❌ AgentLoop 未初始化"

    messages = getattr(loop, 'messages', [])
    if not messages:
        return "❌ 对话历史为空，无法导出"

    state = getattr(loop, 'state', None)

    # 解析参数
    use_json = False
    filename = None

    for arg in args:
        if arg.lower() in ('json', 'JSON'):
            use_json = True
        else:
            filename = arg

    # 生成默认文件名
    if not filename:
        timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        first_prompt = _extract_first_prompt(messages)
        if first_prompt:
            safe_name = _sanitize_filename(first_prompt)
            filename = f"{timestamp}-{safe_name}"
        else:
            filename = f"conversation-{timestamp}"

    # 添加扩展名
    ext = ".json" if use_json else ".md"
    if not filename.endswith(ext):
        # 移除旧扩展名
        if '.' in filename:
            filename = filename.rsplit('.', 1)[0]
        filename += ext

    # 生成内容
    if use_json:
        content = _format_as_json(messages, state)
    else:
        content = _format_as_markdown(messages)

    # 写入文件
    try:
        # 在当前工作目录下创建 exports/ 子目录
        cwd = os.getcwd()
        export_dir = os.path.join(cwd, "exports")
        os.makedirs(export_dir, exist_ok=True)

        filepath = os.path.join(export_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

        lines = []
        lines.append(f"✅ 对话已导出")
        lines.append(f"  文件: {filepath}")
        lines.append(f"  格式: {'JSON' if use_json else 'Markdown'}")
        lines.append(f"  消息: {len(messages)} 条")
        lines.append(f"  大小: {len(content):,} 字符")
        if state:
            lines.append(f"  费用: ${state.total_cost_usd:.6f}")
        return "\n".join(lines)

    except Exception as e:
        return f"❌ 导出失败: {e}"


register_command("export", {
    "description": "导出对话记录 - Markdown/JSON 格式，自动保存至 exports/ 目录",
    "handler": export_handler,
    "category": "session",
    "args_help": "[json] [filename] 导出对话"
})
