# 工具系统与权限管理

## 1. 工具系统概述

### 1.1 为什么需要工具系统?

LLM 本身只能生成文本,无法直接与外部环境交互。工具系统让 AI 能够:

- 📖 **读取文件** - 理解代码库
- ✍️ **写入文件** - 创建和修改代码
- 💻 **执行命令** - 运行测试、git 操作等
- 🔍 **搜索内容** - grep、find 等

通过工具,AI 从"聊天机器人"升级为"编程助手"。

### 1.2 Claude Code 的工具架构

Claude Code 实现了约 **40+ 个内置工具**,分为以下几类:

| 类别 | 工具示例 | 数量 |
|------|---------|------|
| 文件操作 | Read, Write, Edit, Glob | ~8 |
| 系统命令 | Bash, PowerShell | ~2 |
| 网络工具 | WebFetch, WebSearch | ~2 |
| 任务管理 | TaskCreate, TaskStop | ~6 |
| MCP 集成 | ListMcpResources, ReadMcpResource | ~2 |
| Agent 协作 | Agent, TeamCreate | ~5 |
| 其他 | Grep, LSP, Config | ~15 |

**MVP 策略:** 我们只实现最核心的 4 个工具,后续按需扩展。

---

## 2. 工具注册表设计

### 2.1 核心数据结构

```python
# tools/registry.py
from typing import Dict, Callable, Any, List

# 工具定义类型
ToolDefinition = Dict[str, Any]

# 工具注册表(全局单例)
TOOL_REGISTRY: Dict[str, ToolDefinition] = {}


def register_tool(name: str, definition: ToolDefinition):
    """
    注册工具到全局注册表
    
    Args:
        name: 工具名称(唯一标识)
        definition: 工具定义,包含:
            - description: 工具描述
            - parameters: JSON Schema 参数定义
            - handler: 执行函数
            - permission_level: 权限级别(read/write/execute)
    """
    if name in TOOL_REGISTRY:
        raise ValueError(f"工具 '{name}' 已存在")
    
    # 验证必需字段
    required_fields = ["description", "parameters", "handler", "permission_level"]
    for field in required_fields:
        if field not in definition:
            raise ValueError(f"工具 '{name}' 缺少必需字段: {field}")
    
    TOOL_REGISTRY[name] = definition


def get_tool_schemas() -> List[Dict]:
    """
    生成 OpenAI 兼容的工具定义列表
    
    Returns:
        OpenAI API 所需的 tools 参数格式
    """
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


def get_tool_handler(tool_name: str) -> Callable:
    """
    获取工具的执行函数
    
    Args:
        tool_name: 工具名称
        
    Returns:
        工具 handler 函数
    """
    if tool_name not in TOOL_REGISTRY:
        raise KeyError(f"未知工具: {tool_name}")
    
    return TOOL_REGISTRY[tool_name]["handler"]
```

### 2.2 工具定义示例

```python
# 注册 read_file 工具
register_tool("read_file", {
    "description": "读取指定路径的文件内容",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "文件路径(相对或绝对路径)"
            }
        },
        "required": ["path"]
    },
    "handler": read_file_handler,
    "permission_level": "read"
})

# 注册 write_file 工具
register_tool("write_file", {
    "description": "写入内容到指定文件",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "文件路径"
            },
            "content": {
                "type": "string",
                "description": "要写入的内容"
            }
        },
        "required": ["path", "content"]
    },
    "handler": write_file_handler,
    "permission_level": "write"
})
```

### 2.3 生成的 OpenAI Schema

调用 `get_tool_schemas()` 后生成的格式:

```json
[
  {
    "type": "function",
    "function": {
      "name": "read_file",
      "description": "读取指定路径的文件内容",
      "parameters": {
        "type": "object",
        "properties": {
          "path": {
            "type": "string",
            "description": "文件路径(相对或绝对路径)"
          }
        },
        "required": ["path"]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "write_file",
      "description": "写入内容到指定文件",
      "parameters": {
        "type": "object",
        "properties": {
          "path": {"type": "string", "description": "文件路径"},
          "content": {"type": "string", "description": "要写入的内容"}
        },
        "required": ["path", "content"]
      }
    }
  }
]
```

---

## 3. 工具基类与扩展接口

### 3.1 抽象基类设计

