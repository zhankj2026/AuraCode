"""
消息管理系统

Claude Code 使用扁平消息历史,所有消息按时间顺序存储在列表中。
支持 system/user/assistant/tool 四种角色,符合 OpenAI/Claude API 规范。
"""

from typing import List, Dict, Any, Literal

MessageType = Literal["system", "user", "assistant", "tool"]
Message = Dict[str, Any]


def create_system_message(content: str) -> Message:
    """
    创建系统消息
    
    Args:
        content: 系统提示词内容
        
    Returns:
        系统消息字典
    """
    return {"role": "system", "content": content}


def create_user_message(content: str) -> Message:
    """
    创建用户消息
    
    Args:
        content: 用户输入内容
        
    Returns:
        用户消息字典
    """
    return {"role": "user", "content": content}


def create_assistant_message(content: str) -> Message:
    """
    创建助手消息
    
    Args:
        content: 助手回复内容
        
    Returns:
        助手消息字典
    """
    return {"role": "assistant", "content": content}


def create_tool_result_message(content: str) -> Message:
    """
    创建工具结果消息(以 user 角色返回)
    
    注意: OpenAI/Claude API 要求 user 和 assistant 必须交替出现,
    工具结果是"环境反馈",不是助手的主动行为,所以归类为 user 消息。
    
    Args:
        content: 工具执行结果(JSON 字符串)
        
    Returns:
        工具结果消息字典
    """
    return {"role": "user", "content": content}


def validate_message_sequence(messages: List[Message]) -> bool:
    """
    验证消息序列是否符合交替规则
    
    规则:
    - system 消息只能在开头
    - user 和 assistant 必须交替出现
    - tool 结果必须以 user 角色返回
    
    Args:
        messages: 消息列表
        
    Returns:
        是否符合规则
    """
    if not messages:
        return False
    
    # 检查 system 消息位置
    if messages[0]["role"] != "system":
        return False
    
    # 检查交替规则
    for i in range(1, len(messages)):
        prev_role = messages[i-1]["role"]
        curr_role = messages[i]["role"]
        
        # system 后必须是 user
        if prev_role == "system" and curr_role != "user":
            return False
        
        # user 后可以是 assistant 或 user(tool 结果)
        # assistant 后必须是 user
        if prev_role == "assistant" and curr_role != "user":
            return False
    
    return True
