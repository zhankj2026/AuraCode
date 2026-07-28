#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core.loop.persistence — 会话持久化服务集成

封装四类会话级持久化服务：
    - SessionTranscript  完整对话转录（用户/助手/工具/费用）
    - SessionMemory      会话记忆（跨轮摘要，注入系统提示词）
    - SessionEnv         会话环境（venv/conda 脚本注入 shell 命令）
    - ProjectStore       项目级配置（preferred_model / auto_compact …）

这四个服务对象由 ``AgentLoop.__init__`` 创建并挂在 ``loop`` 上
（``loop._session_transcript`` 等），本类仅提供操作方法。
"""

import logging

logger = logging.getLogger(__name__)


class SessionPersistence:
    """会话持久化服务的统一访问层。"""

    def __init__(self, loop):
        self.loop = loop

    def apply_project_config(self):
        """ProjectStore: 加载项目级配置并应用到当前会话"""
        loop = self.loop
        if not loop._project_store:
            return
        try:
            cfg = loop._project_store.load()
            # 应用 preferred_model
            if cfg.preferred_model and not loop.model:
                loop.model = cfg.preferred_model
                logger.info(f"ProjectStore: applied preferred_model={cfg.preferred_model}")
            # 应用 auto_compact 设置
            if hasattr(cfg, 'auto_compact_enabled'):
                loop.state.auto_compact_enabled = cfg.auto_compact_enabled
            # 记录加载的配置
            logger.info(
                f"ProjectStore config loaded: "
                f"allowed_tools={len(cfg.allowed_tools)}, "
                f"mcp_servers={len(cfg.mcp_servers)}, "
                f"permission_rules={len(cfg.permission_rules)}"
            )
        except Exception as e:
            logger.warning(f"ProjectStore apply config failed: {e}")

    def get_session_memory_context(self) -> str:
        """SessionMemory: 读取会话记忆并生成上下文注入片段"""
        loop = self.loop
        if not loop._session_memory:
            return ""
        try:
            content = loop._session_memory.read()
            if not content or loop._session_memory.is_empty():
                return ""
            # 截取前 2000 字符作为上下文（防止过长）
            truncated = content[:2000]
            if len(content) > 2000:
                truncated += "\n... [truncated]"
            return f"## Session Memory (Current Progress)\n\n{truncated}"
        except Exception as e:
            logger.debug(f"SessionMemory read failed: {e}")
            return ""

    def inject_session_env(self, arguments: dict, tool_name: str):
        """SessionEnv: 为 shell 命令注入会话环境脚本"""
        loop = self.loop
        if not loop._session_env:
            return
        try:
            env_script = loop._session_env.get_combined_script()
            if not env_script:
                return
            # 将环境脚本前置到命令中
            command = arguments.get("command", "")
            if command:
                if tool_name == "run_powershell":
                    # PowerShell: 用分号连接
                    arguments["command"] = f"{env_script}; {command}"
                else:
                    # Shell: 用 && 连接
                    arguments["command"] = f"source <(echo '{env_script}') && {command}"
                logger.debug(f"SessionEnv injected into {tool_name}")
        except Exception as e:
            logger.debug(f"SessionEnv injection failed: {e}")

    def transcript_record_user(self, user_input: str):
        """SessionTranscript: 记录用户消息"""
        loop = self.loop
        if not loop._session_transcript:
            return
        try:
            import uuid
            loop._session_transcript.append_message(
                message={"role": "user", "content": user_input},
                uuid=str(uuid.uuid4()),
            )
        except Exception as e:
            logger.debug(f"Transcript record user failed: {e}")

    def transcript_record_assistant(self, msg: dict, model: str = "", usage=None):
        """SessionTranscript: 记录助手消息"""
        loop = self.loop
        if not loop._session_transcript:
            return
        try:
            import uuid
            usage_dict = {}
            if usage:
                usage_dict = {
                    "prompt_tokens": getattr(usage, 'prompt_tokens', 0) or 0,
                    "completion_tokens": getattr(usage, 'completion_tokens', 0) or 0,
                    "total_tokens": getattr(usage, 'total_tokens', 0) or 0,
                }
            loop._session_transcript.append_message(
                message=msg,
                uuid=str(uuid.uuid4()),
                model=model or loop.model,
                usage=usage_dict,
            )
        except Exception as e:
            logger.debug(f"Transcript record assistant failed: {e}")

    def transcript_record_tool(self, tool_name: str, arguments: dict, result):
        """SessionTranscript: 记录工具调用及结果"""
        loop = self.loop
        if not loop._session_transcript:
            return
        try:
            loop._session_transcript.append_metadata("tool_use", {
                "tool_name": tool_name,
                "arguments": {k: str(v)[:500] for k, v in arguments.items()},
                "result_preview": str(result)[:500],
                "success": not isinstance(result, str) or not result.startswith("Error:"),
            })
        except Exception as e:
            logger.debug(f"Transcript record tool failed: {e}")

    def transcript_record_cost(self, model: str, usage):
        """SessionTranscript: 记录费用"""
        loop = self.loop
        if not loop._session_transcript or not usage:
            return
        try:
            prompt_tokens = getattr(usage, 'prompt_tokens', 0) or 0
            completion_tokens = getattr(usage, 'completion_tokens', 0) or 0
            # 简单费用估算（实际定价由 SessionState 计算）
            cost_usd = 0.0  # 由 state 追踪，此处仅记录 token
            loop._session_transcript.append_cost_record(
                model=model or loop.model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_usd=cost_usd,
            )
        except Exception as e:
            logger.debug(f"Transcript record cost failed: {e}")

    def update_session_memory_turn(self):
        """SessionMemory: 每轮结束后尝试更新记忆（轻量级，不强制 LLM）"""
        loop = self.loop
        if not loop._session_memory or not loop.state.messages:
            return
        try:
            since = loop._session_memory.last_summarized_index + 1
            new_msgs = loop.state.messages[since:]
            # 只有新增 4 条以上消息时才更新（避免频繁写入）
            if len(new_msgs) >= 4:
                loop._session_memory.update_with_summary(
                    messages=list(loop.state.messages),
                    since_index=since,
                    llm_client=None,  # 使用简单摘要，不消耗 LLM
                    llm_model="",
                )
        except Exception as e:
            logger.debug(f"SessionMemory turn update failed: {e}")

    def close(self):
        """关闭会话持久化存储（flush + cleanup）"""
        loop = self.loop
        # 转录: flush 并关闭
        if loop._session_transcript:
            try:
                loop._session_transcript.close()
            except Exception as e:
                logger.debug(f"Transcript close failed: {e}")
        # 会话记忆: 尝试更新
        if loop._session_memory and loop.state.messages:
            try:
                since = loop._session_memory.last_summarized_index + 1
                if since < len(loop.state.messages):
                    loop._session_memory.update_with_summary(
                        messages=loop.state.messages,
                        since_index=since,
                        llm_client=loop.client,
                        llm_model=loop.model,
                    )
            except Exception as e:
                logger.debug(f"Session memory update on close failed: {e}")
        # 全局单例清理
        try:
            from services.session_transcript import close_transcript
            from services.session_memory import close_session_memory
            from services.session_env import close_session_env
            close_transcript()
            close_session_memory()
            close_session_env()
        except Exception:
            pass