虽然 MVP 使用简单的 dict 注册,但为了未来扩展性,我们设计了抽象基类:

```python
# tools/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseTool(ABC):
    """
    工具基类(可选,用于复杂工具)
    
    简单工具可直接使用 dict 注册,复杂工具可继承此类
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称(唯一标识)"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述"""
        pass
    
    @property
    @abstractmethod
    def parameters(self) -> Dict[str, Any]:
        """JSON Schema 参数定义"""
        pass
    
    @property
    def permission_level(self) -> str:
        """
        权限级别
        
        Returns:
            "read" - 只读操作,通常自动批准
            "write" - 写入操作,需用户确认
            "execute" - 执行命令,需用户确认
        """
        return "read"
    
    @abstractmethod
    def execute(self, **kwargs) -> Any:
        """
        执行工具
        
        Args:
            **kwargs: 工具参数
            
        Returns:
            执行结果(字符串或可序列化的对象)
            
        Raises:
            Exception: 执行失败时抛出异常
        """
        pass
    
    def to_definition(self) -> Dict[str, Any]:
        """
        转换为注册表所需的 dict 格式
        
        Returns:
            工具定义字典
        """
        return {
            "description": self.description,
            "parameters": self.parameters,
            "handler": self.execute,
            "permission_level": self.permission_level
        }
```

### 3.2 使用基类扩展示例

```python
# tools/builtin/grep_tool.py
from tools.base import BaseTool
import subprocess


class GrepTool(BaseTool):
    """递归搜索文件内容"""
    
    @property
    def name(self) -> str:
        return "grep"
    
    @property
    def description(self) -> str:
        return "在文件中递归搜索匹配的模式"
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "要搜索的正则表达式"
                },
                "path": {
                    "type": "string",
                    "description": "搜索起始目录,默认为当前目录",
                    "default": "."
                }
            },
            "required": ["pattern"]
        }
    
    def execute(self, pattern: str, path: str = ".") -> str:
        try:
            result = subprocess.run(
                ["grep", "-r", "-n", pattern, path],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                return result.stdout
            elif result.returncode == 1:
                return f"未找到匹配: {pattern}"
            else:
                return f"错误: {result.stderr}"
        
        except subprocess.TimeoutExpired:
            return "错误: 搜索超时(10s)"
        except Exception as e:
            return f"错误: {str(e)}"


# 注册工具
grep_tool = GrepTool()
register_tool(grep_tool.name, grep_tool.to_definition())
```

---

## 4. 内置工具实现

### 4.1 read_file - 读取文件

```python
# tools/builtin/read_file.py
import os
from typing import Dict, Any


def read_file_handler(path: str) -> str:
    """
    读取文件内容
    
    Args:
        path: 文件路径(相对或绝对)
        
    Returns:
        文件内容字符串
        
    Raises:
        FileNotFoundError: 文件不存在
        PermissionError: 无读取权限
        UnicodeDecodeError: 文件编码错误
    """
    # 安全检查: 防止路径遍历攻击
    if not _is_safe_path(path):
        raise PermissionError(f"不允许访问的路径: {path}")
    
    # 检查文件是否存在
    if not os.path.exists(path):
        raise FileNotFoundError(f"文件不存在: {path}")
    
    # 检查是否为文件(而非目录)
    if not os.path.isfile(path):
        raise IsADirectoryError(f"路径是目录: {path}")
    
    # 读取文件
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # 限制文件大小(防止读取超大文件)
        max_size = 100 * 1024  # 100KB
        if len(content) > max_size:
            content = content[:max_size] + "\n\n... (文件过大,已截断)"
        
        return content
    
    except UnicodeDecodeError:
        # 尝试其他编码
        try:
            with open(path, "r", encoding="latin-1") as f:
                return f.read()
        except Exception:
            raise UnicodeDecodeError(
                "utf-8", b"", 0, 1, 
                f"无法解码文件,可能为二进制文件: {path}"
            )


def _is_safe_path(path: str) -> bool:
    """
    检查路径是否安全(防止路径遍历攻击)
    
    Args:
        path: 待检查的路径
        
    Returns:
        是否安全
    """
    # 禁止访问父目录
    if ".." in path:
        return False
    
    # 禁止访问系统目录
    forbidden_prefixes = ["/etc/", "/usr/", "/var/", "C:\\Windows\\"]
    abs_path = os.path.abspath(path)
    
    for prefix in forbidden_prefixes:
        if abs_path.startswith(prefix):
            return False
    
    return True


# 注册工具
from tools.registry import register_tool

register_tool("read_file", {
    "description": "读取指定路径的文件内容",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "文件路径(相对或绝对路径)"
            }
        },
        "required": ["path"]
    },
    "handler": read_file_handler,
    "permission_level": "read"
})
```

