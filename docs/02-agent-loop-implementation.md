# Agent Loop 核心实现

## 1. Agent Loop 概述

### 1.1 什么是 Agent Loop?

Agent Loop(智能体循环)是 Claude Code 的核心引擎,它实现了 **TAOR 循环**(Think-Act-Observe-Repeat):

```
Think (思考) → Act (行动/调用工具) → Observe (观察结果) → Repeat (重复)
```

这个循环让 AI 能够:
1. 理解用户意图
2. 决定使用哪些工具
3. 执行工具并观察结果
4. 基于结果继续决策或结束任务

### 1.2 核心伪代码

Claude Code 的 Agent Loop 本质上非常简洁:

```python
# Agent Loop 核心逻辑(~50 行)
while True:
    # Step 1: 模型推理
    response = llm.chat(messages, tools=tools)
    
    # Step 2: 检查是否结束
    if response.stop_reason == "end_turn":
        print(response.content)
        break
    
    # Step 3: 执行工具调用
    for tool_call in response.tool_calls:
        result = execute_tool(tool_call.name, tool_call.arguments)
        messages.append({"role": "user", "content": result})
    
    # Step 4: 继续循环(工具结果喂回模型)
```

> 💡 **关键洞察:** 这就是所有现代 AI Agent 的核心骨架!

---

## 2. 完整实现详解

### 2.1 类结构设计

```python
# core/agent_loop.py
import os
import json
import logging
from typing import List, Dict, Any, Optional
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
                - base_url: API 基础 URL
                - model: 模型名称(默认 gpt-4o)
                - max_iterations: 最大迭代次数(默认 20)
                - permission_mode: 权限模式(normal/auto/plan/bypass)
        """
        # 1. 初始化 LLM 客户端
        self.client = OpenAI(
            api_key=config.get("api_key") or os.environ.get("OPENAI_API_KEY"),
            base_url=config.get("base_url", "https://api.openai.com/v1")
        )
        
        # 2. 配置参数
        self.model = config.get("model", "gpt-4o")
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
                
                # 追加助手消息到历史
                self.messages.append({
                    "role": "assistant",
                    "content": assistant_content
                })
                
                # 打印助手回复(流式输出可在此处扩展)
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
                    
                    # Step 5: 工具结果追加为 user 消息
                    # (符合 API 交替规则: user/assistant/user/assistant...)
                    self.messages.append({
                        "role": "user",
                        "content": json.dumps(tool_result, ensure_ascii=False)
                    })
                    
                    # 打印工具执行结果
                    print(f"✅ Tool Result: {tool_result.get('result', '')[:200]}")
                
                # Step 6: 继续循环(工具结果会喂回 LLM)
                
            except Exception as e:
                logger.error(f"Iteration {iteration} failed: {e}", exc_info=True)
                return f"❌ 错误: {str(e)}"
        
        # 达到最大迭代次数
        logger.warning("Reached max iterations")
        return "⚠️ 达到最大迭代次数,任务未完成。请尝试简化任务或增加 max_iterations。"
    
    def _init_messages(self, user_input: str):
        """
        初始化消息历史(系统提示词 + 用户输入)
        
        Args:
            user_input: 用户输入
        """
        system_prompt = self._build_system_prompt()
        self.messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ]
        logger.debug(f"Messages initialized, system prompt length: {len(system_prompt)}")
    
    def _build_system_prompt(self) -> str:
        """
        构建系统提示词(简化版 4 层)
        
        Returns:
            完整的系统提示词字符串
        """
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
        """
        调用 LLM,传入消息历史和工具定义
        
        Returns:
            OpenAI ChatCompletion 响应对象
        """
        logger.debug(f"Calling LLM with {len(self.messages)} messages")
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=self.messages,
            tools=self.tools,
            tool_choice="auto",  # 让模型自动决定是否调用工具
            temperature=0.2,     # 较低温度,提高确定性
            max_tokens=4096
        )
        
        # 记录 token 使用情况(可选)
        usage = response.usage
        if usage:
            logger.info(f"Token usage: prompt={usage.prompt_tokens}, "
                       f"completion={usage.completion_tokens}, "
                       f"total={usage.total_tokens}")
        
        return response
    
    def _execute_tool(self, tool_call) -> Dict[str, Any]:
        """
        执行工具调用(经过权限检查)
        
        Args:
            tool_call: OpenAI ToolCall 对象
            
        Returns:
            工具执行结果字典
        """
        tool_name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments)
        
        logger.info(f"Executing tool: {tool_name}, args: {arguments}")
        
        # 1. 查找工具
        tool = TOOL_REGISTRY.get(tool_name)
        if not tool:
            error_msg = f"未知工具: {tool_name}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        
        # 2. 权限检查(三道防线第一道:黑名单)
        if not self.permission_manager.check_permission(tool_name, arguments):
            error_msg = f"权限拒绝: {tool_name} 操作被安全策略拦截"
            logger.warning(error_msg)
            return {"success": False, "error": error_msg}
        
        # 3. 执行工具(沙箱环境)
        try:
            handler = tool["handler"]
            result = handler(**arguments)
            
            # 4. 输出截断(防止上下文溢出)
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
```

