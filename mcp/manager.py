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
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from mcp.client.base import MCPClient, MCPSessionExpiredError
from mcp.config.types import McpServerConfig, McpStdioServerConfig, McpSSEServerConfig
from mcp.tools.adapter import MCPToolAdapter
from mcp.tools.validation import validate_and_truncate_output

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
        """添加并连接 MCP 服务器（热加载）"""
        if name in self.servers:
            logger.warning(f"MCP server '{name}' already exists, reconnecting...")
            await self.remove_server(name)

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
        try:
            result = await adapter.execute(arguments)
            return result
        except MCPSessionExpiredError:
            state.connected = False
            state.error_count += 1
            raise
        except Exception as e:
            state.error_count += 1
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
