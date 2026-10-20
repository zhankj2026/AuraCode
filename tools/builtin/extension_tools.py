#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2026 zhankj
#
# This source code is licensed under the [Apache-2.0] license.
# For the full license text, please refer to the LICENSE file in the root directory.
#
# Author: zhankj <creating2018@aliyun.com>
# Project Homepage: http://www.auracode.top
#

"""
扩展管理工具 - 通过对话创建/管理 定时任务、MCP、技能、插件、钩子。

设计原则：
- 全部复用既有底层能力（SkillManager / McpConfigManager / HookConfigLoader /
  PluginLoader / CronScheduler），本文件只做面向 LLM 的工具层封装。
- 所有创建操作 permission_level=write：normal 模式下弹权限确认，
  用户看到要写什么才放行。
- MCP 与插件创建后提示「下个会话生效」（会话启动时加载）；
  钩子创建后调用 config_loader.reload() 即时生效。
"""

import json
import os
import shutil
from typing import Dict, Any

from tools.registry import register_tool


def _project_root() -> str:
    """当前会话的项目根。

    优先级：
    1. AgentLoop.project_root（最准确；通过 tool_executor 注入的上下文拿）
    2. SkillManager.project_root
    3. 环境变量（Bridge 会话线程 chdir 期间设置的）——不可靠，仅兜底
    4. cwd —— 最后兜底（注意：Bridge 线程在 loop 初始化后 chdir 回引擎目录，
       此值往往是错的，所以放在最后）

    工具 handler 执行时 tool_executor 会把 loop 挂到本模块的
    _CURRENT_LOOP（见 core/loop/tool_executor.py 的钩子），从这里取最稳。
    """
    # 1) tool_executor 注入的当前 loop
    loop = _CURRENT_LOOP.get("loop") if _CURRENT_LOOP else None
    if loop is not None and getattr(loop, "project_root", None):
        return loop.project_root
    # 2) SkillManager
    try:
        from skills.context import SkillContext
        mgr = SkillContext._skill_manager
        if mgr and getattr(mgr, "project_root", None):
            return mgr.project_root
    except Exception:
        pass
    # 3) 环境变量兜底
    env_root = os.environ.get("AURACODE_PROJECT_ROOT")
    if env_root and os.path.isdir(env_root):
        return env_root
    # 4) cwd
    return os.getcwd()


# tool_executor 执行 handler 前注入当前 AgentLoop（thread-local，会话线程安全）
_CURRENT_LOOP = {}


# ════════════════════════════════════════════════════════════════
# 技能（Skill）
# ════════════════════════════════════════════════════════════════

def skill_create_handler(
    name: str,
    description: str,
    prompt_content: str,
    trigger: str = "",
    scope: str = "project",
) -> str:
    """创建自定义技能（SKILL.md + prompt.md 落盘）"""
    try:
        from skills.context import SkillContext
        mgr = SkillContext._skill_manager
        if mgr is None:
            return "❌ 技能系统未初始化（本会话未启用技能）"
        result = mgr.create_skill(
            name=name,
            description=description,
            trigger=trigger or f"当用户要求使用 {name} 技能时激活",
            prompt_content=prompt_content,
            scope=scope,
        )
        return f"{result}\n\n提示：使用 show_available_skills 可确认已加载；activate_skill('{name}') 立即激活。"
    except Exception as e:
        return f"❌ 创建技能失败: {e}"


def skill_delete_handler(name: str) -> str:
    try:
        from skills.context import SkillContext
        mgr = SkillContext._skill_manager
        if mgr is None:
            return "❌ 技能系统未初始化"
        return mgr.delete_skill(name)
    except Exception as e:
        return f"❌ 删除技能失败: {e}"


# ════════════════════════════════════════════════════════════════
# MCP 服务器
# ════════════════════════════════════════════════════════════════

def _mcp_json_path(scope: str) -> str:
    root = _project_root()
    if scope == "user":
        return os.path.join(os.path.expanduser("~"), ".auracode", "mcp.json")
    return os.path.join(root, ".mcp.json")


def _read_mcp_json(path: str) -> Dict[str, Any]:
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data.get("mcpServers"), dict):
                return data
        except Exception:
            pass
    return {"mcpServers": {}}