---

## 3. 消息管理系统

### 3.1 消息类型定义

Claude Code 使用**扁平消息历史**,所有消息按时间顺序存储在列表中:

```python
# core/message.py
from typing import List, Dict, Any, Literal

MessageType = Literal["system", "user", "assistant", "tool"]

Message = Dict[str, Any]

def create_system_message(content: str) -> Message:
    """创建系统消息"""
    return {"role": "system", "content": content}

def create_user_message(content: str) -> Message:
    """创建用户消息"""
    return {"role": "user", "content": content}

def create_assistant_message(content: str) -> Message:
    """创建助手消息"""
    return {"role": "assistant", "content": content}

def create_tool_result_message(content: str) -> Message:
    """创建工具结果消息(以 user 角色返回)"""
    return {"role": "user", "content": content}

def validate_message_sequence(messages: List[Message]) -> bool:
    """
    验证消息序列是否符合交替规则
    
    规则:
    - system 消息只能在开头
    - user 和 assistant 必须交替出现
    - tool 结果必须以 user 角色返回
    """
    if not messages:
        return False
    
    # 检查 system 消息位置
    if messages[0]["role"] != "system":
        return False
    
    # 检查交替规则
    for i in range(1, len(messages)):
        prev_role = messages[i-1]["role"]
        curr_role = messages[i]["role"]
        
        # system 后必须是 user
        if prev_role == "system" and curr_role != "user":
            return False
        
        # user 后可以是 assistant 或 user(tool 结果)
        # assistant 后必须是 user
        if prev_role == "assistant" and curr_role != "user":
            return False
    
    return True
```

### 3.2 角色交替规则

OpenAI/Claude API 要求严格的消息角色交替:

```
✅ 正确:
system → user → assistant → user(tool result) → assistant → user → ...

❌ 错误:
system → user → user (连续两个 user)
user → assistant → assistant (连续两个 assistant)
```

**为什么工具结果要以 user 角色返回?**

因为 API 要求 `user` 和 `assistant` 必须交替,而工具结果是"环境反馈",不是助手的主动行为,所以归类为 user 消息。

---

## 4. 系统提示词组装(4 层结构)

### 4.1 层级说明

| 层级 | 内容 | 稳定性 | Token 占用 |
|------|------|-------|-----------|
| 1. 角色定义 | "你是 AI 编程助手..." | 固定 | ~100 |
| 2. 项目上下文 | CLAUDE.md + 技术栈检测 | 每次会话加载 | ~500-2000 |
| 3. 工具说明 | 工具列表 + 参数描述 | 固定 | ~300 |
| 4. 安全规则 | 禁止操作清单 | 固定 | ~150 |

### 4.2 动态注入示例

```python
def _build_system_prompt(self) -> str:
    parts = []
    
    # 第 1 层: 基础角色(固定)
    parts.append("""你是一个 AI 编程助手...""")
    
    # 第 2 层: 项目上下文(动态加载)
    project_context = load_project_context()
    if project_context:
        parts.append(project_context)
    # 示例输出:
    # ## 项目约定
    # - 使用 FastAPI 构建 REST API
    # - PostgreSQL 作为主数据库
    # 
    # ## 技术栈
    # - Python 项目
    # - Node.js/JavaScript 项目
    
    # 第 3 层: 工具说明(从注册表动态生成)
    parts.append("""可用工具:
- read_file: 读取指定路径的文件内容
- write_file: 写入内容到指定文件
- run_command: 执行 Shell 命令
- list_directory: 列出目录内容""")
    
    # 第 4 层: 安全规则(固定)
    parts.append("""安全规则:
1. 不要在系统目录外执行危险命令
2. 修改文件前先备份或确认
3. 永远不要执行 rm -rf / 等危险操作""")
    
    return "\n\n".join(parts)
```

---

## 5. 错误处理与重试

