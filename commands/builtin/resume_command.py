"""
/resume 命令 - 会话恢复

支持列出、搜索和恢复之前的会话。

用法:
  /resume              - 列出最近会话
  /resume <id>         - 按 ID（或前缀）恢复指定会话
  /resume search <kw>  - 搜索会话
  /resume latest       - 恢复最近一次会话
  /resume delete <id>  - 删除指定会话
  /resume stats        - 查看存储统计
"""

import logging
from commands.registry import register_command

logger = logging.getLogger(__name__)


def _format_session_line(meta, index: int = 0) -> str:
    """格式化单条会话列表行"""
    # 时间: 取日期+时间部分
    updated = meta.updated_at[:19].replace("T", " ") if meta.updated_at else "?"
    prompt = meta.first_prompt[:60].replace("\n", " ") if meta.first_prompt else "(无)"
    status_icon = {
        "completed": "✅",
        "active": "🟢",
        "aborted": "⏹️",
        "error": "❌",
    }.get(meta.status, "⚪")

    line = (
        f"  {status_icon} [{meta.session_id[:8]}] "
        f"{updated}  |  "
        f"{meta.turn_count}轮 {meta.total_tokens}tok "
    )
    if meta.total_cost_usd > 0:
        line += f"${meta.total_cost_usd:.4f} "
    line += f"| {meta.model}"
    line += f"\n     └─ {prompt}"
    return line


def resume_handler(args, loop=None):
    """
    /resume 命令处理函数

    Args:
        args: 命令参数列表
        loop: AgentLoop 实例（用于恢复会话）
    """
    from core.session_store import SessionStore, restore_session_to_loop

    store = SessionStore()

    # 无参数 → 列出最近会话
    if not args:
        sessions = store.list_sessions(limit=15)
        if not sessions:
            return "📭 没有找到保存的会话。\n\n会话会在每次对话结束后自动保存到 ~/.auracode/sessions/"

        lines = [f"📂 最近会话 (共 {store.get_session_count()} 个):\n"]
        for i, meta in enumerate(sessions):
            lines.append(_format_session_line(meta, i))
        lines.append("")
        lines.append("💡 用法:")
        lines.append("  /resume <id>         恢复指定会话")
        lines.append("  /resume latest       恢复最近一次会话")
        lines.append("  /resume search <关键词>  搜索会话")
        lines.append("  /resume delete <id>  删除会话")
        lines.append("  /resume stats        存储统计")
        return "\n".join(lines)

    action = args[0]

    # /resume latest → 恢复最近会话
    if action == "latest":
        record = store.get_latest_session()
        if not record:
            return "📭 没有找到保存的会话。"

        if loop is None:
            return f"⚠️ 无法恢复: AgentLoop 不可用\n\n最近会话:\n{_format_session_line(record.meta)}"

        success = restore_session_to_loop(loop, record)
        if success:
            meta = record.meta
            result = (
                f"✅ 已恢复会话 [{meta.session_id[:8]}]\n"
                f"   模型: {meta.model}\n"
                f"   消息: {meta.message_count} 条\n"
                f"   轮次: {meta.turn_count}\n"
                f"   Token: {meta.total_tokens}\n"
                f"   首条: {meta.first_prompt[:80]}"
            )
            # AwaySummary: 生成离开时摘要
            try:
                from services.away_summary import generate_away_summary, get_away_summary_service
                messages = record.messages or []
                if messages:
                    summary_result = generate_away_summary(messages)
                    if summary_result.success:
                        svc = get_away_summary_service()
                        result += "\n\n" + svc.format_display(summary_result)
            except Exception:
                pass
            return result
        else:
            return "❌ 恢复失败，请检查日志。"

    # /resume search <keyword>
    if action == "search":
        keyword = " ".join(args[1:]) if len(args) > 1 else ""
        if not keyword:
            return "❌ 请提供搜索关键词: /resume search <关键词>"

        results = store.search_sessions(keyword)
        if not results:
            return f"🔍 未找到包含 \"{keyword}\" 的会话。"

        lines = [f"🔍 搜索结果 \"{keyword}\" ({len(results)} 个匹配):\n"]
        for i, meta in enumerate(results):
            lines.append(_format_session_line(meta, i))
        return "\n".join(lines)

    # /resume delete <id>
    if action == "delete":
        if len(args) < 2:
            return "❌ 请提供会话 ID: /resume delete <id>"

        target_id = args[1]
        deleted = store.delete_session(target_id)
        if deleted:
            return f"🗑️ 已删除会话 [{target_id}]"
        else:
            return f"❌ 未找到会话 [{target_id}]"

    # /resume stats → 存储统计
    if action == "stats":
        count = store.get_session_count()
        size_bytes = store.get_storage_size_bytes()
        if size_bytes > 1024 * 1024:
            size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
        elif size_bytes > 1024:
            size_str = f"{size_bytes / 1024:.1f} KB"
        else:
            size_str = f"{size_bytes} B"

        lines = [
            "📊 会话存储统计:",
            f"   存储目录: {store.sessions_dir}",
            f"   总会话数: {count}",
            f"   存储大小: {size_str}",
        ]
        return "\n".join(lines)

    # /resume <id> → 恢复指定会话
    target_id = action
    record = store.load_session(target_id)
    if not record:
        # 可能是 search 的简写
        results = store.search_sessions(target_id)
        if results:
            lines = [f"🔍 ID \"{target_id}\" 未精确匹配，搜索到 {len(results)} 个相关会话:\n"]
            for i, meta in enumerate(results[:5]):
                lines.append(_format_session_line(meta, i))
            lines.append(f"\n💡 使用 /resume <id> 恢复指定会话")
            return "\n".join(lines)
        return f"❌ 未找到会话 [{target_id}]"

    if loop is None:
        meta = record.meta
        return (
            f"⚠️ AgentLoop 不可用，无法恢复。\n\n"
            f"会话详情:\n{_format_session_line(meta)}\n"
            f"   消息数: {meta.message_count}\n"
            f"   Token: {meta.total_tokens}"
        )

    success = restore_session_to_loop(loop, record)
    if success:
        meta = record.meta
        result = (
            f"✅ 已恢复会话 [{meta.session_id[:8]}]\n"
            f"   模型: {meta.model}\n"
            f"   消息: {meta.message_count} 条\n"
            f"   轮次: {meta.turn_count}\n"
            f"   Token: {meta.total_tokens}\n"
            f"   费用: ${meta.total_cost_usd:.4f}\n"
            f"   首条: {meta.first_prompt[:80]}\n"
            f"\n💡 消息已加载到当前会话，继续对话即可。"
        )
        # AwaySummary: 生成离开时摘要
        try:
            from services.away_summary import generate_away_summary, get_away_summary_service
            messages = record.messages or []
            if messages:
                summary_result = generate_away_summary(messages)
                if summary_result.success:
                    svc = get_away_summary_service()
                    result += "\n\n" + svc.format_display(summary_result)
        except Exception:
            pass
        return result
    else:
        return "❌ 恢复失败，请检查日志。"


# 注册命令
register_command("resume", {
    "description": "恢复之前的会话 (列出/搜索/恢复/删除)",
    "handler": resume_handler,
    "args_help": "[id|latest|search <关键词>|delete <id>|stats]",
    "category": "system",
})
