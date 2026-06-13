"""
Hook 配置加载器

参考 Claude Code 的 hooksSettings.ts 设计，
支持从 JSON 配置文件加载 Hook 规则。

配置文件格式 (hooks.json):
{
    "hooks": [
        {
            "event": "PreToolUse",
            "matcher": "run_command",
            "command": "echo 'About to run command' >> /tmp/hook.log",
            "priority": 10,
            "timeout": 5,
            "enabled": true,
            "description": "Log shell commands"
        },
        {
            "event": "PostToolUse",
            "matcher": "write_file",
            "command": "python -m py_compile {file_path}",
            "on_fail": "warn",
            "priority": 5
        }
    ]
}

支持的配置路径 (按优先级):
1. 项目级: .opencode/hooks.json
2. 用户级: ~/.opencode/hooks.json
"""

import json
import os
import logging
import subprocess
import time
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class HookConfigEntry:
    """单条 Hook 配置规则"""
    event: str                          # 事件类型 (PreToolUse, PostToolUse, etc.)
    command: str                        # 要执行的 Shell 命令
    matcher: Optional[str] = None       # 工具名匹配 (None = 匹配所有)
    priority: int = 0                   # 优先级 (越大越先执行)
    timeout: float = 10.0               # 命令超时 (秒)
    enabled: bool = True                # 是否启用
    description: str = ""               # 描述
    on_fail: str = "ignore"             # 失败策略: ignore / warn / block
    on_success: str = "continue"        # 成功策略: continue / short_circuit
    env: Dict[str, str] = field(default_factory=dict)  # 附加环境变量

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HookConfigEntry":
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)


