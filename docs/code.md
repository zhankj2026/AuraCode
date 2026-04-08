# 提高编程工具编程能力的技术方案

**版本**: 2.0  
**日期**: 2026-04-06  
**基于**: Claude Code 源码分析 + MVP 实践经验

---

## 1. 概述

编程工具的核心能力要求包括:代码理解、代码搜索、代码编辑、代码验证、任务协同。本文档基于 Claude Code 源码架构分析,提供从基础到高级的**可执行**实施方案。

能力层次结构:

```
L4 协同能力: Subagent / Skill / Hook / 多任务并行
L3 验证能力: 静态分析 / 测试执行 / 质量评估
L2 编辑能力: 精确替换 / 预览差异 / 安全回滚
L1 理解能力: 语义搜索 / 符号索引 / 依赖分析
L0 基础能力: Agent Loop / 工具注册 / 权限控制
```

**当前状态**: L4 已完成 (Phase 0/1/2/3/4/5 已完成) - 12 个工具 + 插件/Hook/Skill 系统  
**目标**: 6 周内达到 L4

---

## 2. 基础能力层(L0) - ✅ 已完成

### 2.1 Agent 执行循环

**实现位置**: `core/agent_loop.py` (270行)

**核心设计**:
- 单线程 `while` 循环,模型返回文本时终止
- 消息历史扁平存储,按 `user`/`assistant` 交替追加
- 工具调用结果以 `user` 角色返回,保持 API 兼容

```python
while iteration < max_iterations:
    response = llm.chat(messages, tools=tool_schemas)
    if not response.tool_calls:
        return response.content
    for call in response.tool_calls:
        result = execute_tool(call)
        messages.append({"role": "user", "content": result})
```

### 2.2 工具注册表

**实现位置**: `tools/registry.py` (82行)

**设计模式**: 集中式注册,JSON Schema 定义

```python
TOOL_REGISTRY = {
    "read_file": {
        "description": "读取文件内容",
        "parameters": {...},  # JSON Schema
        "handler": read_file_handler,
        "permission_level": "read"
    }
}
```

**扩展方式**:
```python
# tools/builtin/my_tool.py
from tools.registry import register_tool

def my_handler(arg1: str) -> str:
    return "result"

register_tool("my_tool", {
    "description": "我的工具",
    "parameters": {...},
    "handler": my_handler,
    "permission_level": "read"
})

# tools/builtin/__init__.py
from . import my_tool  # 触发注册
```

### 2.3 权限管理

**实现位置**: `permissions/manager.py` (120行)

**三道防线**:
1. 命令黑名单(`rm -rf /`、`sudo` 等直接拦截)
2. Plan 模式拦截(禁止所有修改操作)
3. 用户确认(写入/执行前询问)

**四种模式**:
- `normal` - 需确认(默认)
- `auto` - 自动批准读操作
- `plan` - 只分析不执行
- `bypass` - 全跳过

**输出截断**: 限制返回 500 行,防上下文溢出

---

## 3. 代码理解能力(L1) - 🎯 Phase 1 (第1-2周)

### 3.1 代码搜索工具

**实施方案**: 基于 grep/find 的增强搜索

**新增工具**:

```
# tools/builtin/grep.py
def grep_handler(
    pattern: str, 
    path: str = ".", 
    file_pattern: str = "*.py",
    case_sensitive: bool = False
) -> str:
    """增强版 grep - 支持文件过滤和大小写控制"""
    import subprocess
    
    cmd = ["grep", "-rn"]
    if not case_sensitive:
        cmd.append("-i")
    cmd.extend(["--include=" + file_pattern, pattern, path])
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    # 限制输出
    lines = result.stdout.splitlines()
    if len(lines) > 100:
        return "\n".join(lines[:100]) + f"\n... (共 {len(lines)} 行,显示前100行)"
    return result.stdout

register_tool("grep", {
    "description": "递归搜索文件内容(支持正则)",
    "parameters": {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "搜索模式(正则)"},
            "path": {"type": "string", "description": "搜索路径", "default": "."},
            "file_pattern": {"type": "string", "description": "文件匹配模式", "default": "*"},
            "case_sensitive": {"type": "boolean", "description": "区分大小写", "default": False}
        },
        "required": ["pattern"]
    },
    "handler": grep_handler,
    "permission_level": "read"
})
```

