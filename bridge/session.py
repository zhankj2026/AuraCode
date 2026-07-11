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
Bridge Session 核心实现

每个 BridgeSession 在独立线程中运行一个 AgentLoop 实例，
通过事件队列与外部通信，支持远程权限审批。
"""

import io
import os
import sys
import time
import uuid
import json
import queue
import logging
import threading
from typing import Any, Callable, Dict, List, Optional

from bridge.types import (
    BridgeEvent, BridgeEventType, SessionConfig, SessionInfo,
    SessionState, PermissionRequest, PermissionResponse, SessionActivity,
)
from core.session_store import SessionStore, auto_save_session

logger = logging.getLogger(__name__)


# ── Thread-safe stdout 捕获 ──────────────────────────────────────────────────

class ThreadLocalWriter(io.TextIOBase):
    """线程感知的 stdout 替换：每个线程的输出捕获到独立的 StringIO"""

    def __init__(self, original_stdout):
        super().__init__()
        self._original = original_stdout
        self._local = threading.local()

    def enable_capture(self):
        self._local.buffer = io.StringIO()

    def get_captured(self) -> str:
        buf = getattr(self._local, "buffer", None)
        if buf is None:
            return ""
        text = buf.getvalue()
        buf.truncate(0)
        buf.seek(0)
        return text

    def write(self, s: str) -> int:
        buf = getattr(self._local, "buffer", None)
        if buf is not None:
            return buf.write(s)
        return self._original.write(s)

    def flush(self):
        buf = getattr(self._local, "buffer", None)
        if buf is not None:
            buf.flush()
        self._original.flush()

    def fileno(self):
        return self._original.fileno()

    @property
    def encoding(self):
        return getattr(self._original, "encoding", "utf-8")

    def isatty(self):
        return False

    def readable(self):
        return False

    def writable(self):
        return True


# ── Thread-safe stderr 捕获 ──────────────────────────────────────────────────

class ThreadLocalErrWriter(io.TextIOBase):
    """线程感知的 stderr 替换：捕获 stderr 并维护 ring buffer"""

    MAX_LINES = 10  # ring buffer 大小

    def __init__(self, original_stderr):
        super().__init__()
        self._original = original_stderr
        self._local = threading.local()
        self._ring_lock = threading.Lock()
        self._ring: List[str] = []

    def enable_capture(self):
        self._local.buffer = io.StringIO()

    def get_captured(self) -> str:
        buf = getattr(self._local, "buffer", None)
        if buf is None:
            return ""
        text = buf.getvalue()
        buf.truncate(0)
        buf.seek(0)
        return text

    def write(self, s: str) -> int:
        buf = getattr(self._local, "buffer", None)
        if buf is not None:
            buf.write(s)
        ret = self._original.write(s)
        if s.strip():
            with self._ring_lock:
                self._ring.append(s.rstrip())
                if len(self._ring) > self.MAX_LINES:
                    self._ring = self._ring[-self.MAX_LINES:]
        return ret

    def flush(self):
        buf = getattr(self._local, "buffer", None)
        if buf is not None:
            buf.flush()
        self._original.flush()

    def fileno(self):
        return self._original.fileno()

    @property
    def encoding(self):
        return getattr(self._original, "encoding", "utf-8")

    def isatty(self):
        return False

    def get_ring_buffer(self) -> List[str]:
        """获取最近 stderr 行"""
        with self._ring_lock:
            return list(self._ring)


# ── 工具摘要映射 ──

TOOL_VERBS = {
    "read_file": "Reading", "write_file": "Writing",
    "replace_in_file": "Editing", "run_command": "Running",
    "run_powershell": "Running", "glob": "Searching",
    "grep": "Searching", "find": "Searching",
    "web_fetch": "Fetching", "web_search": "Searching",
    "notebook_edit": "Editing notebook", "lsp": "LSP",
    "todo_write": "Planning", "task_create": "Creating task",
    "task_update": "Updating task",
}


def _tool_summary(tool_name: str, arguments: Dict[str, Any]) -> str:
    """生成工具执行摘要"""
    verb = TOOL_VERBS.get(tool_name, tool_name)
    target = (
        arguments.get("file_path") or arguments.get("path")
        or arguments.get("pattern") or arguments.get("url")
        or arguments.get("query")
        or (arguments.get("command", "")[:60] if arguments.get("command") else "")
        or ""
    )
    return f"{verb} {target}".strip() if target else verb


# ── BridgePermissionManager ──────────────────────────────────────────────────

# 危险命令黑名单（复用 PermissionManager 的逻辑）
DANGEROUS_PATTERNS = [
    "rm -rf /", "rm -rf *", "sudo ", "shutdown", "reboot",
    "mkfs", "dd if=/dev/zero", ":(){ :|:& };:", "chmod 777 /",
    "chown -R root:root /",
]


class BridgePermissionManager:
    """
    Bridge 专用权限管理器。

    替代 stdin 交互确认，将权限请求发送到远程客户端并阻塞等待响应。
    """

    def __init__(
        self,
        session_id: str,
        mode: str,
        emit_event: Callable[[BridgeEvent], None],
    ):
        self.session_id = session_id
        self.mode = mode
        self._emit_event = emit_event

        # 挂起的权限请求: request_id -> (Event, response)
        self._pending: Dict[str, threading.Event] = {}
        self._responses: Dict[str, PermissionResponse] = {}
        self._lock = threading.Lock()

    def check_permission(self, tool_name: str, arguments: Dict[str, Any]) -> bool:
        """检查工具调用权限"""
        # 防线 1: 黑名单
        if tool_name == "run_command":
            command = arguments.get("command", "")
            for pattern in DANGEROUS_PATTERNS:
                if pattern.lower() in command.lower():
                    return False

        # 防线 2: bypass 模式直接通过
        if self.mode == "bypass":
            return True

        # 防线 3: plan 模式拒绝修改
        if self.mode == "plan":
            if tool_name in ("write_file", "run_command"):
                return False

        # 防线 4: auto 模式下文件操作自动通过，命令需审批
        if self.mode == "auto":
            if tool_name != "run_command":
                return True
            # run_command 仍需审批，继续往下走

        # normal 模式: write_file + run_command 需审批
        # auto 模式: 仅 run_command 需审批
        needs_review = tool_name in ("write_file", "run_command")
        if not needs_review:
            return True

        return self._request_remote_permission(tool_name, arguments)

    def _request_remote_permission(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> bool:
        """发送权限请求到远程客户端并阻塞等待"""
        request_id = str(uuid.uuid4())
        wait_event = threading.Event()

        # 构建描述
        if tool_name == "run_command":
            desc = f"执行命令: {arguments.get('command', '')[:200]}"
        else:
            desc = f"写入文件: {arguments.get('file_path', arguments.get('path', ''))}"

        perm_request = PermissionRequest(
            request_id=request_id,
            tool_name=tool_name,
            tool_input=arguments,
            description=desc,
        )

        with self._lock:
            self._pending[request_id] = wait_event

        # 推送权限请求事件
        self._emit_event(BridgeEvent(
            type=BridgeEventType.PERMISSION_REQUEST.value,
            session_id=self.session_id,
            data=perm_request.to_dict(),
        ))

        # 阻塞等待响应 (最多等 5 分钟)
        got_response = wait_event.wait(timeout=300)

        with self._lock:
            self._pending.pop(request_id, None)
            response = self._responses.pop(request_id, None)

        if not got_response or response is None:
            return False

        return response.behavior == "allow"

    def respond(self, request_id: str, behavior: str, message: str = ""):
        """响应权限请求（从外部线程调用）"""
        with self._lock:
            event = self._pending.get(request_id)
            if event:
                self._responses[request_id] = PermissionResponse(
                    request_id=request_id,
                    behavior=behavior,
                    message=message,
                )
                event.set()
                return True
        return False

    def cancel_all(self):
        """取消所有挂起的权限请求（会话停止时调用）"""
        with self._lock:
            for event in self._pending.values():
                event.set()
            self._pending.clear()
            self._responses.clear()


# ── BridgeSession ────────────────────────────────────────────────────────────

class BridgeSession:
    """
    Bridge 会话：在独立线程中运行 AgentLoop。

    线程安全：send_message / respond_permission / stop 可从任何线程调用。
    """

    def __init__(
        self,
        config: SessionConfig,
        event_callback: Callable[[BridgeEvent], None],
    ):
        self.config = config
        self.session_id = config.session_id
        self._event_callback = event_callback

        # 状态
        self.state = SessionState.IDLE
        self._stop_flag = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # 消息队列（线程安全）
        self._message_queue: queue.Queue[str] = queue.Queue()

        # 事件历史（含序列号支持重放）
        self._events: List[BridgeEvent] = []
        self._events_lock = threading.Lock()
        self._event_seq = 0  # 事件序列号（单调递增）

        # 权限管理器（在 _init_agent_loop 中创建）
        self._perm_manager: Optional[BridgePermissionManager] = None

        # AgentLoop（在线程中初始化）
        self._agent_loop = None
        self._init_error: Optional[str] = None

        # 统计
        self.created_at = time.time()
        self.last_activity = 0.0
        self.title = ""
        self._round_count = 0  # 已处理的消息轮次数
        self._session_store = SessionStore()  # 会话持久化

        # 活动追踪
        self.current_activity: Optional[Dict[str, Any]] = None
        self._recent_activities: List[SessionActivity] = []  # ring buffer, max 10
        self._activities_lock = threading.Lock()

        # stderr 捕获（ring buffer）
        self._err_writer: Optional[ThreadLocalErrWriter] = None

        # 超时看门狗
        self._watchdog_thread: Optional[threading.Thread] = None

    # ── 公共方法 ─────────────────────────────────────────────────────

    def start(self):
        """启动会话线程"""
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name=f"bridge-{self.session_id[:8]}"
        )
        self._thread.start()

    def send_message(self, content: str):
        """发送用户消息（线程安全）"""
        if self._stop_flag.is_set():
            raise RuntimeError("Session is stopped")
        self._message_queue.put(content)

    def respond_permission(self, request_id: str, behavior: str, message: str = "") -> bool:
        """回复权限请求"""
        if self._perm_manager:
            return self._perm_manager.respond(request_id, behavior, message)
        return False

    def stop(self, timeout: float = 5.0):
        """停止会话"""
        self._stop_flag.set()
        if self._perm_manager:
            self._perm_manager.cancel_all()
        # 放入哨兵值唤醒阻塞的线程
        self._message_queue.put(None)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        self.state = SessionState.COMPLETED
        self._emit(BridgeEvent(
            type=BridgeEventType.SESSION_STOPPED.value,
            session_id=self.session_id,
            data={"reason": "stopped"},
        ))

    def interrupt(self) -> bool:
        """
        中断当前正在执行的 turn（不终止会话线程）。

        参考标准实现 interrupt control_request。
        如果 AgentLoop 正在运行 run()，会触发 abort；
        run() 返回后清除 abort 标志，会话保持 IDLE 等待下一条消息。
        """
        if self._stop_flag.is_set():
            return False
        if self.state != SessionState.RUNNING:
            return False  # 空闲中无需中断
        if self._agent_loop and not self._agent_loop.is_aborted():
            self._agent_loop.abort()
            self._emit(BridgeEvent(
                type=BridgeEventType.INTERRUPTED.value,
                session_id=self.session_id,
                data={"message": "Current turn interrupted"},
            ))
            return True
        return False

    def switch_model(self, new_model: str) -> bool:
        """
        热切换模型（仅在会话空闲时生效）。

        参考标准实现 set_model control_request。
        """
        if self.state != SessionState.IDLE:
            return False  # 正在运行中不能切换
        if not self._agent_loop:
            return False
        old_model = self._agent_loop.model
        if old_model == new_model:
            return False
        self._agent_loop.model = new_model
        self.config.model = new_model  # 同步配置
        self._emit(BridgeEvent(
            type=BridgeEventType.MODEL_CHANGED.value,
            session_id=self.session_id,
            data={"old_model": old_model, "new_model": new_model},
        ))
        logger.info(f"Model switched: {old_model} → {new_model}")
        return True

    def _setup_ask_user_callback(self):
        """
        设置 ask_user 工具的回调。

        当 ask_user 工具被调用时，发送一个特殊的权限请求事件到前端，
        前端显示问题选择框让用户选择。
        """
        try:
            from tools.builtin.ask_user import set_ask_user_callback

            def ask_user_bridge_callback(question, options, multi_select=False):
                """Bridge 模式下的 ask_user 回调"""
                request_id = str(uuid.uuid4())
                wait_event = threading.Event()

                # 构建权限请求
                perm_request = PermissionRequest(
                    request_id=request_id,
                    tool_name="ask_user",
                    tool_input={
                        "question": question,
                        "options": options,
                        "multi_select": multi_select,
                    },
                    description=question,
                )

                # 注册等待
                with self._perm_manager._lock:
                    self._perm_manager._pending[request_id] = wait_event

                # 发送事件到前端
                self._emit(BridgeEvent(
                    type=BridgeEventType.PERMISSION_REQUEST.value,
                    session_id=self.session_id,
                    data=perm_request.to_dict(),
                ))

                # 阻塞等待用户响应（最多 5 分钟）
                got_response = wait_event.wait(timeout=300)

                if not got_response:
                    # 超时
                    with self._perm_manager._lock:
                        if request_id in self._perm_manager._pending:
                            del self._perm_manager._pending[request_id]
                    return "超时"

                # 获取响应
                with self._perm_manager._lock:
                    response = self._perm_manager._responses.pop(request_id, None)
                    if request_id in self._perm_manager._pending:
                        del self._perm_manager._pending[request_id]

                if response and response.behavior == "allow":
                    # 用户选择了选项
                    return response.message or "用户选择: Other"
                else:
                    return "用户取消"

            set_ask_user_callback(ask_user_bridge_callback)
            logger.info("ask_user callback registered for Bridge session")
        except ImportError:
            logger.warning("Failed to import ask_user module")
        except Exception as e:
            logger.warning(f"Failed to setup ask_user callback: {e}")

    def _setup_cron_callback(self):
        """
        设置 Cron 调度器的回调。

        当 Cron 任务触发时，将 prompt 发送到 AgentLoop 执行，
        并将执行结果通过事件推送到前端。
        """
        try:
            from tools.builtin.cron_tool import get_cron_scheduler

            def cron_bridge_callback(job):
                """Bridge 模式下的 cron 回调"""
                logger.info(f"[Cron Bridge] Firing job {job.job_id}: {job.prompt[:50]}...")
                
                # 发送 cron 任务触发事件
                self._emit(BridgeEvent(
                    type="cron_triggered",
                    session_id=self.session_id,
                    data={
                        "job_id": job.job_id,
                        "prompt": job.prompt,
                        "cron": job.cron,
                    },
                ))
                
                # 将 prompt 发送到 AgentLoop 执行
                if self._agent_loop:
                    try:
                        result = self._agent_loop.run(job.prompt)
                        logger.info(f"[Cron Bridge] Job {job.job_id} completed")
                        
                        # 发送执行完成事件
                        self._emit(BridgeEvent(
                            type="cron_completed",
                            session_id=self.session_id,
                            data={
                                "job_id": job.job_id,
                                "success": True,
                                "summary": result.summary[:100] if result.summary else "done",
                            },
                        ))
                    except Exception as e:
                        logger.error(f"[Cron Bridge] Job {job.job_id} failed: {e}")
                        self._emit(BridgeEvent(
                            type="cron_completed",
                            session_id=self.session_id,
                            data={
                                "job_id": job.job_id,
                                "success": False,
                                "error": str(e),
                            },
                        ))

            scheduler = get_cron_scheduler()
            scheduler.register_callback(cron_bridge_callback)
            logger.info("Cron callback registered for Bridge session")
        except ImportError:
            logger.warning("Failed to import cron_tool module")
        except Exception as e:
            logger.warning(f"Failed to setup cron callback: {e}")

    def get_info(self) -> SessionInfo:
        """获取会话摘要"""
        with self._activities_lock:
            activity = self.current_activity.copy() if self.current_activity else None
        return SessionInfo(
            session_id=self.session_id,
            state=self.state,
            work_dir=self.config.work_dir,
            model=self.config.model,
            created_at=self.created_at,
            event_count=len(self._events),
            last_activity=self.last_activity,
            title=self.title,
            current_activity=activity,
            round_count=self._round_count,
        )

    def get_events(self, since: int = 0) -> List[Dict[str, Any]]:
        """获取事件历史（支持从指定序列号重放）"""
        with self._events_lock:
            return [e.to_dict() for e in self._events[since:]]

    def get_event_count(self) -> int:
        """获取当前事件总数"""
        with self._events_lock:
            return len(self._events)

    def replay_events(self, from_seq: int) -> List[Dict[str, Any]]:
        """重放从指定序列号开始的所有事件（断线重连用）"""
        with self._events_lock:
            if from_seq >= len(self._events):
                return []
            events = [e.to_dict() for e in self._events[from_seq:]]
            logger.info(
                f"Event replay: seq {from_seq} → {len(self._events)} "
                f"({len(events)} events)"
            )
            return events

    @property
    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ── 内部方法 ─────────────────────────────────────────────────────

    def _emit(self, event: BridgeEvent):
        """记录事件并回调（含序列号）"""
        with self._events_lock:
            self._event_seq += 1
            event.data['_seq'] = self._event_seq
            self._events.append(event)
        self.last_activity = time.time()
        try:
            self._event_callback(event)
        except Exception:
            pass

    def _init_agent_loop(self):
        """在线程中初始化 AgentLoop"""
        # 切换工作目录
        original_dir = os.getcwd()
        try:
            if self.config.work_dir and os.path.isdir(self.config.work_dir):
                # 确保 work_dir 是绝对路径
                abs_work_dir = os.path.abspath(self.config.work_dir)
                logger.info(f"Bridge session: work_dir={self.config.work_dir}, abs_work_dir={abs_work_dir}")
                os.chdir(abs_work_dir)
                logger.info(f"Bridge session: changed to {abs_work_dir}, cwd={os.getcwd()}")

            # 设置环境变量供 AgentLoop 使用
            if self.config.api_key:
                os.environ["OPENAI_API_KEY"] = self.config.api_key
            if self.config.base_url:
                os.environ["OPENAI_BASE_URL"] = self.config.base_url

            from core.agent_loop import AgentLoop

            # api_key / base_url 优先用会话配置，其次从环境变量读取
            api_key = self.config.api_key or os.environ.get("OPENAI_API_KEY")
            base_url = self.config.base_url or os.environ.get("OPENAI_BASE_URL")

            logger.info(
                f"Init AgentLoop: model={self.config.model}, "
                f"api_key={'set(' + api_key[:8] + '...)' if api_key else 'MISSING'}, "
                f"base_url={base_url or 'default'}"
            )

            # 使用绝对路径作为 project_root
            config = {
                "api_key": api_key,
                "base_url": base_url,
                "model": self.config.model,
                "max_iterations": self.config.max_iterations,
                "permission_mode": self.config.permission_mode,
                "enable_plugins": False,  # Bridge 模式关闭插件减少开销
                "enable_hooks": True,
                "enable_skills": True,
                "active_skills": [],
                "project_root": abs_work_dir if self.config.work_dir else os.getcwd(),  # 工具文件操作的基准路径
            }
            logger.info(f"Bridge session: config.project_root={config['project_root']}")

            self._agent_loop = AgentLoop(config)

            # 注册 AgentLoop 事件回调 → 实时推送到 Bridge WebSocket
            self._agent_loop.event_callback = self._on_agent_event

            # 设置 ask_user 工具的回调（通过权限请求机制发送到前端）
            self._setup_ask_user_callback()

            # 注册 Cron 调度器回调（将任务执行结果推送到前端）
            self._setup_cron_callback()

            # 替换权限管理器为 Bridge 专用版
            self._perm_manager = BridgePermissionManager(
                session_id=self.session_id,
                mode=self.config.permission_mode,
                emit_event=self._emit,
            )
            self._agent_loop.permission_manager = self._perm_manager

        finally:
            os.chdir(original_dir)

    def _run_loop(self):
        """线程主函数：消息循环"""
        # 安装线程感知的 stdout 捕获
        writer = ThreadLocalWriter(sys.stdout)
        old_stdout = sys.stdout
        sys.stdout = writer

        # 安装 stderr 捕获（ring buffer）
        err_writer = ThreadLocalErrWriter(sys.stderr)
        old_stderr = sys.stderr
        sys.stderr = err_writer
        self._err_writer = err_writer

        try:
            # 初始化 AgentLoop
            self._init_agent_loop()

            self._emit(BridgeEvent(
                type=BridgeEventType.SESSION_STARTED.value,
                session_id=self.session_id,
                data={"model": self.config.model, "work_dir": self.config.work_dir},
            ))

            # 启动超时看门狗
            self._watchdog_thread = threading.Thread(
                target=self._watchdog_loop, daemon=True,
                name=f"watchdog-{self.session_id[:8]}",
            )
            self._watchdog_thread.start()

            # 消息处理循环
            while not self._stop_flag.is_set():
                try:
                    # 阻塞等待消息，每 1 秒检查一次停止标志
                    message = self._message_queue.get(timeout=1.0)
                except queue.Empty:
                    continue

                if message is None:
                    break  # 哨兵值

                self._process_message(message, writer)

        except Exception as e:
            logger.error(f"Bridge session {self.session_id} error: {e}", exc_info=True)
            self.state = SessionState.FAILED
            self._emit(BridgeEvent(
                type=BridgeEventType.SESSION_ERROR.value,
                session_id=self.session_id,
                data={"error": str(e)},
            ))
        finally:
            # 退出前持久化会话
            self._save_session_on_exit()
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            if self.state not in (SessionState.COMPLETED, SessionState.FAILED):
                self.state = SessionState.COMPLETED

    def _watchdog_loop(self):
        """超时看门狗：定期检测空闲时间，超时自动停止会话"""
        while not self._stop_flag.is_set():
            # 每 60 秒检查一次
            if not self._stop_flag.wait(timeout=60.0):
                pass  # 超时继续检查
            else:
                break  # stop_flag 被设置

            timeout = self.config.session_timeout
            if timeout <= 0:
                continue  # 0 = 不超时

            idle_seconds = time.time() - self.last_activity
            if idle_seconds > timeout:
                logger.warning(
                    f"Session {self.session_id} timed out after "
                    f"{idle_seconds:.0f}s idle (timeout={timeout}s)"
                )
                self.stop()
                break

    def _save_session_on_exit(self):
        """退出时持久化会话到 ~/.auracode/sessions/"""
        try:
            if not self._agent_loop:
                return
            state = self._agent_loop.state
            if not state.messages:
                return

            status = "completed" if self.state != SessionState.FAILED else "error"

            meta = auto_save_session(
                store=self._session_store,
                messages=state.messages,
                model=self.config.model,
                turn_count=self._round_count,
                total_tokens=state.total_usage.total_tokens,
                total_cost_usd=state.total_cost_usd,
                status=status,
                session_id=self.session_id,
            )
            if meta:
                logger.info(
                    f"Bridge session saved: {self.session_id} "
                    f"({meta.message_count} msgs, {self._round_count} rounds)"
                )
                # 发射会话归档事件
                self._emit(BridgeEvent(
                    type=BridgeEventType.SESSION_ARCHIVED.value,
                    session_id=self.session_id,
                    data={
                        "message_count": meta.message_count,
                        "total_tokens": state.total_usage.total_tokens,
                        "status": status,
                    },
                ))
        except Exception as e:
            logger.warning(f"Bridge session save failed: {e}")

    def _process_message(self, content: str, writer: ThreadLocalWriter):
        """处理一条用户消息"""
        self.state = SessionState.RUNNING

        # 发射用户消息事件
        self._emit(BridgeEvent(
            type=BridgeEventType.USER_MESSAGE.value,
            session_id=self.session_id,
            data={"content": content},
        ))

        # 设置标题（取第一条消息的前 50 字符）
        if not self.title:
            self.title = content[:50].strip()

        # 启用 stdout 捕获
        writer.enable_capture()

        try:
            # 记录运行前的消息数量（用于 diff）
            pre_msg_count = len(self._agent_loop.messages) if self._agent_loop else 0

            # 运行 AgentLoop
            result = self._agent_loop.run(content)
            self._round_count += 1

            # 清除中断标志（如果有），为下一轮 run 做准备
            if self._agent_loop.is_aborted():
                self._agent_loop.state.clear_abort()

            # 提取新增的消息并生成事件
            new_messages = self._agent_loop.messages[pre_msg_count:]
            self._extract_events(new_messages)

            # 捕获的 stdout 输出
            output = writer.get_captured()
            if output.strip():
                self._emit(BridgeEvent(
                    type=BridgeEventType.OUTPUT.value,
                    session_id=self.session_id,
                    data={"text": output.strip()},
                ))

            # stderr 捕获
            if self._err_writer:
                stderr_lines = self._err_writer.get_ring_buffer()
                if stderr_lines:
                    self._emit(BridgeEvent(
                        type=BridgeEventType.OUTPUT.value,
                        session_id=self.session_id,
                        data={"text": "\n".join(stderr_lines), "stream": "stderr"},
                    ))

            # 提取 QueryResult 结构化信息
            result_data = {"success": True}
            if result:
                result_data["result"] = result.text or ""
                result_data["status"] = result.status
                result_data["stop_reason"] = result.stop_reason
                result_data["num_turns"] = result.num_turns
                result_data["duration_ms"] = result.duration_ms
                # 将 LLM 生成的会话总结透传给前端
                if getattr(result, 'summary', None):
                    result_data["summary"] = result.summary
            else:
                result_data["result"] = ""

            # 轮次完成事件
            # 注意：一轮完成 ≠ 会话结束。会话保持 IDLE 等待下一条用户消息。
            self.state = SessionState.IDLE
            self._clear_activity()
            self._emit(BridgeEvent(
                type=BridgeEventType.RESULT.value,
                session_id=self.session_id,
                data=result_data,
            ))

        except Exception as e:
            logger.error(f"Message processing failed: {e}", exc_info=True)
            output = writer.get_captured()
            if output.strip():
                self._emit(BridgeEvent(
                    type=BridgeEventType.OUTPUT.value,
                    session_id=self.session_id,
                    data={"text": output.strip()},
                ))
            # 清除中断标志
            if self._agent_loop and self._agent_loop.is_aborted():
                self._agent_loop.state.clear_abort()
            self.state = SessionState.IDLE
            self._clear_activity()
            self._emit(BridgeEvent(
                type=BridgeEventType.RESULT.value,
                session_id=self.session_id,
                data={"result": "", "success": False, "error": str(e)},
            ))

    def _on_agent_event(self, event: Dict[str, Any]):
        """
        AgentLoop 事件回调处理器。

        将 AgentLoop._emit_event() 发出的事件转换为 BridgeEvent 并推送到 WebSocket。
        事件在 run() 执行过程中实时触发，无需等待整轮完成。
        同时维护活动追踪 ring buffer。
        """
        event_type = event.get("type", "")
        event_data = event.get("data", {})

        # 映射 AgentLoop 事件类型到 BridgeEventType
        type_map = {
            "turn_start": BridgeEventType.TURN_START,
            "turn_complete": BridgeEventType.TURN_COMPLETE,
            "tool_execute": BridgeEventType.TOOL_EXECUTE,
            "tool_complete": BridgeEventType.TOOL_COMPLETE,
            "context_compacted": BridgeEventType.CONTEXT_COMPACTED,
            "fallback_activated": BridgeEventType.FALLBACK_ACTIVATED,
            "prompt_too_long_recovery": BridgeEventType.PROMPT_TOO_LONG_RECOVERY,
            "aborted": BridgeEventType.ABORTED,
            "llm_call": BridgeEventType.LLM_CALL,
            "text_chunk": BridgeEventType.TEXT_CHUNK,  # Token 级流式
        }

        bridge_type = type_map.get(event_type)
        if bridge_type:
            self._emit(BridgeEvent(
                type=bridge_type.value,
                session_id=self.session_id,
                data={
                    **event_data,
                    "turn": event.get("turn", 0),
                },
            ))
            logger.debug(f"Agent event → Bridge: {event_type} turn={event.get('turn')}")

        # ── 活动追踪 ──
        if event_type == "tool_execute":
            tool_name = event_data.get("tool_name", "")
            arguments = event_data.get("arguments", {})
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except (json.JSONDecodeError, TypeError):
                    arguments = {}
            summary = _tool_summary(tool_name, arguments)
            activity = SessionActivity(type="tool_start", summary=summary)
            self._push_activity(activity)

        elif event_type == "tool_complete":
            tool_name = event_data.get("tool_name", "")
            activity = SessionActivity(
                type="result",
                summary=f"{tool_name} completed",
            )
            self._push_activity(activity)
            self._clear_activity()

        elif event_type == "turn_complete":
            self._clear_activity()

    def _push_activity(self, activity: SessionActivity):
        """推入活动 ring buffer 并更新 current_activity"""
        with self._activities_lock:
            self.current_activity = activity.to_dict()
            self._recent_activities.append(activity)
            if len(self._recent_activities) > 10:
                self._recent_activities = self._recent_activities[-10:]

    def _clear_activity(self):
        """清除当前活动"""
        with self._activities_lock:
            self.current_activity = None

    def _extract_events(self, messages: List[Dict[str, Any]]):
        """从 AgentLoop 新增的消息中提取事件（后置补充，与实时回调互补）"""
        for msg in messages:
            role = msg.get("role", "")

            if role == "assistant":
                content = msg.get("content", "")
                if content:
                    self._emit(BridgeEvent(
                        type=BridgeEventType.ASSISTANT_MESSAGE.value,
                        session_id=self.session_id,
                        data={"content": content},
                    ))
                # 工具调用
                tool_calls = msg.get("tool_calls", [])
                for tc in tool_calls:
                    func = tc.get("function", {})
                    self._emit(BridgeEvent(
                        type=BridgeEventType.TOOL_CALL.value,
                        session_id=self.session_id,
                        data={
                            "tool_call_id": tc.get("id", ""),
                            "tool_name": func.get("name", ""),
                            "arguments": func.get("arguments", ""),
                        },
                    ))

            elif role == "tool":
                self._emit(BridgeEvent(
                    type=BridgeEventType.TOOL_RESULT.value,
                    session_id=self.session_id,
                    data={
                        "tool_call_id": msg.get("tool_call_id", ""),
                        "content": msg.get("content", ""),
                    },
                ))
