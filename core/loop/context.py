#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core.loop.context — 协作者共享上下文契约

拆分采用「组合 + 传递 loop」模式：每个协作者在构造时接收 ``AgentLoop``
实例（``loop``），通过它访问共享可变状态（``loop.state`` / ``loop.client`` /
``loop.tools`` …）并调用兄弟协作者（``loop.events.emit()`` /
``loop.file_tracker.track_file_history()`` …）。

``LoopContext`` 是一个 ``typing.Protocol``，仅用于：

1. 文档化协作者依赖的 ``loop`` 表面（类型检查 / IDE 提示）；
2. 作为未来进一步解耦（把共享状态抽成独立 dataclass）的接缝。

运行时协作者**不**导入本模块，也不导入 ``AgentLoop``——这保证了依赖无环：
``agent_loop.py`` → 各协作者 → ``retry`` / ``llm_client`` 等底层模块。

旧方法 → 新位置映射表（供对照）：

    错误分类/重试（纯函数, core/loop/retry.py）
        _extract_status_code      -> extract_status_code
        _classify_error           -> classify_error
        _is_transient_error       -> is_transient_error
        _is_rate_limit_error      -> is_rate_limit_error
        _is_server_error          -> is_server_error
        _get_retry_wait           -> get_retry_wait
        _extract_retry_after      -> extract_retry_after
        _extract_wait_hint        -> extract_wait_hint

    EventEmitter (core/loop/events.py)
        _emit_event               -> emit
        _emit_text_chunk          -> emit_text_chunk
        _fire_lifecycle_hook      -> fire_lifecycle_hook
        _write_llm_log            -> write_llm_log
        _build_result_metadata    -> build_result_metadata
        _trigger_auto_memory_extraction -> trigger_auto_memory_extraction

    SystemPromptBuilder (core/loop/prompt_builder.py)
        _build_system_prompt      -> build_system_prompt
        _init_messages            -> init_messages
        _build_environment_context-> build_environment_context
        _build_memory_context(_legacy) / _base_role / _get_*_section /
        _tools_description / _security_rules / _build_context_management_guidance
        _is_git_repository / _get_git_status_snapshot / _get_git_status_detailed

    LLMClient (core/loop/llm_client.py)
        _call_llm_streaming       -> call_streaming
        _call_llm                 -> call
        _try_fix_json             -> LLMClient.try_fix_json (静态)
        StreamResult / _StreamToolCall (数据类)

    ToolExecutor (core/loop/tool_executor.py)
        _execute_tool             -> execute
        _trigger_failure_hook / _trigger_tool_error_hook (私有, 同类)

    ContextManager (core/loop/context_manager.py)
        _compact_messages         -> compact
        _image_strip / _snip_old_tool_results / _compact_messages_llm /
        _microcompact / _microcompact_old_tool_inputs / _find_tool_name_for_result /
        _context_collapse

    FileChangeTracker (core/loop/file_tracker.py)
        _track_file_operation     -> track_file_operation
        _auto_validate_after_change -> auto_validate_after_change
        _record_history           -> record_history
        _track_file_history       -> track_file_history

    SessionPersistence (core/loop/persistence.py)
        _apply_project_config     -> apply_project_config
        _get_session_memory_context -> get_session_memory_context
        _inject_session_env       -> inject_session_env
        _transcript_record_user/assistant/tool/cost -> transcript_record_*
        _update_session_memory_turn -> update_session_memory_turn
        _close_session_persistence -> close

留在 AgentLoop（core/agent_loop.py）：
    __init__ / _init_extensions / messages 属性 / run / _run_inner /
    _build_programmatic_summary / abort / is_aborted /
    activate_skill / deactivate_skill / list_skills / list_active_skills /
    register_hook / unregister_hook / list_hooks / list_plugins / get_system_status
"""

from typing import TYPE_CHECKING, Any, List, Optional

if TYPE_CHECKING:  # 仅类型检查时启用，避免运行时循环导入
    from openai import OpenAI

    from core.session_state import SessionState
    from permissions.manager import PermissionManager
    from core.loop.events import EventEmitter
    from core.loop.prompt_builder import SystemPromptBuilder
    from core.loop.llm_client import LLMClient
    from core.loop.tool_executor import ToolExecutor
    from core.loop.context_manager import ContextManager
    from core.loop.file_tracker import FileChangeTracker
    from core.loop.persistence import SessionPersistence
    from core.loop.extension_facade import ExtensionFacade
    from core.loop.summary import SummaryBuilder
    from core.loop.tool_dispatcher import ToolDispatcher
    from core.loop.orchestrator import LoopOrchestrator


class LoopContext:
    """
    协作者依赖的 ``loop`` 表面（结构化协议）。

    ``AgentLoop`` 实例在结构上满足该协议；协作者以 ``loop: "AgentLoop"``
    的形式持有引用。此处仅作契约文档，不在运行时强制。
    """

    # ── 共享可变状态 / 不变配置 ──
    state: "SessionState"
    client: "OpenAI"
    tools: List[Any]
    model: str
    max_tokens: int
    project_root: str
    work_dir: str
    max_iterations: Optional[int]
    max_budget_tokens: Optional[int]
    max_budget_usd: Optional[float]
    context_compact_threshold: int
    max_output_recovery_limit: int

    # ── 扩展系统 ──
    hooks_enabled: bool
    plugins_enabled: bool
    skills_enabled: bool
    memory_enabled: bool
    hook_manager: Any
    plugin_loader: Any
    skill_manager: Any
    memory_manager: Any
    auto_memory_extractor: Any
    permission_manager: "PermissionManager"
    tool_enhancer: Any
    event_callback: Optional[Any]

    # ── 会话持久化服务（SessionPersistence 持有） ──
    _session_transcript: Any
    _session_memory: Any
    _session_env: Any
    _project_store: Any

    # ── ContextCollapse 共享状态（FileChangeTracker 写, ContextManager 读） ──
    _cc_file_ops: List[Any]

    # ── 兄弟协作者（装配后回填） ──
    events: "EventEmitter"
    prompt_builder: "SystemPromptBuilder"
    llm_client: "LLMClient"
    tool_executor: "ToolExecutor"
    context_manager: "ContextManager"
    file_tracker: "FileChangeTracker"
    persistence: "SessionPersistence"
    extensions: "ExtensionFacade"
    summary_builder: "SummaryBuilder"
    tool_dispatcher: "ToolDispatcher"
    orchestrator: "LoopOrchestrator"
