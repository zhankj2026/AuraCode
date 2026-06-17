"""
插件注册中心 — 插件生态建设核心模块

功能:
- PluginRegistry: 插件注册/发现/生命周期管理
- PluginBus: 插件间事件通信总线
- DependencyResolver: 插件依赖解析与加载顺序
- PluginManifest: 插件清单/元数据标准格式

用法:
    registry = PluginRegistry()
    registry.register_plugin(MyPlugin())
    registry.start_all()
    registry.bus.emit("tool.called", {"tool": "write_file"})
"""

import logging
import time
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set
from datetime import datetime

logger = logging.getLogger(__name__)


# ── 插件清单 ────────────────────────────────────────────────


@dataclass
class PluginManifest:
    """插件清单 — 标准化元数据"""
    name: str
    version: str
    description: str = ""
    author: str = ""
    license: str = "MIT"
    homepage: str = ""
    dependencies: List[str] = field(default_factory=list)   # 依赖的其他插件
    provides: List[str] = field(default_factory=list)       # 提供的能力标签
    requires: Dict[str, str] = field(default_factory=dict)  # 环境要求 (python>=3.9, etc)
    tags: List[str] = field(default_factory=list)
    enabled: bool = True
    source: str = "user"  # 来源: builtin / project / user / marketplace

    @property
    def plugin_id(self) -> str:
        """规范插件 ID: {name}@{source}"""
        return f"{self.name}@{self.source}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "plugin_id": self.plugin_id,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "source": self.source,
            "dependencies": self.dependencies,
            "provides": self.provides,
            "tags": self.tags,
            "enabled": self.enabled,
        }

    @staticmethod
    def from_plugin(plugin) -> 'PluginManifest':
        """从 ToolPlugin 实例自动提取清单"""
        manifest = PluginManifest(
            name=getattr(plugin, 'name', 'unknown'),
            version=getattr(plugin, 'version', '0.0.1'),
            description=getattr(plugin, 'description', ''),
            source=getattr(plugin, 'source', 'user'),
        )
        # 额外属性
        for attr in ('author', 'license', 'homepage', 'dependencies',
                      'provides', 'requires', 'tags'):
            if hasattr(plugin, attr):
                setattr(manifest, attr, getattr(plugin, attr))
        return manifest


# ── 插件注册中心 ────────────────────────────────────────────


@dataclass
class PluginEntry:
    """插件注册条目"""
    manifest: PluginManifest
    plugin: Any  # ToolPlugin instance
    registered_at: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = "registered"  # registered/active/error/disabled
    error: Optional[str] = None
    load_time_ms: float = 0.0