def _write_mcp_json(path: str, data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def mcp_add_handler(
    name: str,
    transport: str = "stdio",
    command: str = "",
    args: str = "",
    url: str = "",
    env: str = "",
    scope: str = "project",
) -> str:
    """添加 MCP 服务器配置到 .mcp.json（stdio/http/sse/ws）"""
    try:
        transport = (transport or "stdio").lower()
        entry: Dict[str, Any] = {"type": transport}

        if transport == "stdio":
            if not command:
                return "❌ stdio 传输需要 command 参数（如 'npx' / 'python'）"
            entry["command"] = command
            if args:
                entry["args"] = [a.strip() for a in args.split(" ") if a.strip()]
            if env:
                for kv in env.split(";"):
                    if "=" in kv:
                        k, v = kv.split("=", 1)
                        entry.setdefault("env", {})[k.strip()] = v.strip()
        elif transport in ("http", "sse", "ws", "websocket"):
            if not url:
                return f"❌ {transport} 传输需要 url 参数"
            entry["url"] = url
        else:
            return f"❌ 不支持的传输类型: {transport}（可选 stdio/http/sse/ws）"

        path = _mcp_json_path(scope)
        data = _read_mcp_json(path)
        existed = name in data["mcpServers"]
        data["mcpServers"][name] = entry
        _write_mcp_json(path, data)
        where = "用户级 ~/.auracode/mcp.json" if scope == "user" else f"工程级 {path}"
        action = "已覆盖" if existed else "已添加"
        return (f"✅ MCP 服务器 '{name}' {action}到 {where}\n"
                f"配置: {json.dumps(entry, ensure_ascii=False)}\n"
                f"⏳ 新会话启动时自动连接；如需立即使用请新建会话。")
    except Exception as e:
        return f"❌ 添加 MCP 失败: {e}"


def mcp_remove_handler(name: str, scope: str = "project") -> str:
    try:
        path = _mcp_json_path(scope)
        data = _read_mcp_json(path)
        if name not in data["mcpServers"]:
            return f"⚠️ '{name}' 不在 {path} 中"
        del data["mcpServers"][name]
        _write_mcp_json(path, data)
        return f"✅ 已从 {path} 移除 '{name}'（新会话起不再连接）"
    except Exception as e:
        return f"❌ 移除 MCP 失败: {e}"


def mcp_list_servers_handler() -> str:
    try:
        lines = []
        for scope, path in (("project", _mcp_json_path("project")),
                            ("user", _mcp_json_path("user"))):
            data = _read_mcp_json(path)
            servers = data.get("mcpServers", {})
            if not servers:
                continue
            lines.append(f"[{scope}] {path}")
            for name, cfg in servers.items():
                kind = cfg.get("type", "stdio")
                target = cfg.get("command", "") or cfg.get("url", "")
                args = " ".join(cfg.get("args", []) or [])
                lines.append(f"  - {name} ({kind}): {target} {args}".rstrip())
        return "\n".join(lines) if lines else "未配置任何 MCP 服务器"
    except Exception as e:
        return f"❌ 读取 MCP 配置失败: {e}"


# ════════════════════════════════════════════════════════════════
# 钩子（Hooks）
# ════════════════════════════════════════════════════════════════

_HOOK_EVENTS = (
    "PreToolUse", "PostToolUse", "PostToolUseFailure", "ToolError",
    "SessionStart", "SessionEnd", "Stop", "UserMessage", "Notification",
    "SubagentStart", "SubagentStop", "PreCompact", "PostCompact",
)


def _hooks_json_path(scope: str) -> str:
    root = _project_root()
    if scope == "user":
        return os.path.join(os.path.expanduser("~"), ".auracode", "hooks.json")
    return os.path.join(root, ".auracode", "hooks.json")


def _read_hooks_json(path: str) -> Dict[str, Any]:
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data.get("hooks"), list):
                return data
        except Exception:
            pass
    return {"hooks": []}


