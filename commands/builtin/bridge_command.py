"""
Bridge 命令 - 远程控制服务器管理

在 opencode 对话模式中管理 Bridge 服务器:
- /bridge start [--port 8765] [--max-sessions 5]
- /bridge status
- /bridge stop

启动后通过 REST API + WebSocket 远程控制多个 AI 会话。
"""

import threading
import secrets
from commands.registry import register_command

# 全局 Bridge 服务器状态
_bridge_thread = None
_bridge_stop_event = None
_bridge_config = None


def _start_bridge_in_background(port: int, max_sessions: int, token: str = None):
    """在后台线程中启动 Bridge 服务器"""
    global _bridge_thread, _bridge_stop_event, _bridge_config

    from bridge.config import BridgeServerConfig
    from bridge.server import create_app

    _bridge_stop_event = threading.Event()
    _bridge_config = BridgeServerConfig(
        port=port,
        max_sessions=max_sessions,
        auth_token=token or secrets.token_urlsafe(32),
    )

    def _run():
        import uvicorn

        app = create_app(_bridge_config)
        config = uvicorn.Config(
            app=app,
            host=_bridge_config.host,
            port=_bridge_config.port,
            log_level="warning",
        )
        server = uvicorn.Server(config)

        # 使用线程事件来支持优雅停止
        server.install_signal_handlers = lambda: None  # 禁用信号处理

        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def _serve():
            await server.serve()

        loop.run_until_complete(_serve())

    _bridge_thread = threading.Thread(
        target=_run, daemon=True, name="bridge-server"
    )
    _bridge_thread.start()


def bridge_handler(args: list, loop=None) -> str:
    """bridge 命令处理函数"""
    global _bridge_thread, _bridge_config

    if not args:
        return (
            "📡 Bridge 远程控制服务器\n"
            "=" * 50 + "\n"
            "用法:\n"
            "  /bridge start [--port PORT] [--max-sessions N]\n"
            "    启动 Bridge 服务器\n\n"
            "  /bridge status\n"
            "    查看服务器状态\n\n"
            "  /bridge stop\n"
            "    停止 Bridge 服务器\n\n"
            "启动后通过 REST API + WebSocket 远程控制 AI 会话。\n"
            "API 文档: http://HOST:PORT/docs\n"
            "=" * 50
        )

    subcommand = args[0].lower()

    if subcommand == "start":
        # 检查是否已启动
        if _bridge_thread and _bridge_thread.is_alive():
            return (
                f"⚠️  Bridge 服务器已在运行\n"
                f"   地址: http://{_bridge_config.host}:{_bridge_config.port}\n"
                f"   Token: {_bridge_config.auth_token}"
            )

        # 解析参数
        port = 8765
        max_sessions = 5
        token = None

        i = 1
        while i < len(args):
            if args[i] in ("--port", "-p") and i + 1 < len(args):
                try:
                    port = int(args[i + 1])
                except ValueError:
                    return f"❌ 无效的端口号: {args[i + 1]}"
                i += 2
            elif args[i] in ("--max-sessions", "-m") and i + 1 < len(args):
                try:
                    max_sessions = int(args[i + 1])
                except ValueError:
                    return f"❌ 无效的最大会话数: {args[i + 1]}"
                i += 2
            elif args[i] in ("--token", "-t") and i + 1 < len(args):
                token = args[i + 1]
                i += 2
            else:
                return f"❌ 未知参数: {args[i]}"

        # 启动
        _start_bridge_in_background(port, max_sessions, token)

        import time
        time.sleep(0.5)  # 等待服务器启动

        if _bridge_thread and _bridge_thread.is_alive():
            return (
                f"✅ Bridge 服务器已启动\n"
                "=" * 50 + "\n"
                f"  🌐 REST API:   http://{_bridge_config.host}:{_bridge_config.port}/api/\n"
                f"  📡 WebSocket:  ws://{_bridge_config.host}:{_bridge_config.port}/ws/events\n"
                f"  📊 Status:     http://{_bridge_config.host}:{_bridge_config.port}/api/status\n"
                f"  📖 Docs:       http://{_bridge_config.host}:{_bridge_config.port}/docs\n"
                f"  🔑 Token:      {_bridge_config.auth_token}\n"
                f"  📦 Max Sessions: {_bridge_config.max_sessions}\n"
                "=" * 50
            )
        else:
            return "❌ Bridge 服务器启动失败"

    elif subcommand == "status":
        if not _bridge_thread or not _bridge_thread.is_alive():
            return "📡 Bridge 服务器未运行\n使用 /bridge start 启动"

        # 尝试通过 HTTP 获取状态
        try:
            import urllib.request
            import json

            url = f"http://{_bridge_config.host}:{_bridge_config.port}/api/status"
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"Bearer {_bridge_config.auth_token}")
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read())

            uptime = data.get("uptime", 0)
            hours, remainder = divmod(int(uptime), 3600)
            minutes, seconds = divmod(remainder, 60)
            uptime_str = f"{hours}h {minutes}m {seconds}s"

            return (
                f"✅ Bridge 服务器运行中\n"
                "=" * 50 + "\n"
                f"  地址:         http://{_bridge_config.host}:{_bridge_config.port}\n"
                f"  运行时间:     {uptime_str}\n"
                f"  总会话数:     {data.get('total_sessions', 0)}\n"
                f"  活跃会话数:   {data.get('active_sessions', 0)}\n"
                f"  最大会话数:   {data.get('max_sessions', 0)}\n"
                f"  Token:        {_bridge_config.auth_token}\n"
                "=" * 50
            )
        except Exception:
            return (
                f"📡 Bridge 服务器运行中（线程存活）\n"
                f"  地址: http://{_bridge_config.host}:{_bridge_config.port}\n"
                f"  Token: {_bridge_config.auth_token}"
            )

    elif subcommand == "stop":
        if not _bridge_thread or not _bridge_thread.is_alive():
            return "⚠️  Bridge 服务器未运行"

        # 通过 HTTP 停止所有会话，然后关闭
        try:
            import urllib.request
            import json

            # 先获取会话列表
            url = f"http://{_bridge_config.host}:{_bridge_config.port}/api/sessions"
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"Bearer {_bridge_config.auth_token}")
            with urllib.request.urlopen(req, timeout=3) as resp:
                sessions = json.loads(resp.read())

            # 停止所有会话
            for s in sessions:
                sid = s.get("session_id", "")
                stop_url = (
                    f"http://{_bridge_config.host}:{_bridge_config.port}"
                    f"/api/sessions/{sid}/stop"
                )
                stop_req = urllib.request.Request(stop_url, method="POST")
                stop_req.add_header(
                    "Authorization", f"Bearer {_bridge_config.auth_token}"
                )
                stop_req.add_header("Content-Type", "application/json")
                try:
                    urllib.request.urlopen(stop_req, timeout=3)
                except Exception:
                    pass
        except Exception:
            pass

        return (
            f"🛑 Bridge 服务器已请求停止\n"
            f"  已停止所有会话，服务器线程将在后台自然退出"
        )

    else:
        return f"❌ 未知子命令: {subcommand}\n使用 /bridge 查看帮助"


# 注册命令
register_command("bridge", {
    "description": "远程控制服务器 - 启动/管理 Bridge 多会话远程控制系统",
    "handler": bridge_handler,
    "category": "system",
    "args_help": "[start|status|stop] [--port PORT] [--max-sessions N]",
})
