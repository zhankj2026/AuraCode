"""
会话记忆摘要 (Session Memory)

参考标准projects/{cwd}/{sessionId}/session-memory/summary.md
每个会话维护一个 Markdown 格式的摘要文件，用于:

1. 上下文压缩 (compact) — 用摘要替代旧消息，释放上下文窗口
2. 会话恢复 (resume) — 快速了解之前做了什么
3. 跨轮次连续性 — 记住当前任务进度

存储结构:
~/.auracode/projects/{sanitized-cwd}/{session_id}/session-memory/summary.md

何时保存:
- 每次 LLM 响应完成后（token 超过阈值时触发提取）
- compact 操作前（确保最新状态被记录）
- 会话退出时
"""

import os
import re
import logging
import threading
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


# ── 路径工具 ──

def _auracode_home() -> str:
    return os.path.join(os.path.expanduser("~"), ".auracode")


def _sanitize_path(path: str) -> str:
    normalized = os.path.normpath(os.path.abspath(path))
    if len(normalized) >= 2 and normalized[1] == ':':
        normalized = normalized[2:]
    sanitized = re.sub(r'[^a-zA-Z0-9]', '-', normalized)
    sanitized = re.sub(r'-+', '-', sanitized).strip('-')
    if len(sanitized) > 200:
        h = abs(hash(path)) % (16 ** 8)
        sanitized = f"{sanitized[:200]}-{h:08x}"
    return sanitized


def get_session_memory_dir(session_id: str, cwd: str) -> str:
    """获取会话记忆目录"""
    proj_dir = os.path.join(_auracode_home(), "projects", _sanitize_path(cwd))
    return os.path.join(proj_dir, session_id, "session-memory")


def get_session_memory_path(session_id: str, cwd: str) -> str:
    """获取 summary.md 路径"""
    return os.path.join(get_session_memory_dir(session_id, cwd), "summary.md")


# ── 摘要模板 ──

DEFAULT_TEMPLATE = """# Session Memory

_Current session progress and context. Updated automatically._

## Current Task

_What is the user currently working on?_


## Progress

_What has been accomplished so far?_


## Key Decisions

_Important architectural or design decisions made during this session._


## Open Issues

_Unresolved problems or blockers._


## Files Modified

_List of files created or modified during this session._

"""


# ── 会话记忆管理器 ──