def hook_add_handler(
    event: str,
    command: str,
    matcher: str = "",
    on_fail: str = "ignore",
    timeout: float = 10.0,
    description: str = "",
    scope: str = "project",
) -> str:
    """添加钩子（事件触发时执行 shell 命令），创建后即时生效"""
    try:
        event = event.strip()
        # 容错：模型可能给小写
        matched = next((e for e in _HOOK_EVENTS if e.lower() == event.lower()), None)
        if matched is None:
            return (f"❌ 未知事件 '{event}'。支持: {', '.join(_HOOK_EVENTS)}")
        if on_fail not in ("ignore", "warn", "block"):
            on_fail = "ignore"

        path = _hooks_json_path(scope)
        data = _read_hooks_json(path)
        entry = {
            "event": matched,
            "command": command,
            "matcher": matcher or None,
            "on_fail": on_fail,
            "timeout": timeout,
            "enabled": True,
            "description": description,
        }
        data["hooks"].append(entry)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        # 配置已落盘。热重载当前会话的 HookManager 需要拿到 AgentLoop 实例，
        # 工具层拿不到（解耦设计），因此统一提示下个会话完全生效——
        # 与 MCP/插件的生命周期一致，避免用户误解部分生效。
        return (f"✅ 钩子已添加到 {path}\n"
                f"事件: {matched} | 匹配: {matcher or '所有工具'} | 失败策略: {on_fail}\n"
                f"命令: {command}\n（下个会话完全生效）")
    except Exception as e:
        return f"❌ 添加钩子失败: {e}"


def hook_remove_handler(event: str, command: str = "", scope: str = "project") -> str:
    try:
        path = _hooks_json_path(scope)
        data = _read_hooks_json(path)
        before = len(data["hooks"])
        data["hooks"] = [
            h for h in data["hooks"]
            if not (h.get("event", "").lower() == event.lower()
                    and (not command or h.get("command") == command))
        ]
        removed = before - len(data["hooks"])
        if removed == 0:
            return f"⚠️ 未找到匹配的钩子（event={event}{', command=' + command if command else ''}）"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return f"✅ 已移除 {removed} 个钩子（下个会话完全生效）"
    except Exception as e:
        return f"❌ 移除钩子失败: {e}"


def hook_list_handler() -> str:
    try:
        lines = []
        for scope in ("project", "user"):
            path = _hooks_json_path(scope)
            data = _read_hooks_json(path)
            hooks = [h for h in data.get("hooks", []) if h.get("enabled", True)]
            if not hooks:
                continue
            lines.append(f"[{scope}] {path}")
            for h in hooks:
                m = f" (匹配 {h['matcher']})" if h.get("matcher") else ""
                d = f" — {h['description']}" if h.get("description") else ""
                lines.append(f"  - {h['event']}{m}: {h['command']}{d}")
        return "\n".join(lines) if lines else "未配置任何钩子"
    except Exception as e:
        return f"❌ 读取钩子失败: {e}"


# ════════════════════════════════════════════════════════════════
# 插件（Plugin）
# ════════════════════════════════════════════════════════════════

_PLUGIN_TEMPLATE = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""{description}

