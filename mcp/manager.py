"""
MCP Manager - MCP 服务器热加载/注销管理器

功能:
- 运行时动态添加/移除/重启 MCP 服务器
- 自动发现工具并注册到 TOOL_REGISTRY
- 工具结果缓存 (TTL)
- 服务器健康状态追踪

用法:
    mgr = McpManager()
    await mgr.add_server("my-server", config)
    await mgr.remove_server("my-server")
    await mgr.refresh_tools()
"""

import asyncio
import hashlib
import json
import logging
import os
import time
import yaml
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp.client.base import MCPClient, MCPSessionExpiredError
from mcp.config.types import McpServerConfig, McpStdioServerConfig, McpSSEServerConfig
from mcp.tools.adapter import MCPToolAdapter
from mcp.tools.validation import validate_and_truncate_output
from mcp.security import is_mcp_server_allowed, get_security_policy

logger = logging.getLogger(__name__)


@dataclass
class ToolCacheEntry:
    """工具结果缓存条目"""
    result: Any
    timestamp: float
    ttl: float  # 秒

    def is_expired(self) -> bool:
        return (time.time() - self.timestamp) > self.ttl


@dataclass
class McpServerState:
    """MCP 服务器运行时状态"""
    name: str
    config: McpServerConfig
    client: Optional[MCPClient] = None
    connected: bool = False
    tools: List[Dict[str, Any]] = field(default_factory=list)
    tool_adapters: Dict[str, MCPToolAdapter] = field(default_factory=dict)
    error: Optional[str] = None
    last_connect_time: Optional[float] = None
    call_count: int = 0
    error_count: int = 0