```python
# tools/builtin/find.py
def find_handler(
    path: str = ".",
    name_pattern: str = None,
    type: str = None,  # file/dir
    max_depth: int = 3
) -> str:
    """查找文件(按名称/类型/深度)"""
    import subprocess
    
    cmd = ["find", path, "-maxdepth", str(max_depth)]
    if type == "file":
        cmd.append("-type")
        cmd.append("f")
    elif type == "dir":
        cmd.append("-type")
        cmd.append("d")
    if name_pattern:
        cmd.extend(["-name", name_pattern])
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout

register_tool("find", {
    "description": "查找文件(按名称/类型/深度)",
    "parameters": {...},
    "handler": find_handler,
    "permission_level": "read"
})
```

**预期效果**:
```
用户: "找到所有处理用户认证的函数"
AI: 使用 grep 搜索 "def.*(auth|login|authenticate)"
AI: 找到 15 个匹配,分析后给出建议
```

### 3.2 代码结构分析

**实施方案**: 使用 AST 分析代码结构

```
# tools/builtin/analyze_file.py
import ast
import json

def analyze_file_handler(path: str) -> str:
    """分析文件结构(函数/类/导入)"""
    with open(path, "r", encoding="utf-8") as f:
        source = f.read()
    
    tree = ast.parse(source)
    
    analysis = {
        "classes": [],
        "functions": [],
        "imports": [],
        "line_count": len(source.splitlines())
    }
    
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            analysis["classes"].append({
                "name": node.name,
                "line": node.lineno,
                "methods": [
                    n.name for n in node.body 
                    if isinstance(n, ast.FunctionDef)
                ]
            })
        elif isinstance(node, ast.FunctionDef):
            analysis["functions"].append({
                "name": node.name,
                "line": node.lineno,
                "args": [arg.arg for arg in node.args.args]
            })
        elif isinstance(node, ast.Import):
            for alias in node.names:
                analysis["imports"].append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                analysis["imports"].append(f"{node.module}.{alias.name}")
    
    return json.dumps(analysis, indent=2, ensure_ascii=False)

register_tool("analyze_file", {
    "description": "分析 Python 文件结构",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径"}
        },
        "required": ["path"]
    },
    "handler": analyze_file_handler,
    "permission_level": "read"
})
```

**预期效果**:
```
用户: "分析 core/agent_loop.py 的结构"
AI: {
  "classes": [
    {"name": "AgentLoop", "line": 21, "methods": ["__init__", "run", "_call_llm"]}
  ],
  "functions": [],
  "imports": ["os", "json", "logging", "openai.OpenAI"],
  "line_count": 270
}
```

### 3.3 项目结构感知

**增强现有**: `core/context.py` 已实现基础检测

**增强方案**:
```python
def get_project_summary(project_root: str) -> Dict:
    """生成项目结构摘要"""
    summary = {
        "type": detect_project_type(project_root),
        "entry_files": find_entry_files(project_root),
        "test_dirs": find_test_dirs(project_root),
        "config_files": find_config_files(project_root),
        "dependencies": extract_dependencies(project_root),
        "structure": generate_file_tree(project_root, max_depth=2)
    }
    return summary
```

**工具化**:
```python
register_tool("project_summary", {
    "description": "获取项目结构摘要",
    "parameters": {...},
    "handler": get_project_summary,
    "permission_level": "read"
})
```

---

## 4. 代码编辑能力(L2) - ✅ Phase 2 已完成

### 4.1 精确替换工具

**问题**: 当前 `write_file` 整体覆盖,不安全

**解决方案**: 添加行级编辑原语

