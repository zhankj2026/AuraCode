"""
服务模块

提供诊断追踪、会话摘要等后台服务。
"""

from services.diagnostic_tracker import DiagnosticTracker, get_diagnostic_tracker
from services.away_summary import AwaySummaryService, get_away_summary_service, generate_away_summary
from services.tip_system import TipScheduler, Tip, TipContext, get_tip_scheduler, BUILTIN_TIPS

__all__ = [
    "DiagnosticTracker", "get_diagnostic_tracker",
    "AwaySummaryService", "get_away_summary_service", "generate_away_summary",
    "TipScheduler", "Tip", "TipContext", "get_tip_scheduler", "BUILTIN_TIPS",
]
