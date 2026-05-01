"""
MCP OAuth authentication support.

This module provides OAuth 2.0 authentication for MCP servers
that require OAuth-based access tokens.
"""

import asyncio
import base64
import hashlib
import secrets
import time
from typing import Any
import urllib.parse

import httpx


class OAuthError(Exception):
    """Base OAuth error."""

    def __init__(self, message: str, error_code: str | None = None):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class AuthServerError(OAuthError):
    """Raised when the authorization server is unavailable."""

    pass


class TokenError(OAuthError):
    """Raised when token exchange or refresh fails."""

    pass


class OAuthClient:
    """
    OAuth 2.0 client for MCP server authentication.

    Supports the Authorization Code flow with PKCE.
    """

    def __init__(
        self,
        client_id: str,
        auth_server_metadata_url: str | None = None,
        authorization_endpoint: str | None = None,
        token_endpoint: str | None = None,
        callback_port: int | None = None,
        redirect_uri: str | None = None,
    ):
        """
        Initialize the OAuth client.

        Args:
            client_id: OAuth client identifier.
            auth_server_metadata_url: URL of the authorization server metadata.
            authorization_endpoint: Direct authorization endpoint URL (if no metadata URL).
            token_endpoint: Direct token endpoint URL (if no metadata URL).
            callback_port: Local port for callback (default: random).
            redirect_uri: Custom redirect URI (default: http://localhost:port/callback).
        """
        self.client_id = client_id
        self.auth_server_metadata_url = auth_server_metadata_url
        self.authorization_endpoint = authorization_endpoint
        self.token_endpoint = token_endpoint
        self.callback_port = callback_port
        self.redirect_uri = redirect_uri

        self._metadata: dict[str, str] | None = None
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._expires_at: float | None = None
        self._http_client: httpx.AsyncClient | None = None

    async def get_metadata(self) -> dict[str, str]:
        """
        Fetch authorization server metadata.

        Returns:
            Dictionary with authorization server endpoints.

        Raises:
            AuthServerError: If metadata fetch fails.
        """
        if self._metadata:
            return self._metadata

        if not self.auth_server_metadata_url:
            # Use directly configured endpoints
            if not self.authorization_endpoint or not self.token_endpoint:
                raise OAuthError(
                    "Either auth_server_metadata_url or both authorization_endpoint "
                    "and token_endpoint must be provided"
                )
            self._metadata = {
                "authorization_endpoint": self.authorization_endpoint,
                "token_endpoint": self.token_endpoint,
            }
            return self._metadata

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.auth_server_metadata_url)
                response.raise_for_status()
                self._metadata = response.json()

        except httpx.HTTPStatusError as e:
            raise AuthServerError(
                f"Failed to fetch auth server metadata: {e.response.status_code}"
            )
        except Exception as e:
            raise AuthServerError(f"Failed to fetch auth server metadata: {e}")

        return self._metadata

    def generate_code_verifier(self) -> str:
        """Generate a PKCE code verifier."""
        return secrets.token_urlsafe(32)

    def generate_code_challenge(self, verifier: str) -> str:
        """Generate a PKCE code challenge from verifier."""
        digest = hashlib.sha256(verifier.encode()).digest()
        return base64.urlsafe_b64encode(digest).decode().rstrip("=")

    def build_authorization_url(
        self,
        code_verifier: str,
        scope: str | None = None,
        state: str | None = None,
    ) -> str:
        """
        Build the authorization URL.

        Args:
            code_verifier: PKCE code verifier.
            scope: OAuth scopes to request.
            state: Optional state parameter for security.

        Returns:
            Authorization URL to redirect the user to.
        """
        metadata = asyncio.get_event_loop().run_until_complete(self.get_metadata())

        auth_endpoint = metadata.get("authorization_endpoint")
        if not auth_endpoint:
            raise OAuthError("Missing authorization_endpoint in metadata")

        code_challenge = self.generate_code_challenge(code_verifier)
        redirect_uri = self.redirect_uri or f"http://localhost:{self.callback_port}/callback"

        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }

        if scope:
            params["scope"] = scope

        if state:
            params["state"] = state

        url = f"{auth_endpoint}?{urllib.parse.urlencode(params)}"
        return url

    async def exchange_code_for_token(
        self,
        code: str,
        code_verifier: str,
    ) -> dict[str, Any]:
        """
        Exchange authorization code for access token.

        Args:
            code: Authorization code from the callback.
            code_verifier: PKCE code verifier used in authorization request.

        Returns:
            Token response with access_token, refresh_token, expires_in, etc.

        Raises:
            TokenError: If token exchange fails.
        """
        metadata = await self.get_metadata()
        token_endpoint = metadata.get("token_endpoint")

        if not token_endpoint:
            raise OAuthError("Missing token_endpoint in metadata")

        redirect_uri = self.redirect_uri or f"http://localhost:{self.callback_port}/callback"

        data = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    token_endpoint,
                    data=data,
                    headers={"Accept": "application/json"},
                )
                response.raise_for_status()
                token_data = response.json()

        except httpx.HTTPStatusError as e:
            error_data = e.response.json() if e.response.headers.get("content-type", "").startswith("application/json") else {}
            raise TokenError(
                f"Token exchange failed: {e.response.status_code}",
                error_code=error_data.get("error"),
            )
        except Exception as e:
            raise TokenError(f"Token exchange failed: {e}")

        # Store tokens
        self._access_token = token_data.get("access_token")
        self._refresh_token = token_data.get("refresh_token")

        expires_in = token_data.get("expires_in")
        if expires_in:
            self._expires_at = time.time() + int(expires_in)

        return token_data

    async def refresh_access_token(self) -> dict[str, Any]:
        """
        Refresh the access token using refresh token.

        Returns:
            New token response.

        Raises:
            TokenError: If refresh fails.
        """
        if not self._refresh_token:
            raise TokenError("No refresh token available")

        metadata = await self.get_metadata()
        token_endpoint = metadata.get("token_endpoint")

        if not token_endpoint:
            raise OAuthError("Missing token_endpoint in metadata")

        data = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "refresh_token": self._refresh_token,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    token_endpoint,
                    data=data,
                    headers={"Accept": "application/json"},
                )
                response.raise_for_status()
                token_data = response.json()

        except httpx.HTTPStatusError as e:
            error_data = e.response.json() if e.response.headers.get("content-type", "").startswith("application/json") else {}
            raise TokenError(
                f"Token refresh failed: {e.response.status_code}",
                error_code=error_data.get("error"),
            )
        except Exception as e:
            raise TokenError(f"Token refresh failed: {e}")

        # Update tokens
        self._access_token = token_data.get("access_token")
        if "refresh_token" in token_data:
            self._refresh_token = token_data.get("refresh_token")

        expires_in = token_data.get("expires_in")
        if expires_in:
            self._expires_at = time.time() + int(expires_in)

        return token_data

    async def get_access_token(self) -> str:
        """
        Get a valid access token, refreshing if necessary.

        Returns:
            Valid access token.

        Raises:
            TokenError: If token is not available or refresh fails.
        """
        if not self._access_token:
            raise TokenError("Not authenticated")

        # Check if token needs refresh
        if self._expires_at and time.time() >= self._expires_at - 60:
            # Refresh 1 minute before expiry
            await self.refresh_access_token()

        return self._access_token

    def is_authenticated(self) -> bool:
        """Check if client has a valid access token."""
        return self._access_token is not None

    async def start_local_auth_server(
        self,
        on_auth_code: callable,
    ) -> tuple[asyncio.Task, int]:
        """
        Start a local HTTP server for OAuth callback.

        Args:
            on_auth_code: Async callback function that receives (code, state).

        Returns:
            Tuple of (server task, actual port used).
        """
        from aiohttp import web

        app = web.Application()
        routes = web.RouteTableDef()

        @routes.get("/callback")
        async def callback_handler(request: web.Request):
            params = request.query
            code = params.get("code")
            state = params.get("state")
            error = params.get("error")

            if error:
                return web.Response(
                    text=f"Authorization failed: {error}",
                    status=400
                )

            if code:
                # Notify the callback
                asyncio.create_task(on_auth_code(code, state))

            return web.Response(
                text="Authorization successful! You can close this window.",
                content_type="text/html"
            )

        app.add_routes(routes)

        # Start server
        runner = web.AppRunner(app)
        await runner.setup()
        port = self.callback_port or 0  # 0 = random port
        site = web.TCPSite(runner, "localhost", port)
        await site.start()

        actual_port = site._server.sockets[0].getsockname()[1]

        # Create a task to keep the server running
        async def server_task():
            try:
                while True:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                await runner.cleanup()

        task = asyncio.create_task(server_task())

        return task, actual_port


