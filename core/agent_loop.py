"""
Agent Loop 核心实现

基于 Claude Code 的 TAOR 循环(Think-Act-Observe-Repeat)设计,
实现完整的智能体交互流程。
"""

import os
import json
import logging
import asyncio
from typing import List, Dict, Any
from openai import OpenAI

from tools.registry import TOOL_REGISTRY, get_tool_schemas, register_tool
from permissions.manager import PermissionManager
from core.context import load_project_context

# 集成扩展系统
from plugins.loader import PluginLoader
from hooks.manager import HookManager, HookResult
from skills.loader import SkillManager

logger = logging.getLogger(__name__)


class AgentLoop:
    """
    简化版 AI 编程工具核心
    基于 Claude Code 的 TAOR 循环设计
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

        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=60.0  # 60秒超时
        )

        # 2. 配置参数
        self.model = config.get("model", "glm-4-plus")
        self.max_iterations = config.get("max_iterations", 20)

        # 3. 消息历史(扁平存储)
        self.messages: List[Dict[str, Any]] = []

        # 4. 扩展系统集成
        self._init_extensions(config)

        # 5. 工具定义(JSON Schema) - 包含内置工具 + 插件工具
        self.tools = get_tool_schemas()

        # 6. 权限管理器
        self.permission_manager = PermissionManager(
            config.get("permission_mode", "normal")
        )

        logger.info(f"AgentLoop initialized with model={self.model}, "
                   f"max_iterations={self.max_iterations}")

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

        # 3. 技能系统
        self.skill_manager = None
        self.skills_enabled = config.get("enable_skills", True)

        if self.skills_enabled:
            try:
                self.skill_manager = SkillManager()
                logger.info(f"加载了 {len(self.skill_manager.skills)} 个技能")
            except Exception as e:
                logger.warning(f"技能系统初始化失败: {e}")
                self.skill_manager = None
    
    def run(self, user_input: str) -> str:
        """
        主入口:处理用户输入并执行 Agent Loop
        
        Args:
            user_input: 用户的自然语言指令
            
        Returns:
            最终响应文本
        """
        logger.info(f"Starting agent loop with input: {user_input[:50]}...")
        
        # 1. 初始化消息(系统提示词 + 用户输入)
        self._init_messages(user_input)
        
        # 2. Agent Loop - 核心循环
        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1
            logger.info(f"Iteration {iteration}/{self.max_iterations}")
            
            try:
                # Step 1: 调用 LLM
                response = self._call_llm()
                
                # Step 2: 解析响应
                message = response.choices[0].message
                assistant_content = message.content or ""
                
                # 追加助手消息到历史 — 必须保留 tool_calls 字段
                # 参考 OpenAI API 规范: assistant 消息须带 tool_calls,否则后续 tool 消息会报错
                assistant_msg: Dict[str, Any] = {
                    "role": "assistant",
                    "content": assistant_content
                }
                if message.tool_calls:
                    assistant_msg["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in message.tool_calls
                    ]
                self.messages.append(assistant_msg)
                
                # 打印助手回复
                if assistant_content:
                    print(f"\n🤖 Assistant: {assistant_content}\n")
                
                # Step 3: 检查是否有工具调用
                if not message.tool_calls:
                    # 无工具调用 → 任务完成
                    logger.info("No tool calls, task completed")
                    return assistant_content
                
                # Step 4: 执行所有工具调用
                for tool_call in message.tool_calls:
                    tool_result = self._execute_tool(tool_call)
                    
                    # Step 5: 工具结果以 role=tool 返回(OpenAI 规范)
                    # 必须包含 tool_call_id 与 assistant 消息对应
                    result_content = tool_result.get("result") if tool_result.get("success") else f"Error: {tool_result.get('error')}"
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": str(result_content)
                    })
                    
                    # 打印工具执行结果
                    status = "✅" if tool_result.get("success") else "❌"
                    print(f"{status} [{tool_call.function.name}] {str(result_content)[:200]}")
                
                # Step 6: 继续循环
                
            except Exception as e:
                logger.error(f"Iteration {iteration} failed: {e}", exc_info=True)
                return f"❌ 错误: {str(e)}"
        
        # 达到最大迭代次数
        logger.warning("Reached max iterations")
        return "⚠️ 达到最大迭代次数,任务未完成。请尝试简化任务或增加 max_iterations。"
    
    def _init_messages(self, user_input: str):
        """初始化消息历史"""
        system_prompt = self._build_system_prompt()
        self.messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ]
        logger.debug(f"Messages initialized, system prompt length: {len(system_prompt)}")
    
    def _build_system_prompt(self) -> str:
        """构建系统提示词(增强版 5 层)"""
        parts = []

        # 第 1 层: 基础角色定义
        parts.append(self._base_role())

        # 第 2 层: 项目上下文(CLAUDE.md)
        project_context = load_project_context()
        if project_context:
            parts.append(project_context)

        # 第 3 层: 技能提示词(新增)
        if self.skill_manager and self.skills_enabled:
            active_skills = self.skill_manager.get_active_skills()
            if active_skills:
                skill_prompts = self.skill_manager.get_active_prompts()
                if skill_prompts:
                    parts.append(f"## 激活的技能\n\n{skill_prompts}")
                    logger.debug(f"包含 {len(active_skills)} 个激活的技能提示词")

        # 第 4 层: 工具说明
        parts.append(self._tools_description())

        # 第 5 层: 安全规则
        parts.append(self._security_rules())

        return "\n\n".join(parts)
    
    def _base_role(self) -> str:
        """基础角色定义"""
        return """你是一个 AI 编程助手,可以读写文件、执行命令来帮助用户完成编程任务。