```
# tools/builtin/edit_file.py
import difflib

def replace_in_file_handler(
    path: str,
    old_text: str,
    new_text: str,
    replace_all: bool = False
) -> str:
    """替换文件中的文本(支持预览)"""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    
    if old_text not in content:
        return f"错误: 未找到匹配文本 '{old_text[:50]}...'"
    
    if replace_all:
        new_content = content.replace(old_text, new_text)
    else:
        new_content = content.replace(old_text, new_text, 1)
    
    # 生成 diff
    diff = generate_diff(content, new_content, path)
    
    return f"✅ 替换成功\n\n{diff}"

def generate_diff(old: str, new: str, path: str) -> str:
    """生成 unified diff"""
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    
    diff = difflib.unified_diff(
        old_lines, new_lines,
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
        n=3
    )
    return "".join(diff)

register_tool("replace_in_file", {
    "description": "替换文件中的文本(显示差异)",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径"},
            "old_text": {"type": "string", "description": "要替换的文本"},
            "new_text": {"type": "string", "description": "新文本"},
            "replace_all": {"type": "boolean", "description": "替换所有匹配", "default": False}
        },
        "required": ["path", "old_text", "new_text"]
    },
    "handler": replace_in_file_handler,
    "permission_level": "write"
})
```

### 4.2 安全机制 - ✅ 已完成

**自动备份**: ✅ 已实现
- 时间戳 + 微秒确保唯一性
- 备份到 `.backup` 目录

**撤销支持**: ✅ 已实现
- `undo_edit` 工具 - 撤销上次编辑
- `edit_history` 工具 - 查看编辑历史
- 最多保留 50 条记录
- 支持指定文件撤销

**实现位置**: 
- `tools/builtin/undo_edit.py` (163行)
- `tools/builtin/replace_in_file.py` 集成记录功能

---

## 5. 代码验证能力(L3) - ✅ Phase 3 已完成

### 5.1 静态检查集成 - ✅ 已完成

**实现位置**: `tools/builtin/lint.py` (165行)

**功能特性**:
- 自动检测编程语言(Python/JavaScript/TypeScript)
- 集成 ruff(Python) 和 eslint(JS/TS)
- 支持自动修复模式(--fix)
- 输出限制 200 行,防上下文溢出

**使用示例**:
```python
# 检查 Python 文件
lint(path="src/main.py", language="python")

# 自动修复 JavaScript
lint(path="src/", language="javascript", fix=True)
```
# tools/builtin/lint.py
def lint_handler(path: str = None, language: str = None) -> str:
    """运行静态检查"""
    import subprocess
    
    # 自动检测语言
    if not language:
        language = detect_language(path)
    
    linters = {
        "python": ["ruff", "check", path or "."],
        "javascript": ["npx", "eslint", path or "."],
        "typescript": ["npx", "eslint", "--ext", ".ts", path or "."],
    }
    
    if language not in linters:
        return f"不支持的语言: {language}"
    
    result = subprocess.run(
        linters[language],
        capture_output=True,
        text=True,
        timeout=60
    )
    
    output = result.stdout or result.stderr
    return output if output else "✅ 无问题"

register_tool("lint", {
    "description": "运行静态检查(ruff/eslint)",
    "parameters": {...},
    "handler": lint_handler,
    "permission_level": "read"
})
```

### 5.2 测试执行 - ✅ 已完成

**实现位置**: `tools/builtin/run_tests.py` (297行)

**功能特性**:
- 自动检测测试框架(pytest/jest/unittest)
- 支持运行特定测试或全部测试
- 支持 --last-failed 只运行失败用例
- 自动解析测试结果并统计
- 输出限制 3000 字符

**使用示例**:
```python
# 运行所有测试
run_tests()

# 运行特定测试文件
run_tests(test_path="tests/test_main.py")