### 4.2 write_file - 写入文件

```python
# tools/builtin/write_file.py
import os
from typing import Dict, Any


def write_file_handler(path: str, content: str) -> str:
    """
    写入内容到文件
    
    Args:
        path: 文件路径
        content: 要写入的内容
        
    Returns:
        成功消息
        
    Raises:
        PermissionError: 无写入权限
        OSError: 文件系统错误
    """
    # 安全检查
    if not _is_safe_path(path):
        raise PermissionError(f"不允许写入的路径: {path}")
    
    # 自动创建目录
    directory = os.path.dirname(path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
    
    # 写入文件
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        
        return f"✅ 成功写入 {path} ({len(content)} 字符)"
    
    except PermissionError:
        raise PermissionError(f"无写入权限: {path}")
    except OSError as e:
        raise OSError(f"写入失败: {e}")


def _is_safe_path(path: str) -> bool:
    """安全检查(同 read_file)"""
    if ".." in path:
        return False
    
    forbidden_prefixes = ["/etc/", "/usr/", "/var/", "C:\\Windows\\"]
    abs_path = os.path.abspath(path)
    
    for prefix in forbidden_prefixes:
        if abs_path.startswith(prefix):
            return False
    
    return True


# 注册工具
from tools.registry import register_tool

register_tool("write_file", {
    "description": "写入内容到指定文件",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "文件路径"
            },
            "content": {
                "type": "string",
                "description": "要写入的内容"
            }
        },
        "required": ["path", "content"]
    },
    "handler": write_file_handler,
    "permission_level": "write"
})
```

### 4.3 run_command - 执行命令

```python
# tools/builtin/run_command.py
import subprocess
import platform
from typing import Dict, Any


def run_command_handler(command: str) -> str:
    """
    执行 Shell 命令
    
    Args:
        command: 要执行的命令
        
    Returns:
        命令输出(stdout + stderr)
        
    Raises:
        TimeoutExpired: 命令执行超时
        Exception: 其他错误
    """
    # 安全检查: 黑名单已在权限管理器中实现
    
    # 根据操作系统选择 shell
    if platform.system() == "Windows":
        shell = True
        executable = "powershell.exe"
    else:
        shell = True
        executable = "/bin/bash"
    
    try:
        # 执行命令
        result = subprocess.run(
            command,
            shell=shell,
            executable=executable,
            capture_output=True,
            text=True,
            timeout=30,  # 30 秒超时
            cwd=os.getcwd()  # 在当前工作目录执行
        )
        
        # 组合输出
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            if output:
                output += "\n--- STDERR ---\n"
            output += result.stderr
        
        # 添加退出码
        if result.returncode != 0:
            output += f"\n--- EXIT CODE: {result.returncode} ---"
        
        return output
    
    except subprocess.TimeoutExpired:
        raise TimeoutError("命令执行超时(30s)")
    except Exception as e:
        raise Exception(f"命令执行失败: {e}")


# 注册工具
from tools.registry import register_tool

register_tool("run_command", {
    "description": "执行 Shell 命令",
    "parameters": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "要执行的命令"
            }
        },
        "required": ["command"]
    },
    "handler": run_command_handler,
    "permission_level": "execute"
})
```

### 4.4 list_directory - 列出目录

