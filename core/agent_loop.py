"""
Agent Loop 核心实现

基于 Claude Code 的 TAOR 循环(Think-Act-Observe-Repeat)设计,
实现完整的智能体交互流程。
"""

import os
import json
import logging
from typing import List, Dict, Any
from openai import OpenAI

from tools.registry import TOOL_REGISTRY, get_tool_schemas
from permissions.manager import PermissionManager
from core.context import load_project_context

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
        
        # 4. 工具定义(JSON Schema)
        self.tools = get_tool_schemas()
        
        # 5. 权限管理器
        self.permission_manager = PermissionManager(
            config.get("permission_mode", "normal")
        )
        
        logger.info(f"AgentLoop initialized with model={self.model}, "
                   f"max_iterations={self.max_iterations}")
    
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
        """构建系统提示词(简化版 4 层)"""
        parts = []
        
        # 第 1 层: 基础角色定义
        parts.append(self._base_role())
        
        # 第 2 层: 项目上下文(CLAUDE.md)
        project_context = load_project_context()
        if project_context:
            parts.append(project_context)
        
        # 第 3 层: 工具说明
        parts.append(self._tools_description())
        
        # 第 4 层: 安全规则
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
        """执行工具调用(经过权限检查)"""
        tool_name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments)
        
        logger.info(f"Executing tool: {tool_name}, args: {arguments}")
        
        # 1. 查找工具
        tool = TOOL_REGISTRY.get(tool_name)
        if not tool:
            error_msg = f"未知工具: {tool_name}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        
        # 2. 权限检查
        if not self.permission_manager.check_permission(tool_name, arguments):
            error_msg = f"权限拒绝: {tool_name} 操作被安全策略拦截"
            logger.warning(error_msg)
            return {"success": False, "error": error_msg}
        
        # 3. 执行工具
        try:
            handler = tool["handler"]
            result = handler(**arguments)
            
            # 4. 输出截断
            if isinstance(result, str) and len(result.splitlines()) > 500:
                lines = result.splitlines()
                truncated = (
                    lines[:250] + 
                    [f"... (截断 {len(lines) - 500} 行) ..."] + 
                    lines[-250:]
                )
                result = "\n".join(truncated)
            
            logger.info(f"Tool {tool_name} executed successfully")
            return {"success": True, "result": result}
            
        except Exception as e:
            error_msg = f"工具执行失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"success": False, "error": error_msg}
