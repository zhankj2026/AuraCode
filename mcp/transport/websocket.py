#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2026 zhankj
#
# This source code is licensed under the [ Apache-2.0] license.
# For the full license text, please refer to the LICENSE file in the root directory.
#
# Author: zhankj <creating2018@aliyun.com>
# Project Homepage: http://www.auracode.top
#

"""
WebSocket transport for MCP servers.

This module implements the WebSocket transport for communicating with
MCP servers over WebSocket connections.
"""

import asyncio
import json
from typing import Any

import websockets.client
from websockets.exceptions import ConnectionClosed

from mcp.transport.base import Transport, TransportError, TransportClosedError


class WebSocketTransport(Transport):
    """
    WebSocket transport for MCP servers.

    This transport uses WebSocket to communicate with MCP servers
    that support the WebSocket protocol.
    """

    def __init__(
        self,
        url: str,
        headers: dict[str, str] | None = None,
    ):
        """
        Initialize the WebSocket transport.

        Args:
            url: The WebSocket server URL (ws:// or wss://).
            headers: Optional HTTP headers for the connection handshake.
        """
        super().__init__()
        self.url = url
        self.headers = headers or {}
        self._websocket: websockets.client.WebSocketClientProtocol | None = None
        self._receive_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the WebSocket connection."""
        if self._closed:
            raise TransportClosedError("Cannot start closed transport")

        try:
            extra_headers = dict(self.headers) if self.headers else None
            self._websocket = await websockets.client.connect(
                self.url,
                extra_headers=extra_headers,
            )

            # Start receiving messages
            self._receive_task = asyncio.create_task(self._receive_messages())

        except (ConnectionRefusedError, ConnectionClosed) as e:
            raise TransportError(f"Connection refused: {self.url}", e)
        except Exception as e:
            raise TransportError(f"Failed to connect: {e}", e)

    async def close(self) -> None:
        """Close the WebSocket connection."""
        self._closed = True

        # Cancel receive task
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
            self._receive_task = None

        # Close WebSocket
        if self._websocket:
            try:
                await self._websocket.close()
            except Exception:
                pass
            self._websocket = None

        # Fail any pending requests
        for future in self._pending_requests.values():
            if not future.done():
                future.set_exception(TransportClosedError())
        self._pending_requests.clear()

    async def _send_message(self, message: dict[str, Any]) -> None:
        """Send a message through the WebSocket."""
        if not self._websocket:
            raise TransportClosedError("WebSocket not connected")

        try:
            data = json.dumps(message)
            await self._websocket.send(data)
        except ConnectionClosed as e:
            raise TransportClosedError(f"Connection closed: {e}")
        except Exception as e:
            raise TransportError(f"Failed to send message: {e}", e)

    async def _receive_messages(self) -> None:
        """Receive and handle messages from the WebSocket."""
        if not self._websocket:
            return

        try:
            async for message in self._websocket:
                if self._closed:
                    break

                try:
                    data = json.loads(message)
                    self._handle_message(data)
                except json.JSONDecodeError:
                    # Invalid JSON, skip
                    continue

        except asyncio.CancelledError:
            # Task was cancelled
            pass
        except ConnectionClosed:
            # Connection closed by server
            pass
        except Exception:
            # Other error
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
