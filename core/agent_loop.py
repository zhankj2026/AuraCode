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
Agent Loop 核心实现

基于 TAOR 循环(Think-Act-Observe-Repeat)设计,
实现完整的智能体交互流程。

本模块为「薄外壳 / 组合根」：仅负责装配协作者、运行主循环、暴露公共 API。
具体逻辑（提示词构建 / LLM 调用 / 工具执行 / 上下文压缩 / 持久化 …）已拆分到
``core.loop`` 子包的各协作者模块。详见 ``core/loop/context.py`` 的映射表。
"""

import os
import json
import logging
import asyncio
import threading
from typing import List, Dict, Any, Optional
from openai import OpenAI

from tools.registry import get_tool_schemas, register_tool
from permissions.manager import PermissionManager
from core.memory import get_memory_manager
from core.session_state import SessionState, QueryResult, TokenUsage

# 集成扩展系统
from plugins.loader import PluginLoader
from hooks.manager import HookManager, HookResult
from skills.loader import SkillManager
from skills.context import SkillContext
from core.tool_enhancer import get_tool_enhancer
from core.auto_memory import AutoMemoryExtractor

# 协作者（core.loop 子包）
from core.loop.events import EventEmitter
from core.loop.prompt_builder import SystemPromptBuilder
from core.loop.llm_client import LLMClient
from core.loop.tool_executor import ToolExecutor
from core.loop.context_manager import ContextManager
from core.loop.file_tracker import FileChangeTracker
from core.loop.persistence import SessionPersistence
from core.loop.extension_facade import ExtensionFacade
from core.loop.summary import SummaryBuilder
from core.loop.tool_dispatcher import ToolDispatcher
from core.loop.orchestrator import LoopOrchestrator

logger = logging.getLogger(__name__)

class AgentLoop:
    """
    AI 编程助手核心引擎
    基于 TAOR 循环设计

    本类为组合根：装配各协作者（``core.loop``）并编排主循环。
    共享状态与兄弟协作者通过 ``self``（即各协作者持有的 ``loop``）访问。
    """

    def __init__(self, config: Dict[str, Any]):
        """
        初始化 Agent Loop

        Args:
            config: 配置字典,包含:
                - api_key: LLM API 密钥(可选,从环境变量读取)
                - base_url: API 基础 URL(可选,从环境变量读取)
                - model: 模型名称(默认 glm-4-plus)
                - max_iterations: 最大迭代次数(默认 20)
                - default_max_tokens: 每次 LLM 请求的输出 token 上限(默认 32000)
                - max_tokens: 整个 query 的 输入+输出 token 总预算(历史命名,实际是预算)
                - max_budget_usd: 费用预算上限(美元)
                - permission_mode: 权限模式(normal/auto/plan/bypass)
                - enable_plugins: 是否启用插件(默认 True)
                - enable_hooks: 是否启用钩子(默认 True)
                - enable_skills: 是否启用技能(默认 True)
        """
        # 1. 初始化 LLM 客户端
        api_key = config.get("api_key") or os.environ.get("OPENAI_API_KEY")
        base_url = config.get("base_url") or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")

        if not api_key:
            raise ValueError("未设置 API Key,请设置 OPENAI_API_KEY 环境变量")

        # ── 超时配置 ──
        # OpenAI SDK timeout = httpx 连接+首字节等待时间。
        # LLM streaming 场景下，复杂任务首 token 延迟可能 > 60s，
        # 业界标准设置 600s (10min)，我们默认 300s (5min)。
        # 优先级: config > 环境变量 API_TIMEOUT_MS > 默认 300s
        if "api_timeout" in config:
            api_timeout = float(config["api_timeout"])
        else:
            env_timeout = os.environ.get("API_TIMEOUT_MS")
            api_timeout = float(env_timeout) / 1000.0 if env_timeout else 300.0

        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=api_timeout,
            max_retries=0,  # 禁用 SDK 内置重试，由外层控制
        )

        # 2. 配置参数
        self.model = config.get("model", "glm-4.7")
        self.max_iterations = config.get("max_iterations")  # None 表示无限制

        # ⚠️ max_tokens 命名陷阱（配置键名与属性名语义相反，极易混淆）:
        #   - self.max_tokens        : 每次 LLM 请求的输出 token 上限
        #                              （透传给 API 的 max_tokens 参数）
        #                              配置键: config["default_max_tokens"]（默认 32000）
        #   - self.max_budget_tokens : 整个 query 的 输入+输出 token 总预算
        #                              配置键: config["max_tokens"]（历史命名，实际是预算）
        self.max_tokens = config.get("default_max_tokens", 32000)
        self.max_budget_tokens = config.get("max_tokens")  # token 预算（输入+输出）
        # 费用预算（美元）
        self.max_budget_usd = config.get("max_budget_usd")
        # 工作目录：工具文件操作的基准路径（Bridge 模式下为用户指定的 work_dir）
        self.project_root = os.path.abspath(config.get("project_root", "."))
        # work_dir 别名：系统提示词的"主工作目录"、git 检测、project_context 等多处
        # 用 getattr(self, 'work_dir', os.getcwd()) 兜底。若不赋值，这些会落到进程
        # CWD（Bridge 服务器启动目录，如 opencode/），与用户配置的 work_dir 不一致，
        # 导致模型被告知错误的工作目录。这里与 project_root 对齐即可。
        self.work_dir = self.project_root
        # 详细日志：显示 project_root 解析结果
        logger.info(f"AgentLoop init: project_root={self.project_root}, work_dir={self.work_dir}, cwd={os.getcwd()}, config.project_root={config.get('project_root', '.')}")
        # 注入 project_root 到 plan_mode 模块（替代 os.getcwd()）
        try:
            from tools.builtin.plan_mode import set_project_root
            set_project_root(self.project_root)
        except ImportError:
            pass
        self.max_output_recovery_limit = config.get("max_output_recovery_limit", 3)
        self.context_compact_threshold = config.get("context_compact_threshold", None)
        if self.context_compact_threshold is None:
            # 动态计算压缩阈值：根据模型上下文窗口自动调整
            from commands.builtin.context_command import _get_context_window, _get_dynamic_threshold
            cw = _get_context_window(self.model)
            self.context_compact_threshold = _get_dynamic_threshold(cw)
            logger.info(f"动态压缩阈值: {self.context_compact_threshold} (模型窗口: {cw:,})")

        # 3. 会话状态管理（集中式）
        self.state = SessionState(
            max_budget_usd=config.get("max_budget_usd"),
            fallback_model=config.get("fallback_model"),
        )

        # 4. 扩展系统集成
        self._init_extensions(config)

        # 5. 工具定义(JSON Schema) - 包含内置工具 + 插件工具
        self.tools = get_tool_schemas()

        # 6. 权限管理器
        self.permission_manager = PermissionManager(
            config.get("permission_mode", "normal")
        )

        # 7. 记忆系统
        self.memory_enabled = config.get("enable_memory", True)
        self.memory_manager = None
        if self.memory_enabled:
            try:
                self.memory_manager = get_memory_manager(config.get("project_root", "."))
                # 将 LLM 客户端和模型传递给 MemoryManager，供 LLM 驱动记忆召回使用
                self.memory_manager.llm_client = self.client
                self.memory_manager.llm_model = self.model
                logger.info("Memory system enabled")
            except Exception as e:
                logger.warning(f"Memory system initialization failed: {e}")
                self.memory_enabled = False

        # 7.5 自动记忆提取器
        self.auto_memory_extractor = None
        if self.memory_enabled and self.memory_manager:
            try:
                self.auto_memory_extractor = AutoMemoryExtractor(
                    memory_manager=self.memory_manager,
                    llm_client=self.client,
                    llm_model=self.model,
                    min_turns_between=config.get("auto_memory_min_turns", 1),
                )
                logger.info("Auto-memory extractor enabled")
            except Exception as e:
                logger.warning(f"Auto-memory extractor init failed: {e}")

        # 7.6 会话持久化存储
        self._session_transcript = None
        self._session_memory = None
        self._session_env = None
        self._project_store = None
        try:
            session_id = getattr(self, '_session_id', '') or str(id(self))[:8]
            cwd = config.get('project_root', '') or config.get('work_dir', '') or os.getcwd()

            from services.session_transcript import init_transcript
            from services.session_memory import init_session_memory
            from services.session_env import init_session_env
            from services.project_store import get_project_store

            self._session_transcript = init_transcript(session_id=session_id, cwd=cwd)
            self._session_memory = init_session_memory(session_id=session_id, cwd=cwd)
            self._session_env = init_session_env(session_id=session_id)
            self._project_store = get_project_store(cwd=cwd)
            logger.info(f"Session persistence initialized: transcript + memory + env + project ({session_id})")

        except Exception as e:
            logger.warning(f"Session persistence init failed: {e}")

        # 8. 事件回调（供 Bridge 等外部系统订阅）
        self.event_callback = None

        # 9. 工具智能增强（自动摘要 + 幂等重试 + 输出裁剪）
        self.tool_enhancer = get_tool_enhancer()

        # 10. 装配协作者（core.loop）
        #     顺序无关：构造器仅存储 loop 引用，实际使用发生在 run() 期间。
        self.events = EventEmitter(self)
        self.prompt_builder = SystemPromptBuilder(self)
        self.llm_client = LLMClient(self)
        self.tool_executor = ToolExecutor(self)
        self.context_manager = ContextManager(self)
        self.file_tracker = FileChangeTracker(self)
        self.persistence = SessionPersistence(self)
        self.extensions = ExtensionFacade(self)
        self.summary_builder = SummaryBuilder(self)
        self.tool_dispatcher = ToolDispatcher(self)
        self.orchestrator = LoopOrchestrator(self)

        # ProjectStore: 加载项目级配置并应用（原 _apply_project_config）
        self.persistence.apply_project_config()

        logger.info(f"AgentLoop initialized with model={self.model}, "
                   f"max_iterations={self.max_iterations}, "
                   f"fallback_model={self.state.fallback_model}, "
                   f"max_budget_usd={self.state.max_budget_usd}")

    # ========== 消息历史兼容属性 ==========

    @property
    def messages(self) -> List[Dict[str, Any]]:
        """向后兼容：直接访问 self.state.messages"""
        return self.state.messages

    @messages.setter
    def messages(self, value: List[Dict[str, Any]]):
        self.state.messages = value

    def _init_extensions(self, config: Dict[str, Any]):
        """
        初始化扩展系统(插件、钩子、技能)

        Args:
            config: 配置字典
        """
        # 1. 插件系统
        self.plugin_loader = None
        self.plugins_enabled = config.get("enable_plugins", True)

        if self.plugins_enabled:
            try:
                self.plugin_loader = PluginLoader()
                plugins = self.plugin_loader.load_all_plugins()
                logger.info(f"加载了 {len(plugins)} 个插件")

                # 注册插件提供的工具
                plugin_tools = self.plugin_loader.get_all_tools()
                for tool_def in plugin_tools:
                    try:
                        register_tool(
                            tool_def["name"],
                            {
                                "description": tool_def["description"],
                                "parameters": tool_def["parameters"],
                                "handler": tool_def["handler"],
                                "permission_level": tool_def.get("permission_level", "read")
                            }
                        )
                        logger.debug(f"注册插件工具: {tool_def['name']}")
                    except ValueError as e:
                        logger.warning(f"插件工具注册失败 {tool_def.get('name')}: {e}")

            except Exception as e:
                logger.warning(f"插件系统初始化失败: {e}")
                self.plugin_loader = None

        # 2. 钩子系统
        self.hook_manager = HookManager()
        self.hooks_enabled = config.get("enable_hooks", True)
        self._hook_config_loader = None  # Hook 配置加载器

        if self.hooks_enabled and self.plugin_loader:
            # 注册插件提供的钩子
            try:
                plugin_hooks = self.plugin_loader.get_all_hooks()
                for hook_def in plugin_hooks:
                    try:
                        self.hook_manager.register_hook(
                            hook_def["event"],
                            hook_def["handler"],
                            hook_def.get("matcher"),
                            hook_def.get("priority", 0)
                        )
                        logger.debug(f"注册插件钩子: {hook_def['event']} -> {hook_def.get('matcher')}")
                    except ValueError as e:
                        logger.warning(f"插件钩子注册失败: {e}")
            except Exception as e:
                logger.warning(f"插件钩子注册失败: {e}")

        # 2.5 加载配置文件驱动的 Hook
        if self.hooks_enabled:
            try:
                from hooks.config_loader import HookConfigLoader
                project_root = config.get("project_root", ".")
                self._hook_config_loader = HookConfigLoader(
                    hook_manager=self.hook_manager,
                    project_root=project_root,
                )
                loaded = self._hook_config_loader.load()
                if loaded > 0:
                    logger.info(f"从配置文件加载了 {loaded} 个 Hook")
            except Exception as e:
                logger.warning(f"Hook 配置加载失败: {e}")

        # 3. 技能系统
        self.skill_manager = None
        self.skills_enabled = config.get("enable_skills", True)

        if self.skills_enabled:
            try:
                self.skill_manager = SkillManager()
                logger.info(f"加载了 {len(self.skill_manager.skills)} 个技能 (仅元数据)")

                # 设置全局技能上下文，让工具可以访问
                SkillContext.set_skill_manager(self.skill_manager)
                logger.debug("技能上下文已设置")

                # 自动激活配置中指定的技能
                active_skills = config.get("active_skills", [])
                if active_skills:
                    logger.info(f"自动激活技能: {active_skills}")
                    for skill_name in active_skills:
                        try:
                            self.skill_manager.activate_skill(skill_name)
                            logger.info(f"  -> 激活成功: {skill_name}")
                        except ValueError as e:
                            logger.warning(f"  -> 激活失败 {skill_name}: {e}")

            except Exception as e:
                logger.warning(f"技能系统初始化失败: {e}")
                self.skill_manager = None

    # ========== 主循环 ==========

    def run(self, user_input: str) -> QueryResult:
        """
        主入口：处理用户输入并执行 Agent Loop

        返回结构化 QueryResult（含状态/token/成本/耗时）。

        Args:
            user_input: 用户的自然语言指令

        Returns:
            QueryResult 结构化结果
        """
        result = self.orchestrator.run(user_input)
        # 记录到全局历史日志
        self.file_tracker.record_history(user_input, result)
        return result

    # ========== 中断控制 ==========

    def abort(self):
        """便捷方法：中断当前执行"""
        self.state.abort()
        self.events.emit("aborted", {})

    def is_aborted(self) -> bool:
        """检查是否已中断"""
        return self.state.is_aborted()

    # ========== 扩展系统控制方法 ==========
    # 实现已迁至 core.loop.extension_facade.ExtensionFacade，
    # 此处保留同名方法作为转发桩，保证 commands / tests 等既有调用方零破坏。

    def activate_skill(self, name: str) -> bool:
        """激活指定的技能（转发到 ExtensionFacade）"""
        return self.extensions.activate_skill(name)

    def deactivate_skill(self, name: str) -> bool:
        """停用指定的技能（转发到 ExtensionFacade）"""
        return self.extensions.deactivate_skill(name)

    def list_skills(self) -> str:
        """列出所有可用技能（转发到 ExtensionFacade）"""
        return self.extensions.list_skills()

    def list_active_skills(self) -> List[str]:
        """获取已激活的技能列表（转发到 ExtensionFacade）"""
        return self.extensions.list_active_skills()

    def register_hook(
        self,
        event: str,
        handler,
        matcher: str = None,
        priority: int = 0,
    ) -> int:
        """手动注册钩子（转发到 ExtensionFacade）"""
        return self.extensions.register_hook(event, handler, matcher, priority)

    def unregister_hook(self, hook_id: int) -> bool:
        """删除钩子（转发到 ExtensionFacade）"""
        return self.extensions.unregister_hook(hook_id)

    def list_hooks(self) -> str:
        """列出所有已注册的钩子（转发到 ExtensionFacade）"""
        return self.extensions.list_hooks()

    def list_plugins(self) -> str:
        """列出所有已加载的插件（转发到 ExtensionFacade）"""
        return self.extensions.list_plugins()

    def get_system_status(self) -> Dict[str, Any]:
        """获取扩展系统状态（转发到 ExtensionFacade）"""
        return self.extensions.get_system_status()
