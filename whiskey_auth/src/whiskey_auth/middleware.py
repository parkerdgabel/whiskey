"""Authentication middleware for web applications."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from whiskey_auth.core import AuthContext, AuthProvider
from whiskey_auth.providers import ProviderRegistry


async def create_auth_context(
    provider: AuthProvider | None = None,
    user: Any = None,
    provider_name: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuthContext:
    """Create authentication context.

    Args:
        provider: Authentication provider used
        user: Authenticated user
        provider_name: Name of the provider
        metadata: Additional metadata

    Returns:
        Authentication context
    """
    return AuthContext(
        user=user,
        provider=provider_name or (provider.__class__.__name__ if provider else None),
        authenticated_at=datetime.now() if user else None,
        metadata=metadata or {},
    )


class AuthenticationMiddleware:
    """Middleware for handling authentication in web applications.

    This middleware extracts authentication credentials from requests,
    validates them using configured providers, and makes the authenticated
    user available for injection.
    """

    def __init__(
        self,
        registry: ProviderRegistry,
        header_name: str = "Authorization",
        header_prefix: str = "Bearer",
        cookie_name: str | None = "session_id",
        query_param: str | None = "token",
    ):
        """Initialize authentication middleware.

        Args:
            registry: Provider registry
            header_name: Header name for auth tokens
            header_prefix: Header value prefix (e.g., "Bearer")
            cookie_name: Cookie name for session tokens
            query_param: Query parameter for tokens
        """
        self.registry = registry
        self.header_name = header_name
        self.header_prefix = header_prefix
        self.cookie_name = cookie_name
        self.query_param = query_param

    async def middleware(self, request: Any, call_next: Callable) -> Any:
        """Middleware function for Whiskey ASGI integration.
        
        This is the actual middleware function that will be called by the
        ASGI extension when processing requests.
        
        Args:
            request: The incoming request object
            call_next: Function to call the next middleware/handler
            
        Returns:
            Response from the next handler
        """
        # Extract auth context from request
        auth_context = await self.extract_auth_from_request(request)
        
        # Store auth context in the container's request scope
        from whiskey import Container
        container = request.scope.get("whiskey_container")
        if container:
            container[AuthContext] = auth_context
        
        # Call next handler
        response = await call_next(request)
        return response

    async def extract_auth_from_request(self, request: Any) -> AuthContext:
        """Extract authentication from request object.
        
        Args:
            request: Request object with headers, cookies, etc.
            
        Returns:
            Authentication context
        """
        # Try header-based auth first
        auth_header = request.headers.get(self.header_name)
        
        if auth_header and auth_header.startswith(f"{self.header_prefix} "):
            token = auth_header[len(self.header_prefix) + 1:]
            
            # Try JWT provider
            jwt_provider = await self.registry.get_instance("jwt")
            if jwt_provider:
                user = await jwt_provider.authenticate(token=token)
                if user:
                    return await create_auth_context(
                        provider=jwt_provider, user=user, provider_name="jwt"
                    )
        
        # Try cookie-based auth
        if self.cookie_name:
            session_id = request.cookies.get(self.cookie_name)
            
            if session_id:
                # Try session provider
                session_provider = await self.registry.get_instance("session")
                if session_provider:
                    user = await session_provider.authenticate(session_id=session_id)
                    if user:
                        return await create_auth_context(
                            provider=session_provider, user=user, provider_name="session"
                        )
        
        # Try query parameter auth
        if self.query_param:
            # Get query params from request
            query_params = dict(request.scope.get("query_string", b"").decode("utf-8").split("&"))
            token = None
            for param in query_params:
                if "=" in param:
                    k, v = param.split("=", 1)
                    if k == self.query_param:
                        token = v
                        break
            
            if token:
                # Try API key provider
                api_key_provider = await self.registry.get_instance("api_key")
                if api_key_provider:
                    user = await api_key_provider.authenticate(api_key=token)
                    if user:
                        return await create_auth_context(
                            provider=api_key_provider, user=user, provider_name="api_key"
                        )
        
        # No authentication found
        return await create_auth_context()

    async def extract_auth(self, scope: dict) -> AuthContext:
        """Extract authentication from request.

        Args:
            scope: ASGI scope

        Returns:
            Authentication context
        """
        # Try header-based auth first
        headers = dict(scope.get("headers", []))
        auth_header = headers.get(self.header_name.lower().encode())

        if auth_header:
            auth_str = auth_header.decode("utf-8")
            if auth_str.startswith(f"{self.header_prefix} "):
                token = auth_str[len(self.header_prefix) + 1 :]

                # Try JWT provider
                jwt_provider = await self.registry.get_instance("jwt")
                if jwt_provider:
                    user = await jwt_provider.authenticate(token=token)
                    if user:
                        return await create_auth_context(
                            provider=jwt_provider, user=user, provider_name="jwt"
                        )

        # Try cookie-based auth
        if self.cookie_name:
            cookies = self._parse_cookies(headers.get(b"cookie", b""))
            session_id = cookies.get(self.cookie_name)

            if session_id:
                # Try session provider
                session_provider = await self.registry.get_instance("session")
                if session_provider:
                    user = await session_provider.authenticate(session_id=session_id)
                    if user:
                        return await create_auth_context(
                            provider=session_provider, user=user, provider_name="session"
                        )

        # Try query parameter auth
        if self.query_param:
            query_string = scope.get("query_string", b"").decode("utf-8")
            params = self._parse_query_string(query_string)
            token = params.get(self.query_param)

            if token:
                # Try API key provider
                api_key_provider = await self.registry.get_instance("api_key")
                if api_key_provider:
                    user = await api_key_provider.authenticate(api_key=token)
                    if user:
                        return await create_auth_context(
                            provider=api_key_provider, user=user, provider_name="api_key"
                        )

        # No authentication found
        return await create_auth_context()

    def _parse_cookies(self, cookie_header: bytes) -> dict[str, str]:
        """Parse cookie header.

        Args:
            cookie_header: Cookie header value

        Returns:
            Dictionary of cookie name to value
        """
        cookies = {}
        if cookie_header:
            for cookie in cookie_header.decode("utf-8").split(";"):
                cookie = cookie.strip()
                if "=" in cookie:
                    name, value = cookie.split("=", 1)
                    cookies[name] = value
        return cookies

    def _parse_query_string(self, query_string: str) -> dict[str, str]:
        """Parse query string.

        Args:
            query_string: Query string

        Returns:
            Dictionary of parameter name to value
        """
        params = {}
        if query_string:
            for param in query_string.split("&"):
                if "=" in param:
                    name, value = param.split("=", 1)
                    params[name] = value
        return params


class AuthContextMiddleware:
    """Middleware that makes auth context available for DI.

    This middleware should be used after AuthenticationMiddleware
    to make the auth context available for dependency injection.
    """

    def __init__(self, app: Any):
        """Initialize auth context middleware.

        Args:
            app: Next ASGI app/middleware
        """
        self.app = app

    async def middleware(self, request: Any, call_next: Callable) -> Any:
        """Middleware function for Whiskey ASGI integration.
        
        Args:
            request: The incoming request object
            call_next: Function to call the next middleware/handler
            
        Returns:
            Response from the next handler
        """
        # The AuthContext should already be in the container from AuthenticationMiddleware
        # Just call the next handler
        return await call_next(request)
