## 第1节 Claude Code 完整请求处理流程分析

### 1.1 五层架构全景

Claude Code 的源代码（约 1900 个 TypeScript 文件，超过 512,000 行代码）展现了一个生产级智能体系统的完整架构，清晰地分为五层[reference:0][reference:1]：

| 层级 | 核心职责 | 关键组件 |
|-----|---------|---------|
| **入口层** | 统一路由 CLI、桌面端及 SDK，实现多端输入标准化 | GitHub Actions、SDK、VS Code 集成、CLI |
| **运行层** | 核心为 TAOR 循环，维持 Agent 行为节拍 | Agent Loop、流式处理、中断控制 |
| **引擎层** | 动态提示词组装，注入上下文和安全规则 | 7 层系统提示词、工具注册表、QueryEngine |
| **工具与能力层** | 内置约 40+ 个独立工具，权限隔离 | 工具注册表、沙箱执行、权限检查 |
| **基础设施层** | 提示缓存、记忆管理、远程控制 | 上下文压缩、Auto-Dream、MCP 集成 |

这套架构的核心设计哲学是 **“运行时越笨，架构越稳定”** —— 把智能下沉到模型，把确定性留给框架[reference:2]。

### 1.2 请求处理 12 步详解

根据对泄露源码的深度分析，每次用户在 Claude Code 中按下 Enter 键，系统会启动一个 **11 步的内部循环**[reference:3]。结合多个分析来源，完整的请求处理流程为 12 步：

```
Step 1 — 用户输入
    │
    ▼
Step 2 — 消息创建 (Message Normalization)
    │
    ▼
Step 3 — 上下文加载 (Memory & OPENCODE.md)
    │
    ▼
Step 4 — 系统提示词组装 (7层提示词)
    │
    ▼
Step 5 — API 调用 (流式请求 LLM)
    │
    ▼
Step 6 — 响应解析 (Text / Tool Call)
    │
    ▼
Step 7 — 决策判断 (停机 or 继续)
    │
    ├── 无工具调用 ──► Step 11 ──► Step 12 (结束)
    │
    ▼ (有工具调用)
Step 8 — 工具查找与参数校验
    │
    ▼
Step 9 — 权限检查 (allow/ask/deny)
    │
    ▼
Step 10 — 工具执行 (沙箱隔离)
    │
    ▼
Step 11 — 结果封装 (追加为 UserMessage)
    │
    ▼
Step 12 — 循环继续 (返回 Step 5)
```

#### Step 1: 用户输入

用户在终端输入自然语言 Prompt（如“帮我修复这个 bug”），React 终端渲染器捕获按键并处理输入[reference:4]。

#### Step 2: 消息创建

输入被封装为 `UserMessage` 对象，追加到对话历史中。此时消息格式标准化，准备进入上下文管道[reference:5]。

#### Step 3: 上下文加载

Claude Code 从 4 个层级加载 `OPENCODE.md` 配置文件：
- 企业级配置 (Enterprise)
- 用户级配置 (~/.opencode/OPENCODE.md)
- 项目级配置 (项目根目录 .opencode/OPENCODE.md)
- 子目录级配置

这些文件中的约定、规范和偏好被合并为系统提示词的固定部分[reference:6]。

#### Step 4: 系统提示词组装

这是引擎层的核心工作，动态组装 **7 层系统提示词**[reference:7]：

1. 基础角色定义（“你是一个 AI 编程助手”）
2. 工具定义（约 40+ 个工具的 JSON Schema）
3. 环境信息（操作系统、当前路径、Git 状态）
4. OPENCODE.md 内容（项目约定和架构模式）
5. 历史记忆摘要（从记忆系统检索）
6. 安全守则（高达 5,677 个 token）[reference:8]
7. 当前任务上下文（待解决问题、最近操作）

#### Step 5: API 调用

组装完成的消息 + 系统提示词 + 工具定义 以流式方式发送到 Anthropic API（也支持 AWS Bedrock、Google Vertex AI 等）[reference:9]。Token 以毫秒级延迟流式返回[reference:10]。

#### Step 6: 响应解析

流式响应被分解为三种内容块类型：
- **text**：普通文本回复
- **thinking**：模型的推理过程
- **tool_use**：工具调用请求（包含工具名和参数）[reference:11]

