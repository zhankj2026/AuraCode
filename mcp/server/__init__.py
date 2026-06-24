"""
MCP Server - 将 OpenCode 作为 MCP Server 运行

对标 Claude Code 的 src/entrypoints/mcp.ts，实现：
1. StdioServerTransport Server
2. 工具暴露机制（将 OpenCode 工具转为 MCP 工具）
3. 工具调用代理（接收外部请求并调用内置工具）

用法:
    python -m mcp.server  # 作为 MCP Server 启动
    # 或编程方式:
    from mcp.server import start_mcp_server
    await start_mcp_server(cwd=".", debug=False, verbose=False)
"""
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class McpServer:
    """
    MCP Server 实现
    
    将 OpenCode 的所有工具通过 MCP 协议暴露给外部客户端。
    外部 AI 代理或其他系统可以通过 MCP 调用 OpenCode 的工具。
    """
    
    def __init__(
        self,
        name: str = "opencode",
        version: str = "1.0.0",
        cwd: Optional[str] = None,
        debug: bool = False,
        verbose: bool = False,
    ):
        """
        初始化 MCP Server
        
        Args:
            name: Server 名称
            version: Server 版本
            cwd: 工作目录
            debug: 调试模式
            verbose: 详细日志
        """
        self.name = name
        self.version = version
        self.cwd = cwd or str(Path.cwd())
        self.debug = debug
        self.verbose = verbose
        
        # 工具注册表
        self._tools: Dict[str, Dict[str, Any]] = {}
        
        # JSON-RPC 消息 ID 计数器
        self._message_id = 0
        
        # 运行时状态
        self._running = False
        self._stdin_reader: Optional[asyncio.Task] = None
    
    async def start(self) -> None:
        """启动 MCP Server（通过 stdio）"""
        logger.info(f"Starting MCP Server: {self.name} v{self.version}")
        logger.info(f"Working directory: {self.cwd}")
        
        # 加载工具
        self._load_tools()
        logger.info(f"Loaded {len(self._tools)} tools")
        
        # 发送初始化完成通知
        await self._send_initialized_notification()
        
        # 开始监听 stdin
        self._running = True
        self._stdin_reader = asyncio.create_task(self._read_loop())
        
        logger.info("MCP Server ready, waiting for requests...")
        
        try:
            await self._stdin_reader
        except asyncio.CancelledError:
            logger.info("MCP Server shutting down")
        finally:
            self._running = False
    
    async def stop(self) -> None:
        """停止 MCP Server"""
        self._running = False
        if self._stdin_reader:
            self._stdin_reader.cancel()
            try:
                await self._stdin_reader
            except asyncio.CancelledError:
                pass
    
    def _load_tools(self) -> None:
        """加载 OpenCode 工具并转换为 MCP 格式"""
        try:
            # 导入工具注册表
            from tools.registry import TOOL_REGISTRY
            
            for tool_name, tool_def in TOOL_REGISTRY.items():
                # 转换为 MCP 工具格式
                mcp_tool = self._convert_to_mcp_tool(tool_name, tool_def)
                self._tools[tool_name] = mcp_tool
                
                if self.verbose:
                    logger.debug(f"  Loaded tool: {tool_name}")
        
        except ImportError as e:
            logger.error(f"Failed to load tools: {e}")
            raise
    
    def _convert_to_mcp_tool(self, name: str, tool_def: Dict) -> Dict:
        """
        将 OpenCode 工具定义转换为 MCP 工具格式
        
        MCP Tool Schema:
        {
            "name": "tool_name",
            "description": "Tool description",
            "inputSchema": {
                "type": "object",
                "properties": {...},
                "required": [...]
            }
        }
        """
        return {
            "name": name,
            "description": tool_def.get("description", ""),
            "inputSchema": tool_def.get("parameters", {
                "type": "object",
                "properties": {},
                "required": []
            }),
        }
    
    async def _read_loop(self) -> None:
        """读取 stdin 的 JSON-RPC 消息循环"""
        stdin = asyncio.get_event_loop()._loop.create_task(
            self._read_stdin()
        )
        
        while self._running:
            try:
                line = await asyncio.wait_for(
                    self._read_stdin_line(),
                    timeout=1.0
                )
                
                if not line:
                    continue
                
                # 解析 JSON-RPC 消息
                message = json.loads(line.strip())
                
                # 处理消息
                await self._handle_message(message)
            
            except asyncio.TimeoutError:
                continue
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON: {e}")
            except Exception as e:
                logger.error(f"Error reading message: {e}")
                if self.debug:
                    import traceback
                    traceback.print_exc()
    
    async def _read_stdin_line(self) -> Optional[str]:
        """从 stdin 读取一行"""
        loop = asyncio.get_event_loop()
        line = await loop.run_in_executor(None, sys.stdin.readline)
        return line if line else None
    
    async def _handle_message(self, message: Dict) -> None:
        """
        处理 JSON-RPC 消息
        
        支持的消息类型:
        - initialize: 初始化请求
        - tools/list: 列出工具
        - tools/call: 调用工具
        - notifications/initialized: 初始化通知（忽略）
        """
        jsonrpc = message.get("jsonrpc", "2.0")
        method = message.get("method")
        msg_id = message.get("id")
        params = message.get("params", {})
        
        if self.verbose:
            logger.debug(f"Received: method={method}, id={msg_id}")
        
        # 路由到处理方法
        if method == "initialize":
            await self._handle_initialize(msg_id, params)
        
        elif method == "tools/list":
            await self._handle_tools_list(msg_id)
        
        elif method == "tools/call":
            await self._handle_tools_call(msg_id, params)
        
        elif method == "initialized":
            # 客户端初始化完成通知，无需响应
            if self.verbose:
                logger.debug("Client initialized")
        
        elif msg_id is not None:
            # 未知方法，返回错误
            await self._send_error_response(
                msg_id,
                -32601,
                f"Method not found: {method}"
            )
    
    async def _handle_initialize(self, msg_id: int, params: Dict) -> None:
        """处理 initialize 请求"""
        # MCP 协议要求返回服务器能力
        response = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": self.name,
                    "version": self.version
                }
            }
        }
        
        await self._send_response(response)
        
        if self.verbose:
            logger.info(f"Initialized with params: {params}")
    
    async def _handle_tools_list(self, msg_id: int) -> None:
        """处理 tools/list 请求"""
        tools_list = list(self._tools.values())
        
        response = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "tools": tools_list
            }
        }
        
        await self._send_response(response)
        
        if self.verbose:
            logger.debug(f"Listed {len(tools_list)} tools")
    
    async def _handle_tools_call(self, msg_id: int, params: Dict) -> None:
        """
        处理 tools/call 请求
        
        调用 OpenCode 内置工具并返回结果
        """
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        if self.verbose:
            logger.info(f"Calling tool: {tool_name}")
            logger.debug(f"Arguments: {arguments}")
        
        # 检查工具是否存在
        if tool_name not in self._tools:
            await self._send_error_response(
                msg_id,
                -32602,
                f"Tool not found: {tool_name}"
            )
            return
        
        # 调用工具
        try:
            result = await self._call_tool(tool_name, arguments)
            
            # 返回成功结果
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": str(result) if not isinstance(result, str) else result
                        }
                    ]
                }
            }
            
            await self._send_response(response)
            
            if self.verbose:
                logger.debug(f"Tool {tool_name} returned successfully")
        
        except Exception as e:
            logger.error(f"Tool {tool_name} failed: {e}")
            if self.debug:
                import traceback
                traceback.print_exc()
            
            # 返回错误结果
            error_text = str(e)
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "isError": True,
                    "content": [
                        {
                            "type": "text",
                            "text": error_text
                        }
                    ]
                }
            }
            
            await self._send_response(response)
    
    async def _call_tool(self, tool_name: str, arguments: Dict) -> Any:
        """
        调用 OpenCode 工具
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
        
        Returns:
            工具执行结果
        """
        try:
            # 导入工具处理器
            from tools.registry import TOOL_REGISTRY
            
            tool_def = TOOL_REGISTRY.get(tool_name)
            if not tool_def:
                raise ValueError(f"Tool {tool_name} not found in registry")
            
            handler = tool_def.get("handler")
            if not handler:
                raise ValueError(f"Tool {tool_name} has no handler")
            
            # 调用工具处理器
            # 注意：这里简化了权限检查，实际应该集成 PermissionManager
            result = handler(**arguments)
            
            # 如果是协程，等待完成
            if asyncio.iscoroutine(result):
                result = await result
            
            return result
        
        except Exception as e:
            logger.error(f"Failed to call tool {tool_name}: {e}")
            raise
    
    async def _send_initialized_notification(self) -> None:
        """发送 initialized 通知"""
        notification = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        await self._send_response(notification)
    
    async def _send_response(self, response: Dict) -> None:
        """发送 JSON-RPC 响应到 stdout"""
        json_str = json.dumps(response, ensure_ascii=False)
        sys.stdout.write(json_str + "\n")
        sys.stdout.flush()
        
        if self.verbose:
            logger.debug(f"Sent: {json_str[:100]}...")
    
    async def _send_error_response(
        self,
        msg_id: int,
        code: int,
        message: str
    ) -> None:
        """发送错误响应"""
        response = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {
                "code": code,
                "message": message
            }
        }
        await self._send_response(response)


async def start_mcp_server(
    cwd: str = ".",
    debug: bool = False,
    verbose: bool = False,
) -> None:
    """
    启动 MCP Server（便捷函数）
    
    Args:
        cwd: 工作目录
        debug: 调试模式
        verbose: 详细日志
    """
    server = McpServer(
        name="opencode",
        version="1.0.0",
        cwd=cwd,
        debug=debug,
        verbose=verbose,
    )
    
    try:
        await server.start()
    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt")
    finally:
        await server.stop()


def main():
    """CLI 入口点"""
    import argparse
    
    parser = argparse.ArgumentParser(description="OpenCode MCP Server")
    parser.add_argument("--cwd", default=".", help="Working directory")
    parser.add_argument("--debug", action="store_true", help="Debug mode")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")
    
    args = parser.parse_args()
    
    # 配置日志
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    
    # 启动服务器
    asyncio.run(start_mcp_server(
        cwd=args.cwd,
        debug=args.debug,
        verbose=args.verbose,
    ))


if __name__ == "__main__":
    main()