class SessionMemory:
    """
    会话记忆管理器

    功能:
    - update(): 更新会话记忆（LLM 生成摘要）
    - read(): 读取当前记忆内容
    - is_empty(): 检查记忆是否为空模板
    - get_last_summarized_index(): 获取上次摘要覆盖到的消息索引
    """

    def __init__(self, session_id: str, cwd: str):
        self.session_id = session_id
        self.cwd = cwd
        self._memory_dir = get_session_memory_dir(session_id, cwd)
        self._memory_path = get_session_memory_path(session_id, cwd)
        self._last_summarized_index: int = -1
        self._last_update_tokens: int = 0
        self._lock = threading.Lock()
        self._extraction_in_progress = False

        # 确保目录存在
        os.makedirs(self._memory_dir, exist_ok=True)

        # 初始化文件（如果不存在）
        if not os.path.exists(self._memory_path):
            try:
                with open(self._memory_path, "w", encoding="utf-8") as f:
                    f.write(DEFAULT_TEMPLATE)
            except Exception as e:
                logger.warning(f"Failed to create session memory file: {e}")

        logger.debug(f"SessionMemory initialized: {self._memory_path}")

    def read(self) -> str:
        """读取当前记忆内容"""
        try:
            with open(self._memory_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.warning(f"Failed to read session memory: {e}")
            return ""

    def is_empty(self) -> bool:
        """检查记忆是否为空（仅有模板，无实际内容）"""
        content = self.read()
        if not content:
            return True
        # 去掉模板标题后检查是否有实际内容
        lines = content.strip().split("\n")
        for line in lines:
            line = line.strip()
            if (line
                    and not line.startswith("#")
                    and not line.startswith("_")
                    and not line.startswith("*")
                    and line != ""):
                return False
        return True

    def write(self, content: str) -> bool:
        """
        直接写入记忆内容（覆盖）

        Args:
            content: Markdown 格式的记忆内容

        Returns:
            是否写入成功
        """
        with self._lock:
            try:
                with open(self._memory_path, "w", encoding="utf-8") as f:
                    f.write(content)
                logger.info(f"Session memory updated ({len(content)} chars)")
                return True
            except Exception as e:
                logger.error(f"Failed to write session memory: {e}")
                return False

    def update_with_summary(
        self,
        messages: List[Dict[str, Any]],
        since_index: int,
        llm_client: Any = None,
        llm_model: str = "",
    ) -> bool:
        """
        使用 LLM 生成对话摘要并更新记忆文件。

        Args:
            messages: 当前对话消息列表
            since_index: 从哪条消息开始提取（之前的已被摘要过）
            llm_client: LLM 客户端（有 .chat_completion() 方法）
            llm_model: 模型名

        Returns:
            是否更新成功
        """
        if self._extraction_in_progress:
            return False

        new_messages = messages[since_index:]
        if len(new_messages) < 2:
            return False

        self._extraction_in_progress = True

        try:
            # 压缩消息为文本
            transcript = self._compress_messages(new_messages)
            current_memory = self.read()

            # 构建摘要提示
            prompt = self._build_summary_prompt(transcript, current_memory)

            # 调用 LLM 生成摘要
            if llm_client and hasattr(llm_client, "chat_completion"):
                response = llm_client.chat_completion(
                    model=llm_model,
                    messages=[
                        {"role": "system", "content": self._SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.3,
                    max_tokens=2000,
                )
                summary = self._extract_content(response)
            else:
                # 无 LLM 时生成简单摘要
                summary = self._simple_summary(new_messages)

            if summary:
                self.write(summary)
                self._last_summarized_index = len(messages) - 1
                self._last_update_tokens = sum(
                    len(str(m.get("content", ""))) // 4 for m in new_messages
                )
                return True

            return False

        except Exception as e:
            logger.warning(f"Session memory update failed: {e}")
            return False
        finally:
            self._extraction_in_progress = False

    @property
    def last_summarized_index(self) -> int:
        """上次摘要覆盖到的消息索引"""
        return self._last_summarized_index

    @last_summarized_index.setter
    def last_summarized_index(self, value: int):
        self._last_summarized_index = value

    @property
    def last_update_tokens(self) -> int:
        """上次更新时的 token 数"""
        return self._last_update_tokens

    # ── 内部方法 ──

    _SYSTEM_PROMPT = """You are a session memory manager. Your job is to create and maintain 
a concise summary of the current coding session.

Rules:
1. Preserve the section structure (## headers) from the template
2. Update each section with relevant information from the conversation
3. Keep it concise — focus on actionable information
4. Include file paths, function names, and key decisions
5. List any unresolved issues or blockers
6. If the current memory already has content, merge new information into it
7. Remove outdated information that's no longer relevant

Output the complete updated session memory in Markdown format."""

    def _build_summary_prompt(self, transcript: str, current_memory: str) -> str:
        """构建摘要请求"""
        parts = []
        if current_memory and not self.is_empty():
            parts.append(f"## Current Session Memory (update this):\n\n{current_memory}")
        parts.append(f"## New Conversation:\n\n{transcript}")
        parts.append("Please update the session memory with information from the new conversation.")
        return "\n\n---\n\n".join(parts)

    def _compress_messages(self, messages: List[Dict[str, Any]], max_chars: int = 8000) -> str:
        """压缩消息列表为文本摘要"""
        lines = []
        total_chars = 0

        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")

            if isinstance(content, list):
                # 多模态内容，取文本部分
                text_parts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text_parts.append(part.get("text", ""))
                content = " ".join(text_parts)

            content = str(content)

            # 截断过长的内容
            if len(content) > 1000:
                content = content[:1000] + "... [truncated]"

            line = f"**{role}**: {content}"
            if total_chars + len(line) > max_chars:
                lines.append(f"... [{len(messages) - len(lines)} more messages truncated]")
                break

            lines.append(line)
            total_chars += len(line)

        return "\n\n".join(lines)

    def _simple_summary(self, messages: List[Dict[str, Any]]) -> str:
        """无 LLM 时生成简单摘要"""
        user_messages = []
        assistant_actions = []
        files_modified = set()

        for msg in messages:
            role = msg.get("role", "")
            content = str(msg.get("content", ""))[:200]

            if role == "user" and content:
                user_messages.append(content)
            elif role == "assistant":
                # 提取工具调用
                tool_calls = msg.get("tool_calls", [])
                for tc in tool_calls:
                    fn = tc.get("function", {})
                    name = fn.get("name", "")
                    args = fn.get("arguments", "")
                    if name in ("write_file", "search_replace", "create_file"):
                        # 尝试提取文件路径
                        try:
                            import json
                            a = json.loads(args) if isinstance(args, str) else args
                            fp = a.get("path") or a.get("file_path", "")
                            if fp:
                                files_modified.add(fp)
                        except Exception:
                            pass
                    assistant_actions.append(f"{name}: {args[:100]}")

        # 构建摘要
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        lines = [
            f"# Session Memory",
            f"_Last updated: {now}_",
            "",
            "## Current Task",
        ]

        if user_messages:
            lines.append(f"User request: {user_messages[-1][:200]}")
        else:
            lines.append("_No task recorded yet._")

        lines.extend(["", "## Progress"])
        if assistant_actions:
            for action in assistant_actions[-10:]:
                lines.append(f"- {action}")
        else:
            lines.append("_No progress recorded yet._")

        lines.extend(["", "## Key Decisions", "_None recorded._"])
        lines.extend(["", "## Open Issues", "_None recorded._"])

        lines.extend(["", "## Files Modified"])
        if files_modified:
            for fp in sorted(files_modified):
                lines.append(f"- {fp}")
        else:
            lines.append("_No files modified._")

        return "\n".join(lines)

    def _extract_content(self, response: Any) -> str:
        """从 LLM 响应中提取内容"""
        if isinstance(response, dict):
            choices = response.get("choices", [])
            if choices:
                msg = choices[0].get("message", {})
                return msg.get("content", "")
        elif isinstance(response, str):
            return response
        return ""


# ── 全局单例 ──

_current_memory: Optional[SessionMemory] = None


def get_session_memory() -> Optional[SessionMemory]:
    """获取当前会话记忆实例"""
    return _current_memory


def init_session_memory(session_id: str, cwd: str) -> SessionMemory:
    """初始化当前会话记忆"""
    global _current_memory
    _current_memory = SessionMemory(session_id=session_id, cwd=cwd)
    return _current_memory


def close_session_memory():
    """关闭当前会话记忆"""
    global _current_memory
    _current_memory = None