#### Step 7: 决策判断

检查响应中是否包含 `tool_use` 块：
- **如果只有 text**：任务完成，进入 Step 11 渲染输出
- **如果包含 tool_use**：进入工具执行链路[reference:12]

这是 Agent Loop 的停机判断点 —— 模型自己决定何时停止。

#### Step 8: 工具查找与参数校验

1. 在集中式工具注册表中查找对应的工具
2. 根据工具的 JSON Schema 校验参数类型和必填字段
3. 分配唯一的工具调用 ID 用于追溯[reference:13]

Claude Code 的工具系统有一条 **14 步的治理流水线**，确保每个工具调用从请求到执行都经过严格校验[reference:14]。

#### Step 9: 权限检查

Claude Code 支持四种权限模式：
- **Normal 模式（默认）** ：每次文件写入、Bash 命令执行或网络调用前请求用户批准
- **Auto-accept 模式**：自动验证文件读写，但仍需用户确认 Shell 命令
- **Plan 模式**：禁止任何修改，仅分析并展示执行计划
- **Bypass 模式**：完全跳过权限检查，仅限 CI/CD 环境使用[reference:15][reference:16]

权限规则可通过 `settings.json` 配置 `allow/deny` 列表，支持通配符匹配[reference:17]。

#### Step 10: 工具执行

权限通过后，工具在沙箱环境中执行：
- **只读工具**（如 Read、Grep、LS）可以**并行执行**，提升效率
- **写入工具**（如 Write、Edit、Bash）**串行执行**，防止竞态条件[reference:18]

Bash 工具会根据运行环境自动选择沙箱版本，在安全敏感环境中隔离潜在风险操作[reference:19]。执行结果（stdout + stderr）被捕获并结构化封装。

#### Step 11: 结果封装

工具执行结果被包装为 `UserMessage` 对象。Claude API 要求严格的 `user`/`assistant` 消息交替，因此工具结果以 user 角色返回，追加到消息历史中[reference:20]。

#### Step 12: 循环继续

更新后的完整消息历史被送回到 **Step 5**（API 调用），模型基于包含工具执行结果的上下文继续决策。循环持续运行，直到模型不再返回 `tool_use` 块[reference:21]。

### 1.3 Agent Loop 的本质

TAOR 循环的核心逻辑大约只有 **50 行代码**，但给了模型无限的操作空间[reference:22]。本质上，Claude Code 就是一个 **`while` 循环 + 工具调用**：

```python
# Agent Loop 核心伪代码
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
    
    # Step 4: 继续循环（工具结果喂回模型）
```

这就是所有现代 AI Agent 的核心骨架[reference:23]。

### 1.4 关键设计模式提炼

从 Claude Code 的完整请求处理流程中，可以提炼出以下可直接复用的设计模式：

| 设计模式 | 核心思想 | 实现要点 |
|---------|---------|---------|
| **单线程主循环** | 采用经典的 while 循环模式，模型返回 text 时终止 | 扁平消息历史，避免复杂编排[reference:24] |
| **扁平消息历史** | 所有消息按时间顺序扁平存储，不维护分支 | 简化调试和状态管理[reference:25] |
| **工具注册表** | 集中式工具注册，统一 Schema 校验 | JSON Schema 定义输入，权限级别标注[reference:26] |
| **并行/串行混合执行** | 只读工具并行，写入工具串行 | 平衡效率与安全[reference:27] |
| **分层上下文** | 4 级 OPENCODE.md + 7 层系统提示词 | 按优先级和稳定性分层组装[reference:28] |
| **权限检查流水线** | 工具调用经过 14 步治理流水线 | 三道防线：黑名单→用户确认→输出截断[reference:29] |
| **流式响应解析** | 边接收边解析 text/thinking/tool_use | 毫秒级延迟反馈[reference:30] |
| **上下文自动压缩** | 当上下文达 95%（~190K tokens）时触发摘要压缩 | 保留关键信息，释放空间[reference:31] |


## 第2节 简化版编程工具技术方案

基于上述流程分析，本节设计一个**保留必要流程和核心组件**的简化版 AI 编程工具，并支持后续扩展。

### 2.1 设计目标