# 只运行失败的测试
run_tests(failed_only=True)
```
# tools/builtin/test.py
def run_tests_handler(
    test_path: str = None,
    framework: str = None,
    failed_only: bool = False
) -> str:
    """运行测试"""
    import subprocess
    
    # 自动检测框架
    if not framework:
        framework = detect_test_framework()
    
    commands = {
        "pytest": ["pytest", test_path or "tests"],
        "jest": ["npx", "jest", test_path or ""],
        "unittest": ["python", "-m", "unittest", "discover"],
    }
    
    if failed_only and framework == "pytest":
        commands["pytest"].append("--last-failed")
    
    result = subprocess.run(
        commands[framework],
        capture_output=True,
        text=True,
        timeout=120
    )
    
    # 解析结果
    stats = parse_test_output(result.stdout)
    
    return f"测试结果:\n{result.stdout}\n\n统计: {stats}"

register_tool("run_tests", {
    "description": "运行测试套件",
    "parameters": {...},
    "handler": run_tests_handler,
    "permission_level": "execute"
})
```

---

## 6. 扩展与协同能力(L4) - ✅ Phase 4 已完成 (Phase 5-6 进行中)

### 6.1 插件化架构 - ✅ 已完成

**参考 Claude Code 实现**: `src/plugins/builtinPlugins.ts`

**实现位置**:
- `plugins/base.py` (89行) - 插件基类
- `plugins/loader.py` (199行) - 插件加载器
- `plugins/example_autoformat.py` (106行) - 示例插件

**核心设计**:
- ToolPlugin 抽象基类,定义插件接口
- PluginLoader 动态扫描和加载插件
- 支持工具定义和钩子注册
- 自动检查插件可用性

**使用示例**:
```python
from plugins.loader import PluginLoader

# 加载所有插件
loader = PluginLoader()
plugins = loader.load_all_plugins()

# 获取插件提供的工具
all_tools = loader.get_all_tools()

# 获取插件提供的钩子
all_hooks = loader.get_all_hooks()
```
# plugins/base.py
from abc import ABC, abstractmethod
from typing import List, Dict