@dataclass
class HookExecutionLog:
    """Hook 执行日志条目"""
    hook_id: int
    event: str
    command: str
    tool_name: Optional[str]
    timestamp: str
    duration_ms: float
    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    result: str = "success"             # success / failed / timeout / blocked
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class HookConfigLoader:
    """
    Hook 配置加载器

    从 JSON 配置文件加载 Hook 规则，注册到 HookManager，
    并维护执行日志。
    """

    # 默认配置搜索路径
    CONFIG_PATHS = [
        ".opencode/hooks.json",
        os.path.expanduser("~/.opencode/hooks.json"),
    ]

    def __init__(self, hook_manager=None, project_root: str = "."):
        """
        Args:
            hook_manager: HookManager 实例
            project_root: 项目根目录
        """
        self.hook_manager = hook_manager
        self.project_root = project_root
        self.entries: List[HookConfigEntry] = []
        self._registered_hook_ids: List[int] = []
        self._execution_log: List[HookExecutionLog] = []
        self._max_log_size = 500  # 最大日志条目数
        self._config_path: Optional[str] = None

    def find_config(self) -> Optional[str]:
        """查找配置文件路径"""
        # 项目级优先
        project_path = os.path.join(self.project_root, ".opencode", "hooks.json")
        if os.path.exists(project_path):
            return project_path

        # 用户级
        user_path = os.path.expanduser("~/.opencode/hooks.json")
        if os.path.exists(user_path):
            return user_path

        return None

    def load(self, config_path: Optional[str] = None) -> int:
        """
        加载 Hook 配置并注册到 HookManager

        Args:
            config_path: 指定配置路径（None 则自动搜索）

        Returns:
            成功注册的 Hook 数量
        """
        path = config_path or self.find_config()
        if not path:
            logger.debug("No hooks config found")
            return 0

        if not os.path.exists(path):
            logger.warning(f"Hooks config not found: {path}")
            return 0

        self._config_path = path

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"Failed to parse hooks config {path}: {e}")
            return 0

        hooks_data = data.get("hooks", [])
        if not hooks_data:
            logger.info(f"No hooks defined in {path}")
            return 0

        # 先清除旧的注册
        self.unload()

        registered = 0
        for item in hooks_data:
            try:
                entry = HookConfigEntry.from_dict(item)
                if not entry.enabled:
                    continue

                self.entries.append(entry)

                # 创建 handler 并注册到 HookManager
                handler = self._create_handler(entry)
                if self.hook_manager:
                    hook_id = self.hook_manager.register_hook(
                        event=entry.event,
                        handler=handler,
                        matcher=entry.matcher,
                        priority=entry.priority,
                    )
                    self._registered_hook_ids.append(hook_id)
                    registered += 1

            except Exception as e:
                logger.warning(f"Failed to register hook from config: {e}")

        logger.info(f"Loaded {registered} hooks from {path}")
        return registered

    def unload(self):
        """卸载所有已注册的配置 Hook"""
        if self.hook_manager:
            for hook_id in self._registered_hook_ids:
                try:
                    self.hook_manager.unregister_hook(hook_id)
                except Exception:
                    pass
        self._registered_hook_ids.clear()
        self.entries.clear()

    def reload(self) -> int:
        """重新加载配置"""
        self.unload()
        return self.load(self._config_path)

    def _create_handler(self, entry: HookConfigEntry):
        """
        为配置条目创建异步 handler 函数

        handler 执行 Shell 命令，记录日志，根据 on_fail/on_success 策略返回 HookResult
        """
        loader = self  # 闭包引用

        async def handler(**kwargs) -> "HookResult":
            from hooks.manager import HookResult

            tool_name = kwargs.get("tool_name", "")
            start_time = time.time()

            # 构建命令（支持变量替换）
            cmd = entry.command
            # 替换常见变量
            if "{tool_name}" in cmd:
                cmd = cmd.replace("{tool_name}", tool_name or "")
            # 替换 input 参数
            input_data = kwargs.get("input", {})
            if isinstance(input_data, dict):
                for key, val in input_data.items():
                    placeholder = "{" + key + "}"
                    if placeholder in cmd:
                        cmd = cmd.replace(placeholder, str(val))

            # 构建环境变量
            env = os.environ.copy()
            env["HOOK_EVENT"] = entry.event
            env["HOOK_TOOL_NAME"] = tool_name or ""
            if isinstance(input_data, dict):
                env["HOOK_INPUT_JSON"] = json.dumps(input_data, ensure_ascii=False)
            env.update(entry.env)

            # 执行命令
            log_entry = HookExecutionLog(
                hook_id=-1,
                event=entry.event,
                command=cmd,
                tool_name=tool_name,
                timestamp=datetime.now().isoformat(),
                duration_ms=0,
            )

            try:
                result = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=entry.timeout,
                    env=env,
                    cwd=loader.project_root,
                )
                duration_ms = (time.time() - start_time) * 1000

                log_entry.duration_ms = duration_ms
                log_entry.exit_code = result.returncode
                log_entry.stdout = result.stdout[:1000]  # 限制日志大小
                log_entry.stderr = result.stderr[:1000]

                if result.returncode != 0:
                    log_entry.result = "failed"
                    logger.warning(
                        f"Hook command failed [{entry.event}]: {cmd[:80]} "
                        f"(exit={result.returncode})"
                    )

                    if entry.on_fail == "block":
                        log_entry.result = "blocked"
                        loader._add_log(log_entry)
                        return HookResult(
                            allow=False,
                            block_reason=f"Hook blocked: {entry.description or cmd[:100]}",
                        )
                    elif entry.on_fail == "warn":
                        loader._add_log(log_entry)
                        return HookResult(
                            allow=True,
                            additional_context=f"[Hook Warning] {result.stderr[:500]}",
                        )
                    # ignore: 继续执行
                    loader._add_log(log_entry)
                    return HookResult(allow=True)

                # 成功
                log_entry.result = "success"
                loader._add_log(log_entry)

                hook_result = HookResult(allow=True)
                if entry.on_success == "short_circuit":
                    hook_result.short_circuit = True

                # 解析 stdout 中的附加指令
                if result.stdout.strip():
                    hook_result.additional_context = result.stdout.strip()[:1000]

                return hook_result

            except subprocess.TimeoutExpired:
                log_entry.result = "timeout"
                log_entry.duration_ms = entry.timeout * 1000
                log_entry.error = f"Command timed out after {entry.timeout}s"
                loader._add_log(log_entry)
                logger.warning(f"Hook command timed out: {cmd[:80]}")

                if entry.on_fail == "block":
                    return HookResult(allow=False, block_reason="Hook timed out")
                return HookResult(allow=True)

            except Exception as e:
                log_entry.result = "failed"
                log_entry.duration_ms = (time.time() - start_time) * 1000
                log_entry.error = str(e)
                loader._add_log(log_entry)
                logger.error(f"Hook command error: {e}")

                if entry.on_fail == "block":
                    return HookResult(allow=False, block_reason=f"Hook error: {e}")
                return HookResult(allow=True)

        return handler

    def _add_log(self, entry: HookExecutionLog):
        """添加执行日志条目（限制大小）"""
        self._execution_log.append(entry)
        if len(self._execution_log) > self._max_log_size:
            self._execution_log = self._execution_log[-self._max_log_size:]

    def get_execution_log(self, limit: int = 50) -> List[HookExecutionLog]:
        """获取执行日志（最近 N 条）"""
        return self._execution_log[-limit:]

    def clear_log(self):
        """清空执行日志"""
        self._execution_log.clear()

    def get_config_info(self) -> Dict[str, Any]:
        """获取当前配置信息"""
        return {
            "config_path": self._config_path,
            "entries_count": len(self.entries),
            "registered_hooks": len(self._registered_hook_ids),
            "log_size": len(self._execution_log),
            "entries": [e.to_dict() for e in self.entries],
        }

    def add_entry(self, entry: HookConfigEntry) -> int:
        """
        动态添加 Hook 配置条目

        Returns:
            Hook ID 或 -1（失败时）
        """
        self.entries.append(entry)

        if self.hook_manager:
            handler = self._create_handler(entry)
            try:
                hook_id = self.hook_manager.register_hook(
                    event=entry.event,
                    handler=handler,
                    matcher=entry.matcher,
                    priority=entry.priority,
                )
                self._registered_hook_ids.append(hook_id)
                return hook_id
            except Exception as e:
                logger.error(f"Failed to add hook: {e}")
                return -1
        return -1

    def save_config(self, path: Optional[str] = None) -> bool:
        """
        保存当前配置到文件

        Args:
            path: 保存路径（默认使用当前配置路径）

        Returns:
            True 如果保存成功
        """
        save_path = path or self._config_path
        if not save_path:
            save_path = os.path.join(self.project_root, ".opencode", "hooks.json")

        try:
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            data = {
                "hooks": [e.to_dict() for e in self.entries],
            }
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._config_path = save_path
            logger.info(f"Hooks config saved to {save_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save hooks config: {e}")
            return False
