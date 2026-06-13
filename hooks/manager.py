"""
Hook 管理器 - 工具执行钩子系统

基于 code.md Phase 4 实现
参考: 第 6.2 节
"""

import asyncio
import logging
from typing import Callable, Dict, Any, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class HookResult:
    """
    钩子执行结果
    
    Attributes:
        allow: 是否允许继续执行
        modified_input: 修改后的输入参数
        block_reason: 阻止执行的原因
        additional_context: 附加的上下文信息
        short_circuit: 短路标志 — 即使 allow=True 也终止后续钩子
        metadata: 附加结构化数据（供下游消费）
    """
    allow: bool = True
    modified_input: Optional[Dict[str, Any]] = None
    block_reason: Optional[str] = None
    additional_context: Optional[str] = None
    short_circuit: bool = False
    metadata: Optional[Dict[str, Any]] = None


# 定义钩子事件类型
HOOK_EVENTS = [
    # ── 工具生命周期 ──
    "PreToolUse",          # 工具执行前
    "PostToolUse",         # 工具执行后（成功）
    "PostToolUseFailure",  # 工具执行失败时
    "ToolError",           # 工具抛出异常时（区别于权限拒绝）
    # ── 会话生命周期 ──
    "SessionStart",        # 会话开始时
    "SessionEnd",          # 会话结束时
    "Stop",                # Agent Loop 停止时（正常/异常/中断）
    "UserMessage",         # 用户消息提交时
    "Notification",        # 系统通知（预算警告、压缩事件等）
    # ── 子代理 ──
    "SubagentStart",       # 子代理启动时
    "SubagentStop",        # 子代理结束时
    # ── 上下文管理 ──
    "PreCompact",          # 上下文压缩开始前
    "PostCompact",         # 上下文压缩完成后
    "ContextWarning",      # 上下文接近阈值警告
]


