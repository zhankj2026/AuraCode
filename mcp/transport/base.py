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
MCP transport layer base classes.

This module provides the base transport interface and common error types.
"""

import abc
import asyncio
import json
from typing import Any


class TransportError(Exception):
    """Base class for transport errors."""

    def __init__(self, message: str, cause: Exception | None = None):
        self.message = message
        self.cause = cause
        super().__init__(message)


class JSONRPCError(TransportError):
    """JSON-RPC protocol error."""

    def __init__(self, code: int, message: str, data: Any = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(f"JSON-RPC error {code}: {message}")


class TransportClosedError(TransportError):
    """Raised when the transport is closed."""

    def __init__(self, message: str = "Transport is closed"):
        super().__init__(message)


class Transport(abc.ABC):
    """
    Base class for MCP transport implementations.

    Transports handle the low-level communication with MCP servers,
    regardless of the protocol (stdio, HTTP, WebSocket, etc.).
    """

    def __init__(self):
        self._closed = False
        self._message_id = 0
        self._pending_requests: dict[int, asyncio.Future] = {}

    @abc.abstractmethod
    async def start(self) -> None:
        """Start the transport and establish connection."""

    @abc.abstractmethod
    async def close(self) -> None:
        """Close the transport and cleanup resources."""

    @property
    def closed(self) -> bool:
        """Check if the transport is closed."""
        return self._closed

    async def send_request(
        self, method: str, params: dict[str, Any] | None = None
    ) -> Any:
        """
        Send a JSON-RPC request and wait for response.

        Args:
            method: The JSON-RPC method name.
            params: Optional parameters for the method.

        Returns:
            The result from the server.

        Raises:
            TransportClosedError: If the transport is closed.
            JSONRPCError: If the server returns an error.
        """
        if self._closed:
            raise TransportClosedError()

        request_id = self._message_id
        self._message_id += 1

        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
        }
        if params is not None:
            request["params"] = params

        future: asyncio.Future = asyncio.Future()
        self._pending_requests[request_id] = future

        try:
            await self._send_message(request)
            return await future
        except Exception as e:
            self._pending_requests.pop(request_id, None)
            if isinstance(e, TransportError):
                raise
            raise TransportError(f"Failed to send request: {e}", e)

    async def send_notification(
        self, method: str, params: dict[str, Any] | None = None
    ) -> None:
        """
        Send a JSON-RPC notification (no response expected).

        Args:
            method: The JSON-RPC method name.
            params: Optional parameters for the method.
        """
        if self._closed:
            raise TransportClosedError()

        notification = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params is not None:
            notification["params"] = params

        await self._send_message(notification)

    @abc.abstractmethod
    async def _send_message(self, message: dict[str, Any]) -> None:
        """Send a raw message through the transport."""

    def _handle_message(self, message: dict[str, Any]) -> None:
        """
        Handle an incoming message from the server.

        This should be called by subclasses when they receive a message.
        """
        if "id" in message:
            # Response to a request
            request_id = message.get("id")
            if request_id in self._pending_requests:
                future = self._pending_requests.pop(request_id)
                if "error" in message:
                    error = message["error"]
                    future.set_exception(
                        JSONRPCError(
                            code=error.get("code", -1),
                            message=error.get("message", "Unknown error"),
                            data=error.get("data"),
                        )
                    )
                else:
                    future.set_result(message.get("result"))
        # Notifications are not handled at transport level
