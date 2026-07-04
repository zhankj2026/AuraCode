#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2026 zhankj
#
# This source code is licensed under the [ Apache-2.0] license.
# For the full license text, please refer to the LICENSE file in the root directory.
#
# Author: zhankj <creating2018@aliyun.com>
# Project Homepage: http://www.auracode.top
#

"""
Hook 管理器 - 工具执行钩子系统

基于 code.md Phase 4 实现
参考: 第 6.2 节

增强功能:
- 中间件管道: before/after 中间件转换数据
- 热重载: 文件监听自动重载配置
- 错误隔离: Hook 失败不影响系统 + 健康追踪
"""

import asyncio
import os
import time
import logging
import threading
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
    增强: 中间件管道 + 热重载 + 错误隔离
    """

    def __init__(self):
        """初始化钩子管理器"""
        # 按事件类型组织钩子
        self.hooks: Dict[str, List[Dict[str, Any]]] = {
            event: [] for event in HOOK_EVENTS
        }
        self._hook_count = 0

        # 中间件管道
        self._middlewares: List[Dict[str, Any]] = []

        # 错误隔离与健康追踪
        self._error_count = 0
        self._last_error: Optional[str] = None

        # 热重载
        self._watcher_thread: Optional[threading.Thread] = None
        self._watcher_stop: Optional[threading.Event] = None
        self._watcher_path: Optional[str] = None
        self._watcher_interval: float = 5.0
        self._reload_callback: Optional[Callable] = None

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
            event: 钩子事件类型
            handler: 钩子处理函数
            matcher: 可选,只匹配特定工具名称
            priority: 优先级,数字越大越先执行

        Returns:
            钩子 ID
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
        self.hooks[event].sort(key=lambda h: h['priority'], reverse=True)

        matcher_info = f" (匹配: {matcher})" if matcher else ""
        logger.info(f"注册钩子: {event}{matcher_info} [ID: {hook_id}, 优先级: {priority}]")

        return hook_id

    def unregister_hook(self, hook_id: int) -> bool:
        """删除钩子"""
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
            钩子执行结果
        """
        if event not in HOOK_EVENTS:
            raise ValueError(f"无效的钩子事件: {event}")

        if 'tool_name' not in kwargs:
            kwargs['tool_name'] = tool_name

        event_hooks = self.hooks.get(event, [])

        # 执行 before 中间件
        if self._middlewares:
            kwargs = await self._run_middlewares('before', event, tool_name, kwargs)

        if not event_hooks:
            # 即使无钩子也执行 after 中间件
            if self._middlewares:
                kwargs = await self._run_middlewares('after', event, tool_name, kwargs)
            return HookResult(allow=True)

        logger.debug(f"执行钩子: {event} (共 {len(event_hooks)} 个)")

        for hook in event_hooks:
            if hook['matcher'] and hook['matcher'] != tool_name:
                continue

            try:
                handler = hook['handler']

                if asyncio.iscoroutinefunction(handler):
                    result = await handler(**kwargs)
                else:
                    result = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: handler(**kwargs)
                    )

                if not isinstance(result, HookResult):
                    logger.warning(f"钩子处理函数应返回 HookResult 实例")
                    continue

                if not result.allow:
                    logger.warning(
                        f"钩子阻止执行: {event} "
                        f"(原因: {result.block_reason})"
                    )
                    return result

                if result.short_circuit:
                    logger.debug(
                        f"钩子触发短路: {event} [ID: {hook['id']}]"
                    )
                    return result

                if result.modified_input:
                    kwargs.update(result.modified_input)

            except Exception as e:
                logger.error(f"钩子执行失败: {event} [ID: {hook['id']}]: {e}")
                self._error_count += 1
                self._last_error = f"{event}[{hook['id']}]: {e}"
                # 错误隔离: 钩子失败不阻止工具执行
                continue

        # 执行 after 中间件
        if self._middlewares:
            kwargs = await self._run_middlewares('after', event, tool_name, kwargs)

        return HookResult(allow=True)

    def get_hook_stats(self) -> Dict[str, int]:
        """获取钩子统计信息"""
        return {
            event: len(hooks)
            for event, hooks in self.hooks.items()
        }

    def list_hooks(self, event: str = None) -> List[Dict[str, Any]]:
        """列出已注册的钩子"""
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
        """清除钩子"""
        if event:
            if event in self.hooks:
                count = len(self.hooks[event])
                self.hooks[event].clear()
                logger.info(f"清除 {event} 的 {count} 个钩子")
        else:
            for evt in HOOK_EVENTS:
                self.hooks[evt].clear()
            logger.info("清除所有钩子")

    # ── 中间件管道 ─────────────────────────────────────────────────────

    def register_middleware(
        self,
        phase: str,
        handler: Callable,
        priority: int = 0,
    ) -> int:
        """
        注册中间件

        中间件在钩子执行前(before)或后(after)运行，可转换数据。

        Args:
            phase: 'before' 或 'after'
            handler: async def handler(event, tool_name, kwargs) -> dict
            priority: 优先级

        Returns:
            中间件 ID
        """
        if phase not in ('before', 'after'):
            raise ValueError(f"phase 必须是 'before' 或 'after'，当前: {phase}")

        mw_id = self._hook_count
        self._hook_count += 1

        mw = {
            'id': mw_id,
            'phase': phase,
            'handler': handler,
            'priority': priority,
        }
        self._middlewares.append(mw)
        self._middlewares.sort(key=lambda m: m['priority'], reverse=True)
        logger.info(f"注册中间件: {phase} [ID: {mw_id}, 优先级: {priority}]")
        return mw_id

    def unregister_middleware(self, mw_id: int) -> bool:
        """移除中间件"""
        for i, mw in enumerate(self._middlewares):
            if mw['id'] == mw_id:
                self._middlewares.pop(i)
                logger.info(f"移除中间件 [ID: {mw_id}]")
                return True
        return False

    async def _run_middlewares(self, phase: str, event: str, tool_name: str, kwargs: dict) -> dict:
        """执行中间件管道"""
        for mw in self._middlewares:
            if mw['phase'] != phase:
                continue
            try:
                handler = mw['handler']
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(event, tool_name, kwargs)
                else:
                    result = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: handler(event, tool_name, kwargs)
                    )
                if isinstance(result, dict):
                    kwargs.update(result)
            except Exception as e:
                logger.warning(f"中间件执行失败 [ID: {mw['id']}]: {e}")
                self._error_count += 1
        return kwargs

    # ── 错误隔离与健康追踪 ─────────────────────────────────────────────

    def get_health(self) -> Dict[str, Any]:
        """获取 Hook 系统健康状态"""
        total_hooks = sum(len(h) for h in self.hooks.values())
        return {
            'total_hooks': total_hooks,
            'total_middlewares': len(self._middlewares),
            'error_count': self._error_count,
            'last_error': self._last_error,
            'healthy': self._error_count < 10,
            'watcher_active': (
                self._watcher_thread is not None
                and self._watcher_thread.is_alive()
            ),
        }

    def reset_health(self):
        """重置健康计数器"""
        self._error_count = 0
        self._last_error = None

    # ── 热重载支持 ─────────────────────────────────────────────────────

    def start_file_watcher(self, config_path: str, interval: float = 5.0):
        """
        启动文件监听线程，配置变更时自动重载

        Args:
            config_path: 配置文件路径
            interval: 检查间隔（秒）
        """
        if self._watcher_thread and self._watcher_thread.is_alive():
            logger.warning("文件监听已在运行")
            return

        self._watcher_path = config_path
        self._watcher_interval = interval
        self._watcher_stop = threading.Event()
        self._watcher_thread = threading.Thread(
            target=self._file_watcher_loop,
            daemon=True,
            name="hook-watcher"
        )
        self._watcher_thread.start()
        logger.info(f"Hook 文件监听已启动: {config_path} (每 {interval}s)")

    def stop_file_watcher(self):
        """停止文件监听"""
        if self._watcher_stop:
            self._watcher_stop.set()
        if self._watcher_thread and self._watcher_thread.is_alive():
            self._watcher_thread.join(timeout=3.0)
        logger.info("Hook 文件监听已停止")

    def _file_watcher_loop(self):
        """文件监听循环"""
        last_mtime = 0
        if self._watcher_path and os.path.exists(self._watcher_path):
            last_mtime = os.path.getmtime(self._watcher_path)

        while not self._watcher_stop.is_set():
            self._watcher_stop.wait(timeout=self._watcher_interval)
            if self._watcher_stop.is_set():
                break

            try:
                if self._watcher_path and os.path.exists(self._watcher_path):
                    current_mtime = os.path.getmtime(self._watcher_path)
                    if current_mtime > last_mtime:
                        logger.info(f"检测到配置变更，触发重载: {self._watcher_path}")
                        last_mtime = current_mtime
                        self._trigger_reload()
            except Exception as e:
                logger.warning(f"文件监听异常: {e}")

    def _trigger_reload(self):
        """触发配置重载（通过回调）"""
        if self._reload_callback:
            try:
                self._reload_callback()
                logger.info("Hook 配置重载成功")
            except Exception as e:
                logger.error(f"Hook 配置重载失败: {e}")
                self._error_count += 1
                self._last_error = str(e)

    def set_reload_callback(self, callback: Callable):
        """设置重载回调（由 HookConfigLoader 注册）"""
        self._reload_callback = callback
