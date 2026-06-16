"""
服务模块

提供诊断追踪、会话摘要、全局历史、设置管理、文件历史等后台服务。
"""

from services.diagnostic_tracker import DiagnosticTracker, get_diagnostic_tracker
from services.away_summary import AwaySummaryService, get_away_summary_service, generate_away_summary
from services.tip_system import TipScheduler, Tip, TipContext, get_tip_scheduler, BUILTIN_TIPS
from services.history_log import HistoryLog, HistoryEntry, get_history_log
from services.settings_store import SettingsStore, get_settings_store
from services.file_history import FileHistory, FileBackup, Snapshot, get_file_history

__all__ = [
    "DiagnosticTracker", "get_diagnostic_tracker",
    "AwaySummaryService", "get_away_summary_service", "generate_away_summary",
    "TipScheduler", "Tip", "TipContext", "get_tip_scheduler", "BUILTIN_TIPS",
    "HistoryLog", "HistoryEntry", "get_history_log",
    "SettingsStore", "get_settings_store",
    "FileHistory", "FileBackup", "Snapshot", "get_file_history",
]