```python
# tools/builtin/list_directory.py
import os
from typing import Dict, Any


def list_directory_handler(path: str = ".") -> str:
    """
    列出目录内容
    
    Args:
        path: 目录路径,默认为当前目录
        
    Returns:
        目录内容列表(文件和子目录)
        
    Raises:
        NotADirectoryError: 路径不是目录
        PermissionError: 无读取权限
    """
    # 安全检查
    if not _is_safe_path(path):
        raise PermissionError(f"不允许访问的目录: {path}")
    
    # 检查是否为目录
    if not os.path.exists(path):
        raise FileNotFoundError(f"目录不存在: {path}")
    
    if not os.path.isdir(path):
        raise NotADirectoryError(f"路径不是目录: {path}")
    
    try:
        # 列出目录内容
        items = os.listdir(path)
        
        # 分类文件和目录
        files = []
        dirs = []
        
        for item in items:
            full_path = os.path.join(path, item)
            if os.path.isdir(full_path):
                dirs.append(item + "/")
            else:
                files.append(item)
        
        # 排序
        files.sort()
        dirs.sort()
        
        # 格式化输出
        output = f"目录: {os.path.abspath(path)}\n\n"
        
        if dirs:
            output += "📁 子目录:\n"
            for d in dirs:
                output += f"  {d}\n"
            output += "\n"
        
        if files:
            output += "📄 文件:\n"
            for f in files:
                output += f"  {f}\n"
        
        # 限制输出数量
        max_items = 50
        if len(items) > max_items:
            output += f"\n... (共 {len(items)} 项,显示前 {max_items} 项)"
        
        return output
    
    except PermissionError:
        raise PermissionError(f"无读取权限: {path}")


def _is_safe_path(path: str) -> bool:
    """安全检查"""
    if ".." in path:
        return False
    return True


# 注册工具
from tools.registry import register_tool

register_tool("list_directory", {
    "description": "列出目录内容",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "目录路径,默认为当前目录",
                "default": "."
            }
        },
        "required": []
    },
    "handler": list_directory_handler,
    "permission_level": "read"
})
```

---

## 5. 权限管理器(三道防线)

### 5.1 权限模式详解

| 模式 | 行为 | 适用场景 |
|------|------|---------|
| **normal** | 每次写入/命令需用户确认 | 日常开发(默认) |
| **auto** | 自动批准文件读写,命令仍需确认 | 批量文件操作 |
| **plan** | 禁止所有修改,仅分析 | 代码审查、学习 |
| **bypass** | 完全跳过检查 | CI/CD 环境 |

### 5.2 权限管理器实现

```python
# permissions/manager.py
from typing import Dict, Any


class PermissionManager:
    """
    权限管理器 - 实现三道防线
    
    防线 1: Plan 模式拦截
    防线 2: 黑名单检查
    防线 3: 用户确认(normal 模式)
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
        "> /dev/sd",
        ":(){ :|:& };:",  # Fork bomb
        "chmod 777 /",
        "chown -R root:root /"
    ]
    
    def __init__(self, mode: str = "normal"):
        """
        初始化权限管理器
        
        Args:
            mode: 权限模式(normal/auto/plan/bypass)
        """
        valid_modes = ["normal", "auto", "plan", "bypass"]
        if mode not in valid_modes:
            raise ValueError(f"无效的权限模式: {mode},必须是 {valid_modes}")
        
        self.mode = mode
    
    def check_permission(self, tool_name: str, arguments: Dict[str, Any]) -> bool:
        """
        检查工具调用权限
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
            
        Returns:
            是否允许执行
        """
        # 防线 0: Bypass 模式直接通过
        if self.mode == "bypass":
            return True
        
        # 防线 1: Plan 模式拒绝所有修改操作
        if self.mode == "plan":
            if tool_name in ["write_file", "run_command"]:
                print(f"[Plan Mode] ❌ 阻止修改操作: {tool_name}")
                return False
        
        # 防线 2: 命令黑名单检查(针对 run_command)
        if tool_name == "run_command":
            command = arguments.get("command", "")
            for pattern in self.DANGEROUS_PATTERNS:
                if pattern.lower() in command.lower():
                    print(f"[Security] ❌ 阻止危险命令: {command[:50]}...")
                    return False
        
        # 防线 3: 用户确认(normal 模式需要确认写入和命令)
        if self.mode == "normal":
            if tool_name in ["write_file", "run_command"]:
                confirm = input(f"⚠️  执行 {tool_name}? 确认? (y/N): ")
                if confirm.lower() != "y":
                    print("用户取消操作")
                    return False
        
        # Auto 模式: 文件操作自动通过,命令仍需确认
        if self.mode == "auto":
            if tool_name == "run_command":
                confirm = input(f"⚠️  执行命令? 确认? (y/N): ")
                return confirm.lower() == "y"
        
        return True
    
    def truncate_output(self, output: str, max_lines: int = 500) -> str:
        """
        输出截断 - 防止上下文溢出
        
        Args:
            output: 原始输出
            max_lines: 最大行数
            
        Returns:
            截断后的输出
        """
        lines = output.splitlines()
        if len(lines) <= max_lines:
            return output
        
        # 保留前半部分和后半部分
        half = max_lines // 2
        truncated = (
            lines[:half] + 
            [f"... (截断 {len(lines) - max_lines} 行) ..."] + 
            lines[-half:]
        )
        return "\n".join(truncated)
```