### 5.1 API 超时重试(指数退避)

```python
import time
from openai import APITimeoutError, APIConnectionError

def _call_llm_with_retry(self, max_retries: int = 3):
    """
    调用 LLM 带重试机制
    
    Args:
        max_retries: 最大重试次数
        
    Returns:
        OpenAI ChatCompletion 响应
    """
    for attempt in range(max_retries):
        try:
            return self._call_llm()
        
        except (APITimeoutError, APIConnectionError) as e:
            if attempt == max_retries - 1:
                raise  # 最后一次重试仍失败,抛出异常
            
            # 指数退避: 1s, 2s, 4s, ...
            wait_time = 2 ** attempt
            logger.warning(f"API call failed (attempt {attempt + 1}): {e}. "
                         f"Retrying in {wait_time}s...")
            time.sleep(wait_time)
        
        except Exception as e:
            # 其他错误不重试,直接抛出
            logger.error(f"Unexpected error: {e}", exc_info=True)
            raise
```

### 5.2 工具执行异常捕获

```python
def _execute_tool(self, tool_call) -> Dict[str, Any]:
    try:
        # ... 权限检查 ...
        
        handler = tool["handler"]
        result = handler(**arguments)
        
        return {"success": True, "result": result}
    
    except FileNotFoundError as e:
        return {"success": False, "error": f"文件不存在: {e}"}
    
    except PermissionError as e:
        return {"success": False, "error": f"权限不足: {e}"}
    
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "命令执行超时(30s)"}
    
    except Exception as e:
        logger.error(f"Tool execution failed: {e}", exc_info=True)
        return {"success": False, "error": f"未知错误: {str(e)}"}
```

### 5.3 最大迭代次数限制

```python
# 防止无限循环导致 API 费用失控
MAX_ITERATIONS = 20  # 默认值,可通过配置调整

while iteration < MAX_ITERATIONS:
    # ... Agent Loop 逻辑 ...

return "⚠️ 达到最大迭代次数,任务未完成。"
```

---

## 6. 日志与调试

### 6.1 日志级别设计

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# 日志级别使用规范:
# DEBUG   - 详细调试信息(消息历史、token 使用)
# INFO    - 正常流程(迭代次数、工具调用)
# WARNING - 潜在问题(接近最大迭代次数)
# ERROR   - 错误但可恢复(API 超时、工具执行失败)
# CRITICAL - 严重错误(配置缺失、无法启动)
```

### 6.2 关键日志点

```python
# 1. Agent Loop 启动
logger.info(f"Starting agent loop with input: {user_input[:50]}...")

# 2. 每次迭代
logger.info(f"Iteration {iteration}/{self.max_iterations}")

# 3. LLM 调用
logger.debug(f"Calling LLM with {len(self.messages)} messages")
logger.info(f"Token usage: prompt={usage.prompt_tokens}, ...")

# 4. 工具执行
logger.info(f"Executing tool: {tool_name}, args: {arguments}")
logger.info(f"Tool {tool_name} executed successfully")

# 5. 错误处理
logger.error(f"Iteration {iteration} failed: {e}", exc_info=True)
logger.warning(f"Reached max iterations")
```

---

## 7. 单元测试示例

### 7.1 测试 Agent Loop 基本功能

```python
# tests/test_agent_loop.py
import pytest
from unittest.mock import Mock, patch
from core.agent_loop import AgentLoop


@pytest.fixture
def mock_openai_response():
    """模拟 OpenAI 响应"""
    response = Mock()
    response.choices = [Mock()]
    response.choices[0].message = Mock()
    response.choices[0].message.content = "任务完成"
    response.choices[0].message.tool_calls = None
    response.usage = Mock()
    response.usage.prompt_tokens = 100
    response.usage.completion_tokens = 50
    response.usage.total_tokens = 150
    return response


def test_agent_loop_basic(mock_openai_response):
    """测试 Agent Loop 基本流程"""
    config = {
        "api_key": "test-key",
        "model": "gpt-4o",
        "max_iterations": 5,
        "permission_mode": "bypass"
    }
    
    loop = AgentLoop(config)
    
    # Mock LLM 调用
    with patch.object(loop.client.chat.completions, 'create', 
                     return_value=mock_openai_response):
        result = loop.run("你好")
        
        assert result == "任务完成"
        assert len(loop.messages) == 3  # system + user + assistant


