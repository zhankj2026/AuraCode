"""
/memory 命令 - 记忆管理

提供记忆的查看、搜索、编辑、删除、导出等功能。
直接对接 MemoryManager，让用户在对话中管理记忆。

用法:
    /memory                    — 列出所有记忆（按类型分组）
    /memory list [type]        — 列出记忆（可过滤类型）
    /memory search <keyword>   — 搜索记忆
    /memory show <type> <title> — 查看记忆详情
    /memory add <type> <title> <content> — 添加记忆
    /memory edit <type> <title> <content> — 编辑记忆
    /memory delete <type> <title> — 删除记忆
    /memory export [path]      — 导出记忆
    /memory stats              — 记忆统计
"""

from typing import Optional
from commands.registry import register_command

# 全局 MemoryManager 引用（由 AgentLoop 或 CLI 注入）
_memory_manager = None


def set_memory_manager(mm):
    """设置全局 MemoryManager 实例"""
    global _memory_manager
    _memory_manager = mm


def _get_mm():
    """获取 MemoryManager，如果未初始化则尝试创建"""
    global _memory_manager
    if _memory_manager is None:
        try:
            from core.memory import MemoryManager
            _memory_manager = MemoryManager(".")
        except Exception as e:
            return None
    return _memory_manager


def memory_handler(args: str, loop=None) -> str:
    """记忆管理命令处理器"""
    mm = _get_mm()
    if mm is None:
        return "❌ 记忆系统未初始化"

    parts = args.strip().split()
    if not parts:
        return _cmd_list(mm, [])

    sub = parts[0].lower()
    rest = parts[1:]

    if sub == "list":
        return _cmd_list(mm, rest)
    elif sub == "search":
        return _cmd_search(mm, rest)
    elif sub == "show":
        return _cmd_show(mm, rest)
    elif sub == "add":
        return _cmd_add(mm, rest)
    elif sub == "edit":
        return _cmd_edit(mm, rest)
    elif sub == "delete" or sub == "rm":
        return _cmd_delete(mm, rest)
    elif sub == "export":
        return _cmd_export(mm, rest)
    elif sub == "stats":
        return _cmd_stats(mm)
    elif sub == "help":
        return _cmd_help()
    else:
        # 尝试作为 list 的类型过滤
        if sub in ["user", "feedback", "project", "reference"]:
            return _cmd_list(mm, [sub])
        return f"未知子命令: {sub}\n\n{_cmd_help()}"


def _cmd_list(mm, rest) -> str:
    """列出记忆"""
    mem_type = rest[0] if rest else None
    memories = mm.list_memories(memory_type=mem_type)

    if not memories:
        if mem_type:
            return f"📭 没有找到类型 '{mem_type}' 的记忆"
        return "📭 记忆为空，使用 /memory add 添加"

    # 按类型分组
    from core.memory import MEMORY_TYPES
    by_type = {}
    for m in memories:
        t = m["type"]
        if t not in by_type:
            by_type[t] = []
        by_type[t].append(m)

    lines = [f"📚 记忆列表 (共 {len(memories)} 条)", ""]
    for t, mems in sorted(by_type.items()):
        type_desc = MEMORY_TYPES.get(t, {}).get("description", t)
        lines.append(f"  [{t}] {type_desc} ({len(mems)} 条):")
        for m in mems:
            desc = m.get("description", "")[:60]
            lines.append(f"    • {m['title']} — {desc}")
        lines.append("")

    return "\n".join(lines)


def _cmd_search(mm, rest) -> str:
    """搜索记忆"""
    if not rest:
        return "用法: /memory search <关键词>"

    keyword = " ".join(rest)
    results = mm.search_memories(keyword)

    if not results:
        return f"🔍 未找到包含 '{keyword}' 的记忆"

    lines = [f"🔍 搜索结果: '{keyword}' ({len(results)} 条匹配)", ""]
    for m in results:
        desc = m.get("description", "")[:60]
        lines.append(f"  [{m['type']}] {m['title']} — {desc}")
    return "\n".join(lines)