class PluginRegistry:
    """
    插件注册中心

    管理插件的完整生命周期:
    - 注册 (register)
    - 依赖解析 (resolve_dependencies)
    - 激活 (activate / start_all)
    - 注销 (unregister)
    - 状态查询 (list_plugins / get_plugin_info)
    """

    def __init__(self):
        self._entries: Dict[str, PluginEntry] = {}
        self._lock = threading.Lock()
        self.bus = PluginBus()
        self._resolver = DependencyResolver()

    def register_plugin(self, plugin, manifest: PluginManifest = None) -> PluginEntry:
        """
        注册插件

        Args:
            plugin: ToolPlugin 实例
            manifest: 可选清单, 不提供则自动从插件提取

        Returns:
            PluginEntry
        """
        if manifest is None:
            manifest = PluginManifest.from_plugin(plugin)

        name = manifest.name
        with self._lock:
            if name in self._entries:
                logger.warning(f"Plugin '{name}' already registered, replacing...")
                self.unregister_plugin(name)

            entry = PluginEntry(manifest=manifest, plugin=plugin)
            self._entries[name] = entry

            # 注册依赖图
            self._resolver.add_plugin(name, manifest.dependencies)

            # 注册到事件总线
            if hasattr(plugin, 'on_event'):
                self.bus.subscribe_all(plugin.on_event)

            logger.info(f"Plugin registered: {name} v{manifest.version}")
            return entry

    def unregister_plugin(self, name: str) -> bool:
        """注销插件"""
        with self._lock:
            entry = self._entries.pop(name, None)
            if not entry:
                return False

            # 清理资源
            try:
                if hasattr(entry.plugin, 'cleanup'):
                    entry.plugin.cleanup()
            except Exception as e:
                logger.warning(f"Plugin cleanup error: {name}: {e}")

            # 从依赖图移除
            self._resolver.remove_plugin(name)

            logger.info(f"Plugin unregistered: {name}")
            return True

    def activate_plugin(self, name: str) -> bool:
        """激活指定插件"""
        with self._lock:
            entry = self._entries.get(name)
            if not entry:
                return False

            if entry.status == "active":
                return True

            # 检查依赖
            missing = self._resolver.get_missing_dependencies(name)
            if missing:
                entry.status = "error"
                entry.error = f"Missing dependencies: {missing}"
                logger.error(f"Cannot activate '{name}': {entry.error}")
                return False

            start = time.time()
            try:
                if hasattr(entry.plugin, 'initialize'):
                    result = entry.plugin.initialize()
                    if result is False:
                        entry.status = "error"
                        entry.error = "initialize() returned False"
                        return False
                entry.status = "active"
                entry.load_time_ms = (time.time() - start) * 1000
                logger.info(f"Plugin activated: {name} ({entry.load_time_ms:.1f}ms)")
                return True
            except Exception as e:
                entry.status = "error"
                entry.error = str(e)[:200]
                logger.error(f"Plugin activation failed: {name}: {e}")
                return False

    def start_all(self) -> Dict[str, bool]:
        """
        按依赖顺序激活所有已注册插件

        Returns:
            {plugin_name: success}
        """
        order = self._resolver.resolve_load_order()
        results = {}

        for name in order:
            with self._lock:
                entry = self._entries.get(name)
                if not entry or not entry.manifest.enabled:
                    continue

            results[name] = self.activate_plugin(name)

        active = sum(1 for v in results.values() if v)
        logger.info(f"Plugin startup: {active}/{len(results)} activated")
        return results

    def stop_all(self):
        """停止所有插件"""
        # 反序停止 (先停依赖方)
        order = self._resolver.resolve_load_order()
        for name in reversed(order):
            self.deactivate_plugin(name)

    def deactivate_plugin(self, name: str) -> bool:
        """停用插件 (不注销)"""
        with self._lock:
            entry = self._entries.get(name)
            if not entry or entry.status != "active":
                return False

        try:
            if hasattr(entry.plugin, 'cleanup'):
                entry.plugin.cleanup()
            entry.status = "registered"
            return True
        except Exception as e:
            logger.error(f"Plugin deactivation error: {name}: {e}")
            return False

    # ── 查询 API ──

    def get_plugin(self, name: str):
        """获取插件实例"""
        entry = self._entries.get(name)
        return entry.plugin if entry else None

    def list_plugins(self) -> List[Dict[str, Any]]:
        """列出所有插件信息（含 plugin_id 和 source）"""
        result = []
        with self._lock:
            for name, entry in self._entries.items():
                result.append({
                    "name": name,
                    "plugin_id": entry.manifest.plugin_id,
                    "version": entry.manifest.version,
                    "description": entry.manifest.description,
                    "source": entry.manifest.source,
                    "status": entry.status,
                    "error": entry.error,
                    "load_time_ms": round(entry.load_time_ms, 2),
                    "dependencies": entry.manifest.dependencies,
                    "provides": entry.manifest.provides,
                    "registered_at": entry.registered_at,
                })
        return result

    def get_enabled_plugins(self) -> List[str]:
        """获取已启用插件名列表（manifest.enabled=True 且状态为 active）"""
        return [
            n for n, e in self._entries.items()
            if e.status == "active" and e.manifest.enabled
        ]

    def get_disabled_plugins(self) -> List[str]:
        """获取已禁用插件名列表"""
        return [
            n for n, e in self._entries.items()
            if not e.manifest.enabled or e.status == "disabled"
        ]

    def get_active_plugins(self) -> List[str]:
        """获取活跃插件名列表"""
        return [n for n, e in self._entries.items() if e.status == "active"]

    def get_stats(self) -> Dict[str, Any]:
        """插件统计"""
        stats = {"total": 0, "active": 0, "error": 0, "disabled": 0}
        with self._lock:
            for entry in self._entries.values():
                stats["total"] += 1
                if entry.status == "active":
                    stats["active"] += 1
                elif entry.status == "error":
                    stats["error"] += 1
                elif not entry.manifest.enabled:
                    stats["disabled"] += 1
        return stats

    def find_by_capability(self, capability: str) -> List[str]:
        """按能力标签查找插件"""
        return [
            name for name, entry in self._entries.items()
            if capability in entry.manifest.provides
        ]


# ── 插件间事件通信 ─────────────────────────────────────────


