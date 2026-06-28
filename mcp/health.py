"""
MCP 服务器健康检查机制

参考标准实现服务器状态分类和健康检查：
- ConnectedMCPServer: ✅ 已连接
- FailedMCPServer: ❌ 连接失败
- NeedsAuthMCPServer: 🔐 需要认证
- PendingMCPServer: ⏳ 重连中
- DisabledMCPServer: ⛔ 已禁用

功能：
1. 定期健康检查（心跳检测）
2. 自动重连机制
3. 状态分类和转换
4. 健康报告生成
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ServerHealthStatus(Enum):
    """服务器健康状态枚举"""
    CONNECTED = "connected"  # ✅ 已连接
    FAILED = "failed"  # ❌ 连接失败
    NEEDS_AUTH = "needs_auth"  # 🔐 需要认证
    PENDING = "pending"  # ⏳ 重连中
    DISABLED = "disabled"  # ⛔ 已禁用


@dataclass
class HealthCheckResult:
    """健康检查结果"""
    server_name: str
    status: ServerHealthStatus
    timestamp: float = field(default_factory=time.time)
    latency_ms: Optional[float] = None
    error: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "server_name": self.server_name,
            "status": self.status.value,
            "timestamp": self.timestamp,
        }
        
        if self.latency_ms is not None:
            result["latency_ms"] = self.latency_ms
        if self.error:
            result["error"] = self.error
        if self.details:
            result["details"] = self.details
        
        return result


@dataclass
class ServerHealthState:
    """服务器健康状态"""
    name: str
    status: ServerHealthStatus = ServerHealthStatus.PENDING
    last_check_time: Optional[float] = None
    last_healthy_time: Optional[float] = None
    consecutive_failures: int = 0
    max_consecutive_failures: int = 3
    check_interval_seconds: float = 30.0
    reconnect_attempts: int = 0
    max_reconnect_attempts: int = 5
    last_error: Optional[str] = None
    history: List[HealthCheckResult] = field(default_factory=list)
    
    def update_status(self, new_status: ServerHealthStatus, error: Optional[str] = None) -> None:
        """更新状态"""
        old_status = self.status
        self.status = new_status
        self.last_check_time = time.time()
        
        if new_status == ServerHealthStatus.CONNECTED:
            self.last_healthy_time = self.last_check_time
            self.consecutive_failures = 0
            self.reconnect_attempts = 0
        elif new_status == ServerHealthStatus.FAILED:
            self.consecutive_failures += 1
            self.last_error = error
        
        # 记录历史
        result = HealthCheckResult(
            server_name=self.name,
            status=new_status,
            error=error,
        )
        self.history.append(result)
        
        # 保留最近 100 条记录
        if len(self.history) > 100:
            self.history = self.history[-100:]
        
        # 状态变更日志
        if old_status != new_status:
            logger.info(
                f"Server '{self.name}' status changed: "
                f"{old_status.value} → {new_status.value}"
                + (f" (error: {error})" if error else "")
            )
    
    def should_reconnect(self) -> bool:
        """是否应该重连"""
        if self.status == ServerHealthStatus.DISABLED:
            return False
        
        if self.status == ServerHealthStatus.NEEDS_AUTH:
            return False
        
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            return False
        
        if self.consecutive_failures >= self.max_consecutive_failures:
            return False
        
        return True
    
    def get_uptime_percentage(self) -> float:
        """获取可用率（最近 100 次检查）"""
        if not self.history:
            return 0.0
        
        connected_count = sum(
            1 for h in self.history[-100:]
            if h.status == ServerHealthStatus.CONNECTED
        )
        
        return (connected_count / min(len(self.history), 100)) * 100.0
    
    def get_avg_latency(self) -> Optional[float]:
        """获取平均延迟（最近 100 次检查）"""
        latencies = [
            h.latency_ms
            for h in self.history[-100:]
            if h.latency_ms is not None
        ]
        
        if not latencies:
            return None
        
        return sum(latencies) / len(latencies)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "status": self.status.value,
            "last_check_time": self.last_check_time,
            "last_healthy_time": self.last_healthy_time,
            "consecutive_failures": self.consecutive_failures,
            "reconnect_attempts": self.reconnect_attempts,
            "last_error": self.last_error,
            "uptime_percentage": self.get_uptime_percentage(),
            "avg_latency_ms": self.get_avg_latency(),
        }


class HealthChecker:
    """
    健康检查器
    
    功能：
    1. 定期检查所有 MCP 服务器状态
    2. 自动重连失败的服务器
    3. 状态监控和报告
    """
    
    def __init__(
        self,
        check_interval: float = 30.0,
        max_reconnect_attempts: int = 5,
        max_consecutive_failures: int = 3,
    ):
        self.check_interval = check_interval
        self.max_reconnect_attempts = max_reconnect_attempts
        self.max_consecutive_failures = max_consecutive_failures
        
        self._states: Dict[str, ServerHealthState] = {}
        self._running = False
        self._check_task: Optional[asyncio.Task] = None
        self._mcp_manager: Optional[Any] = None
    
    def register_server(self, server_name: str) -> ServerHealthState:
        """
        注册服务器
        
        Args:
            server_name: 服务器名称
        
        Returns:
            服务器健康状态
        """
        if server_name not in self._states:
            self._states[server_name] = ServerHealthState(
                name=server_name,
                check_interval_seconds=self.check_interval,
                max_reconnect_attempts=self.max_reconnect_attempts,
                max_consecutive_failures=self.max_consecutive_failures,
            )
            logger.info(f"Registered server '{server_name}' for health checking")
        
        return self._states[server_name]
    
    def unregister_server(self, server_name: str) -> None:
        """注销服务器"""
        if server_name in self._states:
            del self._states[server_name]
            logger.info(f"Unregistered server '{server_name}' from health checking")
    
    def update_status(
        self,
        server_name: str,
        status: ServerHealthStatus,
        error: Optional[str] = None,
    ) -> None:
        """
        更新服务器状态
        
        Args:
            server_name: 服务器名称
            status: 新状态
            error: 错误信息（如果有）
        """
        state = self.register_server(server_name)
        state.update_status(status, error)
    
    async def check_server(self, server_name: str) -> HealthCheckResult:
        """
        检查单个服务器健康状态
        
        Args:
            server_name: 服务器名称
        
        Returns:
            健康检查结果
        """
        start_time = time.time()
        
        try:
            if self._mcp_manager is None:
                return HealthCheckResult(
                    server_name=server_name,
                    status=ServerHealthStatus.FAILED,
                    error="MCP manager not initialized",
                )
            
            # 获取服务器状态
            state = self._mcp_manager.get_server_state(server_name)
            
            if state is None:
                result = HealthCheckResult(
                    server_name=server_name,
                    status=ServerHealthStatus.FAILED,
                    error="Server not found",
                )
                self.update_status(server_name, ServerHealthStatus.FAILED, "Server not found")
                return result
            
            # 检查连接状态
            if hasattr(state, 'connected') and state.connected:
                latency_ms = (time.time() - start_time) * 1000
                
                result = HealthCheckResult(
                    server_name=server_name,
                    status=ServerHealthStatus.CONNECTED,
                    latency_ms=latency_ms,
                )
                self.update_status(server_name, ServerHealthStatus.CONNECTED)
                return result
            else:
                error_msg = getattr(state, 'error', 'Not connected')
                
                # 检查是否是认证错误
                if 'auth' in str(error_msg).lower() or 'oauth' in str(error_msg).lower():
                    result = HealthCheckResult(
                        server_name=server_name,
                        status=ServerHealthStatus.NEEDS_AUTH,
                        error=error_msg,
                    )
                    self.update_status(server_name, ServerHealthStatus.NEEDS_AUTH, error_msg)
                else:
                    result = HealthCheckResult(
                        server_name=server_name,
                        status=ServerHealthStatus.FAILED,
                        error=error_msg,
                    )
                    self.update_status(server_name, ServerHealthStatus.FAILED, error_msg)
                
                return result
        
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            
            result = HealthCheckResult(
                server_name=server_name,
                status=ServerHealthStatus.FAILED,
                latency_ms=latency_ms,
                error=str(e),
            )
            self.update_status(server_name, ServerHealthStatus.FAILED, str(e))
            
            return result
    
    async def check_all_servers(self) -> Dict[str, HealthCheckResult]:
        """
        检查所有服务器健康状态
        
        Returns:
            所有服务器的健康检查结果
        """
        results = {}
        
        for server_name in list(self._states.keys()):
            try:
                result = await self.check_server(server_name)
                results[server_name] = result
            except Exception as e:
                logger.error(f"Error checking server '{server_name}': {e}")
                results[server_name] = HealthCheckResult(
                    server_name=server_name,
                    status=ServerHealthStatus.FAILED,
                    error=str(e),
                )
        
        return results
    
    async def _reconnect_server(self, server_name: str) -> bool:
        """
        尝试重连服务器
        
        Args:
            server_name: 服务器名称
        
        Returns:
            是否重连成功
        """
        state = self._states.get(server_name)
        if state is None:
            return False
        
        if not state.should_reconnect():
            logger.warning(f"Server '{server_name}' should not reconnect")
            return False
        
        state.reconnect_attempts += 1
        
        try:
            logger.info(
                f"Reconnecting server '{server_name}' "
                f"(attempt {state.reconnect_attempts}/{state.max_reconnect_attempts})"
            )
            
            if self._mcp_manager is None:
                return False
            
            # 尝试重新连接
            await self._mcp_manager.reconnect_server(server_name)
            
            # 检查是否成功
            result = await self.check_server(server_name)
            
            if result.status == ServerHealthStatus.CONNECTED:
                logger.info(f"Server '{server_name}' reconnected successfully")
                return True
            else:
                logger.warning(f"Server '{server_name}' reconnection failed: {result.error}")
                return False
        
        except Exception as e:
            logger.error(f"Error reconnecting server '{server_name}': {e}")
            state.update_status(ServerHealthStatus.FAILED, str(e))
            return False
    
    async def _check_loop(self) -> None:
        """健康检查循环"""
        logger.info(f"Health checker started (interval: {self.check_interval}s)")
        
        while self._running:
            try:
                # 检查所有服务器
                results = await self.check_all_servers()
                
                # 尝试重连失败的服务器
                for server_name, result in results.items():
                    if result.status == ServerHealthStatus.FAILED:
                        state = self._states.get(server_name)
                        if state and state.should_reconnect():
                            await self._reconnect_server(server_name)
                
                # 等待下一次检查
                await asyncio.sleep(self.check_interval)
            
            except asyncio.CancelledError:
                logger.info("Health checker cancelled")
                break
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
                await asyncio.sleep(5)  # 错误后等待 5 秒
        
        logger.info("Health checker stopped")
    
    def start(self, mcp_manager: Any) -> None:
        """
        启动健康检查
        
        Args:
            mcp_manager: McpManager 实例
        """
        if self._running:
            logger.warning("Health checker is already running")
            return
        
        self._mcp_manager = mcp_manager
        self._running = True
        
        # 创建后台任务
        self._check_task = asyncio.create_task(self._check_loop())
    
    async def stop(self) -> None:
        """停止健康检查"""
        if not self._running:
            return
        
        self._running = False
        
        if self._check_task:
            self._check_task.cancel()
            try:
                await self._check_task
            except asyncio.CancelledError:
                pass
            
            self._check_task = None
        
        logger.info("Health checker stopped")
    
    def get_server_state(self, server_name: str) -> Optional[ServerHealthState]:
        """获取服务器健康状态"""
        return self._states.get(server_name)
    
    def get_all_states(self) -> Dict[str, ServerHealthState]:
        """获取所有服务器健康状态"""
        return self._states.copy()
    
    def generate_report(self) -> Dict[str, Any]:
        """
        生成健康报告
        
        Returns:
            健康报告字典
        """
        report = {
            "total_servers": len(self._states),
            "connected": 0,
            "failed": 0,
            "needs_auth": 0,
            "pending": 0,
            "disabled": 0,
            "servers": {},
        }
        
        for name, state in self._states.items():
            report["servers"][name] = state.to_dict()
            
            if state.status == ServerHealthStatus.CONNECTED:
                report["connected"] += 1
            elif state.status == ServerHealthStatus.FAILED:
                report["failed"] += 1
            elif state.status == ServerHealthStatus.NEEDS_AUTH:
                report["needs_auth"] += 1
            elif state.status == ServerHealthStatus.PENDING:
                report["pending"] += 1
            elif state.status == ServerHealthStatus.DISABLED:
                report["disabled"] += 1
        
        return report
    
    def get_summary_text(self) -> str:
        """获取健康状态摘要文本"""
        report = self.generate_report()
        
        lines = [
            f"MCP Server Health Report",
            f"{'=' * 50}",
            f"Total servers: {report['total_servers']}",
            f"✅ Connected: {report['connected']}",
            f"❌ Failed: {report['failed']}",
            f"🔐 Needs Auth: {report['needs_auth']}",
            f"⏳ Pending: {report['pending']}",
            f"⛔ Disabled: {report['disabled']}",
            f"",
        ]
        
        for name, state_data in report["servers"].items():
            status = state_data["status"]
            emoji = {
                "connected": "✅",
                "failed": "❌",
                "needs_auth": "🔐",
                "pending": "⏳",
                "disabled": "⛔",
            }.get(status, "❓")
            
            uptime = state_data.get("uptime_percentage", 0)
            avg_latency = state_data.get("avg_latency_ms")
            
            line = f"  {emoji} {name}: {status}"
            if uptime > 0:
                line += f" (uptime: {uptime:.1f}%)"
            if avg_latency is not None:
                line += f" (avg latency: {avg_latency:.1f}ms)"
            
            lines.append(line)
            
            if state_data.get("last_error"):
                lines.append(f"      Error: {state_data['last_error']}")
        
        return "\n".join(lines)


# 全局健康检查器实例
_health_checker: Optional[HealthChecker] = None


def get_health_checker() -> HealthChecker:
    """获取全局健康检查器"""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
    return _health_checker


def initialize_health_checker(
    check_interval: float = 30.0,
    max_reconnect_attempts: int = 5,
    max_consecutive_failures: int = 3,
) -> HealthChecker:
    """
    初始化健康检查器
    
    Args:
        check_interval: 检查间隔（秒）
        max_reconnect_attempts: 最大重连次数
        max_consecutive_failures: 最大连续失败次数
    
    Returns:
        健康检查器实例
    """
    global _health_checker
    _health_checker = HealthChecker(
        check_interval=check_interval,
        max_reconnect_attempts=max_reconnect_attempts,
        max_consecutive_failures=max_consecutive_failures,
    )
    return _health_checker