class HookManager:
    """
    钩子管理器
    
    支持在工具执行的不同阶段注册和触发钩子
    """
    
    def __init__(self):
        """初始化钩子管理器"""
        # 按事件类型组织钩子
        self.hooks: Dict[str, List[Dict[str, Any]]] = {
            event: [] for event in HOOK_EVENTS
        }
        self._hook_count = 0
    
    def register_hook(
        self,
        event: str,
        handler: Callable,
        matcher: str = None,
        priority: int = 0
    ) -> int:
        """
        注册钩子
        
        Args:
            event: 钩子事件类型(PreToolUse/PostToolUse/PostToolUseFailure/
                   SessionStart/SessionEnd/Stop/UserMessage/Notification/
                   SubagentStart/SubagentStop)
            handler: 钩子处理函数,签名为 async def handler(**kwargs) -> HookResult
            matcher: 可选,只匹配特定工具名称(如 "run_command")
            priority: 优先级,数字越大越先执行
        
        Returns:
            钩子 ID,可用于后续删除
        
        Raises:
            ValueError: 如果事件类型无效
        """
        if event not in HOOK_EVENTS:
            raise ValueError(
                f"无效的钩子事件: {event}\n"
                f"有效的事件: {', '.join(HOOK_EVENTS)}"
            )
        
        hook_id = self._hook_count
        self._hook_count += 1
        
        hook = {
            'id': hook_id,
            'event': event,
            'handler': handler,
            'matcher': matcher,
            'priority': priority
        }
        
        self.hooks[event].append(hook)
        
        # 按优先级排序(降序)
        self.hooks[event].sort(key=lambda h: h['priority'], reverse=True)
        
        matcher_info = f" (匹配: {matcher})" if matcher else ""
        logger.info(f"注册钩子: {event}{matcher_info} [ID: {hook_id}, 优先级: {priority}]")
        
        return hook_id
    
    def unregister_hook(self, hook_id: int) -> bool:
        """
        删除钩子
        
        Args:
            hook_id: 钩子 ID(由 register_hook 返回)
        
        Returns:
            True 如果成功删除,False 否则
        """
        for event in HOOK_EVENTS:
            for i, hook in enumerate(self.hooks[event]):
                if hook['id'] == hook_id:
                    self.hooks[event].pop(i)
                    logger.info(f"删除钩子 [ID: {hook_id}]")
                    return True
        
        logger.warning(f"未找到钩子 [ID: {hook_id}]")
        return False
    
    async def execute_hooks(
        self,
        event: str,
        tool_name: str = None,
        **kwargs
    ) -> HookResult:
        """
        执行指定事件的所有钩子
        
        Args:
            event: 钩子事件类型
            tool_name: 工具名称(用于 matcher 匹配)
            **kwargs: 传递给钩子处理函数的参数
        
        Returns:
            钩子执行结果。如果任何一个钩子返回 allow=False,则立即返回
        """
        if event not in HOOK_EVENTS:
            raise ValueError(f"无效的钩子事件: {event}")
        
        # 添加工具名称到 kwargs(如果未提供)
        if 'tool_name' not in kwargs:
            kwargs['tool_name'] = tool_name
        
        # 获取该事件的钩子(已按优先级排序)
        event_hooks = self.hooks.get(event, [])
        
        if not event_hooks:
            return HookResult(allow=True)
        
        logger.debug(f"执行钩子: {event} (共 {len(event_hooks)} 个)")
        
        for hook in event_hooks:
            # 检查 matcher
            if hook['matcher'] and hook['matcher'] != tool_name:
                continue
            
            try:
                # 执行钩子处理函数
                handler = hook['handler']
                
                # 检查是否是协程函数
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(**kwargs)
                else:
                    # 同步函数,在线程池中执行
                    result = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: handler(**kwargs)
                    )
                
                # 检查结果
                if not isinstance(result, HookResult):
                    logger.warning(f"钩子处理函数应返回 HookResult 实例")
                    continue
                
                # 如果不允许,立即返回（短路）
                if not result.allow:
                    logger.warning(
                        f"钩子阻止执行: {event} "
                        f"(原因: {result.block_reason})"
                    )
                    return result
                
                # 短路机制: 即使 allow=True 也可终止后续钩子
                if result.short_circuit:
                    logger.debug(
                        f"钩子触发短路: {event} [ID: {hook['id']}]"
                    )
                    return result
                
                # 如果有修改的输入,更新 kwargs
                if result.modified_input:
                    kwargs.update(result.modified_input)
                
            except Exception as e:
                logger.error(f"钩子执行失败: {event} [ID: {hook['id']}]: {e}")
                # 钩子失败不应阻止工具执行,继续下一个
                continue
        
        return HookResult(allow=True)
    
    def get_hook_stats(self) -> Dict[str, int]:
        """
        获取钩子统计信息
        
        Returns:
            各事件的钩子数量
        """
        return {
            event: len(hooks)
            for event, hooks in self.hooks.items()
        }
    
    def list_hooks(self, event: str = None) -> List[Dict[str, Any]]:
        """
        列出已注册的钩子
        
        Args:
            event: 可选,只列出指定事件的钩子
        
        Returns:
            钩子信息列表
        """
        hooks = []
        
        events_to_list = [event] if event else HOOK_EVENTS
        
        for evt in events_to_list:
            if evt in self.hooks:
                for hook in self.hooks[evt]:
                    hooks.append({
                        'id': hook['id'],
                        'event': evt,
                        'matcher': hook['matcher'],
                        'priority': hook['priority'],
                        'handler': hook['handler'].__name__
                    })
        
        return hooks
    
    def clear_hooks(self, event: str = None):
        """
        清除钩子
        
        Args:
            event: 可选,只清除指定事件的钩子。如果不指定,清除所有钩子
        """
        if event:
            if event in self.hooks:
                count = len(self.hooks[event])
                self.hooks[event].clear()
                logger.info(f"清除 {event} 的 {count} 个钩子")
        else:
            for evt in HOOK_EVENTS:
                self.hooks[evt].clear()
            logger.info("清除所有钩子")