def test_agent_loop_max_iterations():
    """测试最大迭代次数限制"""
    config = {
        "api_key": "test-key",
        "max_iterations": 2
    }
    
    loop = AgentLoop(config)
    
    # Mock 始终返回工具调用(触发无限循环)
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message = Mock()
    mock_response.choices[0].message.content = ""
    mock_response.choices[0].message.tool_calls = [Mock()]
    
    with patch.object(loop.client.chat.completions, 'create', 
                     return_value=mock_response):
        with patch.object(loop, '_execute_tool', 
                         return_value={"success": True, "result": "ok"}):
            result = loop.run("测试")
            
            assert "达到最大迭代次数" in result


def test_build_system_prompt():
    """测试系统提示词组装"""
    config = {"api_key": "test-key"}
    loop = AgentLoop(config)
    
    prompt = loop._build_system_prompt()
    
    assert "AI 编程助手" in prompt
    assert "可用工具" in prompt
    assert "安全规则" in prompt
```

### 7.2 测试消息管理

```python
def test_message_sequence_validation():
    """测试消息序列验证"""
    from core.message import validate_message_sequence, create_system_message, \
                             create_user_message, create_assistant_message
    
    # 正确序列
    messages = [
        create_system_message("You are helpful"),
        create_user_message("Hello"),
        create_assistant_message("Hi!"),
        create_user_message("Thanks")
    ]
    assert validate_message_sequence(messages) is True
    
    # 错误序列(缺少 system)
    messages = [
        create_user_message("Hello"),
        create_assistant_message("Hi!")
    ]
    assert validate_message_sequence(messages) is False
    
    # 错误序列(连续 assistant)
    messages = [
        create_system_message("You are helpful"),
        create_user_message("Hello"),
        create_assistant_message("Hi!"),
        create_assistant_message("How are you?")
    ]
    assert validate_message_sequence(messages) is False
```

---

## 8. 性能优化建议

### 8.1 Token 使用监控

```python
def _call_llm(self):
    response = self.client.chat.completions.create(...)
    
    usage = response.usage
    if usage:
        total_cost = (
            usage.prompt_tokens * 0.000005 +  # GPT-4o 价格
            usage.completion_tokens * 0.000015
        )
        logger.info(f"Token usage: {usage.total_tokens}, "
                   f"Estimated cost: ${total_cost:.4f}")
    
    return response
```

### 8.2 消息历史压缩(Phase 2 扩展)

```python
def _compress_messages(self):
    """
    当消息历史过长时,压缩早期消息
    
    策略:
    1. 保留最近的 5 轮对话
    2. 将早期对话摘要为 "Previous conversation summary: ..."
    3. 保留 system 消息不变
    """
    if len(self.messages) < 20:  # 阈值可调
        return
    
    # 简化实现: 只保留最近 10 条消息
    system_msg = self.messages[0]
    recent_messages = self.messages[-10:]
    self.messages = [system_msg] + recent_messages
    
    logger.info(f"Messages compressed to {len(self.messages)}")
```

---

## 9. 常见问题

### Q1: 为什么工具结果要以 user 角色返回?

**A:** OpenAI/Claude API 要求 `user` 和 `assistant` 必须交替出现。工具结果是"环境反馈",不是助手的主动行为,所以归类为 user 消息。

```python
# ✅ 正确
messages.append({"role": "user", "content": json.dumps(tool_result)})

# ❌ 错误(会导致 API 报错)
messages.append({"role": "tool", "content": json.dumps(tool_result)})
```

### Q2: 如何实现流式输出?

**A:** 使用 OpenAI SDK 的 `stream=True` 参数:

```python
def _call_llm_streaming(self):
    stream = self.client.chat.completions.create(
        model=self.model,
        messages=self.messages,
        tools=self.tools,
        stream=True  # 启用流式
    )
    
    full_content = ""
    for chunk in stream:
        if chunk.choices[0].delta.content:
            content = chunk.choices[0].delta.content
            full_content += content
            print(content, end="", flush=True)  # 实时打印
    
    return full_content
```

### Q3: 如何支持多轮对话?

**A:** 保持 `self.messages` 不被清空,每次 `run()` 只追加新消息:

```python
# cli.py
loop = AgentLoop(config)

while True:
    user_input = input("> ")
    if user_input.lower() in ["exit", "quit"]:
        break
    
    # 消息历史会累积,实现多轮对话
    result = loop.run(user_input)
    print(result)
```

---

**文档版本:** v1.0  
**最后更新:** 2026-04-05  
**相关文档:** 
- [文档 1: 架构总览](./01-architecture-overview.md)
- [文档 3: 工具系统与权限管理](./03-tools-and-permissions.md)
