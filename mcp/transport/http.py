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
HTTP and SSE transport for MCP servers.

This module implements HTTP-based transports for communicating with
remote MCP servers.
"""

import asyncio
import json
from typing import Any

import httpx

from mcp.transport.base import Transport, TransportError, TransportClosedError, JSONRPCError


class HTTPTransport(Transport):
    """
    HTTP transport for MCP servers.

    This transport uses HTTP POST requests to communicate with
    MCP servers that support the HTTP protocol.
    """

    def __init__(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
    ):
        """
        Initialize the HTTP transport.

        Args:
            url: The server URL.
            headers: Optional HTTP headers.
            timeout: Request timeout in seconds.
        """
        super().__init__()
        self.url = url
        self.headers = headers or {}
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def start(self) -> None:
        """Start the HTTP client."""
        if self._closed:
            raise TransportClosedError("Cannot start closed transport")

        self._client = httpx.AsyncClient(
            headers=self.headers,
            timeout=self.timeout,
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        self._closed = True

        if self._client:
            await self._client.aclose()
            self._client = None

        # Fail any pending requests
        for future in self._pending_requests.values():
            if not future.done():
                future.set_exception(TransportClosedError())
        self._pending_requests.clear()

    async def _send_message(self, message: dict[str, Any]) -> Any:
        """Send a message via HTTP POST."""
        if not self._client:
            raise TransportClosedError("Client not started")

        try:
            response = await self._client.post(
                self.url,
                json=message,
            )
            response.raise_for_status()

            data = response.json()
            if "error" in data:
                error = data["error"]
                raise JSONRPCError(
                    code=error.get("code", -1),
                    message=error.get("message", "Unknown error"),
                    data=error.get("data"),
                )

            return data.get("result")

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise TransportClosedError(f"Server not found: {self.url}")
            raise TransportError(f"HTTP error {e.response.status_code}: {e}")
        except httpx.RequestError as e:
            raise TransportError(f"Request failed: {e}")
        except json.JSONDecodeError as e:
            raise TransportError(f"Invalid JSON response: {e}")


class SSETransport(Transport):
    """
    Server-Sent Events transport for MCP servers.

    This transport uses SSE to receive messages from the server
    and HTTP POST to send messages.
    """

    def __init__(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
    ):
        """
        Initialize the SSE transport.

        Args:
            url: The server URL.
            headers: Optional HTTP headers.
            timeout: Request timeout in seconds.
        """
        super().__init__()
        self.url = url
        self.headers = headers or {}
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._sse_task: asyncio.Task | None = None
        self._session_id: str | None = None

    async def start(self) -> None:
        """Start the SSE connection."""
        if self._closed:
            raise TransportClosedError("Cannot start closed transport")

        self._client = httpx.AsyncClient(
            headers=self.headers,
            timeout=self.timeout,
        )

        # Start SSE listener
        self._sse_task = asyncio.create_task(self._listen_sse())

    async def close(self) -> None:
        """Close the SSE connection."""
        self._closed = True

        # Cancel SSE task
        if self._sse_task:
            self._sse_task.cancel()
            try:
                await self._sse_task
            except asyncio.CancelledError:
                pass
            self._sse_task = None

        # Close HTTP client
        if self._client:
            await self._client.aclose()
            self._client = None

        # Fail any pending requests
        for future in self._pending_requests.values():
            if not future.done():
                future.set_exception(TransportClosedError())
        self._pending_requests.clear()

    async def _send_message(self, message: dict[str, Any]) -> None:
        """Send a message via HTTP POST."""
        if not self._client:
            raise TransportClosedError("Client not started")

        try:
            # Add session ID if we have one
            if self._session_id:
                message.setdefault("params", {})["sessionId"] = self._session_id

            await self._client.post(
                self.url,
                json=message,
            )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise TransportClosedError(f"Server not found: {self.url}")
            raise TransportError(f"HTTP error {e.response.status_code}: {e}")
        except httpx.RequestError as e:
            raise TransportError(f"Request failed: {e}")

    async def _listen_sse(self) -> None:
        """Listen for SSE messages from the server."""
        if not self._client:
            return

        try:
            async with self._client.stream("GET", self.url) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if self._closed:
                        break

                    if not line.strip():
                        continue

                    if line.startswith("data: "):
                        data = line[6:]  # Remove "data: " prefix

                        try:
                            message = json.loads(data)
                            self._handle_message(message)
                        except json.JSONDecodeError:
                            # Invalid JSON, skip
                            continue

        except asyncio.CancelledError:
            # Task was cancelled
            pass
        except Exception as e:
            # Connection error
            if not self._closed:
                # Mark as closed and fail pending requests
                self._closed = True
                for future in self._pending_requests.values():
                    if not future.done():
                        future.set_exception(TransportClosedError(str(e)))
                self._pending_requests.clear()