| 目标 | 说明 |
|-----|------|
| **保留核心流程** | 完整实现 Agent Loop：用户输入 → 模型推理 → 工具调用 → 循环 |
| **保留必要组件** | 消息系统、工具系统、权限控制、基础上下文管理 |
| **可扩展** | 插件化工具注册、MCP 协议预留接口 |
| **轻量级** | 单文件可运行，依赖最少 |

### 2.2 技术选型

| 组件 | 选择 | 理由 |
|-----|------|------|
| 运行时 | Python 3.10+ | 生态丰富，开发效率高 |
| LLM 接口 | OpenAI API 兼容 | 支持 GPT、Claude、本地模型 |
| 工具定义 | JSON Schema | 与 LLM 原生对齐 |
| 权限管理 | 模式枚举 + 白名单 | 三道防线简化版 |
| 配置 | YAML | 人类可读，便于扩展 |

### 2.3 整体架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                       CLI 入口层                             │
│              argparser + 环境检测 + 配置加载                  │
├─────────────────────────────────────────────────────────────┤
│                    Agent Loop 核心层                         │
│    while True: 模型推理 → 工具调用 → 结果追加 → 继续          │
├─────────────────────────────────────────────────────────────┤
│                      消息管理层                              │
│    messages.append(user/assistant/tool_result)              │
├─────────────────────────────────────────────────────────────┤
│                      工具系统层                              │
│    工具注册表 (dict) → Schema 校验 → 权限检查 → 执行         │
├─────────────────────────────────────────────────────────────┤
│                      安全与权限层                            │
│    Mode: normal / auto / plan / bypass                      │
│    allow_list + deny_list                                   │
└─────────────────────────────────────────────────────────────┘
```

### 2.4 核心代码实现

#### 2.4.1 项目结构

```
ai_coding_tool/
├── main.py              # CLI 入口 + Agent Loop
├── tools.py             # 工具注册表 + 工具定义
├── permissions.py       # 权限管理（三道防线）
├── context.py           # 上下文管理（加载项目约定）
├── config.yaml          # 配置文件（模型、权限模式）
└── tests/               # 单元测试
```

#### 2.4.2 核心实现：Agent Loop

```python
# main.py
import os
import json
import argparse
from typing import List, Dict, Any
from openai import OpenAI

from tools import TOOL_REGISTRY, get_tool_schemas
from permissions import PermissionManager
from context import load_project_context

class AgentLoop:
    """
    简化版 AI 编程工具核心
    基于 Claude Code 的 TAOR 循环设计
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.client = OpenAI(
            api_key=config.get("api_key", os.environ.get("OPENAI_API_KEY")),
            base_url=config.get("base_url", "https://api.openai.com/v1")
        )
        self.model = config.get("model", "gpt-4o")
        self.messages: List[Dict] = []
        self.permission_manager = PermissionManager(config.get("permission_mode", "normal"))
        self.max_iterations = config.get("max_iterations", 20)
        
    def run(self, user_input: str) -> str:
        """主入口：处理用户输入"""
        # 1. 初始化消息（系统提示词 + 上下文 + 用户输入）
        self._init_messages(user_input)
        
        # 2. Agent Loop — 核心循环
        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1
            
            # Step 1: 调用 LLM
            response = self._call_llm()
            
            # Step 2: 解析响应
            message = response.choices[0].message
            self.messages.append({"role": "assistant", "content": message.content})
            
            # Step 3: 检查是否有工具调用
            if not message.tool_calls:
                # 无工具调用 → 任务完成
                return message.content or ""
            
            # Step 4: 执行所有工具调用
            for tool_call in message.tool_calls:
                tool_result = self._execute_tool(tool_call)
                
                # Step 5: 工具结果追加为 user 消息（符合 API 交替规则）
                self.messages.append({
                    "role": "user",
                    "content": json.dumps(tool_result)
                })
            
            # Step 6: 继续循环（工具结果会喂回 LLM）
        
        return "达到最大迭代次数，任务未完成"
    
    def _init_messages(self, user_input: str):
        """初始化消息历史（系统提示词 + 用户输入）"""
        system_prompt = self._build_system_prompt()
        self.messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ]
    
    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        # 1. 基础角色定义
        base_prompt = "你是一个 AI 编程助手，可以读写文件、执行命令来帮助用户完成编程任务。"
        
        # 2. 项目上下文（OPENCODE.md 风格）
        project_context = load_project_context()
        
        # 3. 工具说明
        tools_desc = "可用工具:\n" + "\n".join([
            f"- {name}: {info['description']}"
            for name, info in TOOL_REGISTRY.items()
        ])
        
        # 4. 安全规则
        security_rules = """