你的能力:
- 读取和分析代码文件
- 创建和修改文件
- 执行 Shell 命令(如 git、grep、ls 等)
- 理解项目结构和架构

工作原则:
1. 先理解任务,再制定计划
2. 使用工具获取必要信息
3. 逐步执行,每步验证结果
4. 遇到错误时分析原因并调整策略"""
    
    def _tools_description(self) -> str:
        """生成工具说明"""
        tools_desc = "可用工具:\n"
        for name, info in TOOL_REGISTRY.items():
            tools_desc += f"- **{name}**: {info['description']}\n"
        
        tools_desc += "\n使用方法: 直接描述你要执行的操作,我会自动选择合适的工具。"
        return tools_desc
    
    def _security_rules(self) -> str:
        """安全规则"""
        return """安全规则:
1. 不要在系统目录外执行危险命令
2. 修改文件前先确认路径正确
3. 永远不要执行 `rm -rf /` 等危险操作
4. 遇到不确定的操作,先询问用户
5. 保护用户隐私,不要泄露敏感信息"""
    
    def _call_llm(self):
        """调用 LLM"""
        logger.debug(f"Calling LLM with {len(self.messages)} messages")
        
        # 打印调用信息(使用 print 确保可见)
        print(f"\n🤔 思考中... (使用 {len(self.messages)} 条消息历史)")
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                tools=self.tools,
                tool_choice="auto",
                temperature=0.2,
                max_tokens=4096
            )
            
            # 记录 token 使用情况
            usage = response.usage
            if usage:
                logger.info(f"Token usage: prompt={usage.prompt_tokens}, "
                           f"completion={usage.completion_tokens}, "
                           f"total={usage.total_tokens}")
                print(f"💰 Token 使用: 输入={usage.prompt_tokens}, 输出={usage.completion_tokens}, 总计={usage.total_tokens}")
            
            return response
            
        except Exception as e:
            logger.error(f"LLM API 调用失败: {e}")
            raise

    def _execute_tool(self, tool_call) -> Dict[str, Any]:
        """执行工具调用(经过钩子和权限检查)"""
        tool_name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments)

        logger.info(f"Executing tool: {tool_name}, args: {arguments}")

        # 1. 查找工具
        tool = TOOL_REGISTRY.get(tool_name)
        if not tool:
            error_msg = f"未知工具: {tool_name}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        # 2. PreToolUse 钩子
        if self.hooks_enabled and self.hook_manager:
            try:
                # 在新事件循环中执行异步钩子
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                pre_result = loop.run_until_complete(
                    self.hook_manager.execute_hooks(
                        "PreToolUse",
                        tool_name=tool_name,
                        input=arguments
                    )
                )

                loop.close()

                # 检查钩子是否阻止执行
                if not pre_result.allow:
                    error_msg = f"钩子阻止执行: {pre_result.block_reason}"
                    logger.warning(error_msg)

                    # 触发 PostToolUseFailure 钩子
                    if self.hooks_enabled:
                        self._trigger_failure_hook(tool_name, arguments, error_msg)

                    return {"success": False, "error": error_msg}

                # 应用钩子修改的输入
                if pre_result.modified_input:
                    arguments.update(pre_result.modified_input)
                    logger.debug(f"钩子修改了输入参数")

                # 记录附加上下文
                if pre_result.additional_context:
                    logger.debug(f"钩子附加上下文: {pre_result.additional_context}")

            except Exception as e:
                logger.warning(f"PreToolUse 钩子执行失败: {e}")

        # 3. 权限检查
        if not self.permission_manager.check_permission(tool_name, arguments):
            error_msg = f"权限拒绝: {tool_name} 操作被安全策略拦截"
            logger.warning(error_msg)

            # 触发 PostToolUseFailure 钩子
            if self.hooks_enabled:
                self._trigger_failure_hook(tool_name, arguments, error_msg)

            return {"success": False, "error": error_msg}

        # 4. 执行工具
        try:
            handler = tool["handler"]
            result = handler(**arguments)

            # 5. 输出截断
            if isinstance(result, str) and len(result.splitlines()) > 500:
                lines = result.splitlines()
                truncated = (
                    lines[:250] +
                    [f"... (截断 {len(lines) - 500} 行) ..."] +
                    lines[-250:]
                )
                result = "\n".join(truncated)

            logger.info(f"Tool {tool_name} executed successfully")

            # 6. PostToolUse 钩子
            if self.hooks_enabled and self.hook_manager:
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                    post_result = loop.run_until_complete(
                        self.hook_manager.execute_hooks(
                            "PostToolUse",
                            tool_name=tool_name,
                            input=arguments,
                            output={"success": True, "result": result}
                        )
                    )

                    loop.close()

                    # 记录附加上下文
                    if post_result.additional_context:
                        logger.info(f"PostToolUse 钩子: {post_result.additional_context}")

                except Exception as e:
                    logger.warning(f"PostToolUse 钩子执行失败: {e}")

            return {"success": True, "result": result}

        except Exception as e:
            error_msg = f"工具执行失败: {str(e)}"
            logger.error(error_msg, exc_info=True)

            # 触发 PostToolUseFailure 钩子
            if self.hooks_enabled:
                self._trigger_failure_hook(tool_name, arguments, error_msg)

            return {"success": False, "error": error_msg}

    def _trigger_failure_hook(self, tool_name: str, arguments: Dict[str, Any], error: str):
        """触发工具失败钩子"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            loop.run_until_complete(
                self.hook_manager.execute_hooks(
                    "PostToolUseFailure",
                    tool_name=tool_name,
                    input=arguments,
                    error=error
                )
            )

            loop.close()
        except Exception as e:
            logger.warning(f"PostToolUseFailure 钩子执行失败: {e}")

    # ========== 扩展系统控制方法 ==========

    def activate_skill(self, name: str) -> bool:
        """
        激活指定的技能

        Args:
            name: 技能名称

        Returns:
            True 如果成功,False 否则
        """
        if not self.skill_manager or not self.skills_enabled:
            logger.warning("技能系统未启用")
            return False

        try:
            self.skill_manager.activate_skill(name)
            logger.info(f"激活技能: {name}")
            return True
        except ValueError as e:
            logger.warning(f"激活技能失败: {e}")
            return False

    def deactivate_skill(self, name: str) -> bool:
        """
        停用指定的技能

        Args:
            name: 技能名称

        Returns:
            True 如果成功,False 否则
        """
        if not self.skill_manager or not self.skills_enabled:
            logger.warning("技能系统未启用")
            return False

        return self.skill_manager.deactivate_skill(name)

    def list_skills(self) -> str:
        """
        列出所有可用技能

        Returns:
            技能列表字符串
        """
        if not self.skill_manager or not self.skills_enabled:
            return "技能系统未启用"

        return self.skill_manager.list_skills(detailed=True)

    def list_active_skills(self) -> List[str]:
        """
        获取已激活的技能列表

        Returns:
            已激活的技能名称列表
        """
        if not self.skill_manager or not self.skills_enabled:
            return []

        return self.skill_manager.get_active_skills()

    def register_hook(
        self,
        event: str,
        handler,
        matcher: str = None,
        priority: int = 0
    ) -> int:
        """
        手动注册钩子

        Args:
            event: 钩子事件类型
            handler: 钩子处理函数
            matcher: 可选,只匹配特定工具名称
            priority: 优先级,数字越大越先执行

        Returns:
            钩子 ID,如果失败返回 -1
        """
        if not self.hook_manager or not self.hooks_enabled:
            logger.warning("钩子系统未启用")
            return -1

        try:
            hook_id = self.hook_manager.register_hook(event, handler, matcher, priority)
            logger.info(f"注册钩子: {event} [ID: {hook_id}]")
            return hook_id
        except ValueError as e:
            logger.warning(f"注册钩子失败: {e}")
            return -1

    def unregister_hook(self, hook_id: int) -> bool:
        """
        删除钩子

        Args:
            hook_id: 钩子 ID

        Returns:
            True 如果成功,False 否则
        """
        if not self.hook_manager or not self.hooks_enabled:
            return False

        return self.hook_manager.unregister_hook(hook_id)

    def list_hooks(self) -> str:
        """
        列出所有已注册的钩子

        Returns:
            钩子列表字符串
        """
        if not self.hook_manager or not self.hooks_enabled:
            return "钩子系统未启用"

        hooks = self.hook_manager.list_hooks()
        if not hooks:
            return "没有注册的钩子"

        lines = ["已注册的钩子:", ""]
        for h in hooks:
            lines.append(f"  [ID: {h['id']}] {h['event']}")
            if h['matcher']:
                lines.append(f"    匹配: {h['matcher']}")
            lines.append(f"    优先级: {h['priority']}")
            lines.append("")

        return "\n".join(lines)

    def list_plugins(self) -> str:
        """
        列出所有已加载的插件

        Returns:
            插件列表字符串
        """
        if not self.plugin_loader or not self.plugins_enabled:
            return "插件系统未启用"

        plugins = self.plugin_loader.list_plugins()
        if not plugins:
            return "没有加载的插件"

        lines = [f"已加载的插件 (共 {len(plugins)} 个):", ""]
        for p in plugins:
            status = "✅" if p['available'] else "❌"
            lines.append(f"  {status} {p['name']} v{p['version']}")
            lines.append(f"     {p['description']}")
            lines.append("")

        return "\n".join(lines)

    def get_system_status(self) -> Dict[str, Any]:
        """
        获取扩展系统状态

        Returns:
            状态信息字典
        """
        status = {
            "plugins": {
                "enabled": self.plugins_enabled,
                "loaded": len(self.plugin_loader.plugins) if self.plugin_loader else 0
            },
            "hooks": {
                "enabled": self.hooks_enabled,
                "registered": sum(self.hook_manager.get_hook_stats().values()) if self.hook_manager else 0
            },
            "skills": {
                "enabled": self.skills_enabled,
                "total": len(self.skill_manager.skills) if self.skill_manager else 0,
                "active": len(self.skill_manager.get_active_skills()) if self.skill_manager else 0
            },
            "tools": {
                "total": len(TOOL_REGISTRY)
            }
        }

        return status
