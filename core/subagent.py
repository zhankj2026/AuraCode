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
Subagent 管理器 - 并行任务执行 (增强版)

基于 code.md Phase 6 实现，参考 Subagents 设计
实现: 真实 LLM 调用、Fork 模式、结果压缩、Agent 定义文件
"""

import uuid
import threading
import logging
import json
import os
import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


# ── 父会话模型继承（线程局部）─────────────────────────────────────────────
# Subagent 默认继承父 AgentLoop 的当前模型。此前 spawn 链路硬编码 "glm-4-plus"，
# 当目标 API（如 LongCat）不支持该模型时，子代理会以 400 失败。
# AgentLoop 在执行工具前调用 set_current_model(self.model) 注入当前会话模型，
# spawn_subagent 在未显式指定 model 时通过 get_current_model() 继承。
_current_model_local = threading.local()


def set_current_model(model: str) -> None:
    """设置当前线程的"父会话模型"，供 Subagent 默认继承。"""
    _current_model_local.model = model


def get_current_model(default: str = "glm-4-plus") -> str:
    """获取当前线程的父会话模型；未设置时回退到 default。"""
    return getattr(_current_model_local, "model", None) or default


@dataclass
class SubagentHandle:
    """
    Subagent 句柄

    Attributes:
        agent_id: 唯一标识符
        thread: 执行线程
        task: 任务描述
        model: 使用的模型
        agent_type: Agent 类型 (explore/plan/review/general)
        result: 执行结果（压缩后的摘要）
        status: 状态(running/completed/failed/cancelled)
        created_at: 创建时间
        completed_at: 完成时间
        error: 错误信息
        fork_mode: 是否使用 fork 模式
    """
    agent_id: str
    thread: threading.Thread
    task: str
    model: str
    agent_type: str = "general"
    result: Optional[str] = None
    status: str = "running"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    error: Optional[str] = None
    fork_mode: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'agent_id': self.agent_id,
            'task': self.task[:100],  # 限制预览长度
            'model': self.model,
            'agent_type': self.agent_type,
            'status': self.status,
            'fork_mode': self.fork_mode,
            'created_at': self.created_at,
            'completed_at': self.completed_at,
            'result_preview': self.result[:200] if self.result and len(self.result) > 200 else self.result
        }


class AgentDefinition:
    """
    Agent 定义文件解析器

    解析 .auracode/agents/*.md 文件格式的 agent 定义
    """

    @staticmethod
    def parse_file(file_path: str) -> Dict[str, Any]:
        """
        解析 agent 定义文件

        文件格式:
        ---
        name: explore
        description: 搜索和理解代码库
        tools: Read, Grep, Glob
        disallowedTools: Write, Edit, Agent
        model: haiku
        omitProjectMd: true
        background: false
        ---

        Agent 具体提示词内容...

        Returns:
            包含 name, description, tools, disallowedTools, model, prompt, omitProjectMd, background 等的字典
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 解析 frontmatter
            frontmatter_match = re.match(r'^---\n(.*?)\n---\n(.*)$', content, re.DOTALL)
            if not frontmatter_match:
                logger.warning(f"Invalid agent definition format: {file_path}")
                return None

            frontmatter_text = frontmatter_match.group(1)
            prompt_text = frontmatter_match.group(2).strip()

            # 解析 frontmatter 字段
            metadata = {}
            for line in frontmatter_text.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip()
                    value = value.strip()
                    metadata[key] = value

            # 解析工具列表（支持逗号分隔）
            tools_str = metadata.get('tools', '[]')
            if tools_str == '""':
                tools_list = []
            elif tools_str.startswith('[') and tools_str.endswith(']'):
                # JSON 格式
                import json
                try:
                    tools_list = json.loads(tools_str)
                except:
                    tools_list = []
            elif tools_str == '"*"':
                tools_list = ['*']
            else:
                # 逗号分隔
                tools_list = [t.strip() for t in tools_str.split(',') if t.strip()]

            # 解析禁止工具列表
            disallowed_str = metadata.get('disallowedTools', '[]')
            if disallowed_str == '""':
                disallowed_list = []
            elif disallowed_str.startswith('[') and disallowed_str.endswith(']'):
                import json
                try:
                    disallowed_list = json.loads(disallowed_str)
                except:
                    disallowed_list = []
            else:
                disallowed_list = [t.strip() for t in disallowed_str.split(',') if t.strip()]

            # 解析布尔值
            def parse_bool(value: str) -> bool:
                if isinstance(value, bool):
                    return value
                if isinstance(value, str):
                    return value.lower() in ('true', 'yes', '1', 'on')
                return False

            return {
                'name': metadata.get('name', Path(file_path).stem),
                'description': metadata.get('description', ''),
                'tools': tools_list,
                'disallowedTools': disallowed_list,
                'model': metadata.get('model', 'sonnet'),
                'omitProjectMd': parse_bool(metadata.get('omitProjectMd', 'false')),
                'background': parse_bool(metadata.get('background', 'false')),
                'prompt': prompt_text,
                'file_path': file_path
            }

        except Exception as e:
            logger.error(f"Failed to parse agent file {file_path}: {e}")
            return None

    @staticmethod
    def load_agents_directory(directory: str = ".auracode/agents") -> Dict[str, Dict]:
        """
        加载目录中的所有 agent 定义

        Args:
            directory: agent 定义文件目录

        Returns:
            {agent_name: agent_definition} 字典
        """
        agents = {}
        agents_dir = Path(directory)

        if not agents_dir.exists():
            logger.debug(f"Agent directory not found: {directory}")
            return agents

        for md_file in agents_dir.glob("*.md"):
            agent_def = AgentDefinition.parse_file(str(md_file))
            if agent_def:
                agents[agent_def['name']] = agent_def
                logger.debug(f"Loaded agent definition: {agent_def['name']}")

        return agents


class SubagentManager:
    """
    Subagent 管理器 (增强版)

    改进:
    - 真实 LLM API 调用
    - Fork 模式支持
    - 结果自动压缩
    - Agent 定义文件支持
    """

    def __init__(self, max_concurrent: int = 5):
        """
        初始化 Subagent 管理器

        Args:
            max_concurrent: 最大并发数
        """
        self.agents: Dict[str, SubagentHandle] = {}
        self.max_concurrent = max_concurrent
        self._lock = threading.Lock()

        # 加载 agent 定义
        self.agent_definitions = AgentDefinition.load_agents_directory()

        # LLM 客户端配置
        self.api_key = os.environ.get("OPENAI_API_KEY")
        self.base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")

        if not self.api_key:
            logger.warning("OPENAI_API_KEY not set, subagents will use mock execution")

    def _get_llm_client(self):
        """获取 LLM 客户端"""
        try:
            from openai import OpenAI
            return OpenAI(api_key=self.api_key, base_url=self.base_url)
        except Exception as e:
            logger.error(f"Failed to create LLM client: {e}")
            return None

    def _compress_result(self, raw_result: str, task: str) -> str:
        """
        压缩子代理结果，只保留关键信息

        压缩策略:
        1. 提取结论、建议、错误等关键部分
        2. 保留代码片段和文件路径
        3. 丢弃冗余的搜索结果和中间日志

        Args:
            raw_result: 原始执行结果
            task: 任务描述

        Returns:
            压缩后的摘要
        """
        lines = raw_result.splitlines()

        # 关键标记词
        KEYWORDS = [
            "##", "###",  # 标题
            "结论", "建议", "发现",  # 中文关键词
            "conclusion", "recommend", "found",  # 英文关键词
            "错误", "失败", "warning", "error",  # 错误
            "file:", "path:", "line:",  # 文件引用
            "```",  # 代码块
            "**",  # 加粗（可能的关键信息）
        ]

        compressed_lines = []
        current_section = []
        in_code_block = False
        line_count = 0

        for i, line in enumerate(lines):
            # 检测代码块
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                compressed_lines.append(line)
                continue

            # 代码块内直接保留
            if in_code_block:
                compressed_lines.append(line)
                continue

            # 检查是否包含关键词
            has_keyword = any(kw in line.lower() for kw in KEYWORDS)

            if has_keyword:
                # 先缓存的内容
                if current_section:
                    # 只保留非空内容
                    non_empty = [l for l in current_section if l.strip()]
                    if len(non_empty) <= 5:  # 短段落全部保留
                        compressed_lines.extend(current_section)
                    else:  # 长段落只保留首尾
                        compressed_lines.append(current_section[0])
                        compressed_lines.append(f"... (省略 {len(current_section) - 2} 行) ...")
                        compressed_lines.append(current_section[-1])
                    current_section = []

                compressed_lines.append(line)
                line_count += 1
            else:
                current_section.append(line)

                # 每500行强制检查一次
                if len(current_section) >= 500:
                    # 保留重要的非空行
                    non_empty = [l for l in current_section if l.strip()]
                    if len(non_empty) > 50:
                        compressed_lines.append(f"... (省略 {len(current_section)} 行输出) ...")
                    current_section = []

        # 处理剩余内容
        if current_section:
            non_empty = [l for l in current_section if l.strip()]
            if len(non_empty) <= 10:
                compressed_lines.extend(current_section)
            elif non_empty:
                compressed_lines.append(current_section[0])
                compressed_lines.append(f"... (省略 {len(current_section) - 2} 行) ...")
                compressed_lines.append(current_section[-1])

        result = "\n".join(compressed_lines)

        # 添加元数据
        summary = f"# Subagent 执行摘要\n\n"
        summary += f"**任务**: {task[:100]}...\n\n"
        summary += f"**原始输出**: {len(raw_result)} 字符\n"
        summary += f"**压缩后**: {len(result)} 字符\n"
        summary += f"**压缩率**: {100 * (1 - len(result) / len(raw_result)):.1f}%\n\n"
        summary += "---\n\n"
        summary += result

        return summary

    def _execute_task(
        self,
        agent_id: str,
        task: str,
        model: str,
        agent_type: str,
        output_file: str,
        fork_mode: bool = False,
        parent_context: Dict = None,
        progress_callback: Optional[Callable] = None
    ):
        """
        在独立线程中执行任务 (改进版: 真实 LLM 调用)

        Args:
            agent_id: Agent ID
            task: 任务描述
            model: 模型名称
            agent_type: Agent 类型
            output_file: 输出文件路径
            fork_mode: 是否使用 fork 模式
            parent_context: 父会话上下文（fork 模式使用）
            progress_callback: 进度回调
        """
        client = None

        try:
            logger.info(f"Subagent {agent_id} ({agent_type}) 开始执行任务")

            # 构建消息历史
            if fork_mode and parent_context:
                # Fork 模式: 继承父会话上下文
                messages = parent_context.get("messages", []).copy()
                # 添加任务
                messages.append({
                    "role": "user",
                    "content": f"[Subagent Task] {task}"
                })
                logger.debug(f"Using fork mode with {len(messages)} messages from parent")
            else:
                # Fresh 模式: 只使用 agent 定义
                messages = []

                # 添加系统提示词
                if agent_type in self.agent_definitions:
                    agent_def = self.agent_definitions[agent_type]
                    messages.append({
                        "role": "system",
                        "content": agent_def.get('prompt', 'You are a helpful assistant.')
                    })
                else:
                    # 通用提示词
                    messages.append({
                        "role": "system",
                        "content": self._get_default_system_prompt()
                    })

                # 添加任务
                messages.append({
                    "role": "user",
                    "content": task
                })

            # 获取 LLM 客户端
            client = self._get_llm_client()

            if client:
                # 真实 LLM 调用
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.3,
                    max_tokens=4096
                )

                raw_result = response.choices[0].message.content or "No response"

                # 记录 token 使用
                if response.usage:
                    logger.info(f"Subagent {agent_id} token usage: "
                               f"prompt={response.usage.prompt_tokens}, "
                               f"completion={response.usage.completion_tokens}")

            else:
                # Mock 执行（用于测试）
                raw_result = self._mock_execution(task, agent_id, model, progress_callback)

            # 压缩结果
            compressed_result = self._compress_result(raw_result, task)

            # 保存到文件
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(compressed_result)

            # 更新状态
            with self._lock:
                if agent_id in self.agents:
                    self.agents[agent_id].result = compressed_result
                    self.agents[agent_id].status = "completed"
                    self.agents[agent_id].completed_at = datetime.now().isoformat()

            logger.info(f"Subagent {agent_id} 执行完成")

        except Exception as e:
            error_msg = f"Subagent {agent_id} 执行失败: {str(e)}"
            logger.error(error_msg, exc_info=True)

            with self._lock:
                if agent_id in self.agents:
                    self.agents[agent_id].error = str(e)
                    self.agents[agent_id].status = "failed"
                    self.agents[agent_id].completed_at = datetime.now().isoformat()

    def _get_default_system_prompt(self) -> str:
        """获取默认系统提示词"""
        return """You are a specialized sub-agent working on a specific task.

Your role:
1. Focus on the assigned task
2. Return structured, concise results
3. Highlight key findings, risks, and recommendations
4. Include file paths and line numbers for references

Return format:
- Start with key findings
- Include relevant code snippets or file references
- End with specific recommendations or next steps

Do NOT return raw search results or verbose logs."""

    def _mock_execution(
        self,
        task: str,
        agent_id: str,
        model: str,
        progress_callback: Optional[Callable]
    ) -> str:
        """模拟执行（当 LLM 不可用时）"""
        result_lines = [
            f"# Subagent 执行报告 (Mock 模式)",
            f"",
            f"**Agent ID**: {agent_id}",
            f"**任务**: {task}",
            f"**模型**: {model}",
            f"**开始时间**: {datetime.now().isoformat()}",
            f"",
            f"## 执行过程",
            f"",
        ]

        steps = [
            "分析任务需求",
            "收集相关信息",
            "制定执行计划",
            "执行具体操作",
            "验证结果",
        ]

        for i, step in enumerate(steps, 1):
            if progress_callback:
                progress_callback(agent_id, i, len(steps), step)

            result_lines.append(f"{i}. {step} ✓")

        result_lines.extend([
            f"",
            f"## 执行结果",
            f"",
            f"任务执行完成。",
            f"",
            f"**完成时间**: {datetime.now().isoformat()}",
        ])

        return "\n".join(result_lines)

    def spawn_subagent(
        self,
        task: str,
        model: str = None,
        agent_type: str = "general",
        run_in_background: bool = True,
        fork_mode: bool = False,
        parent_context: Dict = None,
        progress_callback: Optional[Callable] = None
    ) -> SubagentHandle:
        """
        创建子 Agent 执行任务

        Args:
            task: 任务描述
            model: 使用的模型名称
            agent_type: Agent 类型 (explore/plan/review/general等)
            run_in_background: 是否后台运行
            fork_mode: 是否继承父会话上下文
            parent_context: 父会话上下文（fork 模式使用）
            progress_callback: 进度回调

        Returns:
            SubagentHandle 句柄
        """
        # 继承父会话模型：未显式指定时使用当前线程模型（由 AgentLoop 注入）
        model = model or get_current_model()

        # 生成唯一 ID
        agent_id = str(uuid.uuid4())[:8]

        # 创建输出文件路径
        output_dir = os.path.join(os.getcwd(), '.subagent_output')
        output_file = os.path.join(output_dir, f"{agent_id}.md")

        # 创建线程
        thread = threading.Thread(
            target=self._execute_task,
            args=(
                agent_id, task, model, agent_type,
                output_file, fork_mode, parent_context, progress_callback
            ),
            daemon=True
        )

        # 创建句柄
        handle = SubagentHandle(
            agent_id=agent_id,
            thread=thread,
            task=task,
            model=model,
            agent_type=agent_type,
            fork_mode=fork_mode
        )

        # 检查并发数限制
        with self._lock:
            running_count = sum(
                1 for agent in self.agents.values()
                if agent.status == "running"
            )

            if running_count >= self.max_concurrent:
                raise RuntimeError(
                    f"达到最大并发数限制: {self.max_concurrent}\n"
                    f"请等待部分任务完成后再提交新任务"
                )

            # 注册
            self.agents[agent_id] = handle

        # 启动线程
        thread.start()

        logger.info(f"创建 Subagent: {agent_id}, 类型: {agent_type}, 任务: {task[:50]}...")

        # 同步运行则等待完成
        if not run_in_background:
            thread.join()

        return handle

    def join_subagent(self, agent_id: str, timeout: float = None) -> str:
        """等待 Subagent 完成并获取结果"""
        if agent_id not in self.agents:
            raise KeyError(f"Subagent 不存在: {agent_id}")

        handle = self.agents[agent_id]
        handle.thread.join(timeout=timeout)

        if handle.thread.is_alive():
            raise TimeoutError(f"Subagent {agent_id} 执行超时({timeout}秒)")

        if handle.status == "failed":
            return f"❌ Subagent 执行失败\n\n{handle.error}"

        return handle.result

    def get_agent_status(self, agent_id: str) -> Dict[str, Any]:
        """获取 Subagent 状态"""
        if agent_id not in self.agents:
            raise KeyError(f"Subagent 不存在: {agent_id}")

        return self.agents[agent_id].to_dict()

    def list_agents(self, status: str = None) -> List[Dict[str, Any]]:
        """列出所有 Subagent"""
        agents = [handle.to_dict() for handle in self.agents.values()]

        if status:
            agents = [a for a in agents if a['status'] == status]

        return agents

    def get_available_agent_types(self) -> List[str]:
        """获取可用的 Agent 类型"""
        types = list(self.agent_definitions.keys())
        # 只有当 "general" 不在定义中时才添加默认的通用类型
        if "general" not in types:
            types.append("general")
        return sorted(types)

    def get_agent_definition(self, agent_type: str) -> Optional[Dict]:
        """获取 Agent 定义"""
        return self.agent_definitions.get(agent_type)

    def get_stats(self) -> Dict[str, int]:
        """获取统计信息"""
        stats = {
            'total': len(self.agents),
            'running': 0,
            'completed': 0,
            'failed': 0,
            'cancelled': 0
        }

        for handle in self.agents.values():
            if handle.status in stats:
                stats[handle.status] += 1

        return stats

    def cancel_agent(self, agent_id: str) -> bool:
        """取消 Subagent"""
        if agent_id not in self.agents:
            return False

        handle = self.agents[agent_id]
        if handle.status != "running":
            return False

        handle.status = "cancelled"
        logger.warning(f"Subagent {agent_id} 标记为取消")
        return True

    def cleanup_finished(self, max_age_hours: float = 24):
        """清理已完成的 Subagent 记录"""
        from datetime import timedelta

        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)

        with self._lock:
            to_remove = []

            for agent_id, handle in self.agents.items():
                if handle.status in ['completed', 'failed', 'cancelled']:
                    if handle.completed_at:
                        completed_time = datetime.fromisoformat(handle.completed_at)
                        if completed_time < cutoff_time:
                            to_remove.append(agent_id)

            for agent_id in to_remove:
                del self.agents[agent_id]

            if to_remove:
                logger.info(f"清理 {len(to_remove)} 个已完成的 Subagent")


# 全局 Subagent 管理器实例
subagent_manager = SubagentManager(max_concurrent=5)


# ── 子代理间消息传递 ─────────────────────────────────────────

@dataclass
class AgentMessage:
    """子代理间消息"""
    sender: str          # 发送者 agent_id
    receiver: str        # 接收者 agent_id ("*" 表示广播)
    content: str         # 消息内容
    msg_type: str = "info"  # info/request/result/error
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class AgentMailbox:
    """
    子代理邮箱 — 支持代理间消息传递与协作

    功能:
    - send(): 发送消息到指定代理或广播
    - receive(): 获取指定代理的所有消息
    - request_and_wait(): 发送请求并等待响应
    - get_conversation(): 获取两个代理间的对话历史
    """

    def __init__(self):
        self._messages: Dict[str, List[AgentMessage]] = {}  # agent_id -> messages
        self._events: Dict[str, threading.Event] = {}  # msg_id -> event
        self._lock = threading.Lock()
        self._message_count = 0

    def send(self, sender: str, receiver: str, content: str,
             msg_type: str = "info") -> str:
        """
        发送消息

        Args:
            sender: 发送者 agent_id
            receiver: 接收者 agent_id ("*" 表示广播)
            content: 消息内容
            msg_type: 消息类型

        Returns:
            message_id
        """
        msg = AgentMessage(
            sender=sender, receiver=receiver,
            content=content, msg_type=msg_type
        )
        msg_id = f"msg_{self._message_count}"
        self._message_count += 1

        with self._lock:
            if receiver == "*":
                # 广播给所有已注册的代理
                for aid in self._messages:
                    if aid != sender:
                        self._messages[aid].append(msg)
            else:
                if receiver not in self._messages:
                    self._messages[receiver] = []
                self._messages[receiver].append(msg)

        logger.debug(f"Message {msg_id}: {sender} → {receiver} [{msg_type}]")
        return msg_id

    def receive(self, agent_id: str, msg_type: str = None,
                since: str = None) -> List[AgentMessage]:
        """
        接收消息

        Args:
            agent_id: 接收者 agent_id
            msg_type: 过滤消息类型
            since: 只返回此时间之后的消息

        Returns:
            消息列表
        """
        with self._lock:
            msgs = list(self._messages.get(agent_id, []))

        if msg_type:
            msgs = [m for m in msgs if m.msg_type == msg_type]
        if since:
            msgs = [m for m in msgs if m.timestamp > since]

        return msgs

    def register_agent(self, agent_id: str):
        """注册代理邮箱"""
        with self._lock:
            if agent_id not in self._messages:
                self._messages[agent_id] = []

    def unregister_agent(self, agent_id: str):
        """注销代理邮箱"""
        with self._lock:
            self._messages.pop(agent_id, None)

    def get_conversation(self, agent_a: str, agent_b: str) -> List[AgentMessage]:
        """获取两个代理间的对话历史"""
        with self._lock:
            msgs_a = [m for m in self._messages.get(agent_a, [])
                      if m.sender == agent_b or m.receiver == agent_b]
            msgs_b = [m for m in self._messages.get(agent_b, [])
                      if m.sender == agent_a or m.receiver == agent_a]

        # 合并并按时间排序
        all_msgs = msgs_a + msgs_b
        seen = set()
        unique = []
        for m in all_msgs:
            key = (m.sender, m.receiver, m.timestamp, m.content)
            if key not in seen:
                seen.add(key)
                unique.append(m)

        return sorted(unique, key=lambda m: m.timestamp)

    def get_stats(self) -> Dict[str, Any]:
        """邮箱统计"""
        with self._lock:
            return {
                "registered_agents": len(self._messages),
                "total_messages": self._message_count,
                "pending_by_agent": {
                    aid: len(msgs) for aid, msgs in self._messages.items()
                },
            }


class SubagentOrchestrator:
    """
    子代理编排器 — 协调多个子代理执行复杂任务

    功能:
    - 编排多代理工作流 (串行/并行/条件)
    - 共享上下文传递
    - 结果聚合分析
    - 阶段化工作流执行（Dynamic Workflows 增强）
    - 中间结果存储（上下文卸载）
    """

    def __init__(self, manager: SubagentManager = None):
        self.manager = manager or subagent_manager
        self.mailbox = AgentMailbox()
        self._shared_context: Dict[str, Any] = {}
        self._workflow_results: Dict[str, List[Dict]] = {}
        self._intermediate_store: Dict[str, Any] = {}  # 中间结果存储（上下文卸载）

    def set_shared_context(self, key: str, value: Any):
        """设置共享上下文"""
        self._shared_context[key] = value

    def get_shared_context(self, key: str, default: Any = None) -> Any:
        """获取共享上下文"""
        return self._shared_context.get(key, default)

    def run_sequential(self, tasks: List[Dict[str, Any]],
                       model: str = None) -> List[Dict]:
        """
        串行执行任务链 (前一个结果自动注入下一个上下文)

        Args:
            tasks: [{"task": "...", "agent_type": "..."}]
            model: 默认模型

        Returns:
            结果列表
        """
        results = []
        prev_result = None

        for i, task_def in enumerate(tasks):
            # 注入前序结果
            task_text = task_def["task"]
            if prev_result:
                task_text += f"\n\n---\n前置任务结果:\n{prev_result[:500]}"

            # 注入共享上下文
            if self._shared_context:
                ctx_str = json.dumps(self._shared_context, ensure_ascii=False)[:300]
                task_text = f"[共享上下文] {ctx_str}\n\n{task_text}"

            agent_type = task_def.get("agent_type", "general")
            handle = self.manager.spawn_subagent(
                task=task_text, model=model,
                agent_type=agent_type, run_in_background=False
            )

            result_dict = {
                "step": i + 1,
                "task": task_def["task"][:100],
                "agent_id": handle.agent_id,
                "agent_type": agent_type,
                "status": handle.status,
                "result_preview": (handle.result or "")[:200],
            }
            results.append(result_dict)

            # 邮箱注册并传递结果
            self.mailbox.register_agent(handle.agent_id)
            if handle.result:
                prev_result = handle.result

        return results

    def run_parallel(self, tasks: List[Dict[str, Any]],
                     model: str = None,
                     timeout: float = 120.0) -> List[Dict]:
        """
        并行执行多个任务并等待全部完成

        Args:
            tasks: [{"task": "...", "agent_type": "..."}]
            model: 默认模型
            timeout: 超时秒数

        Returns:
            结果列表
        """
        handles = []
        results = []

        # 注入共享上下文
        ctx_prefix = ""
        if self._shared_context:
            ctx_str = json.dumps(self._shared_context, ensure_ascii=False)[:300]
            ctx_prefix = f"[共享上下文] {ctx_str}\n\n"

        # 全部启动
        for task_def in tasks:
            task_text = ctx_prefix + task_def["task"]
            agent_type = task_def.get("agent_type", "general")
            handle = self.manager.spawn_subagent(
                task=task_text, model=model,
                agent_type=agent_type, run_in_background=True
            )
            self.mailbox.register_agent(handle.agent_id)
            handles.append((task_def, handle))

        # 全部等待
        for task_def, handle in handles:
            try:
                handle.thread.join(timeout=timeout)
                status = handle.status
                result_preview = (handle.result or "")[:200]
            except Exception as e:
                status = "error"
                result_preview = str(e)[:200]

            results.append({
                "task": task_def["task"][:100],
                "agent_id": handle.agent_id,
                "agent_type": task_def.get("agent_type", "general"),
                "status": status,
                "result_preview": result_preview,
            })

        return results

    def aggregate_results(self, results: List[Dict],
                         strategy: str = "summary") -> Dict[str, Any]:
        """
        聚合多个子代理的执行结果

        Args:
            results: run_parallel 或 run_sequential 返回的结果列表
            strategy: 聚合策略
                - "summary": 汇总各任务状态与关键发现
                - "merge": 合并所有结果文本
                - "vote": 多数投票(对同类任务)

        Returns:
            聚合报告
        """
        total = len(results)
        completed = sum(1 for r in results if r.get("status") == "completed")
        failed = sum(1 for r in results if r.get("status") == "failed")

        report = {
            "total_tasks": total,
            "completed": completed,
            "failed": failed,
            "success_rate": completed / total if total > 0 else 0,
            "strategy": strategy,
            "tasks": results,
        }

        if strategy == "summary":
            # 汇总模式: 提取每个任务的关键发现
            findings = []
            for r in results:
                preview = r.get("result_preview", "")
                # 提取关键行
                lines = preview.split("\n")
                key_lines = [l for l in lines if any(
                    kw in l.lower() for kw in ["##", "**", "found", "error", "建议", "发现"]
                )]
                findings.append({
                    "agent_id": r.get("agent_id", "?"),
                    "task": r.get("task", "")[:60],
                    "key_findings": key_lines[:3],
                })
            report["findings"] = findings

        elif strategy == "merge":
            # 合并模式: 拼接所有结果
            merged = []
            for r in results:
                merged.append(f"### Agent {r.get('agent_id', '?')} - {r.get('task', '')[:50]}")
                merged.append(r.get("result_preview", "(无结果)"))
                merged.append("")
            report["merged_text"] = "\n".join(merged)

        elif strategy == "vote":
            # 投票模式: 统计多数一致的结果
            from collections import Counter
            previews = [r.get("result_preview", "")[:50] for r in results]
            counter = Counter(previews)
            if counter:
                most_common = counter.most_common(1)[0]
                report["consensus"] = most_common[0]
                report["agreement_count"] = most_common[1]
                report["agreement_rate"] = most_common[1] / total

        return report

    # ── Dynamic Workflows 增强 ──

    def run_workflow(self, workflow_script, model: str = None) -> Dict[str, Any]:
        """
        执行阶段化工作流（Dynamic Workflows 核心方法）

        参考标准 Dynamic Workflows 的执行引擎。

        流程:
        1. 验证脚本正确性
        2. 拓扑排序确定执行顺序
        3. 按阶段执行（阶段内并行，阶段间串行）
        4. 综合阶段结果（存入中间存储，不占上下文）
        5. 检查收敛条件
        6. 返回最终结果

        Args:
            workflow_script: WorkflowScript 对象（或字典）
            model: LLM 模型

        Returns:
            工作流执行结果 {
                "workflow_name": str,
                "stages": Dict[stage_name -> stage_result],
                "final_result": str,
                "intermediate_store": Dict,
                "iterations": int,
                "converged": bool
            }

        Raises:
            ValueError: 脚本验证失败或存在循环依赖
        """
        # 延迟导入（避免循环依赖）
        from core.workflow_types import WorkflowScript

        # 支持字典或 WorkflowScript 对象
        if isinstance(workflow_script, dict):
            script = WorkflowScript.from_dict(workflow_script)
        else:
            script = workflow_script

        # 1. 验证脚本
        errors = script.validate()
        if errors:
            raise ValueError(f"工作流脚本验证失败:\n" + "\n".join(f"- {e}" for e in errors))

        # 2. 获取执行顺序（拓扑排序）
        try:
            execution_order = script.get_execution_order()
        except ValueError as e:
            raise ValueError(f"工作流执行顺序错误: {e}")

        # 3. 构建阶段映射
        stage_map = {stage.name: stage for stage in script.stages}

        # 4. 执行工作流
        stage_results = {}
        self._intermediate_store.clear()  # 清空中间存储

        for stage_name in execution_order:
            stage = stage_map[stage_name]

            # 等待依赖完成
            for dep in stage.depends:
                if dep not in stage_results:
                    raise RuntimeError(f"阶段 '{stage_name}' 的依赖 '{dep}' 未执行")

            # 执行阶段
            stage_result = self._execute_stage(stage, stage_results, model)
            stage_results[stage_name] = stage_result

            # 综合结果（如果需要）
            if stage.synthesize:
                synthesized = self._synthesize_stage(stage, stage_result)
                self._intermediate_store[stage_name] = synthesized
            else:
                # 直接存储原始结果
                self._intermediate_store[stage_name] = stage_result

        # 5. 收敛检查
        converged = self._check_convergence(script, self._intermediate_store)

        # 6. 返回结果
        return {
            "workflow_name": script.name,
            "stages": stage_results,
            "final_result": self._intermediate_store.get(execution_order[-1], ""),
            "intermediate_store": {
                k: v[:500] if isinstance(v, str) else v  # 摘要显示
                for k, v in self._intermediate_store.items()
            },
            "iterations": 1,
            "converged": converged,
        }

    def _execute_stage(self, stage, stage_results: Dict, model: str) -> List[Dict]:
        """
        执行单个阶段（阶段内并行）

        Args:
            stage: WorkflowStage 对象
            stage_results: 已完成阶段的结果
            model: LLM 模型

        Returns:
            Agent 结果列表
        """
        handles = []
        results = []

        # 构建阶段上下文（依赖阶段的结果摘要）
        stage_context = ""
        if stage.depends:
            context_parts = []
            for dep in stage.depends:
                dep_result = stage_results.get(dep, {})
                if isinstance(dep_result, dict) and "final_result" in dep_result:
                    context_parts.append(
                        f"### {dep} 阶段结果:\n{dep_result['final_result'][:500]}"
                    )
            if context_parts:
                stage_context = "\n\n---\n\n".join(context_parts) + "\n\n---\n\n"

        # 启动所有 Agent（并行）
        for agent_task in stage.agents:
            # 构建完整 prompt（自包含）
            full_prompt = f"{stage_context}{agent_task.prompt}"

            # 注入中间存储（如果阶段需要访问之前的结果）
            if self._intermediate_store:
                store_summary = json.dumps({
                    k: v[:200] if isinstance(v, str) else str(v)[:200]
                    for k, v in list(self._intermediate_store.items())[-3:]  # 最近 3 个
                }, ensure_ascii=False)
                full_prompt = f"[之前阶段结果摘要] {store_summary}\n\n{full_prompt}"

            handle = self.manager.spawn_subagent(
                task=full_prompt,
                model=model,
                agent_type=agent_task.agent_type.value,
                run_in_background=True
            )
            self.mailbox.register_agent(handle.agent_id)
            handles.append((agent_task, handle))

        # 等待所有完成
        for agent_task, handle in handles:
            try:
                handle.thread.join(timeout=agent_task.timeout)
                status = handle.status
                result = handle.result or ""
            except Exception as e:
                status = "error"
                result = str(e)

            results.append({
                "agent_id": handle.agent_id,
                "agent_type": agent_task.agent_type.value,
                "status": status,
                "result": result,
                "result_preview": result[:200],
            })

        return results

    def _synthesize_stage(self, stage, results: List[Dict]) -> str:
        """
        综合阶段结果

        Args:
            stage: WorkflowStage 对象
            results: Agent 结果列表

        Returns:
            综合后的结果
        """
        # 收集所有发现
        all_findings = "\n\n".join([
            f"### Agent {r['agent_id']} ({r['agent_type']})\n{r['result']}"
            for r in results if r['status'] == 'completed'
        ])

        # 使用综合提示词或默认提示词
        synthesize_prompt = stage.synthesize_prompt or (
            "综合以上所有发现，提取关键信息，消除矛盾，"
            "生成一致的结论。如果有相互矛盾的发现，请标注出来。"
        )

        # 启动综合 Agent
        synthesis_handle = self.manager.spawn_subagent(
            task=f"{synthesize_prompt}\n\n---\n\n所有发现:\n{all_findings}",
            model=None,
            agent_type="general",
            run_in_background=False  # 同步等待
        )

        return synthesis_handle.result or "综合失败"

    def _check_convergence(self, script, intermediate_store: Dict) -> bool:
        """
        检查收敛条件

        Args:
            script: WorkflowScript 对象
            intermediate_store: 中间结果存储

        Returns:
            是否收敛
        """
        if not script.convergence_check:
            # 没有定义收敛检查，默认收敛
            return True

        # TODO: 实现收敛检查逻辑
        # 可以启动一个 Agent 评估是否收敛
        # 或者使用简单的规则（如结果长度、关键词等）

        return True

    def get_intermediate_store(self) -> Dict[str, Any]:
        """获取中间结果存储"""
        return self._intermediate_store.copy()

    def clear_intermediate_store(self):
        """清空中间结果存储"""
        self._intermediate_store.clear()

