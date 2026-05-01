"""
stdio transport for MCP servers.

This module implements the stdio transport for communicating with
local MCP server processes.
"""

import asyncio
import json
import os
from typing import Any

from mcp.transport.base import Transport, TransportError, TransportClosedError


class StdioTransport(Transport):
    """
    stdio transport for MCP servers.

    This transport spawns a subprocess and communicates with it
    via stdin/stdout using JSON-RPC messages.
    """

    def __init__(self, command: str, args: list[str] = None, env: dict[str, str] = None):
        """
        Initialize the stdio transport.

        Args:
            command: The command to run.
            args: Optional list of arguments.
            env: Optional environment variables (merged with os.environ).
        """
        super().__init__()
        self.command = command
        self.args = args or []
        self.env = {**os.environ, **(env or {})}
        self._process: asyncio.subprocess.Process | None = None
        self._read_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the subprocess and begin reading messages."""
        if self._closed:
            raise TransportClosedError("Cannot start closed transport")

        try:
            # Create the subprocess
            self._process = await asyncio.create_subprocess_exec(
                self.command,
                *self.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self.env,
            )

            if self._process.stdout is None:
                raise TransportError("Failed to create stdout pipe")

            # Start reading messages
            self._read_task = asyncio.create_task(self._read_messages())

        except FileNotFoundError as e:
            raise TransportError(f"Command not found: {self.command}", e)
        except Exception as e:
            raise TransportError(f"Failed to start subprocess: {e}", e)

    async def close(self) -> None:
        """Close the transport and cleanup the subprocess."""
        self._closed = True

        # Cancel read task
        if self._read_task:
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass
            self._read_task = None

        # Terminate the process
        if self._process:
            try:
                self._process.terminate()
                # Give it a moment to terminate gracefully
                try:
                    await asyncio.wait_for(self._process.wait(), timeout=0.5)
                except asyncio.TimeoutError:
                    # Force kill if it doesn't terminate
                    self._process.kill()
                    await self._process.wait()
            except Exception:
                pass  # Process may already be dead
            self._process = None

        # Fail any pending requests
        for future in self._pending_requests.values():
            if not future.done():
                future.set_exception(TransportClosedError())
        self._pending_requests.clear()

    async def _send_message(self, message: dict[str, Any]) -> None:
        """Send a message to the subprocess via stdin."""
        if not self._process or self._process.stdin is None:
            raise TransportClosedError("Process not started")

        try:
            # JSON-RPC messages are sent as single-line JSON
            data = json.dumps(message) + "\n"
            self._process.stdin.write(data.encode("utf-8"))
            await self._process.stdin.drain()
        except (BrokenPipeError, ConnectionResetError) as e:
            raise TransportClosedError(f"Connection closed: {e}")
        except Exception as e:
            raise TransportError(f"Failed to send message: {e}", e)

    async def _read_messages(self) -> None:
        """Read messages from the subprocess stdout."""
        if not self._process or self._process.stdout is None:
            return

        try:
            while not self._closed:
                try:
                    line = await asyncio.wait_for(
                        self._process.stdout.readline(), timeout=1.0
                    )
                    if not line:
                        # EOF
                        break

                    line_str = line.decode("utf-8").strip()
                    if not line_str:
                        continue

                    try:
                        message = json.loads(line_str)
                        self._handle_message(message)
                    except json.JSONDecodeError as e:
                        # Invalid JSON, log but continue
                        continue

                except asyncio.TimeoutError:
                    # No data, continue
                    continue

        except asyncio.CancelledError:
            # Task was cancelled
            pass
        except Exception:
            # Connection error or other issue
            pass
        finally:
            # Mark transport as closed
            if not self._closed:
                self._closed = True
            # Fail any pending requests
            for future in self._pending_requests.values():
                if not future.done():
                    future.set_exception(TransportClosedError())
            self._pending_requests.clear()