async def authenticate_oauth(
    client_id: str,
    auth_server_metadata_url: str | None = None,
    scope: str | None = None,
) -> OAuthClient:
    """
    Perform OAuth authentication flow.

    This is a convenience function that handles the full flow:
    1. Starts a local callback server
    2. Generates authorization URL
    3. Waits for user to complete authorization
    4. Exchanges code for token

    Args:
        client_id: OAuth client identifier.
        auth_server_metadata_url: URL of auth server metadata.
        scope: OAuth scopes to request.

    Returns:
        Authenticated OAuthClient with valid access token.

    Raises:
        OAuthError: If authentication fails.
    """
    client = OAuthClient(
        client_id=client_id,
        auth_server_metadata_url=auth_server_metadata_url,
    )

    # Event to signal when we receive the auth code
    auth_code_received = asyncio.Event()
    received_code: tuple[str, str | None] = (None, None)

    async def on_auth_code(code: str, state: str | None):
        nonlocal received_code
        received_code = (code, state)
        auth_code_received.set()

    # Start local server
    server_task, port = await client.start_local_auth_server(on_auth_code)
    client.callback_port = port

    try:
        # Generate code verifier and authorization URL
        code_verifier = client.generate_code_verifier()
        state = secrets.token_urlsafe(16)

        auth_url = client.build_authorization_url(
            code_verifier=code_verifier,
            scope=scope,
            state=state,
        )

        print(f"\nPlease open this URL in your browser:")
        print(f"{auth_url}\n")

        # Wait for callback
        await auth_code_received.wait()

        code, received_state = received_code

        # Verify state
        if received_state != state:
            raise OAuthError("State mismatch - possible CSRF attack")

        # Exchange code for token
        await client.exchange_code_for_token(code, code_verifier)

        return client

    finally:
        # Stop the server
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass
