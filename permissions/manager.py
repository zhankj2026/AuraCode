"""
权限管理器

实现五道防线安全机制:
1. 黑名单检查 - 拦截危险命令(最高优先级)
2. Deny 规则匹配 - 参数级模式拒绝
3. Allow 规则匹配 - 参数级模式放行
4. Plan 模式拦截 - 禁止所有修改操作
5. 用户确认 - normal 模式下需手动批准

支持 4 种权限模式: normal/auto/plan/bypass
支持工具级权限粒度控制（按参数模式匹配 fnmatch）
支持权限审批队列（远程/批量审批）
"""

import fnmatch
import sys
import os
import time
import uuid
import threading
import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


# ── 权限规则与审批数据类 ────────────────────────────────────────────


@dataclass
class PermissionRule:
    """权限规则"""
    pattern: str          # 格式: tool_name:arg_pattern (如 run_command:git status*)
    rule_type: str        # allow / deny
    source: str = "user"  # user / config / runtime
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def matches(self, tool_name: str, arguments: Dict[str, Any]) -> bool:
        """检查规则是否匹配工具调用"""
        if ':' not in self.pattern:
            # 仅工具名匹配
            return fnmatch.fnmatch(tool_name, self.pattern)
        rule_tool, rule_pattern = self.pattern.split(':', 1)
        if not fnmatch.fnmatch(tool_name, rule_tool):
            return False
        if rule_pattern == '*':
            return True
        # 参数匹配：检查 command / file_path / path 等关键参数
        for key in ('command', 'file_path', 'path', 'pattern', 'content'):
            val = arguments.get(key, '')
            if isinstance(val, str) and fnmatch.fnmatch(val, rule_pattern):
                return True
        return False


@dataclass
class ApprovalRequest:
    """权限审批请求"""
    request_id: str
    tool_name: str
    arguments: Dict[str, Any]
    reason: str = ""
    created_at: float = field(default_factory=time.time)
    resolved: bool = False
    decision: Optional[str] = None  # allow / deny / timeout
    timeout_sec: float = 300.0


class PermissionManager:
    """
    权限管理器 - 实现五道防线

    防线 1: 黑名单检查(任何模式都生效)
    防线 2: Deny 规则匹配(参数级模式拒绝)
    防线 3: Allow 规则匹配(参数级模式放行)
    防线 4: Plan 模式拦截
    防线 5: 用户确认(normal 模式)
    """

    # 危险命令黑名单
    DANGEROUS_PATTERNS = [
        "rm -rf /",
        "rm -rf *",
        "sudo ",
        "shutdown",
        "reboot",
        "mkfs",
        "dd if=/dev/zero",
        "> /dev/sd",
        ":(){ :|:& };:",  # Fork bomb
        "chmod 777 /",
        "chown -R root:root /"
    ]

    def __init__(self, mode: str = "normal"):
        """
        初始化权限管理器

        Args:
            mode: 权限模式(normal/auto/plan/bypass)
        """
        valid_modes = ["normal", "auto", "plan", "bypass"]
        if mode not in valid_modes:
            raise ValueError(f"无效的权限模式: {mode},必须是 {valid_modes}")

        self.mode = mode
        self._interactive_enabled = self._check_interactive_available()
        if not self._interactive_enabled:
            logger.warning("交互式输入不可用，将自动拒绝需要确认的操作。"
                         "请设置环境变量 AUTO_CONFIRM=true 来自动允许，或使用 auto/bypass 模式。")

        # ── 参数级规则 ──
        self._rules: List[PermissionRule] = []
        self._rules_lock = threading.Lock()

        # ── 审批队列 ──
        self._pending_approvals: Dict[str, Tuple[ApprovalRequest, threading.Event]] = {}
        self._approval_history: List[ApprovalRequest] = []
        self._approval_lock = threading.Lock()

        # ── 统计数据 ──
        self._stats = {"allowed": 0, "denied": 0, "rule_denied": 0, "blacklisted": 0}

    def _check_interactive_available(self) -> bool:
        """检查交互式输入是否可用"""
        if os.environ.get("AUTO_CONFIRM", "").lower() == "true":
            return True
        try:
            return sys.stdin.isatty()
        except:
            return False

    def _get_user_confirmation(
        self, tool_name: str, prompt: str = "确认?"
    ) -> Optional[bool]:
        """获取用户确认（支持交互式输入和环境变量）"""
        auto_confirm = os.environ.get("AUTO_CONFIRM", "").lower()
        if auto_confirm == "true":
            logger.info(f"AUTO_CONFIRM=true，自动允许: {tool_name}")
            return True
        elif auto_confirm == "false":
            logger.info(f"AUTO_CONFIRM=false，自动拒绝: {tool_name}")
            return False

        if not self._interactive_enabled:
            return None

        try:
            sys.stdout.write(f"⚠️  执行 {tool_name}? {prompt} (y/N): ")
            sys.stdout.flush()
            line = sys.stdin.readline()
            if not line:
                return False
            confirm = line.strip().lower()
            return confirm == "y" or confirm == "yes"
        except EOFError:
            return False
        except KeyboardInterrupt:
            return False
        except Exception as e:
            logger.error(f"获取用户输入失败: {e}")
            return None

    def check_permission(self, tool_name: str, arguments: Dict[str, Any]) -> bool:
        """
        检查工具调用权限（五道防线）

        Args:
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            是否允许执行
        """
        # 防线 1: 命令黑名单检查(最高优先级,任何模式都拦截)
        if tool_name == "run_command":
            command = arguments.get("command", "")
            for pattern in self.DANGEROUS_PATTERNS:
                if pattern.lower() in command.lower():
                    print(f"[Security] ❌ 阻止危险命令: {command[:50]}...")
                    self._stats["blacklisted"] += 1
                    self._stats["denied"] += 1
                    return False

        # 防线 2: Deny 规则匹配（参数级模式拒绝）
        with self._rules_lock:
            for rule in self._rules:
                if rule.rule_type == "deny" and rule.matches(tool_name, arguments):
                    print(f"[Deny Rule] ❌ 规则拒绝: {rule.pattern}")
                    self._stats["rule_denied"] += 1
                    self._stats["denied"] += 1
                    return False

        # 防线 2.5: Allow 规则匹配（参数级模式放行，跳过后续检查）
        with self._rules_lock:
            for rule in self._rules:
                if rule.rule_type == "allow" and rule.matches(tool_name, arguments):
                    logger.debug(f"Allow rule matched: {rule.pattern}")
                    self._stats["allowed"] += 1
                    return True

        # 防线 3: Bypass 模式直接通过(黑名单之后)
        if self.mode == "bypass":
            self._stats["allowed"] += 1
            return True

        # 防线 4: Plan 模式拒绝所有修改操作
        if self.mode == "plan":
            if tool_name in ["write_file", "run_command", "replace_in_file",
                             "run_powershell", "notebook_edit"]:
                print(f"[Plan Mode] ❌ 阻止修改操作: {tool_name}")
                self._stats["denied"] += 1
                return False

        # 防线 5: 用户确认(normal 模式需要确认写入和命令)
        _WRITE_TOOLS = {"write_file", "run_command", "replace_in_file",
                        "run_powershell", "notebook_edit"}
        if self.mode == "normal":
            if tool_name in _WRITE_TOOLS:
                confirm = self._get_user_confirmation(tool_name, "确认?")
                if confirm is False:
                    print("用户取消操作")
                    self._stats["denied"] += 1
                    return False
                elif confirm is None:
                    print(f"⚠️  无法获取用户确认，拒绝操作: {tool_name}")
                    print(f"   提示: 设置环境变量 AUTO_CONFIRM=true 来自动允许")
                    logger.warning(f"权限拒绝: {tool_name} (无法获取用户确认)")
                    self._stats["denied"] += 1
                    return False

        # Auto 模式: 文件操作自动通过,命令仍需确认
        if self.mode == "auto":
            if tool_name == "run_command":
                confirm = self._get_user_confirmation(tool_name, "执行命令?")
                if confirm is False:
                    self._stats["denied"] += 1
                    return False
                elif confirm is None:
                    print(f"⚠️  无法获取用户确认，拒绝操作: {tool_name}")
                    logger.warning(f"权限拒绝: {tool_name} (无法获取用户确认)")
                    self._stats["denied"] += 1
                    return False

        self._stats["allowed"] += 1
        return True

    def truncate_output(self, output: str, max_lines: int = 500) -> str:
        """输出截断 - 防止上下文溢出"""
        lines = output.splitlines()
        if len(lines) <= max_lines:
            return output
        half = max_lines // 2
        truncated = (
            lines[:half] +
            [f"... (截断 {len(lines) - max_lines} 行) ..."] +
            lines[-half:]
        )
        return "\n".join(truncated)

    # ── 规则管理 API ─────────────────────────────────────────────────────

    def add_rule(self, rule_type: str, pattern: str, source: str = "runtime") -> PermissionRule:
        """添加权限规则"""
        if rule_type not in ('allow', 'deny'):
            raise ValueError(f"rule_type 必须是 allow 或 deny，当前: {rule_type}")
        rule = PermissionRule(pattern=pattern, rule_type=rule_type, source=source)
        with self._rules_lock:
            self._rules.append(rule)
        logger.info(f"权限规则已添加: [{rule_type}] {pattern}")
        return rule

    def remove_rule(self, pattern: str) -> bool:
        """移除指定模式的规则"""
        with self._rules_lock:
            for i, r in enumerate(self._rules):
                if r.pattern == pattern:
                    self._rules.pop(i)
                    logger.info(f"权限规则已移除: {pattern}")
                    return True
        return False

    def get_rules(self, rule_type: str = None) -> List[PermissionRule]:
        """获取规则列表"""
        with self._rules_lock:
            if rule_type:
                return [r for r in self._rules if r.rule_type == rule_type]
            return list(self._rules)

    def clear_rules(self):
        """清除所有自定义规则"""
        with self._rules_lock:
            self._rules.clear()
        logger.info("所有自定义权限规则已清除")

    def get_stats(self) -> Dict[str, int]:
        """获取权限统计"""
        return dict(self._stats)

    # ── 审批队列 API ─────────────────────────────────────────────────────

    def request_approval(
        self, tool_name: str, arguments: Dict[str, Any],
        reason: str = "", timeout: float = 300.0
    ) -> ApprovalRequest:
        """创建审批请求"""
        req = ApprovalRequest(
            request_id=str(uuid.uuid4()),
            tool_name=tool_name,
            arguments=arguments,
            reason=reason,
            timeout_sec=timeout,
        )
        wait_event = threading.Event()
        with self._approval_lock:
            self._pending_approvals[req.request_id] = (req, wait_event)
        return req

    def wait_approval(self, request_id: str, timeout: float = 300.0) -> str:
        """等待审批结果 (allow/deny/timeout)"""
        with self._approval_lock:
            item = self._pending_approvals.get(request_id)
        if not item:
            return "deny"
        req, wait_event = item
        resolved = wait_event.wait(timeout=timeout)
        with self._approval_lock:
            self._pending_approvals.pop(request_id, None)
            req.resolved = True
            req.decision = req.decision or ("allow" if resolved else "timeout")
            self._approval_history.append(req)
        return req.decision

    def respond_approval(self, request_id: str, decision: str, message: str = "") -> bool:
        """响应审批请求"""
        with self._approval_lock:
            item = self._pending_approvals.get(request_id)
        if not item:
            return False
        req, wait_event = item
        req.decision = decision
        wait_event.set()
        logger.info(f"审批响应: {request_id} → {decision}")
        return True

    def batch_approve(self, tool_name: str = None) -> int:
        """批量批准所有挂起的审批请求"""
        count = 0
        with self._approval_lock:
            for req, event in self._pending_approvals.values():
                if tool_name is None or req.tool_name == tool_name:
                    req.decision = "allow"
                    event.set()
                    count += 1
        return count

    def get_approval_history(self, limit: int = 20) -> List[ApprovalRequest]:
        """获取审批历史"""
        return self._approval_history[-limit:]

    def get_pending_count(self) -> int:
        """获取挂起的审批数量"""
        with self._approval_lock:
            return len(self._pending_approvals)