由对话创建于 AuraCode。放在 {where}，新会话自动加载。
"""

from typing import List, Dict, Any
from plugins.base import ToolPlugin


class {ClassName}(ToolPlugin):
    @property
    def name(self) -> str:
        return "{name}"

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def description(self) -> str:
        return {description!r}

    @property
    def source(self) -> str:
        return "{source}"

    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {{
                "name": "{tool_name}",
                "description": {description!r},
                "parameters": {{
                    "type": "object",
                    "properties": {{
                        "input": {{"type": "string", "description": "输入参数"}},
                    }},
                    "required": ["input"],
                }},
                "handler": self._run,
                "permission_level": "{permission}",
            }}
        ]

    def get_hooks(self) -> List[Dict[str, Any]]:
        return []

    def is_available(self) -> bool:
        return True

    def _run(self, input: str) -> str:
{tool_body}
'''


def plugin_create_handler(
    name: str,
    description: str,
    tool_name: str = "",
    tool_code: str = "",
    scope: str = "project",
) -> str:
    """生成插件骨架（继承 ToolPlugin，提供单个工具）到 .auracode/plugins/"""
    try:
        if scope not in ("project", "user"):
            return "❌ scope 只能是 project/user"
        root = _project_root()
        base = (os.path.join(root, ".auracode", "plugins") if scope == "project"
                else os.path.join(os.path.expanduser("~"), ".auracode", "plugins"))
        pkg_dir = os.path.join(base, name)
        if os.path.exists(pkg_dir):
            return f"⚠️ 插件已存在: {pkg_dir}"

        # 工具体：用户给的 tool_code（一段 python，参数名 input）或默认 echo
        if tool_code:
            body = "\n".join("        " + l for l in tool_code.strip().splitlines())
        else:
            body = '        return f"[{name}] 收到: {input}"'

        tool_nm = tool_name or f"{name}_tool"
        content = _PLUGIN_TEMPLATE.format(
            description=description,
            where=f".auracode/plugins/{name}/" if scope == "project" else "~/.auracode/plugins/",
            ClassName="".join(p.capitalize() for p in name.replace("-", "_").split("_")),
            name=name,
            tool_name=tool_nm,
            source="project" if scope == "project" else "user",
            permission="read",
            tool_body=body,
        )

        os.makedirs(pkg_dir, exist_ok=True)
        main_file = os.path.join(pkg_dir, "__init__.py")
        with open(main_file, "w", encoding="utf-8") as f:
            f.write(content)

        return (f"✅ 插件 '{name}' 已创建: {main_file}\n"
                f"提供工具: {tool_nm}\n"
                f"⏳ 新会话启动时自动加载（PluginLoader 扫描 "
                f"{'工程' if scope == 'project' else '用户'}级目录）。")
    except Exception as e:
        return f"❌ 创建插件失败: {e}"


def plugin_list_handler() -> str:
    try:
        lines = []
        root = _project_root()
        for scope, base in (("project", os.path.join(root, ".auracode", "plugins")),
                            ("user", os.path.join(os.path.expanduser("~"), ".auracode", "plugins"))):
            if not os.path.isdir(base):
                continue
            pkgs = [d for d in os.listdir(base)
                    if os.path.isdir(os.path.join(base, d)) and not d.startswith(("_", "."))]
            if not pkgs:
                continue
            lines.append(f"[{scope}] {base}")
            for p in sorted(pkgs):
                lines.append(f"  - {p}")
        return "\n".join(lines) if lines else "未安装任何自定义插件"
    except Exception as e:
        return f"❌ 读取插件失败: {e}"


# ════════════════════════════════════════════════════════════════
# 注册
# ════════════════════════════════════════════════════════════════

register_tool("skill_create", {
    "description": """创建自定义技能（写入 .auracode/skills/<name>/SKILL.md）。

技能 = 可复用的提示词包，激活后注入专业知识。
适用于：编码规范、工作流程、领域知识。

示例: skill_create(name="code-review", description="代码评审标准",
  prompt_content="# 代码评审清单\\n1. ...", trigger="评审代码时")""",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "技能名（英文短横线，如 code-review）"},
            "description": {"type": "string", "description": "技能描述"},
            "prompt_content": {"type": "string", "description": "技能提示词全文（Markdown）"},
            "trigger": {"type": "string", "description": "触发条件说明（可选）"},
            "scope": {"type": "string", "enum": ["project", "user"], "description": "作用域，默认 project"},
        },
        "required": ["name", "description", "prompt_content"],
    },
    "handler": skill_create_handler,
    "permission_level": "write",
})

register_tool("skill_delete", {
    "description": "删除自定义技能（内置技能不可删）",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "技能名"},
        },
        "required": ["name"],
    },
    "handler": skill_delete_handler,
    "permission_level": "write",
})

register_tool("mcp_add", {
    "description": """添加 MCP 服务器（写入 .mcp.json，新会话自动连接）。

stdio 示例: mcp_add(name="github", transport="stdio", command="npx",
  args="-y @modelcontextprotocol/server-github", env="GITHUB_TOKEN=xxx")