def _cmd_show(mm, rest) -> str:
    """查看记忆详情"""
    if len(rest) < 2:
        return "用法: /memory show <type> <title>"

    mem_type = rest[0]
    title = " ".join(rest[1:])

    mem = mm.load_memory(mem_type, title)
    if mem is None:
        return f"❌ 记忆不存在: [{mem_type}] {title}"

    lines = [
        f"📋 记忆详情",
        f"  类型: {mem.memory_type}",
        f"  标题: {mem.title}",
        f"  创建: {mem.created_at}",
        f"  更新: {mem.updated_at}",
        f"  元数据: {mem.metadata or '无'}",
        f"",
        f"  内容:",
        f"  {'─' * 50}",
    ]
    for line in mem.content.split("\n"):
        lines.append(f"  {line}")

    return "\n".join(lines)


def _cmd_add(mm, rest) -> str:
    """添加记忆"""
    if len(rest) < 3:
        return "用法: /memory add <type> <title> <content>\n类型: user / feedback / project / reference"

    mem_type = rest[0]
    title = rest[1]
    content = " ".join(rest[2:])

    if mem_type not in ["user", "feedback", "project", "reference"]:
        return f"❌ 无效类型: {mem_type}，可选: user/feedback/project/reference"

    success = mm.save_memory(mem_type, title, content)
    if success:
        return f"✅ 记忆已保存: [{mem_type}] {title}"
    else:
        return f"❌ 保存失败"


def _cmd_edit(mm, rest) -> str:
    """编辑记忆（覆盖内容）"""
    if len(rest) < 3:
        return "用法: /memory edit <type> <title> <new_content>"

    mem_type = rest[0]
    title = rest[1]
    new_content = " ".join(rest[2:])

    # 先检查是否存在
    existing = mm.load_memory(mem_type, title)
    if existing is None:
        return f"❌ 记忆不存在: [{mem_type}] {title}，使用 /memory add 创建"

    success = mm.save_memory(mem_type, title, new_content, existing.metadata)
    if success:
        return f"✅ 记忆已更新: [{mem_type}] {title}"
    else:
        return "❌ 更新失败"


def _cmd_delete(mm, rest) -> str:
    """删除记忆"""
    if len(rest) < 2:
        return "用法: /memory delete <type> <title>"

    mem_type = rest[0]
    title = " ".join(rest[1:])

    success = mm.delete_memory(mem_type, title)
    if success:
        return f"🗑️ 记忆已删除: [{mem_type}] {title}"
    else:
        return f"❌ 删除失败，记忆可能不存在: [{mem_type}] {title}"


def _cmd_export(mm, rest) -> str:
    """导出记忆"""
    output_path = rest[0] if rest else "memory_export.md"
    success = mm.export_memories(output_path)
    if success:
        return f"📦 记忆已导出到: {output_path}"
    else:
        return "❌ 导出失败"


def _cmd_stats(mm) -> str:
    """记忆统计"""
    memories = mm.list_memories()
    if not memories:
        return "📊 记忆统计: 无记忆"

    by_type = {}
    for m in memories:
        t = m["type"]
        by_type[t] = by_type.get(t, 0) + 1

    lines = [
        f"📊 记忆统计",
        f"  总计: {len(memories)} 条",
        f"  存储目录: {mm.memory_dir}",
        f"",
        f"  按类型分布:",
    ]
    from core.memory import MEMORY_TYPES
    for t, count in sorted(by_type.items()):
        desc = MEMORY_TYPES.get(t, {}).get("description", t)
        bar = "█" * min(count, 20)
        lines.append(f"    {t:12s} {count:3d}  {bar}  {desc}")

    return "\n".join(lines)


def _cmd_help() -> str:
    """帮助信息"""
    return """记忆管理命令 /memory

用法:
  /memory                    列出所有记忆（按类型分组）
  /memory list [type]        列出记忆（可选类型过滤: user/feedback/project/reference）
  /memory search <keyword>   搜索记忆（标题+内容）
  /memory show <type> <title> 查看记忆详情
  /memory add <type> <title> <content> 添加记忆
  /memory edit <type> <title> <content> 编辑记忆
  /memory delete <type> <title> 删除记忆
  /memory export [path]      导出记忆到文件（默认 memory_export.md）
  /memory stats              记忆统计信息

记忆类型:
  user       用户信息（角色、偏好、知识）
  feedback   用户反馈（方法指导、确认有效的方法）
  project    项目信息（目标、截止日期、进展）
  reference  外部系统参考（Bug追踪、文档等）"""


register_command("memory", {
    "description": "记忆管理 (查看/搜索/添加/编辑/删除/导出)",
    "handler": memory_handler,
    "args_help": "[list|search|show|add|edit|delete|export|stats] [type] [title] [content]",
    "category": "system",
})

