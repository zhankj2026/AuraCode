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
服务模块

提供诊断追踪、会话摘要、全局历史、设置管理、文件历史、
JSONL转录、会话记忆、项目配置、会话环境、任务存储等后台服务。
"""

from services.diagnostic_tracker import DiagnosticTracker, get_diagnostic_tracker
from services.away_summary import AwaySummaryService, get_away_summary_service, generate_away_summary
from services.tip_system import TipScheduler, Tip, TipContext, get_tip_scheduler, BUILTIN_TIPS
from services.history_log import HistoryLog, HistoryEntry, get_history_log
from services.settings_store import SettingsStore, get_settings_store
from services.file_history import FileHistory, FileBackup, Snapshot, get_file_history
from services.session_transcript import (
    SessionTranscript, TranscriptEntry,
    init_transcript, get_transcript, close_transcript,
    list_session_transcripts,
)
from services.session_memory import (
    SessionMemory,
    init_session_memory, get_session_memory, close_session_memory,
)
from services.project_store import ProjectStore, ProjectConfig, get_project_store
from services.session_env import SessionEnv, init_session_env, get_session_env, close_session_env
from services.task_store import TaskStore, Task, get_task_store

__all__ = [
    "DiagnosticTracker", "get_diagnostic_tracker",
    "AwaySummaryService", "get_away_summary_service", "generate_away_summary",
    "TipScheduler", "Tip", "TipContext", "get_tip_scheduler", "BUILTIN_TIPS",
    "HistoryLog", "HistoryEntry", "get_history_log",
    "SettingsStore", "get_settings_store",
    "FileHistory", "FileBackup", "Snapshot", "get_file_history",
    # 会话存储新模块
    "SessionTranscript", "TranscriptEntry",
    "init_transcript", "get_transcript", "close_transcript",
    "list_session_transcripts",
    "SessionMemory",
    "init_session_memory", "get_session_memory", "close_session_memory",
    "ProjectStore", "ProjectConfig", "get_project_store",
    "SessionEnv", "init_session_env", "get_session_env", "close_session_env",
    "TaskStore", "Task", "get_task_store",
]