### 5.3 权限检查流程

```
LLM 返回 tool_use
    ↓
查找工具注册表
    ↓
权限检查 (PermissionManager.check_permission)
    ├─ 防线 0: bypass 模式 → 直接通过
    ├─ 防线 1: plan 模式 → 拒绝修改操作
    ├─ 防线 2: 黑名单检查 → 拦截危险命令
    └─ 防线 3: 用户确认 → normal 模式需手动批准
    ↓ (通过)
执行工具 handler
    ↓
输出截断(超过 500 行)
    ↓
封装结果为 UserMessage
```

---

## 6. 工具扩展指南

### 6.1 添加工具的 3 步流程

#### Step 1: 实现 handler 函数

```python
# tools/builtin/my_tool.py
def my_tool_handler(param1: str, param2: int = 10) -> str:
    """
    我的自定义工具
    
    Args:
        param1: 参数 1
        param2: 参数 2,默认 10
        
    Returns:
        执行结果字符串
    """
    # 实现逻辑
    result = f"param1={param1}, param2={param2}"
    return result
```

#### Step 2: 注册到 TOOL_REGISTRY

```python
# 在文件末尾添加
from tools.registry import register_tool

register_tool("my_tool", {
    "description": "我的工具描述",
    "parameters": {
        "type": "object",
        "properties": {
            "param1": {
                "type": "string",
                "description": "参数 1 说明"
            },
            "param2": {
                "type": "integer",
                "description": "参数 2 说明",
                "default": 10
            }
        },
        "required": ["param1"]
    },
    "handler": my_tool_handler,
    "permission_level": "read"  # read/write/execute
})
```

#### Step 3: 更新文档

在 `docs/03-tools-and-permissions.md` 中添加使用说明。

### 6.2 完整示例: grep 工具

```python
# tools/builtin/grep.py
import subprocess
from typing import Dict, Any


def grep_handler(pattern: str, path: str = ".", ignore_case: bool = False) -> str:
    """
    递归搜索文件内容
    
    Args:
        pattern: 正则表达式
        path: 搜索目录
        ignore_case: 是否忽略大小写
        
    Returns:
        匹配结果
    """
    cmd = ["grep", "-r", "-n"]
    
    if ignore_case:
        cmd.append("-i")
    
    cmd.extend([pattern, path])
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            return result.stdout
        elif result.returncode == 1:
            return f"未找到匹配: {pattern}"
        else:
            return f"错误: {result.stderr}"
    
    except subprocess.TimeoutExpired:
        return "错误: 搜索超时(10s)"


# 注册
from tools.registry import register_tool

register_tool("grep", {
    "description": "递归搜索文件内容",
    "parameters": {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "要搜索的正则表达式"
            },
            "path": {
                "type": "string",
                "description": "搜索目录,默认为当前目录",
                "default": "."
            },
            "ignore_case": {
                "type": "boolean",
                "description": "是否忽略大小写",
                "default": False
            }
        },
        "required": ["pattern"]
    },
    "handler": grep_handler,
    "permission_level": "read"
})
```

---

## 7. 单元测试示例

### 7.1 测试工具注册表

