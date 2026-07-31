#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core.loop — AgentLoop 的协作者子包

将原 ``core/agent_loop.py``（3423 行的 God Object）按职责拆分为若干
单一职责的协作者模块。``AgentLoop`` 退化为薄外壳（组合根 + 主循环编排 +
公共 API），具体逻辑委托给本包内的协作者：

    retry.py            错误分类与重试退避（纯函数）
    events.py           EventEmitter：事件回调 / 生命周期钩子 / LLM 日志 / 元数据
    prompt_builder.py   SystemPromptBuilder：系统提示词 7 层构建
    llm_client.py       LLMClient：流式 / 同步调用 + StreamResult
    tool_executor.py    ToolExecutor：钩子 / 权限 / 缓存 / 追踪 / 路径注入
    context_manager.py  ContextManager：多级上下文压缩
    file_tracker.py     FileChangeTracker：文件操作记录 / 自动验证 / 历史
    persistence.py      SessionPersistence：transcript / memory / env / project

协作者之间通过 ``loop``（AgentLoop 实例）共享状态与互相调用，避免循环导入。
"""

from core.loop.retry import (
    classify_error,
    is_transient_error,
    is_rate_limit_error,
    is_server_error,
    get_retry_wait,
    extract_status_code,
    extract_retry_after,
    extract_wait_hint,
)
from core.loop.events import EventEmitter
from core.loop.prompt_builder import SystemPromptBuilder
from core.loop.llm_client import LLMClient, StreamResult
from core.loop.tool_executor import ToolExecutor
from core.loop.context_manager import ContextManager
from core.loop.file_tracker import FileChangeTracker
from core.loop.persistence import SessionPersistence
from core.loop.extension_facade import ExtensionFacade
from core.loop.summary import SummaryBuilder
from core.loop.tool_dispatcher import ToolDispatcher
from core.loop.orchestrator import LoopOrchestrator

__all__ = [
    "classify_error",
    "is_transient_error",
    "is_rate_limit_error",
    "is_server_error",
    "get_retry_wait",
    "extract_status_code",
    "extract_retry_after",
    "extract_wait_hint",
    "EventEmitter",
    "SystemPromptBuilder",
    "LLMClient",
    "StreamResult",
    "ToolExecutor",
    "ContextManager",
    "FileChangeTracker",
    "SessionPersistence",
    "ExtensionFacade",
    "SummaryBuilder",
    "ToolDispatcher",
    "LoopOrchestrator",
]