class PluginBus:
    """
    插件间事件通信总线

    支持:
    - emit(): 发布事件
    - subscribe(): 订阅特定事件
    - subscribe_all(): 订阅所有事件
    - request(): 同步请求-响应模式
    """

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}  # event -> handlers
        self._global_handlers: List[Callable] = []
        self._lock = threading.Lock()
        self._event_log: List[Dict] = []
        self._max_log = 200

    def subscribe(self, event: str, handler: Callable):
        """订阅特定事件"""
        with self._lock:
            if event not in self._subscribers:
                self._subscribers[event] = []
            self._subscribers[event].append(handler)

    def unsubscribe(self, event: str, handler: Callable):
        """取消订阅"""
        with self._lock:
            if event in self._subscribers:
                self._subscribers[event] = [
                    h for h in self._subscribers[event] if h != handler
                ]

    def subscribe_all(self, handler: Callable):
        """订阅所有事件"""
        with self._lock:
            self._global_handlers.append(handler)

    def emit(self, event: str, data: Dict[str, Any] = None) -> int:
        """
        发布事件

        Returns:
            触发的处理器数量
        """
        data = data or {}
        triggered = 0

        # 日志
        log_entry = {
            "event": event,
            "data_keys": list(data.keys()),
            "timestamp": time.time(),
        }
        self._event_log.append(log_entry)
        if len(self._event_log) > self._max_log:
            self._event_log = self._event_log[-self._max_log:]

        with self._lock:
            handlers = list(self._subscribers.get(event, []))
            global_handlers = list(self._global_handlers)

        for handler in handlers + global_handlers:
            try:
                handler(event=event, data=data)
                triggered += 1
            except Exception as e:
                logger.warning(f"Bus handler error for '{event}': {e}")

        return triggered

    def request(self, event: str, data: Dict[str, Any] = None) -> List[Any]:
        """
        请求-响应模式: 发布事件并收集所有处理器的返回值

        Returns:
            响应列表
        """
        data = data or {}
        responses = []

        with self._lock:
            handlers = list(self._subscribers.get(event, []))

        for handler in handlers:
            try:
                result = handler(event=event, data=data)
                if result is not None:
                    responses.append(result)
            except Exception as e:
                logger.warning(f"Bus request handler error for '{event}': {e}")

        return responses

    def get_event_log(self, limit: int = 50) -> List[Dict]:
        """获取事件日志"""
        return self._event_log[-limit:]

    def get_subscription_count(self) -> Dict[str, int]:
        """获取各事件的订阅数"""
        with self._lock:
            return {e: len(h) for e, h in self._subscribers.items()}


# ── 依赖解析器 ─────────────────────────────────────────────


class DependencyResolver:
    """
    插件依赖解析器

    支持:
    - 拓扑排序确定加载顺序
    - 循环依赖检测
    - 缺失依赖报告
    """

    def __init__(self):
        self._graph: Dict[str, List[str]] = {}  # plugin -> dependencies

    def add_plugin(self, name: str, dependencies: List[str] = None):
        """注册插件及其依赖"""
        self._graph[name] = dependencies or []

    def remove_plugin(self, name: str):
        """移除插件"""
        self._graph.pop(name, None)

    def get_missing_dependencies(self, name: str) -> List[str]:
        """获取缺失的依赖"""
        deps = self._graph.get(name, [])
        return [d for d in deps if d not in self._graph]

    def detect_cycles(self) -> List[List[str]]:
        """检测循环依赖"""
        visited = set()
        rec_stack = set()
        cycles = []

        def _dfs(node, path):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for dep in self._graph.get(node, []):
                if dep not in self._graph:
                    continue
                if dep not in visited:
                    _dfs(dep, path)
                elif dep in rec_stack:
                    # 找到环
                    cycle_start = path.index(dep)
                    cycles.append(path[cycle_start:] + [dep])

            path.pop()
            rec_stack.discard(node)

        for node in self._graph:
            if node not in visited:
                _dfs(node, [])

        return cycles

    def resolve_load_order(self) -> List[str]:
        """
        拓扑排序解析加载顺序 (依赖优先)

        Returns:
            有序插件名列表

        Raises:
            如有循环依赖则按原始顺序返回 (降级)
        """
        # 检测循环
        cycles = self.detect_cycles()
        if cycles:
            logger.warning(f"Dependency cycles detected: {cycles}")
            return list(self._graph.keys())

        # Kahn 算法拓扑排序
        in_degree = {n: 0 for n in self._graph}
        for node, deps in self._graph.items():
            for dep in deps:
                if dep in in_degree:
                    in_degree[node] = in_degree.get(node, 0)  # ensure exists

        # 计算入度
        for node, deps in self._graph.items():
            for dep in deps:
                if dep in self._graph:
                    in_degree[node] += 1

        # BFS
        queue = [n for n, d in in_degree.items() if d == 0]
        order = []

        while queue:
            node = queue.pop(0)
            order.append(node)

            # 找到依赖当前节点的其他插件
            for other, deps in self._graph.items():
                if node in deps and other not in order:
                    in_degree[other] -= 1
                    if in_degree[other] == 0:
                        queue.append(other)

        # 添加遗漏的 (可能有未解析的外部依赖)
        for name in self._graph:
            if name not in order:
                order.append(name)

        return order
