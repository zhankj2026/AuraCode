#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core.loop.file_tracker — 文件操作追踪 / 自动验证 / 历史

职责：
    - track_file_operation   追踪文件读写，为 ContextCollapse 建立依赖图
    - auto_validate_after_change  代码修改后后台自动验证
    - track_file_history     写入前自动备份（file-history）
    - record_history         记录本轮交互到全局 history.jsonl

``_cc_file_ops`` 是与 ``ContextManager`` 共享的状态（本类写、ContextManager 读），
因此挂在 ``loop`` 上而非本类实例。
"""

import logging
import os
import threading
from typing import Any, Dict

from core.tool_categories import FILE_WRITE_TOOLS

logger = logging.getLogger(__name__)


class FileChangeTracker:
    """追踪文件变更、自动验证与历史记录。"""

    # 读类工具
    _CC_READ_TOOLS = {"read_file", "grep", "find", "glob", "analyze_file"}
    # 写类工具（统一引用 core.tool_categories.FILE_WRITE_TOOLS）
    _CC_WRITE_TOOLS = FILE_WRITE_TOOLS

    # 写入类工具集合（用于 file-history 自动备份）
    _FILE_WRITE_TOOLS = FILE_WRITE_TOOLS

    def __init__(self, loop):
        self.loop = loop

    def track_file_operation(self, tool_name: str, arguments: Dict[str, Any]):
        """追踪文件读写操作，为 ContextCollapse 建立依赖图。"""
        loop = self.loop
        if not hasattr(loop, '_cc_file_ops'):
            loop._cc_file_ops = []  # [(msg_index, op_type, file_path)]

        path = arguments.get("path") or arguments.get("file_path", "")
        if not path:
            return

        abs_path = os.path.abspath(path)
        msg_idx = len(loop.state.messages)  # 即将添加的 tool 消息索引

        if tool_name in self._CC_READ_TOOLS:
            loop._cc_file_ops.append((msg_idx, "read", abs_path))
        elif tool_name in self._CC_WRITE_TOOLS:
            loop._cc_file_ops.append((msg_idx, "write", abs_path))

    def auto_validate_after_change(self, tool_name: str, arguments: Dict[str, Any]):
        """
        代码修改后自动验证

        在 write_file/edit_file/search_replace 执行后，
        异步运行验证，如果发现问题会通知用户。
        """
        loop = self.loop
        # 检查是否启用自动验证
        if not getattr(loop, '_auto_validate_enabled', True):
            return

        # 获取修改的文件路径
        file_path = arguments.get("path") or arguments.get("file_path", "")
        if not file_path:
            return

        # 只验证代码文件
        ext = os.path.splitext(file_path)[1].lower()
        code_extensions = {".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".java", ".cpp", ".c"}
        if ext not in code_extensions:
            return

        # 在后台线程中运行验证（避免阻塞主流程）
        def run_validation():
            try:
                from core.validator import get_validator
                validator = get_validator(loop.project_root)
                result = validator.validate([file_path], run_tests=False)

                if not result.passed:
                    # 验证失败，发出事件通知
                    error_summary = "; ".join(result.errors[:3])
                    logger.warning(f"Auto-validation failed for {file_path}: {error_summary}")
                    loop.events.emit("validation_failed", {
                        "file_path": file_path,
                        "errors": result.errors[:5],
                        "summary": error_summary,
                    })
                else:
                    logger.debug(f"Auto-validation passed for {file_path}")
            except Exception as e:
                logger.warning(f"Auto-validation error: {e}")

        # 启动后台验证线程
        thread = threading.Thread(target=run_validation, daemon=True)
        thread.start()

    def record_history(self, user_input: str, result) -> None:
        """记录本轮交互到全局 history.jsonl"""
        loop = self.loop
        try:
            from services.history_log import get_history_log
            history = get_history_log()

            # 提取工具使用列表
            tools_used = []
            if hasattr(loop, '_cc_file_ops'):
                for _, op_type, _ in loop._cc_file_ops:
                    if op_type == "write":
                        tools_used.append("write_file")

            # 提取助手摘要
            assistant_summary = ""
            if result and hasattr(result, 'text') and result.text:
                assistant_summary = result.text

            status = "success"
            if result and hasattr(result, 'status'):
                status = result.status or "success"

            duration_ms = 0
            if result and hasattr(result, 'duration_ms'):
                duration_ms = result.duration_ms or 0

            session_id = getattr(loop, '_session_id', '') or str(id(loop))[:8]

            history.append(
                session_id=session_id,
                model=loop.state.get_active_model(loop.model) or loop.model,
                user_prompt=user_input,
                assistant_summary=assistant_summary,
                turn_count=loop.state.turn_count,
                status=status,
                tokens_used=result.total_tokens if result and hasattr(result, 'total_tokens') else 0,
                duration_ms=duration_ms,
                tools_used=list(set(tools_used)),
                work_dir=loop.project_root,
            )
        except Exception as e:
            logger.debug(f"History log record failed: {e}")

    def track_file_history(self, tool_name: str, arguments: Dict[str, Any]) -> None:
        """在文件写入前自动备份（file-history）"""
        loop = self.loop
        if tool_name not in self._FILE_WRITE_TOOLS:
            return
        file_path = arguments.get("path") or arguments.get("file_path", "")
        if not file_path:
            return
        try:
            from services.file_history import get_file_history
            fh = get_file_history()
            fh.track_edit(
                file_path=file_path,
                message_index=len(loop.state.messages),
                turn=loop.state.turn_count,
            )
        except Exception as e:
            logger.debug(f"File history track failed: {e}")
