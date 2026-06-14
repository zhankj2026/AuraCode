"""
诊断追踪服务

参考 Claude Code 的 DiagnosticTrackingService 设计，
实现自动 LSP 错误追踪：在文件修改后自动获取编译/lint 诊断，
追踪新增错误并向用户报告。

功能:
1. 基线快照: 会话开始时记录所有文件的初始诊断状态
2. 增量追踪: 文件修改后重新获取诊断，对比基线
3. 新增错误检测: 识别修改引入的新错误
4. 错误报告: 生成人类可读的诊断报告

用法:
    tracker = DiagnosticTracker()
    tracker.set_baseline(file_path, diagnostics)
    new_errors = tracker.track_file_change(file_path, lsp_tool)
    report = tracker.generate_report()
"""

import os
import logging
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class Diagnostic:
    """单条诊断信息"""
    message: str
    severity: str        # Error / Warning / Info / Hint
    line: int = 0
    column: int = 0
    end_line: int = 0
    end_column: int = 0
    source: str = ""
    code: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message": self.message,
            "severity": self.severity,
            "line": self.line,
            "column": self.column,
            "source": self.source,
            "code": self.code,
        }

    @classmethod
    def from_lsp(cls, diag: Dict[str, Any]) -> "Diagnostic":
        """从 LSP diagnostic 格式转换"""
        rng = diag.get("range", {})
        start = rng.get("start", {})
        end = rng.get("end", {})
        return cls(
            message=diag.get("message", ""),
            severity=_severity_name(diag.get("severity", 1)),
            line=start.get("line", 0) + 1,  # LSP 0-based → 1-based
            column=start.get("character", 0) + 1,
            end_line=end.get("line", 0) + 1,
            end_column=end.get("character", 0) + 1,
            source=diag.get("source", ""),
            code=str(diag.get("code", "")),
        )


def _severity_name(level: int) -> str:
    """LSP severity number → name"""
    return {1: "Error", 2: "Warning", 3: "Info", 4: "Hint"}.get(level, "Unknown")


@dataclass
class FileChangeRecord:
    """文件变更记录"""
    file_path: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    baseline_errors: int = 0
    current_errors: int = 0
    new_errors: List[Diagnostic] = field(default_factory=list)
    fixed_errors: List[Diagnostic] = field(default_factory=list)


class DiagnosticTracker:
    """
    LSP 诊断追踪器

    追踪文件修改前后的诊断变化，
    识别修改引入的新错误。
    """

    def __init__(self):
        # 基线诊断: {file_path: [Diagnostic]}
        self._baseline: Dict[str, List[Diagnostic]] = {}
        # 当前诊断: {file_path: [Diagnostic]}
        self._current: Dict[str, List[Diagnostic]] = {}
        # 变更记录
        self._changes: List[FileChangeRecord] = []
        # 文件最后处理时间
        self._timestamps: Dict[str, str] = {}

    def set_baseline(self, file_path: str, diagnostics: List[Dict[str, Any]]):
        """设置文件基线诊断（会话开始时的状态）"""
        abs_path = os.path.abspath(file_path)
        parsed = [Diagnostic.from_lsp(d) for d in diagnostics]
        self._baseline[abs_path] = parsed
        self._current[abs_path] = list(parsed)
        logger.debug(f"Baseline set for {file_path}: {len(parsed)} diagnostics")

    def update_diagnostics(self, file_path: str, diagnostics: List[Dict[str, Any]]):
        """更新文件当前诊断"""
        abs_path = os.path.abspath(file_path)
        parsed = [Diagnostic.from_lsp(d) for d in diagnostics]
        self._current[abs_path] = parsed
        self._timestamps[abs_path] = datetime.now().isoformat()

    def track_file_change(self, file_path: str) -> FileChangeRecord:
        """
        追踪文件变更: 对比基线与当前诊断，识别新增/修复的错误。

        Returns:
            FileChangeRecord
        """
        abs_path = os.path.abspath(file_path)
        baseline = self._baseline.get(abs_path, [])
        current = self._current.get(abs_path, [])

        # 基线错误的特征集合 (message + line)
        baseline_keys = {(d.message, d.line) for d in baseline if d.severity == "Error"}
        current_keys = {(d.message, d.line) for d in current if d.severity == "Error"}

        # 新增错误 = 当前有但基线没有
        new_keys = current_keys - baseline_keys
        new_errors = [d for d in current if d.severity == "Error" and (d.message, d.line) in new_keys]

        # 修复错误 = 基线有但当前没有
        fixed_keys = baseline_keys - current_keys
        fixed_errors = [d for d in baseline if d.severity == "Error" and (d.message, d.line) in fixed_keys]

        record = FileChangeRecord(
            file_path=abs_path,
            baseline_errors=len(baseline_keys),
            current_errors=len(current_keys),
            new_errors=new_errors,
            fixed_errors=fixed_errors,
        )
        self._changes.append(record)

        logger.info(
            f"Tracked {file_path}: baseline={len(baseline_keys)}, "
            f"current={len(current_keys)}, "
            f"new={len(new_errors)}, fixed={len(fixed_errors)}"
        )
        return record

    async def auto_track_from_lsp(self, file_path: str, lsp_tool_func=None) -> Optional[FileChangeRecord]:
        """
        自动从 LSP 获取诊断并追踪变更。

        Args:
            file_path: 文件路径
            lsp_tool_func: LSP 工具函数（如 lsp_tool handler）

        Returns:
            FileChangeRecord 或 None
        """
        if not lsp_tool_func:
            return None

        try:
            result = lsp_tool_func(
                action="diagnostics",
                file_path=file_path,
            )
            if isinstance(result, str):
                import json
                diagnostics = json.loads(result)
            elif isinstance(result, dict):
                diagnostics = result.get("diagnostics", [])
            elif isinstance(result, list):
                diagnostics = result
            else:
                diagnostics = []

            self.update_diagnostics(file_path, diagnostics)
            return self.track_file_change(file_path)

        except Exception as e:
            logger.debug(f"Auto-track failed for {file_path}: {e}")
            return None

    def get_new_errors_summary(self) -> Dict[str, List[Diagnostic]]:
        """获取所有文件的新增错误汇总"""
        result = defaultdict(list)
        for change in self._changes:
            for err in change.new_errors:
                rel_path = os.path.basename(change.file_path)
                result[rel_path].append(err)
        return dict(result)

    def generate_report(self) -> str:
        """生成诊断追踪报告"""
        lines = []
        lines.append("📋 诊断追踪报告")
        lines.append("=" * 40)

        if not self._changes:
            lines.append("无文件变更记录")
            return "\n".join(lines)

        total_new = sum(len(c.new_errors) for c in self._changes)
        total_fixed = sum(len(c.fixed_errors) for c in self._changes)

        lines.append(f"文件变更: {len(self._changes)} 个")
        lines.append(f"新增错误: {total_new}")
        lines.append(f"修复错误: {total_fixed}")
        lines.append("")

        for change in self._changes:
            rel_path = os.path.basename(change.file_path)
            lines.append(f"  📄 {rel_path}")
            lines.append(f"     基线: {change.baseline_errors} 错误 → 当前: {change.current_errors} 错误")

            if change.new_errors:
                lines.append(f"     🔴 新增 {len(change.new_errors)} 个错误:")
                for err in change.new_errors[:5]:
                    lines.append(f"        L{err.line}: {err.message[:80]}")
                if len(change.new_errors) > 5:
                    lines.append(f"        ... 还有 {len(change.new_errors) - 5} 个")

            if change.fixed_errors:
                lines.append(f"     🟢 修复 {len(change.fixed_errors)} 个错误:")
                for err in change.fixed_errors[:3]:
                    lines.append(f"        L{err.line}: {err.message[:80]}")

            lines.append("")

        return "\n".join(lines)

    def get_stats(self) -> Dict[str, Any]:
        """统计信息"""
        return {
            "tracked_files": len(self._baseline),
            "total_changes": len(self._changes),
            "total_new_errors": sum(len(c.new_errors) for c in self._changes),
            "total_fixed_errors": sum(len(c.fixed_errors) for c in self._changes),
        }

    def reset(self):
        """重置所有追踪状态"""
        self._baseline.clear()
        self._current.clear()
        self._changes.clear()
        self._timestamps.clear()


# 全局实例
_tracker: Optional[DiagnosticTracker] = None


def get_diagnostic_tracker() -> DiagnosticTracker:
    """获取全局诊断追踪器"""
    global _tracker
    if _tracker is None:
        _tracker = DiagnosticTracker()
    return _tracker