```python
# tests/test_tools.py
import pytest
from tools.registry import TOOL_REGISTRY, register_tool, get_tool_schemas


def test_register_tool():
    """测试工具注册"""
    # 清理注册表(避免测试间干扰)
    TOOL_REGISTRY.clear()
    
    # 注册工具
    register_tool("test_tool", {
        "description": "测试工具",
        "parameters": {"type": "object"},
        "handler": lambda: "ok",
        "permission_level": "read"
    })
    
    assert "test_tool" in TOOL_REGISTRY
    assert TOOL_REGISTRY["test_tool"]["description"] == "测试工具"


def test_duplicate_registration():
    """测试重复注册报错"""
    TOOL_REGISTRY.clear()
    
    register_tool("dup_tool", {
        "description": "工具 1",
        "parameters": {},
        "handler": lambda: "ok",
        "permission_level": "read"
    })
    
    with pytest.raises(ValueError, match="已存在"):
        register_tool("dup_tool", {
            "description": "工具 2",
            "parameters": {},
            "handler": lambda: "ok",
            "permission_level": "read"
        })


def test_get_tool_schemas():
    """测试生成 OpenAI Schema"""
    TOOL_REGISTRY.clear()
    
    register_tool("schema_test", {
        "description": "测试",
        "parameters": {
            "type": "object",
            "properties": {"name": {"type": "string"}}
        },
        "handler": lambda: "ok",
        "permission_level": "read"
    })
    
    schemas = get_tool_schemas()
    assert len(schemas) == 1
    assert schemas[0]["type"] == "function"
    assert schemas[0]["function"]["name"] == "schema_test"
```

### 7.2 测试权限管理器

```python
# tests/test_permissions.py
import pytest
from unittest.mock import patch
from permissions.manager import PermissionManager


def test_bypass_mode():
    """测试 bypass 模式"""
    manager = PermissionManager(mode="bypass")
    
    # 所有操作都通过
    assert manager.check_permission("write_file", {"path": "/etc/passwd"}) is True
    assert manager.check_permission("run_command", {"command": "rm -rf /"}) is True


def test_plan_mode():
    """测试 plan 模式"""
    manager = PermissionManager(mode="plan")
    
    # 只读操作通过
    assert manager.check_permission("read_file", {"path": "test.txt"}) is True
    
    # 写入操作拒绝
    assert manager.check_permission("write_file", {"path": "test.txt"}) is False
    assert manager.check_permission("run_command", {"command": "ls"}) is False


def test_blacklist():
    """测试黑名单拦截"""
    manager = PermissionManager(mode="bypass")  # 先绕过用户确认
    
    # 危险命令被拦截
    assert manager.check_permission("run_command", {"command": "rm -rf /"}) is False
    assert manager.check_permission("run_command", {"command": "sudo apt install"}) is False


def test_normal_mode_confirmation():
    """测试 normal 模式用户确认"""
    manager = PermissionManager(mode="normal")
    
    # Mock 用户输入
    with patch("builtins.input", return_value="y"):
        assert manager.check_permission("write_file", {"path": "test.txt"}) is True
    
    with patch("builtins.input", return_value="n"):
        assert manager.check_permission("write_file", {"path": "test.txt"}) is False
```

---

## 8. 最佳实践

### 8.1 工具设计原则

1. **单一职责**: 每个工具只做一件事
   ```python
   # ✅ 好: 分离读写
   read_file(path)
   write_file(path, content)
   
   # ❌ 坏: 合并操作
   file_operation(path, mode, content=None)
   ```

2. **明确参数**: 使用 JSON Schema 清晰定义参数
   ```python
   "parameters": {
       "type": "object",
       "properties": {
           "path": {"type": "string", "description": "文件路径"}
       },
       "required": ["path"]  # 明确必填参数
   }
   ```

3. **错误处理**: 捕获异常并返回友好消息
   ```python
   try:
       result = execute()
       return {"success": True, "result": result}
   except Exception as e:
       return {"success": False, "error": str(e)}
   ```

4. **输出限制**: 防止超大输出撑爆上下文
   ```python
   if len(output) > MAX_OUTPUT_LENGTH:
       output = output[:MAX_OUTPUT_LENGTH] + "... (已截断)"
   ```

### 8.2 权限规则设计

1. **最小权限原则**: 默认拒绝,按需开放
2. **白名单优先**: 明确允许的操作比禁止的更安全
3. **通配符支持**: 支持 `run_command:git *` 这样的规则
4. **审计日志**: 记录所有权限决策

---

**文档版本:** v1.0  
**最后更新:** 2026-04-05  
**相关文档:** 
- [文档 1: 架构总览](./01-architecture-overview.md)
- [文档 2: Agent Loop 核心实现](./02-agent-loop-implementation.md)
- [文档 4: 上下文管理与配置系统](./04-context-and-config.md)