http 示例: mcp_add(name="myapi", transport="http", url="https://example.com/mcp")""",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "服务器唯一名"},
            "transport": {"type": "string", "enum": ["stdio", "http", "sse", "ws"], "description": "传输类型，默认 stdio"},
            "command": {"type": "string", "description": "stdio 启动命令（如 npx/python/node）"},
            "args": {"type": "string", "description": "命令参数（空格分隔；含空格的参数用引号）"},
            "url": {"type": "string", "description": "远程服务器 URL（http/sse/ws 必填）"},
            "env": {"type": "string", "description": "环境变量，K=V;K2=V2 分号分隔"},
            "scope": {"type": "string", "enum": ["project", "user"], "description": "project=工程 .mcp.json；user=全局 ~/.auracode/mcp.json"},
        },
        "required": ["name"],
    },
    "handler": mcp_add_handler,
    "permission_level": "write",
})

register_tool("mcp_remove", {
    "description": "从 .mcp.json 移除 MCP 服务器",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "服务器名"},
            "scope": {"type": "string", "enum": ["project", "user"], "description": "默认 project"},
        },
        "required": ["name"],
    },
    "handler": mcp_remove_handler,
    "permission_level": "write",
})

register_tool("mcp_list_servers", {
    "description": "列出工程级与用户级已配置的 MCP 服务器",
    "parameters": {"type": "object", "properties": {}, "required": []},
    "handler": mcp_list_servers_handler,
    "permission_level": "read",
})

register_tool("hook_add", {
    "description": f"""添加钩子：指定事件发生时执行 shell 命令，写入 .auracode/hooks.json。

支持事件: {', '.join(_HOOK_EVENTS)}

示例: hook_add(event="PostToolUse", command="echo %TOOL_NAME% >> log.txt",
  matcher="write_file", description="记录写文件操作")""",
    "parameters": {
        "type": "object",
        "properties": {
            "event": {"type": "string", "description": "钩子事件名（见工具描述）"},
            "command": {"type": "string", "description": "要执行的 shell 命令"},
            "matcher": {"type": "string", "description": "仅匹配指定工具名（可选，如 write_file）"},
            "on_fail": {"type": "string", "enum": ["ignore", "warn", "block"], "description": "失败策略，默认 ignore"},
            "timeout": {"type": "number", "description": "超时秒数，默认 10"},
            "description": {"type": "string", "description": "钩子用途说明"},
            "scope": {"type": "string", "enum": ["project", "user"], "description": "默认 project"},
        },
        "required": ["event", "command"],
    },
    "handler": hook_add_handler,
    "permission_level": "write",
})

register_tool("hook_remove", {
    "description": "移除钩子（按事件 + 可选命令匹配）",
    "parameters": {
        "type": "object",
        "properties": {
            "event": {"type": "string", "description": "钩子事件名"},
            "command": {"type": "string", "description": "完整命令（可选，用于精确定位）"},
            "scope": {"type": "string", "enum": ["project", "user"], "description": "默认 project"},
        },
        "required": ["event"],
    },
    "handler": hook_remove_handler,
    "permission_level": "write",
})

register_tool("hook_list", {
    "description": "列出工程级与用户级已配置的钩子",
    "parameters": {"type": "object", "properties": {}, "required": []},
    "handler": hook_list_handler,
    "permission_level": "read",
})

register_tool("plugin_create", {
    "description": """创建自定义插件（生成 ToolPlugin 骨架到 .auracode/plugins/，新会话自动加载）。

插件可注册新工具。tool_code 为一段 Python（函数体，参数 input），
复杂插件建议创建后手动完善。

示例: plugin_create(name="word-count", description="统计字数",
  tool_name="count_words", tool_code="return str(len(input))")""",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "插件名（英文短横线）"},
            "description": {"type": "string", "description": "插件描述"},
            "tool_name": {"type": "string", "description": "提供的工具名（默认 <name>_tool）"},
            "tool_code": {"type": "string", "description": "工具执行体（Python 语句，可用 input 变量，return 返回字符串）"},
            "scope": {"type": "string", "enum": ["project", "user"], "description": "默认 project"},
        },
        "required": ["name", "description"],
    },
    "handler": plugin_create_handler,
    "permission_level": "write",
})

register_tool("plugin_list", {
    "description": "列出工程级与用户级已安装的自定义插件",
    "parameters": {"type": "object", "properties": {}, "required": []},
    "handler": plugin_list_handler,
    "permission_level": "read",
})
