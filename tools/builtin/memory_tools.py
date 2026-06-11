"""
记忆工具 - 提供 Agent 操作记忆系统的能力
"""

import json
import logging
from typing import Dict, Any, Optional

from core.memory import get_memory_manager, MEMORY_TYPES, memory_freshness_text

logger = logging.getLogger(__name__)


def save_memory_tool(
    memory_type: str,
    title: str,
    content: str,
    metadata: Optional[str] = None
) -> Dict[str, Any]:
    """
    保存记忆

    将重要信息持久化存储,以便在未来的会话中回忆和使用。

    Args:
        memory_type: 记忆类型,可选值: user, feedback, project, reference
            - user: 用户角色、偏好、知识等
            - feedback: 用户对工作方式的反馈和指导
            - project: 项目相关信息、目标、截止日期等
            - reference: 外部系统参考(文档、Bug 追踪等)
        title: 记忆标题,简短描述
        content: 记忆内容,详细信息
        metadata: 可选的 JSON 格式元数据

    Returns:
        操作结果
    """
    try:
        # 验证记忆类型
        if memory_type not in MEMORY_TYPES:
            return {
                "success": False,
                "error": f"无效的记忆类型: {memory_type}。可选值: {', '.join(MEMORY_TYPES.keys())}"
            }

        # 解析元数据
        meta_dict = None
        if metadata:
            try:
                meta_dict = json.loads(metadata)
            except json.JSONDecodeError as e:
                return {
                    "success": False,
                    "error": f"元数据 JSON 格式错误: {e}"
                }

        # 保存记忆
        manager = get_memory_manager()
        success = manager.save_memory(
            memory_type=memory_type,
            title=title,
            content=content,
            metadata=meta_dict
        )

        if success:
            return {
                "success": True,
                "message": f"已保存记忆: {memory_type}/{title}"
            }
        else:
            return {
                "success": False,
                "error": "保存记忆失败"
            }

    except Exception as e:
        logger.error(f"save_memory_tool error: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def load_memory_tool(
    memory_type: str,
    title: str
) -> Dict[str, Any]:
    """
    加载记忆

    读取指定记忆的完整内容。

    Args:
        memory_type: 记忆类型
        title: 记忆标题

    Returns:
        记忆内容
    """
    try:
        manager = get_memory_manager()
        memory = manager.load_memory(memory_type, title)

        if memory is None:
            return {
                "success": False,
                "error": f"记忆不存在: {memory_type}/{title}"
            }

        return {
            "success": True,
            "memory": {
                "type": memory.memory_type,
                "title": memory.title,
                "content": memory.content,
                "metadata": memory.metadata,
                "created_at": memory.created_at,
                "updated_at": memory.updated_at,
                "freshness_warning": memory_freshness_text(
                    memory.updated_at or memory.created_at
                ) or None,
            }
        }

    except Exception as e:
        logger.error(f"load_memory_tool error: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def list_memories_tool(
    memory_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    列出所有记忆

    显示存储的所有记忆或特定类型的记忆。

    Args:
        memory_type: 可选,过滤特定类型的记忆

    Returns:
        记忆列表
    """
    try:
        manager = get_memory_manager()
        memories = manager.list_memories(memory_type)

        return {
            "success": True,
            "count": len(memories),
            "memories": memories
        }

    except Exception as e:
        logger.error(f"list_memories_tool error: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def search_memories_tool(
    query: str
) -> Dict[str, Any]:
    """
    搜索记忆

    根据关键词搜索记忆内容。

    Args:
        query: 搜索关键词

    Returns:
        匹配的记忆列表
    """
    try:
        manager = get_memory_manager()
        results = manager.search_memories(query)

        return {
            "success": True,
            "count": len(results),
            "results": results
        }

    except Exception as e:
        logger.error(f"search_memories_tool error: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def delete_memory_tool(
    memory_type: str,
    title: str
) -> Dict[str, Any]:
    """
    删除记忆

    删除指定的记忆。此操作不可逆。

    Args:
        memory_type: 记忆类型
        title: 记忆标题

    Returns:
        操作结果
    """
    try:
        manager = get_memory_manager()
        success = manager.delete_memory(memory_type, title)

        if success:
            return {
                "success": True,
                "message": f"已删除记忆: {memory_type}/{title}"
            }
        else:
            return {
                "success": False,
                "error": f"记忆不存在或删除失败: {memory_type}/{title}"
            }

    except Exception as e:
        logger.error(f"delete_memory_tool error: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def get_memory_summary_tool() -> Dict[str, Any]:
    """
    获取记忆摘要

    显示所有记忆的概览信息。

    Returns:
        记忆摘要
    """
    try:
        manager = get_memory_manager()
        summary = manager.get_memory_summary()

        return {
            "success": True,
            "summary": summary
        }

    except Exception as e:
        logger.error(f"get_memory_summary_tool error: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def get_relevant_memories_tool(
    context: str,
    max_results: int = 5
) -> Dict[str, Any]:
    """
    获取相关记忆

    根据当前上下文智能获取相关的记忆。
    优先使用 LLM 语义选择，降级为关键词匹配。
    返回结果包含新鲜度警告(对陈旧记忆)。

    Args:
        context: 当前上下文描述
        max_results: 最大返回数量,默认 5

    Returns:
        相关记忆列表
    """
    try:
        manager = get_memory_manager()

        # 获取 LLM 客户端(如果 MemoryManager 有)
        client = getattr(manager, 'llm_client', None)
        model = getattr(manager, 'llm_model', None)

        # 使用 LLM 驱动的记忆召回
        relevant = manager.get_relevant_memories_with_llm(
            query=context,
            client=client,
            model=model,
            max_results=max_results,
        )

        memories_result = []
        for m in relevant:
            entry = {
                "type": m.memory_type,
                "title": m.title,
                "content": m.content,
                "created_at": m.created_at,
            }
            # 添加新鲜度警告
            freshness = memory_freshness_text(m.updated_at or m.created_at)
            if freshness:
                entry["freshness_warning"] = freshness
            memories_result.append(entry)

        return {
            "success": True,
            "count": len(memories_result),
            "memories": memories_result,
            "selection_method": "llm" if client and model else "keyword",
        }

    except Exception as e:
        logger.error(f"get_relevant_memories_tool error: {e}")
        return {
            "success": False,
            "error": str(e)
        }


# 导出工具注册信息
def register_memory_tools():
    """注册所有记忆工具到工具注册表"""
    from tools.registry import register_tool

    tools = [
        {
            "name": "save_memory",
            "description": "保存记忆到持久化存储。用于记录用户信息、反馈、项目信息等,以便在未来的会话中回忆和使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "memory_type": {
                        "type": "string",
                        "enum": ["user", "feedback", "project", "reference"],
                        "description": "记忆类型: user(用户信息), feedback(用户反馈), project(项目信息), reference(外部参考)"
                    },
                    "title": {
                        "type": "string",
                        "description": "记忆标题,简短描述该记忆"
                    },
                    "content": {
                        "type": "string",
                        "description": "记忆内容,详细信息"
                    },
                    "metadata": {
                        "type": "string",
                        "description": "可选的 JSON 格式元数据"
                    }
                },
                "required": ["memory_type", "title", "content"]
            },
            "handler": save_memory_tool,
            "permission_level": "write"
        },
        {
            "name": "load_memory",
            "description": "加载指定记忆的完整内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "memory_type": {
                        "type": "string",
                        "enum": ["user", "feedback", "project", "reference"],
                        "description": "记忆类型"
                    },
                    "title": {
                        "type": "string",
                        "description": "记忆标题"
                    }
                },
                "required": ["memory_type", "title"]
            },
            "handler": load_memory_tool,
            "permission_level": "read"
        },
        {
            "name": "list_memories",
            "description": "列出所有记忆或特定类型的记忆",
            "parameters": {
                "type": "object",
                "properties": {
                    "memory_type": {
                        "type": "string",
                        "enum": ["user", "feedback", "project", "reference"],
                        "description": "可选,过滤特定类型的记忆"
                    }
                }
            },
            "handler": list_memories_tool,
            "permission_level": "read"
        },
        {
            "name": "search_memories",
            "description": "根据关键词搜索记忆内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词"
                    }
                },
                "required": ["query"]
            },
            "handler": search_memories_tool,
            "permission_level": "read"
        },
        {
            "name": "delete_memory",
            "description": "删除指定的记忆(不可逆操作)",
            "parameters": {
                "type": "object",
                "properties": {
                    "memory_type": {
                        "type": "string",
                        "enum": ["user", "feedback", "project", "reference"],
                        "description": "记忆类型"
                    },
                    "title": {
                        "type": "string",
                        "description": "记忆标题"
                    }
                },
                "required": ["memory_type", "title"]
            },
            "handler": delete_memory_tool,
            "permission_level": "write"
        },
        {
            "name": "get_memory_summary",
            "description": "获取所有记忆的概览摘要",
            "parameters": {
                "type": "object",
                "properties": {}
            },
            "handler": get_memory_summary_tool,
            "permission_level": "read"
        },
        {
            "name": "get_relevant_memories",
            "description": "根据当前上下文智能获取相关的记忆。优先使用 LLM 语义选择，降级为关键词匹配。陈旧记忆会附带新鲜度警告。",
            "parameters": {
                "type": "object",
                "properties": {
                    "context": {
                        "type": "string",
                        "description": "当前上下文描述"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "最大返回数量,默认 5",
                        "default": 5
                    }
                },
                "required": ["context"]
            },
            "handler": get_relevant_memories_tool,
            "permission_level": "read"
        }
    ]

    for tool_def in tools:
        try:
            register_tool(
                tool_def["name"],
                {
                    "description": tool_def["description"],
                    "parameters": tool_def["parameters"],
                    "handler": tool_def["handler"],
                    "permission_level": tool_def["permission_level"]
                }
            )
            logger.info(f"Registered memory tool: {tool_def['name']}")
        except ValueError as e:
            logger.warning(f"Failed to register memory tool {tool_def['name']}: {e}")


# 自动注册记忆工具
register_memory_tools()

