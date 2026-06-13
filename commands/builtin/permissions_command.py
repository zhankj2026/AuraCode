"""
/permissions 命令 - 权限规则管理

提供权限模式查看、切换，以及 allow/deny 规则的管理。
对接 PermissionManager + config.yaml 持久化。

用法:
    /permissions                 — 查看当前权限配置
    /permissions mode [mode]     — 查看/切换权限模式
    /permissions list            — 列出所有规则
    /permissions allow <rule>    — 添加 allow 规则
    /permissions deny <rule>     — 添加 deny 规则
    /permissions remove <a|d> <rule> — 移除规则
    /permissions reset           — 重置为默认规则
    /permissions stats           — 权限统计
"""

import os
import yaml
import logging
from typing import Optional, List, Dict, Any
from commands.registry import register_command

logger = logging.getLogger(__name__)

# 全局权限管理器引用
_permission_manager = None
# 配置文件路径
_config_path = None
# 运行时权限规则（独立于 PermissionManager 的规则追踪）
_runtime_rules: Dict[str, List[str]] = {"allow": [], "deny": []}


def set_permission_manager(pm, config_path: str = None):
    """设置全局 PermissionManager 实例和配置路径"""
    global _permission_manager, _config_path
    _permission_manager = pm
    _config_path = config_path
    # 从 PermissionManager 读取已有规则
    _load_rules_from_config()


def _load_rules_from_config():
    """从 config.yaml 加载权限规则"""
    global _runtime_rules
    if _config_path and os.path.exists(_config_path):
        try:
            with open(_config_path, 'r', encoding='utf-8') as f:
                cfg = yaml.safe_load(f) or {}
            perms = cfg.get("permissions", {})
            _runtime_rules["allow"] = list(perms.get("allow_rules", []))
            _runtime_rules["deny"] = list(perms.get("deny_rules", []))
        except Exception as e:
            logger.warning(f"加载权限配置失败: {e}")


def _save_rules_to_config():
    """将权限规则持久化到 config.yaml"""
    if not _config_path:
        return False
    try:
        cfg = {}
        if os.path.exists(_config_path):
            with open(_config_path, 'r', encoding='utf-8') as f:
                cfg = yaml.safe_load(f) or {}
        if "permissions" not in cfg:
            cfg["permissions"] = {}
        cfg["permissions"]["allow_rules"] = _runtime_rules["allow"]
        cfg["permissions"]["deny_rules"] = _runtime_rules["deny"]
        with open(_config_path, 'w', encoding='utf-8') as f:
            yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)
        return True
    except Exception as e:
        logger.error(f"保存权限配置失败: {e}")
        return False


def permissions_handler(args: str, loop=None) -> str:
    """权限管理命令处理器"""
    parts = args.strip().split()

    if not parts:
        return _cmd_show()

    sub = parts[0].lower()
    rest = parts[1:]

    if sub == "mode":
        return _cmd_mode(rest)
    elif sub == "list":
        return _cmd_list()
    elif sub == "allow":
        return _cmd_allow(rest)
    elif sub == "deny":
        return _cmd_deny(rest)
    elif sub == "remove" or sub == "rm":
        return _cmd_remove(rest)
    elif sub == "reset":
        return _cmd_reset()
    elif sub == "stats":
        return _cmd_stats()
    elif sub == "help":
        return _cmd_help()
    else:
        return f"未知子命令: {sub}\n\n{_cmd_help()}"


def _cmd_show() -> str:
    """显示当前权限配置"""
    lines = ["🔐 权限配置", ""]

    # 当前模式
    if _permission_manager:
        lines.append(f"  模式: {_permission_manager.mode}")
        mode_desc = {
            "normal": "写入和命令需用户确认",
            "auto": "文件操作自动通过，命令仍需确认",
            "plan": "只读模式，禁止所有修改操作",
            "bypass": "跳过所有权限检查（危险）",
        }.get(_permission_manager.mode, "")
        lines.append(f"  说明: {mode_desc}")
    else:
        lines.append("  模式: (未初始化)")

    lines.append("")

    # 规则列表
    allow_rules = _runtime_rules.get("allow", [])
    deny_rules = _runtime_rules.get("deny", [])

    lines.append(f"  ✅ Allow 规则 ({len(allow_rules)} 条):")
    if allow_rules:
        for r in allow_rules:
            lines.append(f"    + {r}")
    else:
        lines.append(f"    (无)")

    lines.append("")
    lines.append(f"  ❌ Deny 规则 ({len(deny_rules)} 条):")
    if deny_rules:
        for r in deny_rules:
            lines.append(f"    - {r}")
    else:
        lines.append(f"    (无)")

    # 黑名单
    if _permission_manager:
        lines.append("")
        lines.append(f"  🚫 内置黑名单 ({len(_permission_manager.DANGEROUS_PATTERNS)} 条):")
        for p in _permission_manager.DANGEROUS_PATTERNS[:5]:
            lines.append(f"    • {p}")
        if len(_permission_manager.DANGEROUS_PATTERNS) > 5:
            lines.append(f"    ... 还有 {len(_permission_manager.DANGEROUS_PATTERNS) - 5} 条")

    return "\n".join(lines)