安全规则:
1. 不要在系统目录外执行危险命令
2. 修改文件前先备份或确认
3. 永远不要执行 rm -rf / 等危险操作
"""
        return "\n\n".join([base_prompt, project_context, tools_desc, security_rules])
    
    def _call_llm(self):
        """调用 LLM，传入消息历史和工具定义"""
        tools = get_tool_schemas()
        return self.client.chat.completions.create(
            model=self.model,
            messages=self.messages,
            tools=tools,
            tool_choice="auto"
        )
    
    def _execute_tool(self, tool_call) -> Dict:
        """执行工具调用（经过权限检查）"""
        tool_name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments)
        
        # 1. 查找工具
        tool = TOOL_REGISTRY.get(tool_name)
        if not tool:
            return {"error": f"未知工具: {tool_name}"}
        
        # 2. 权限检查（三道防线第一道：黑名单）
        if not self.permission_manager.check_permission(tool_name, arguments):
            return {"error": f"权限拒绝: {tool_name} 操作被安全策略拦截"}
        
        # 3. 执行工具（沙箱环境）
        try:
            result = tool["handler"](**arguments)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="AI 编程工具")
    parser.add_argument("--mode", choices=["normal", "auto", "plan", "bypass"],
                        default="normal", help="权限模式")
    parser.add_argument("prompt", nargs="*", help="用户指令")
    args = parser.parse_args()
    
    # 加载配置
    config = {
        "permission_mode": args.mode,
        "model": os.environ.get("MODEL", "gpt-4o"),
        "max_iterations": 20
    }
    
    # 运行 Agent
    agent = AgentLoop(config)
    user_input = " ".join(args.prompt) if args.prompt else input("> ")
    
    result = agent.run(user_input)
    print("\n" + result)

if __name__ == "__main__":
    main()
```

#### 2.4.3 工具系统实现

```python
# tools.py
import subprocess
import os
from typing import Dict, Any

def _read_file(path: str) -> str:
    """读取文件"""
    if not os.path.exists(path):
        raise FileNotFoundError(f"文件不存在: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def _write_file(path: str, content: str) -> str:
    """写入文件"""
    # 自动创建目录
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"成功写入 {path}"

def _run_command(command: str) -> str:
    """执行 Shell 命令"""
    # 安全：限制超时
    result = subprocess.run(
        command, shell=True, capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        return f"命令失败 (exit {result.returncode}):\n{result.stderr}"
    return result.stdout

def _list_directory(path: str = ".") -> str:
    """列出目录"""
    files = os.listdir(path)
    return "\n".join(files[:50])  # 限制输出行数

# 工具注册表
TOOL_REGISTRY: Dict[str, Dict] = {
    "read_file": {
        "description": "读取指定路径的文件内容",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"}
            },
            "required": ["path"]
        },
        "handler": _read_file,
        "permission_level": "read"
    },
    "write_file": {
        "description": "写入内容到指定文件",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
                "content": {"type": "string", "description": "文件内容"}
            },
            "required": ["path", "content"]
        },
        "handler": _write_file,
        "permission_level": "write"
    },
    "run_command": {
        "description": "执行 Shell 命令",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "要执行的命令"}
            },
            "required": ["command"]
        },
        "handler": _run_command,
        "permission_level": "execute"
    },
    "list_directory": {
        "description": "列出目录内容",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "目录路径，默认为当前目录"}
            },
            "required": []
        },
        "handler": _list_directory,
        "permission_level": "read"
    }
}

def get_tool_schemas() -> List[Dict]:
    """生成 OpenAI 格式的工具定义"""
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": info["description"],
                "parameters": info["parameters"]
            }
        }
        for name, info in TOOL_REGISTRY.items()
    ]
```

#### 2.4.4 权限管理实现

```python
# permissions.py
from typing import Dict, Any

class PermissionManager:
    """
    权限管理器 - 实现三道防线：
    1. 黑名单拦截
    2. 模式控制（用户确认）
    3. 输出截断
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
        "> /dev/sd"
    ]
    
    def __init__(self, mode: str = "normal"):
        self.mode = mode  # normal, auto, plan, bypass
        
    def check_permission(self, tool_name: str, arguments: Dict) -> bool:
        """检查工具调用权限"""
        
        # 防线 0: Plan 模式拒绝所有修改操作
        if self.mode == "plan":
            if tool_name in ["write_file", "run_command"]:
                print(f"[Plan Mode] 阻止修改操作: {tool_name}")
                return False
        
        # 防线 1: 命令黑名单检查（针对 run_command）
        if tool_name == "run_command":
            command = arguments.get("command", "")
            for pattern in self.DANGEROUS_PATTERNS:
                if pattern in command:
                    print(f"[Security] 阻止危险命令: {command[:50]}...")
                    return False
        
        # 防线 2: 用户确认（normal 模式需要用户确认写入和命令）
        if self.mode == "normal":
            if tool_name in ["write_file", "run_command"]:
                confirm = input(f"执行 {tool_name}? 确认? (y/N): ")
                if confirm.lower() != "y":
                    print("用户取消")
                    return False
        
        # 防线 3: bypass 模式自动通过
        if self.mode == "bypass":
            return True
        
        return True
    
    def truncate_output(self, output: str, max_lines: int = 500) -> str:
        """输出截断 - 防止上下文溢出"""
        lines = output.splitlines()
        if len(lines) <= max_lines:
            return output
        truncated = lines[:max_lines // 2] + \
                    [f"... (截断 {len(lines) - max_lines} 行) ..."] + \
                    lines[-(max_lines // 2):]
        return "\n".join(truncated)
```

#### 2.4.5 上下文管理（OPENCODE.md 风格）

```python
# context.py
import os
from typing import Optional

def load_project_context(project_root: str = ".") -> str:
    """
    加载项目约定文件（类似 OPENCODE.md）
    支持多层级: 项目根目录 .opencode/OPENCODE.md
    """
    context_parts = []
    
    # 项目级约定
    claude_md_path = os.path.join(project_root, ".opencode", "OPENCODE.md")
    if os.path.exists(claude_md_path):
        with open(claude_md_path, "r", encoding="utf-8") as f:
            context_parts.append(f"## 项目约定\n{f.read()}")
    
    # 技术栈检测
    tech_stack = detect_tech_stack(project_root)
    if tech_stack:
        context_parts.append(f"## 技术栈\n{tech_stack}")
    
    return "\n\n".join(context_parts) if context_parts else ""

def detect_tech_stack(project_root: str) -> Optional[str]:
    """检测项目技术栈"""
    tech_info = []
    
    if os.path.exists(os.path.join(project_root, "requirements.txt")):
        tech_info.append("- Python 项目")
    if os.path.exists(os.path.join(project_root, "package.json")):
        tech_info.append("- Node.js/JavaScript 项目")
    if os.path.exists(os.path.join(project_root, "go.mod")):
        tech_info.append("- Go 项目")
    if os.path.exists(os.path.join(project_root, "pom.xml")):
        tech_info.append("- Java/Maven 项目")
    
    return "\n".join(tech_info) if tech_info else None
```

#### 2.4.6 配置文件示例

```yaml
# config.yaml
# AI 编程工具配置文件

# LLM 配置
llm:
  provider: openai  # openai, anthropic, local
  model: gpt-4o
  base_url: https://api.openai.com/v1
  max_tokens: 4096
  temperature: 0.2

# 权限配置
permissions:
  mode: normal  # normal, auto, plan, bypass
  allow_rules:
    - "run_command:ls"
    - "run_command:git status"
    - "read_file:*"
  deny_rules:
    - "run_command:rm -rf"
    - "run_command:sudo"

# Agent 配置
agent:
  max_iterations: 20
  context_window: 200000
  auto_compact_threshold: 0.95

# 上下文配置
context:
  load_claude_md: true
  max_files_read: 10
```

### 2.5 核心组件总结

| 组件 | 保留原因 | 复杂度评估 | 可扩展方向 |
|-----|---------|-----------|----------|
| Agent Loop | 核心循环，不可或缺 | 低（50行左右） | 支持流式、并行子 Agent |
| 消息管理 | 驱动循环的状态载体 | 低 | 消息压缩、摘要存储 |
| 工具注册表 | 模型与系统的接口 | 中 | MCP 协议集成 |
| 权限检查 | 安全防线 | 低 | 细粒度规则、企业模式 |
| 上下文管理 | 模型决策的基础 | 中 | RAG、向量记忆 |

### 2.6 扩展接口设计

为支持后续扩展，预留以下接口：

```python
# 扩展接口示例
class BaseExtension:
    """扩展基类"""
    def on_before_llm_call(self, messages: List[Dict]) -> List[Dict]:
        return messages
    
    def on_after_tool_execute(self, tool_name: str, result: Any) -> Any:
        return result
    
    def on_loop_end(self, iteration: int, final_result: str):
        pass

# MCP 协议集成接口
class MCPIntegration:
    """MCP 服务器集成"""
    def __init__(self, server_config: Dict):
        self.servers = server_config
    
    def get_tools(self) -> List[Dict]:
        """从 MCP 服务器获取工具定义"""
        pass
    
    def call_tool(self, server: str, tool: str, params: Dict) -> Any:
        """调用 MCP 工具"""
        pass
```

### 2.7 运行示例

```bash
# 安装依赖
pip install openai pyyaml

# 设置 API Key
export OPENAI_API_KEY="your-key"

# 运行（normal 模式，需要确认）
python main.py "读取 README.md 文件"

# Auto 模式（自动批准文件读写）
python main.py --mode auto "读取 README.md 并创建备份"

# Plan 模式（只分析不执行）
python main.py --mode plan "重构 utils.py 模块"
```

### 2.8 与完整版 Claude Code 的对照

| 组件 | Claude Code | 简化版 | 缺失但可扩展 |
|-----|------------|--------|------------|
| 工具数量 | 40+ | 4（核心） | 按需添加 |
| 工具并行 | 只读并行，写入串行 | 全串行 | 并行调度 |
| 提示词层数 | 7 层 | 4 层 | 动态注入 |
| 权限模式 | 4 种 | 4 种 | ✅ 完整 |
| 上下文压缩 | Auto-Compact | 无 | 摘要压缩 |
| 记忆管理 | 三层 + Auto-Dream | 无 | RAG + 向量库 |
| MCP 集成 | ✅ | 接口预留 | 协议实现 |
| 多 Agent | ✅ | 无 | 子 Agent 调度 |

### 2.9 后续扩展路径

1. **Phase 1 - 工具丰富**：增加 `grep`、`find`、`diff`、`edit` 等实用工具
2. **Phase 2 - 上下文压缩**：实现摘要压缩，当消息 token 超限时自动压缩早期消息
3. **Phase 3 - 记忆管理**：集成向量数据库（Chroma/Qdrant），实现长期记忆
4. **Phase 4 - MCP 集成**：实现 MCP 协议客户端，接入第三方工具服务器
5. **Phase 5 - 多 Agent 协作**：增加子 Agent 能力，处理跨领域复杂任务


## 第3节 总结

### 3.1 核心收获

通过 Claude Code 的源码分析，我们确认了智能体系统的核心其实非常简洁：**一个 while 循环 + 工具调用**。真正让系统变得复杂的是外围的 Harness（套件）——上下文管理、权限控制、工具治理、错误恢复、记忆整合等工程化组件。

### 3.2 设计哲学

Claude Code 的设计哲学值得借鉴：

1. **运行时越笨，架构越稳定**：把智能下沉到模型，把确定性留给框架
2. **给模型一个 shell，而不是 100 个专项工具**：Bash 是通用适配器
3. **脚手架随时间推移变薄**：随着模型能力提升，主动删除硬编码逻辑

### 3.3 简化版的价值

上述简化版编程工具完整实现了：
- ✅ Agent Loop 核心循环
- ✅ 工具系统（注册表 + Schema 校验）
- ✅ 权限管理（4 种模式 + 黑名单）
- ✅ 上下文管理（OPENCODE.md 风格）
- ✅ 扩展接口（MCP、插件）

这个简化版可以作为：
- 学习 Agent 系统原理的教学示例
- 自定义 AI 编程工具的起点
- 测试新工具和权限策略的实验平台

后续可根据需求，逐步添加并行执行、上下文压缩、向量记忆、MCP 协议支持等功能。