class ToolPlugin(ABC):
    """插件基类"""
    
    @abstractmethod
    def get_tools(self) -> List[Dict]:
        """返回工具定义列表"""
        pass
    
    @abstractmethod
    def get_hooks(self) -> List[Dict]:
        """返回钩子定义列表"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """检查插件是否可用"""
        pass

# plugins/loader.py
def load_plugins(plugins_dir: str = "plugins") -> List[ToolPlugin]:
    """扫描并加载插件"""
    plugins = []
    for filename in os.listdir(plugins_dir):
        if filename.endswith(".py") and not filename.startswith("_"):
            module = import_module(f"plugins.{filename[:-3]}")
            for attr in dir(module):
                cls = getattr(module, attr)
                if isinstance(cls, type) and issubclass(cls, ToolPlugin):
                    plugins.append(cls())
    return plugins
```

### 6.2 Hook 系统 - ✅ 已完成

**参考 Claude Code 实现**: `src/utils/hooks.ts` (3400+行)

**实现位置**: `hooks/manager.py` (254行)

**核心钩子点**:

| 钩子 | 触发时机 | 用途 |
|-----|---------|------|
| `PreToolUse` | 工具执行前 | 拦截危险命令、修改参数 |
| `PostToolUse` | 工具执行后 | 自动格式化、审计日志 |
| `SessionStart` | 会话开始时 | 加载用户配置 |
| `PostToolUseFailure` | 工具失败时 | 自动重试、错误修复 |

**功能特性**:
- 支持优先级排序
- 支持工具匹配器(matcher)
- 支持修改工具输入
- 支持阻止工具执行
- 异步/同步钩子兼容

**使用示例**:
```python
from hooks.manager import HookManager, HookResult

hook_manager = HookManager()

# 注册钩子
async def check_dangerous(**kwargs):
    if kwargs.get('tool_name') == 'rm':
        return HookResult(allow=False, block_reason="危险命令")
    return HookResult(allow=True)

hook_manager.register_hook("PreToolUse", check_dangerous, priority=10)

# 执行钩子
result = await hook_manager.execute_hooks(
    "PreToolUse",
    tool_name="rm"
)
```
# hooks/manager.py
from typing import Callable, Dict, Any, List
from dataclasses import dataclass

@dataclass
class HookResult:
    allow: bool = True
    modified_input: Any = None
    block_reason: str = None
    additional_context: str = None

class HookManager:
    """钩子管理器"""
    
    def __init__(self):
        self.hooks: Dict[str, List[Callable]] = {
            "PreToolUse": [],
            "PostToolUse": [],
            "SessionStart": [],
            "PostToolUseFailure": []
        }
    
    def register_hook(self, event: str, handler: Callable, matcher: str = None):
        """注册钩子"""
        self.hooks[event].append({
            "handler": handler,
            "matcher": matcher  # 可选,如 "run_command" 只匹配该工具
        })
    
    async def execute_hooks(self, event: str, **kwargs) -> HookResult:
        """执行钩子链"""
        for hook in self.hooks[event]:
            if hook["matcher"] and hook["matcher"] != kwargs.get("tool_name"):
                continue
            
            result = await hook["handler"](**kwargs)
            if not result.allow:
                return result
            if result.modified_input:
                kwargs["input"] = result.modified_input
        
        return HookResult(allow=True)
```

**使用示例**:
```
# hooks/auto_format.py
from hooks.manager import HookManager

async def auto_format_after_write(**kwargs) -> HookResult:
    """写入文件后自动格式化"""
    tool_name = kwargs.get("tool_name")
    if tool_name != "write_file":
        return HookResult()
    
    filepath = kwargs.get("input", {}).get("path")
    if not filepath.endswith(".py"):
        return HookResult()
    
    import subprocess
    subprocess.run(["black", filepath], capture_output=True)
    
    return HookResult(
        additional_context=f"✅ 已自动格式化 {filepath}"
    )

# 注册
hook_manager = HookManager()
hook_manager.register_hook("PostToolUse", auto_format_after_write)
```

### 6.3 Skill 系统(领域知识注入) - ✅ Phase 5 已完成

**参考 Claude Code 实现**: `src/tools/SkillTool/` 

**实现位置**:
- `skills/loader.py` (334行) - Skill 管理器
- `skills/python-standards/SKILL.md` (240行) - Python 编码规范
- `skills/git-workflow/SKILL.md` (202行) - Git 工作流规范

**设计理念**: 渐进式披露 - 启动时只加载名称,激活后才注入完整提示词

**核心功能**:
- 自动扫描和加载 Skill 元数据
- 按需激活 Skill,加载完整提示词
- 支持激活/停用 Skill
- 合并多个激活 Skill 的提示词
- YAML frontmatter 解析

**使用示例**:
```python
from skills.loader import SkillManager

# 初始化(只加载元数据)
skill_manager = SkillManager()

# 查看可用 Skill
available = skill_manager.get_available_skills()

# 激活 Skill(加载完整提示词)
prompt = skill_manager.activate_skill('python-standards')

# 获取所有激活的提示词
all_prompts = skill_manager.get_active_prompts()
```

**目录结构**:
```
skills/
  python-standards/
    SKILL.md        # 描述 + 触发条件
    prompt.md       # 注入内容
    scripts/        # 可选辅助脚本
  react-best-practices/
    SKILL.md
    prompt.md
```

**SKILL.md 示例**:
```
---
name: python-standards
description: Python 编码规范和最佳实践
trigger: 当编写或修改 Python 代码时激活
---

# Python 编码规范

## 命名约定
- 类名: PascalCase
- 函数名: snake_case
- 常量: UPPER_SNAKE_CASE

## 导入顺序
1. 标准库
2. 第三方库
3. 本地模块

## 错误处理
- 使用具体异常,避免 bare except
- 使用上下文管理器(with 语句)
```

**实现方案**:
```
# skills/loader.py
import os
import yaml

class SkillManager:
    """Skill 管理器"""
    
    def __init__(self, skills_dir: str = "skills"):
        self.skills_dir = skills_dir
        self.skills = self._load_skills()
    
    def _load_skills(self) -> List[Dict]:
        """加载所有 skill 元数据"""
        skills = []
        for skill_name in os.listdir(self.skills_dir):
            skill_md = os.path.join(self.skills_dir, skill_name, "SKILL.md")
            if os.path.exists(skill_md):
                with open(skill_md, "r") as f:
                    content = f.read()
                    # 解析 frontmatter
                    metadata = self._parse_frontmatter(content)
                    metadata["name"] = skill_name
                    skills.append(metadata)
        return skills
    
    def get_available_skills(self) -> List[Dict]:
        """获取可用 skill 列表(轻量)"""
        return [{"name": s["name"], "description": s["description"]} for s in self.skills]
    
    def activate_skill(self, name: str) -> str:
        """激活 skill,返回完整提示词"""
        for skill in self.skills:
            if skill["name"] == name:
                prompt_file = os.path.join(self.skills_dir, name, "prompt.md")
                with open(prompt_file, "r") as f:
                    return f.read()
        raise ValueError(f"Skill 不存在: {name}")
```

**集成到 Agent Loop**:
```
# 在系统提示词中添加 skill 列表
def build_system_prompt(self) -> str:
    parts = [self._base_role()]
    
    # 添加可用 skill 列表(渐进式披露)
    skills = self.skill_manager.get_available_skills()
    if skills:
        parts.append("可用 Skill:\n" + "\n".join(
            f"- /{s['name']}: {s['description']}" for s in skills
        ))
    
    parts.append(self._tools_description())
    return "\n\n".join(parts)
```

### 6.4 Subagent(并行任务)

**参考 Claude Code 实现**: `src/tools/AgentTool/` (789行)

**核心概念**: Subagent 是独立运行的子 Agent,拥有自己的上下文和工具集

**实现方案**(简化版):
```
# core/subagent.py
import threading
from typing import Dict, Any, List
from core.agent_loop import AgentLoop

class SubagentHandle:
    """Subagent 句柄"""
    def __init__(self, agent_id: str, thread: threading.Thread):
        self.agent_id = agent_id
        self.thread = thread
        self.result = None
        self.status = "running"  # running/completed/failed

class SubagentManager:
    """Subagent 管理器"""
    
    def __init__(self):
        self.agents: Dict[str, SubagentHandle] = {}
    
    def spawn_subagent(
        self,
        task: str,
        model: str = "glm-4-plus",
        tools: List[str] = None,
        run_in_background: bool = True
    ) -> SubagentHandle:
        """创建子 Agent"""
        import uuid
        
        agent_id = str(uuid.uuid4())
        config = {
            "model": model,
            "max_iterations": 20,
            "permission_mode": "auto"
        }
        
        agent = AgentLoop(config)
        
        def run():
            try:
                result = agent.run(task)
                self.agents[agent_id].result = result
                self.agents[agent_id].status = "completed"
            except Exception as e:
                self.agents[agent_id].result = str(e)
                self.agents[agent_id].status = "failed"
        
        thread = threading.Thread(target=run)
        thread.start()
        
        handle = SubagentHandle(agent_id, thread)
        self.agents[agent_id] = handle
        
        return handle
    
    def join_subagent(self, handle: SubagentHandle) -> str:
        """等待完成并获取结果"""
        handle.thread.join()
        return handle.result
```

**工具化**:
```
# tools/builtin/subagent.py
from core.subagent import SubagentManager

subagent_manager = SubagentManager()

def spawn_subagent_handler(
    task: str,
    model: str = "glm-4-plus",
    run_in_background: bool = True
) -> str:
    """创建子 Agent 执行任务"""
    handle = subagent_manager.spawn_subagent(
        task=task,
        model=model,
        run_in_background=run_in_background
    )
    
    if run_in_background:
        return f"✅ Subagent 已启动 (ID: {handle.agent_id})\n输出文件: output_{handle.agent_id}.txt"
    else:
        result = subagent_manager.join_subagent(handle)
        return result

def join_subagent_handler(agent_id: str) -> str:
    """获取 Subagent 结果"""
    if agent_id not in subagent_manager.agents:
        return f"错误: 未找到 Agent {agent_id}"
    
    handle = subagent_manager.agents[agent_id]
    result = subagent_manager.join_subagent(handle)
    
    return f"Subagent {agent_id} 状态: {handle.status}\n\n结果:\n{result}"

register_tool("spawn_subagent", {
    "description": "创建子 Agent 并行执行任务",
    "parameters": {...},
    "handler": spawn_subagent_handler,
    "permission_level": "execute"
})

register_tool("join_subagent", {
    "description": "等待 Subagent 完成并获取结果",
    "parameters": {...},
    "handler": join_subagent_handler,
    "permission_level": "read"
})
```

**使用场景**:
```
用户: "并行分析 src/ 目录下的所有模块"
AI: 启动 5 个 Subagent,每个分析一个模块
AI: Subagent 已启动 (ID: abc-123, def-456, ...)
(后台运行)
AI: 用户查询 Subagent 状态
AI: 使用 join_subagent 获取所有结果并汇总
```

---

## 7. 上下文管理

### 7.1 分层提示词系统

**当前实现**: `core/agent_loop.py` 中的 `_build_system_prompt()` (4层)

**增强到 7 层**:

```
def build_system_prompt(self) -> str:
    parts = []
    
    # 第 1 层: 角色定义(不可覆盖)
    parts.append(self._base_role())
    
    # 第 2 层: 工具 schema(自动生成)
    parts.append(self._tools_description())
    
    # 第 3 层: 环境信息
    parts.append(self._environment_info())
    # OS、路径、Git 状态
    
    # 第 4 层: 项目约定(加载 CLAUDE.md)
    project_context = load_project_context()
    if project_context:
        parts.append(project_context)
    
    # 第 5 层: Skill 列表(渐进式披露)
    skills = self.skill_manager.get_available_skills()
    if skills:
        parts.append(self._format_skills_list(skills))
    
    # 第 6 层: 安全规则(硬编码)
    parts.append(self._security_rules())
    
    # 第 7 层: Hook 注入的上下文
    hook_context = self.hook_manager.get_additional_context()
    if hook_context:
        parts.append(hook_context)
    
    return "\n\n".join(parts)
```

### 7.2 上下文压缩

**问题**: 长对话导致 token 溢出

**解决方案**:
```
def compress_context(self, max_tokens: int = 190000) -> List[Dict]:
    """上下文压缩"""
    current_tokens = self._estimate_tokens()
    
    if current_tokens <= max_tokens:
        return self.messages
    
    # 保留最近 50K token 完整消息
    recent_messages = []
    recent_tokens = 0
    for msg in reversed(self.messages):
        msg_tokens = self._estimate_message_tokens(msg)
        if recent_tokens + msg_tokens > 50000:
            break
        recent_messages.insert(0, msg)
        recent_tokens += msg_tokens
    
    # 对更早的消息生成摘要
    old_messages = self.messages[:-len(recent_messages)]
    summary = self._summarize_messages(old_messages)
    
    # 重组: 系统提示 + 摘要 + 最近消息
    return [
        self.messages[0],  # system prompt
        {"role": "user", "content": f"[历史摘要]\n{summary}"},
        *recent_messages
    ]
```

---

## 8. 安全加固

### 8.1 增强权限规则

**当前**: 黑名单 + 用户确认

**增强**: 支持 allow/deny 规则配置

```
# config.yaml
permissions:
  allow:
    - "run_command:git *"
    - "run_command:ls *"
    - "write_file:src/**/*.py"
  deny:
    - "run_command:rm -rf *"
    - "run_command:sudo *"
    - "write_file:/etc/**"
    - "write_file:/**/*.env"
```

### 8.2 审计日志

```
# utils/audit.py
import json
from datetime import datetime

class AuditLogger:
    """审计日志"""
    
    def __init__(self, log_file: str = "audit.log"):
        self.log_file = log_file
    
    def log_tool_call(
        self,
        tool_name: str,
        parameters: Dict,
        result: str,
        duration: float,
        allowed: bool
    ):
        """记录工具调用"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "tool_name": tool_name,
            "parameters": parameters,
            "result_preview": result[:200],
            "duration_ms": duration,
            "allowed": allowed
        }
        
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
```

---

## 9. 实施路线图

| 阶段 | 时间 | 能力 | 关键实现 | 工具数量 | 依赖 |
|-----|------|------|---------|---------|------|
| **Phase 0** | ✅ 完成 | 基础循环 | Agent Loop, 工具注册 | 4 | 无 |
| **Phase 1** | ✅ 完成 | 代码搜索 | grep, find, analyze_file | +3 | Phase 0 |
| **Phase 2** | ✅ 完成 | 精确编辑+撤销 | replace_in_file, undo_edit, edit_history | +3 | Phase 0 |
| **Phase 3** | ✅ 完成 | 验证能力 | lint, run_tests | +2 | Phase 0 |
| **Phase 4** | ✅ 完成 | 插件+Hook | 插件加载器,Hooks | +1 | Phase 0 |
| **Phase 5** | ✅ 完成 | Skill系统 | 渐进式披露 | +1 | Phase 0 |
| **Phase 6** | 第6周 | Subagent | 并行任务 | +2 | Phase 0 |

**总计**: 7 周内从 4 个工具扩展到 16+ 个工具

---

## 10. 关键设计原则

### 10.1 模块化

- 每个工具独立文件,自动注册
- Hook 与工具解耦,可插拔
- Skill 按需加载,节省 token

### 10.2 安全性

- 所有写操作默认需确认
- 自动备份 + 撤销支持
- 审计日志记录所有操作

### 10.3 可扩展性

- 插件系统支持第三方扩展
- Hook 系统支持自定义拦截逻辑
- Skill 系统支持领域知识注入

### 10.4 性能优化

- 上下文压缩防止 token 溢出
- Subagent 并行加速长任务
- 输出截断避免大文件问题

---

## 11. 立即可执行的第一步

### 10分钟增强方案

只需添加 3 个工具,立即提升编程能力:

```
cd opencode