def _cmd_mode(rest) -> str:
    """查看/切换权限模式"""
    if not rest:
        if _permission_manager:
            return f"当前权限模式: {_permission_manager.mode}"
        return "权限管理器未初始化"

    new_mode = rest[0].lower()
    if new_mode not in ["normal", "auto", "plan", "bypass"]:
        return f"❌ 无效模式: {new_mode}，可选: normal/auto/plan/bypass"

    if _permission_manager:
        old_mode = _permission_manager.mode
        _permission_manager.mode = new_mode

        # 持久化到配置
        if _config_path:
            try:
                cfg = {}
                if os.path.exists(_config_path):
                    with open(_config_path, 'r', encoding='utf-8') as f:
                        cfg = yaml.safe_load(f) or {}
                if "permissions" not in cfg:
                    cfg["permissions"] = {}
                cfg["permissions"]["mode"] = new_mode
                with open(_config_path, 'w', encoding='utf-8') as f:
                    yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)
            except Exception:
                pass

        return f"✅ 权限模式已切换: {old_mode} → {new_mode}"
    return "❌ 权限管理器未初始化"


def _cmd_list() -> str:
    """列出所有规则"""
    return _cmd_show()


def _cmd_allow(rest) -> str:
    """添加 allow 规则"""
    if not rest:
        return "用法: /permissions allow <tool:pattern>\n示例: /permissions allow run_command:git status"

    rule = " ".join(rest)
    if rule in _runtime_rules["allow"]:
        return f"⚠️ 规则已存在: {rule}"

    _runtime_rules["allow"].append(rule)
    saved = _save_rules_to_config()
    suffix = "（已持久化）" if saved else "（仅运行时生效）"
    return f"✅ Allow 规则已添加: {rule} {suffix}"


def _cmd_deny(rest) -> str:
    """添加 deny 规则"""
    if not rest:
        return "用法: /permissions deny <tool:pattern>\n示例: /permissions deny run_command:rm -rf"

    rule = " ".join(rest)
    if rule in _runtime_rules["deny"]:
        return f"⚠️ 规则已存在: {rule}"

    _runtime_rules["deny"].append(rule)
    saved = _save_rules_to_config()
    suffix = "（已持久化）" if saved else "（仅运行时生效）"
    return f"✅ Deny 规则已添加: {rule} {suffix}"


def _cmd_remove(rest) -> str:
    """移除规则"""
    if len(rest) < 2:
        return "用法: /permissions remove <allow|deny> <rule>"

    rule_type = rest[0].lower()
    if rule_type not in ["allow", "deny", "a", "d"]:
        return f"❌ 规则类型必须是 allow 或 deny"

    key = "allow" if rule_type in ["allow", "a"] else "deny"
    rule = " ".join(rest[1:])

    if rule not in _runtime_rules[key]:
        return f"❌ 规则不存在: [{key}] {rule}"

    _runtime_rules[key].remove(rule)
    saved = _save_rules_to_config()
    suffix = "（已持久化）" if saved else ""
    return f"🗑️ 规则已移除: [{key}] {rule} {suffix}"


def _cmd_reset() -> str:
    """重置为默认规则"""
    _runtime_rules["allow"] = []
    _runtime_rules["deny"] = []
    _save_rules_to_config()
    return "🔄 权限规则已重置为默认"


def _cmd_stats() -> str:
    """权限统计"""
    lines = [
        "📊 权限统计",
        f"  当前模式: {_permission_manager.mode if _permission_manager else '未知'}",
        f"  Allow 规则: {len(_runtime_rules.get('allow', []))} 条",
        f"  Deny 规则: {len(_runtime_rules.get('deny', []))} 条",
        f"  内置黑名单: {len(_permission_manager.DANGEROUS_PATTERNS) if _permission_manager else 0} 条",
    ]
    if _permission_manager:
        lines.append(f"  交互确认: {'可用' if _permission_manager._interactive_enabled else '不可用'}")
    return "\n".join(lines)


def _cmd_help() -> str:
    return """权限管理命令 /permissions

用法:
  /permissions                  查看当前权限配置
  /permissions mode [mode]      查看/切换权限模式 (normal/auto/plan/bypass)
  /permissions list             列出所有规则
  /permissions allow <rule>     添加 allow 规则 (格式: tool:pattern)
  /permissions deny <rule>      添加 deny 规则 (格式: tool:pattern)
  /permissions remove <a|d> <rule> 移除规则
  /permissions reset            重置为默认规则
  /permissions stats            权限统计信息

规则格式: tool_name:pattern
  示例: run_command:git status   — 允许 git status
        run_command:rm -rf       — 禁止 rm -rf
        read_file:*              — 允许读取所有文件

权限模式:
  normal   写入和命令需用户确认
  auto     文件操作自动通过，命令仍需确认
  plan     只读模式，禁止所有修改操作
  bypass   跳过所有权限检查（危险）"""


register_command("permissions", {
    "description": "权限规则管理 (查看/模式切换/allow/deny 规则)",
    "handler": permissions_handler,
    "args_help": "[mode|list|allow|deny|remove|reset|stats]",
    "category": "system",
})
