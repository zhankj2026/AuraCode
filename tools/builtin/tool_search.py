"""
ToolSearch 工具 - 搜索可用的工具

参考 Claude Code ToolSearchTool 设计，支持按名称/描述/类别搜索工具，
帮助 LLM 在工具较多时发现正确的工具。
"""

from typing import Optional
from tools.registry import register_tool, TOOL_REGISTRY


# 工具类别标签
TOOL_CATEGORIES = {
    # 文件操作
    "read_file": "file", "write_file": "file", "replace_in_file": "file",
    "list_directory": "file", "find": "file", "glob": "file",
    "undo_edit": "file", "notebook_edit": "file",
    # 代码分析
    "grep": "code", "analyze_file": "code", "lint": "code", "lsp_tool": "code",
    # 执行
    "run_command": "execute", "run_powershell": "execute", "run_tests": "execute",
    # 网络
    "web_fetch": "web", "web_search": "web",
    # 辅助
    "todo_write": "aux", "ask_user": "aux", "tool_search": "aux",
    "sleep": "aux", "config": "aux",
    # 规划
    "plan_mode": "plan", "plan_agent": "plan", "subagent": "plan",
    # 记忆
    "get_memory": "memory", "save_memory": "memory", "list_memories": "memory",
    # 技能
    "activate_skill": "skill", "deactivate_skill": "skill", "list_skills": "skill",
}


def tool_search_handler(
    query: str = "",
    category: str = "",
    limit: int = 20,
) -> str:
    """
    搜索可用工具

    Args:
        query: 搜索关键词（匹配工具名或描述）
        category: 按类别过滤 (file/code/execute/web/aux/plan/memory/skill)
        limit: 最大返回数量
    """
    results = []

    for name, info in TOOL_REGISTRY.items():
        # 类别过滤
        if category:
            tool_cat = TOOL_CATEGORIES.get(name, "other")
            if tool_cat != category:
                continue

        # 关键词匹配
        if query:
            q = query.lower()
            name_match = q in name.lower()
            desc_match = q in info.get("description", "").lower()
            if not name_match and not desc_match:
                continue

        results.append({
            "name": name,
            "description": info.get("description", "")[:100],
            "category": TOOL_CATEGORIES.get(name, "other"),
            "permission": info.get("permission_level", "read"),
        })

    if not results:
        # 无匹配时列出所有工具名
        all_names = sorted(TOOL_REGISTRY.keys())
        return f"未找到匹配 '{query}' 的工具。\n\n可用工具 ({len(all_names)}):\n" + \
               ", ".join(all_names)

    # 按名称排序
    results.sort(key=lambda x: x["name"])
    results = results[:limit]

    output = f"找到 {len(results)} 个工具"
    if query:
        output += f" (匹配: '{query}')"
    if category:
        output += f" (类别: {category})"
    output += ":\n\n"

    for r in results:
        output += f"📦 {r['name']} [{r['category']}] ({r['permission']})\n"
        output += f"   {r['description']}\n\n"

    # 附加可用类别列表
    categories = sorted(set(TOOL_CATEGORIES.values()))
    output += f"可用类别: {', '.join(categories)}"

    return output


register_tool("tool_search", {
    "description": (
        "搜索可用的工具。当不确定应该使用哪个工具时，"
        "用此工具按关键词或类别查找。"
        "例如: query='file' 查找文件相关工具, category='code' 查找代码分析工具。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词（匹配工具名或描述）",
                "default": "",
            },
            "category": {
                "type": "string",
                "description": "按类别过滤: file/code/execute/web/aux/plan/memory/skill",
                "default": "",
            },
            "limit": {
                "type": "integer",
                "description": "最大返回数量",
                "default": 20,
            },
        },
        "required": [],
    },
    "handler": tool_search_handler,
    "permission_level": "read",
})