class McpManager:
    """
    MCP 服务器管理器
    
    支持运行时动态:
    - 添加服务器 (add_server)
    - 移除服务器 (remove_server)
    - 重启服务器 (restart_server)
    - 刷新工具列表 (refresh_tools)
    - 缓存工具结果 (call_tool_cached)
    """

    def __init__(self, cache_ttl: float = 60.0, max_cache_size: int = 500):
        self.servers: Dict[str, McpServerState] = {}
        self._cache: Dict[str, ToolCacheEntry] = {}
        self._cache_ttl = cache_ttl
        self._max_cache_size = max_cache_size
        self._registered_tool_names: set = set()

    # ═══════════ 服务器生命周期 ═══════════

    async def add_server(self, name: str, config: McpServerConfig) -> McpServerState:
        """
        添加并连接 MCP 服务器（热加载）
        
        安全检查:
        1. 检查拒绝列表
        2. 检查允许列表
        3. 命令/URL 模式匹配
        """
        if name in self.servers:
            logger.warning(f"MCP server '{name}' already exists, reconnecting...")
            await self.remove_server(name)
        
        # 安全策略检查
        config_dict = self._config_to_dict(config)
        if not is_mcp_server_allowed(name, config_dict):
            error_msg = f"MCP server '{name}' denied by security policy"
            logger.error(error_msg)
            state = McpServerState(name=name, config=config, error=error_msg)
            return state

        state = McpServerState(name=name, config=config)
        self.servers[name] = state

        try:
            client = MCPClient(name, config)
            await client.connect()
            state.client = client
            state.connected = True
            state.last_connect_time = time.time()

            # 发现工具
            tools = await client.list_tools()
            state.tools = tools
            for tool_def in tools:
                tool_name = tool_def.get("name", "")
                adapter = MCPToolAdapter(
                    server_name=name,
                    tool_name=tool_name,
                    tool_description=tool_def.get("description", ""),
                    tool_schema=tool_def.get("inputSchema", {}),
                    mcp_client=client,
                )
                state.tool_adapters[tool_name] = adapter

            logger.info(f"MCP server '{name}' connected: {len(tools)} tools")
            return state

        except Exception as e:
            state.error = str(e)
            state.connected = False
            logger.error(f"MCP server '{name}' connection failed: {e}")
            return state

    async def remove_server(self, name: str) -> bool:
        """断开并移除 MCP 服务器（热注销）"""
        state = self.servers.pop(name, None)
        if not state:
            return False

        # 清理缓存
        prefix = f"mcp__{name}__"
        keys_to_remove = [k for k in self._cache if k.startswith(prefix)]
        for k in keys_to_remove:
            del self._cache[k]

        # 清理已注册的工具名
        for tool_name in state.tool_adapters:
            qualified = f"mcp__{name}__{tool_name}"
            self._registered_tool_names.discard(qualified)

        # 断开连接
        if state.client:
            try:
                await state.client.disconnect()
            except Exception:
                pass

        logger.info(f"MCP server '{name}' removed")
        return True

    async def restart_server(self, name: str) -> Optional[McpServerState]:
        """重启 MCP 服务器"""
        state = self.servers.get(name)
        if not state:
            return None
        config = state.config
        await self.remove_server(name)
        return await self.add_server(name, config)

    async def disconnect_all(self):
        """断开所有服务器"""
        for name in list(self.servers.keys()):
            await self.remove_server(name)

    # ═══════════ 工具调用 ═══════════

    async def call_tool(
        self, server_name: str, tool_name: str, arguments: Dict[str, Any]
    ) -> Any:
        """调用 MCP 工具"""
        state = self.servers.get(server_name)
        if not state or not state.connected:
            raise MCPSessionExpiredError(server_name)

        adapter = state.tool_adapters.get(tool_name)
        if not adapter:
            raise ValueError(f"Tool '{tool_name}' not found on server '{server_name}'")

        state.call_count += 1
        rec_id = self.record_call_start(server_name, tool_name, arguments)
        try:
            result = await adapter.execute(arguments)
            self.record_call_end(rec_id, success=True)
            return result
        except MCPSessionExpiredError:
            state.connected = False
            state.error_count += 1
            self.record_call_end(rec_id, success=False, error="session_expired")
            raise
        except Exception as e:
            state.error_count += 1
            self.record_call_end(rec_id, success=False, error=str(e)[:200])
            raise

    async def call_tool_cached(
        self, server_name: str, tool_name: str, arguments: Dict[str, Any],
        ttl: Optional[float] = None,
    ) -> Any:
        """带缓存的 MCP 工具调用"""
        cache_key = self._make_cache_key(server_name, tool_name, arguments)

        # 检查缓存
        entry = self._cache.get(cache_key)
        if entry and not entry.is_expired():
            rec_id = self.record_call_start(server_name, tool_name, arguments)
            self.record_call_end(rec_id, success=True, cached=True)
            return entry.result

        # 调用
        result = await self.call_tool(server_name, tool_name, arguments)

        # 写入缓存
        self._evict_if_needed()
        self._cache[cache_key] = ToolCacheEntry(
            result=result,
            timestamp=time.time(),
            ttl=ttl or self._cache_ttl,
        )
        return result

    def _make_cache_key(self, server: str, tool: str, args: Dict) -> str:
        args_str = json.dumps(args, sort_keys=True, default=str)
        raw = f"mcp__{server}__{tool}::{args_str}"
        return hashlib.sha256(raw.encode()).hexdigest()[:24]

    def _evict_if_needed(self):
        """淘汰过期或超额缓存"""
        # 先清过期
        now = time.time()
        expired = [k for k, v in self._cache.items() if v.is_expired()]
        for k in expired:
            del self._cache[k]
        # 再按时间淘汰最旧的
        while len(self._cache) >= self._max_cache_size:
            oldest_key = min(self._cache, key=lambda k: self._cache[k].timestamp)
            del self._cache[oldest_key]

    # ═══════════ 工具注册到全局 TOOL_REGISTRY ═══════════

    def register_tools_to_registry(self):
        """将所有已连接 MCP 服务器的工具注册到全局 TOOL_REGISTRY"""
        try:
            from tools.registry import TOOL_REGISTRY, register_tool
        except ImportError:
            return

        for name, state in self.servers.items():
            if not state.connected:
                continue
            for tool_name, adapter in state.tool_adapters.items():
                qualified = adapter.qualified_name
                if qualified in self._registered_tool_names:
                    continue
                TOOL_REGISTRY[qualified] = {
                    "name": qualified,
                    "description": adapter.description,
                    "parameters": adapter.get_parameters(),
                    "handler": adapter,
                    "category": "mcp",
                }
                self._registered_tool_names.add(qualified)

    # ═══════════ 状态查询 ═══════════

    def get_status(self) -> List[Dict[str, Any]]:
        """获取所有服务器状态"""
        result = []
        for name, state in self.servers.items():
            result.append({
                "name": name,
                "connected": state.connected,
                "tools": len(state.tools),
                "calls": state.call_count,
                "errors": state.error_count,
                "error": state.error,
                "config_type": type(state.config).__name__,
                "uptime": (
                    f"{time.time() - state.last_connect_time:.0f}s"
                    if state.last_connect_time else "N/A"
                ),
            })
        return result

    def get_cache_stats(self) -> Dict[str, Any]:
        """缓存统计"""
        active = sum(1 for v in self._cache.values() if not v.is_expired())
        return {
            "total_entries": len(self._cache),
            "active_entries": active,
            "expired_entries": len(self._cache) - active,
            "max_size": self._max_cache_size,
            "default_ttl": self._cache_ttl,
        }

    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()

    # ═══════════ 服务器自动发现 ═══════════

    def discover_servers(self, search_paths: List[str] = None) -> List[Dict[str, Any]]:
        """
        自动发现 MCP 服务器配置

        搜索位置:
        1. .mcp/ 目录下的 *.json / *.yaml 文件
        2. config.yaml 中的 mcp_servers 节
        3. package.json 中的 mcp 字段
        4. 自定义路径列表

        Returns:
            发现的服务器配置列表 [{name, type, config_dict, source}]
        """
        discovered = []
        if search_paths is None:
            search_paths = []

        # 1. .mcp/ 目录
        mcp_dir = Path(".mcp")
        if mcp_dir.exists():
            for f in mcp_dir.iterdir():
                if f.suffix in ('.json', '.yaml', '.yml'):
                    try:
                        cfg = self._parse_config_file(str(f))
                        if cfg:
                            discovered.append({
                                "name": f.stem,
                                "type": cfg.get("type", "stdio"),
                                "config_dict": cfg,
                                "source": str(f),
                            })
                    except Exception as e:
                        logger.warning(f"Failed to parse MCP config {f}: {e}")

        # 2. config.yaml 中的 mcp_servers 节
        for cfg_file in ["config.yaml", "config.yml", ".auracode.yaml"]:
            p = Path(cfg_file)
            if p.exists():
                try:
                    with open(p, 'r', encoding='utf-8') as fh:
                        data = yaml.safe_load(fh) or {}
                    servers = data.get("mcp_servers", data.get("mcpServers", {}))
                    if isinstance(servers, dict):
                        for name, cfg in servers.items():
                            if isinstance(cfg, dict):
                                discovered.append({
                                    "name": name,
                                    "type": cfg.get("type", "stdio"),
                                    "config_dict": cfg,
                                    "source": f"{cfg_file}#mcp_servers",
                                })
                except Exception as e:
                    logger.debug(f"No MCP config in {cfg_file}: {e}")

        # 3. package.json
        pkg = Path("package.json")
        if pkg.exists():
            try:
                with open(pkg, 'r', encoding='utf-8') as fh:
                    data = json.load(fh)
                mcp_cfg = data.get("mcp", data.get("mcpServers", {}))
                if isinstance(mcp_cfg, dict):
                    for name, cfg in mcp_cfg.items():
                        if isinstance(cfg, dict):
                            discovered.append({
                                "name": name,
                                "type": cfg.get("type", "stdio"),
                                "config_dict": cfg,
                                "source": "package.json#mcp",
                            })
            except Exception:
                pass

        # 4. 自定义搜索路径
        for sp in search_paths:
            p = Path(sp)
            if p.exists() and p.suffix in ('.json', '.yaml', '.yml'):
                try:
                    cfg = self._parse_config_file(str(p))
                    if cfg:
                        discovered.append({
                            "name": p.stem,
                            "type": cfg.get("type", "stdio"),
                            "config_dict": cfg,
                            "source": str(p),
                        })
                except Exception:
                    pass

        logger.info(f"Discovered {len(discovered)} MCP servers")
        return discovered

    def _parse_config_file(self, path: str) -> Optional[Dict]:
        """解析 MCP 配置文件"""
        with open(path, 'r', encoding='utf-8') as f:
            if path.endswith('.json'):
                return json.load(f)
            else:
                return yaml.safe_load(f) or {}

    async def auto_register_discovered(self, search_paths: List[str] = None) -> Dict[str, McpServerState]:
        """
        自动发现并注册所有 MCP 服务器

        Returns:
            {server_name: McpServerState} 已注册的服务器
        """
        discovered = self.discover_servers(search_paths)
        registered = {}

        for item in discovered:
            name = item["name"]
            if name in self.servers:
                logger.debug(f"MCP server '{name}' already registered, skipping")
                continue

            config = self._dict_to_config(name, item["config_dict"])
            if config:
                try:
                    state = await self.add_server(name, config)
                    registered[name] = state
                    logger.info(f"Auto-registered MCP server: {name} ({item['source']})")
                except Exception as e:
                    logger.warning(f"Failed to auto-register '{name}': {e}")

        return registered

    def _dict_to_config(self, name: str, cfg: Dict) -> Optional[McpServerConfig]:
        """将字典转换为 McpServerConfig"""
        cfg_type = cfg.get("type", "stdio")
        try:
            if cfg_type == "stdio":
                return McpStdioServerConfig(
                    command=cfg.get("command", ""),
                    args=cfg.get("args", []),
                    env=cfg.get("env", {}),
                )
            elif cfg_type in ("sse", "http"):
                return McpSSEServerConfig(
                    url=cfg.get("url", ""),
                    headers=cfg.get("headers", {}),
                )
            else:
                logger.warning(f"Unknown MCP config type: {cfg_type}")
                return None
        except Exception as e:
            logger.error(f"Failed to create config for '{name}': {e}")
            return None

    # ═══════════ 工具调用链追踪 ═══════════

    @dataclass
    class _CallRecord:
        """调用记录"""
        server: str
        tool: str
        arguments: Dict[str, Any]
        start_time: float
        end_time: Optional[float] = None
        success: bool = True
        error: Optional[str] = None
        cached: bool = False

        @property
        def duration_ms(self) -> float:
            if self.end_time:
                return (self.end_time - self.start_time) * 1000
            return 0.0

        def to_dict(self) -> Dict[str, Any]:
            return {
                "server": self.server,
                "tool": self.tool,
                "arguments": self.arguments,
                "start_time": self.start_time,
                "duration_ms": round(self.duration_ms, 2),
                "success": self.success,
                "error": self.error,
                "cached": self.cached,
            }

    def _ensure_call_tracking(self):
        """延迟初始化调用追踪"""
        if not hasattr(self, '_call_history'):
            self._call_history: List = []
            self._call_history_lock = threading.Lock()
            self._call_stats: Dict[str, Dict[str, int]] = {}

    def record_call_start(self, server: str, tool: str, arguments: Dict) -> int:
        """记录调用开始，返回记录ID"""
        self._ensure_call_tracking()
        rec = self._CallRecord(
            server=server, tool=tool, arguments=arguments,
            start_time=time.time()
        )
        with self._call_history_lock:
            self._call_history.append(rec)
            return len(self._call_history) - 1

    def record_call_end(self, record_id: int, success: bool = True,
                        error: str = None, cached: bool = False):
        """记录调用结束"""
        self._ensure_call_tracking()
        with self._call_history_lock:
            if 0 <= record_id < len(self._call_history):
                rec = self._call_history[record_id]
                rec.end_time = time.time()
                rec.success = success
                rec.error = error
                rec.cached = cached

                # 更新统计
                key = f"{rec.server}::{rec.tool}"
                if key not in self._call_stats:
                    self._call_stats[key] = {"calls": 0, "errors": 0, "cached": 0,
                                              "total_ms": 0}
                self._call_stats[key]["calls"] += 1
                if not success:
                    self._call_stats[key]["errors"] += 1
                if cached:
                    self._call_stats[key]["cached"] += 1
                self._call_stats[key]["total_ms"] += rec.duration_ms

    def get_call_history(self, limit: int = 50, server: str = None,
                         tool: str = None) -> List[Dict[str, Any]]:
        """
        获取调用链历史

        Args:
            limit: 返回条数
            server: 按服务器过滤
            tool: 按工具过滤

        Returns:
            调用记录列表
        """
        self._ensure_call_tracking()
        with self._call_history_lock:
            records = list(self._call_history)

        if server:
            records = [r for r in records if r.server == server]
        if tool:
            records = [r for r in records if r.tool == tool]

        return [r.to_dict() for r in records[-limit:]]

    def get_call_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        获取调用链统计 (按 server::tool 分组)

        Returns:
            {server::tool: {calls, errors, cached, total_ms, avg_ms, error_rate}}
        """
        self._ensure_call_tracking()
        result = {}
        for key, s in self._call_stats.items():
            avg = s["total_ms"] / s["calls"] if s["calls"] > 0 else 0
            err_rate = s["errors"] / s["calls"] if s["calls"] > 0 else 0
            result[key] = {
                **s,
                "avg_ms": round(avg, 2),
                "error_rate": round(err_rate, 4),
            }
        return result
    
    def _config_to_dict(self, config: McpServerConfig) -> Dict[str, Any]:
        """
        将 McpServerConfig 转换为字典（用于安全策略检查）
        
        Args:
            config: MCP 服务器配置对象
        
        Returns:
            配置字典
        """
        if isinstance(config, McpStdioServerConfig):
            return {
                "type": "stdio",
                "command": config.command,
                "args": config.args,
                "env": config.env,
            }
        elif isinstance(config, McpSSEServerConfig):
            return {
                "type": "sse",
                "url": config.url,
                "headers": config.headers,
            }
        else:
            # 尝试获取通用属性
            result = {}
            if hasattr(config, "type"):
                result["type"] = config.type
            if hasattr(config, "command"):
                result["command"] = config.command
            if hasattr(config, "args"):
                result["args"] = config.args
            if hasattr(config, "url"):
                result["url"] = config.url
            if hasattr(config, "env"):
                result["env"] = config.env
            if hasattr(config, "headers"):
                result["headers"] = config.headers
            return result

    def get_debug_report(self) -> Dict[str, Any]:
        """
        获取 MCP 调试报告

        Returns:
            包含服务器状态、调用统计、缓存统计的完整报告
        """
        return {
            "servers": self.get_status(),
            "call_stats": self.get_call_stats(),
            "call_history_count": len(self._call_history) if hasattr(self, '_call_history') else 0,
            "cache": self.get_cache_stats(),
            "registered_tools": len(self._registered_tool_names),
            "timestamp": time.time(),
        }
    
    async def reconnect_server(self, name: str) -> bool:
        """
        重新连接 MCP 服务器（用于健康检查自动重连）
        
        Args:
            name: 服务器名称
        
        Returns:
            是否重连成功
        """
        if name not in self.servers:
            logger.error(f"Server '{name}' not found for reconnection")
            return False
        
        state = self.servers[name]
        config = state.config
        
        try:
            logger.info(f"Reconnecting MCP server '{name}'...")
            
            # 先断开连接
            if state.client:
                try:
                    await state.client.disconnect()
                except Exception as e:
                    logger.warning(f"Error disconnecting server '{name}': {e}")
            
            # 重新连接
            from mcp.client.base import MCPClient
            client = MCPClient(config)
            await client.connect()
            
            # 更新状态
            state.client = client
            state.connected = True
            state.error = None
            state.last_connect_time = time.time()
            
            # 刷新工具列表
            await self._discover_tools(name)
            
            logger.info(f"Server '{name}' reconnected successfully")
            return True
        
        except Exception as e:
            error_msg = f"Failed to reconnect server '{name}': {e}"
            logger.error(error_msg)
            state.connected = False
            state.error = error_msg
            return False
    
    def get_server_state(self, name: str) -> Optional[McpServerState]:
        """
        获取服务器状态（用于健康检查）
        
        Args:
            name: 服务器名称
        
        Returns:
            服务器状态对象，如果不存在则返回 None
        """
        return self.servers.get(name)