# 1. 创建 grep 工具
cat > tools/builtin/grep.py << 'EOF'
import subprocess
from tools.registry import register_tool

def grep_handler(pattern: str, path: str = ".") -> str:
    result = subprocess.run(
        ["grep", "-rn", "-i", pattern, path],
        capture_output=True, text=True
    )
    lines = result.stdout.splitlines()
    if len(lines) > 100:
        return "\n".join(lines[:100]) + f"\n... (共{len(lines)}行)"
    return result.stdout or "未找到匹配"

register_tool("grep", {
    "description": "递归搜索文件内容",
    "parameters": {
        "type": "object",
        "properties": {
            "pattern": {"type": "string"},
            "path": {"type": "string", "default": "."}
        },
        "required": ["pattern"]
    },
    "handler": grep_handler,
    "permission_level": "read"
})
EOF

# 2. 创建 find 工具(类似实现)
# 3. 创建 analyze_file 工具(类似实现)

# 4. 更新 __init__.py
echo -e "from . import grep\nfrom . import find\nfrom . import analyze_file" >> tools/builtin/__init__.py

# 5. 测试
python cli.py --mode bypass "搜索所有包含 'class' 的 Python 文件"
```

**效果提升**:
```
之前: "读取 main.py" → AI 只能看单个文件
现在: "找到所有处理用户的函数" → AI 搜索整个项目
```

---

## 12. 总结

本方案基于 Claude Code 源码架构分析,提供了**从 L0 到 L4 的完整实施路径**:

1. **L0 (已完成)**: Agent Loop + 工具注册 + 权限管理
2. **L1 (已完成)**: 代码搜索(grep/find) + 结构分析(AST)
3. **L2 (已完成)**: 精确编辑 + diff 预览 + 自动备份 + 撤销支持
4. **L3 (已完成)**: Linter 集成 + 测试执行
5. **L4 (已完成)**: 插件系统 ✅ + Hook 拦截 ✅ + Skill 注入 ✅ | Subagent 并行 ⏳

**关键优势**:
- ✅ 每个阶段都可独立交付价值
- ✅ 基于现有架构,扩展成本低
- ✅ 参考 Claude Code 实战验证的设计
- ✅ 保持简洁,避免过度设计

**进度**: 13/16 工具已完成 (81.25%) + 插件/Hook/Skill 系统

**下一步**: Phase 6 - Subagent(并行任务)
