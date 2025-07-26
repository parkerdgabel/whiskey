"""Tests for authentication middleware."""

import pytest
from typing import Any

from whiskey_auth import create_test_user
from whiskey_auth.core import AuthContext, User
from whiskey_auth.middleware import (
    create_auth_context,
    AuthenticationMiddleware,
    AuthContextMiddleware,
)
from whiskey_auth.providers import ProviderRegistry, JWTAuthProvider


class TestCreateAuthContext:
    """Test auth context creation helper."""
    
    @pytest.mark.asyncio
    async def test_create_empty_context(self):
        """Test creating empty auth context."""
        context = await create_auth_context()
        
        assert isinstance(context, AuthContext)
        assert context.user is None
        assert context.provider is None
        assert context.authenticated_at is None
        assert not context.is_authenticated
    
    @pytest.mark.asyncio
    async def test_create_authenticated_context(self):
        """Test creating authenticated context."""
        user = create_test_user(username="testuser")
        
        context = await create_auth_context(
            user=user,
            provider_name="test",
            metadata={"ip": "127.0.0.1"}
        )
        
        assert context.user == user
        assert context.provider == "test"
        assert context.authenticated_at is not None
        assert context.is_authenticated
        assert context.metadata["ip"] == "127.0.0.1"


class TestAuthenticationMiddleware:
    """Test authentication middleware."""
    
    class MockJWTProvider(JWTAuthProvider):
        """Mock JWT provider for testing."""
        
        def __init__(self, user: User | None = None):
            super().__init__(secret="test-secret")
            self.user = user
        
        async def authenticate(self, **credentials) -> User | None:
            token = credentials.get("token")
            if token == "valid-token" and self.user:
                return self.user
            return None
        
        async def get_user_by_id(self, user_id: Any) -> User | None:
            return self.user
    
    @pytest.fixture
    def registry(self):
        """Create provider registry with mock providers."""
        registry = ProviderRegistry()
        
        # Add JWT provider
        user = create_test_user(id=1, username="jwtuser")
        jwt_provider = self.MockJWTProvider(user)
        registry._instances["jwt"] = jwt_provider
        
        return registry
    
    @pytest.fixture
    def middleware(self, registry):
        """Create authentication middleware."""
        return AuthenticationMiddleware(
            registry,
            header_name="Authorization",
            header_prefix="Bearer",
            cookie_name="session_id",
            query_param="api_key"
        )
    
    def create_http_scope(
        self,
        headers: dict[str, str] | None = None,
        cookies: str | None = None,
        query_string: str = ""
    ) -> dict:
        """Create ASGI HTTP scope."""
        scope_headers = []
        
        if headers:
            for name, value in headers.items():
                scope_headers.append((name.lower().encode(), value.encode()))
        
        if cookies:
            scope_headers.append((b"cookie", cookies.encode()))
        
        return {
            "type": "http",
            "headers": scope_headers,
            "query_string": query_string.encode()
        }
    
    @pytest.mark.asyncio
    async def test_extract_auth_from_header(self, middleware, registry):
        """Test extracting auth from Authorization header."""
        scope = self.create_http_scope(
            headers={"Authorization": "Bearer valid-token"}
        )
        
        auth_context = await middleware.extract_auth(scope)
        
        assert auth_context.is_authenticated
        assert auth_context.user.username == "jwtuser"
        assert auth_context.provider == "jwt"
    
    @pytest.mark.asyncio
    async def test_extract_auth_invalid_header(self, middleware):
        """Test extracting auth with invalid header."""
        # Wrong prefix
        scope = self.create_http_scope(
            headers={"Authorization": "Basic sometoken"}
        )
        
        auth_context = await middleware.extract_auth(scope)
        assert not auth_context.is_authenticated
        
        # Invalid token
        scope = self.create_http_scope(
            headers={"Authorization": "Bearer invalid-token"}
        )
        
        auth_context = await middleware.extract_auth(scope)
        assert not auth_context.is_authenticated
    
    @pytest.mark.asyncio
    async def test_extract_auth_no_header(self, middleware):
        """Test extracting auth with no header."""
        scope = self.create_http_scope()
        
        auth_context = await middleware.extract_auth(scope)
        assert not auth_context.is_authenticated
    
    def test_parse_cookies(self, middleware):
        """Test cookie parsing."""
        # Single cookie
        cookies = middleware._parse_cookies(b"session_id=abc123")
        assert cookies == {"session_id": "abc123"}
        
        # Multiple cookies
        cookies = middleware._parse_cookies(b"session_id=abc123; user=alice; theme=dark")
        assert cookies == {
            "session_id": "abc123",
            "user": "alice",
            "theme": "dark"
        }
        
        # Empty cookies
        cookies = middleware._parse_cookies(b"")
        assert cookies == {}
        
        # Malformed cookies
        cookies = middleware._parse_cookies(b"invalid_cookie_format")
        assert cookies == {}
    
    def test_parse_query_string(self, middleware):
        """Test query string parsing."""
        # Single parameter
        params = middleware._parse_query_string("api_key=secret123")
        assert params == {"api_key": "secret123"}
        
        # Multiple parameters
        params = middleware._parse_query_string("api_key=secret&user=alice&debug=true")
        assert params == {
            "api_key": "secret",
            "user": "alice",
            "debug": "true"
        }
        
        # Empty query string
        params = middleware._parse_query_string("")
        assert params == {}
        
        # Malformed query string
        params = middleware._parse_query_string("invalid_query")
        assert params == {}
    
    @pytest.mark.asyncio
    async def test_middleware_call_http(self, middleware):
        """Test middleware with HTTP request."""
        # Track if app was called
        app_called = False
        scope_received = None
        
        async def mock_app(scope, receive, send):
            nonlocal app_called, scope_received
            app_called = True
            scope_received = scope
        
        middleware.app = mock_app
        
        # Create HTTP scope
        scope = self.create_http_scope(
            headers={"Authorization": "Bearer valid-token"}
        )
        
        async def mock_receive():
            pass
        
        async def mock_send(message):
            pass
        
        await middleware(scope, mock_receive, mock_send)
        
        assert app_called
        assert "auth_context" in scope_received
        assert scope_received["auth_context"].is_authenticated
    
    @pytest.mark.asyncio
    async def test_middleware_skip_non_http(self, middleware):
        """Test middleware skips non-HTTP requests."""
        app_called = False
        
        async def mock_app(scope, receive, send):
            nonlocal app_called
            app_called = True
        
        middleware.app = mock_app
        
        # WebSocket scope
        scope = {"type": "websocket"}
        
        async def mock_receive():
            pass
        
        async def mock_send(message):
            pass
        
        await middleware(scope, mock_receive, mock_send)
        
        assert app_called


class TestAuthContextMiddleware:
    """Test auth context middleware."""
    
    @pytest.fixture
    def middleware(self):
        """Create auth context middleware."""
        async def mock_app(scope, receive, send):
            pass
        
        return AuthContextMiddleware(mock_app)
    
    @pytest.mark.asyncio
    async def test_make_context_available(self, middleware):
        """Test making auth context available for DI."""
        from whiskey import Container
        
        # Create mock container
        container = Container()
        stored_context = None
        
        def store_context(context):
            nonlocal stored_context
            stored_context = context
        
        # Mock Container.current()
        original_current = Container.current
        Container.current = lambda: container
        container.__setitem__ = lambda key, value: store_context(value) if key == AuthContext else None
        
        try:
            # Create scope with auth context
            user = create_test_user(username="testuser")
            auth_context = AuthContext(user=user)
            scope = {
                "type": "http",
                "auth_context": auth_context
            }
            
            async def mock_receive():
                pass
            
            async def mock_send(message):
                pass
            
            await middleware(scope, mock_receive, mock_send)
            
            # Verify context was stored
            assert stored_context == auth_context
            
        finally:
            # Restore original
            Container.current = original_current
    
    @pytest.mark.asyncio
    async def test_skip_non_http(self, middleware):
        """Test skipping non-HTTP requests."""
        # Should just pass through
        scope = {"type": "websocket"}
        
        app_called = False
        
        async def mock_app(scope, receive, send):
            nonlocal app_called
            app_called = True
        
        middleware.app = mock_app
        
        async def mock_receive():
            pass
        
        async def mock_send(message):
            pass
        
        await middleware(scope, mock_receive, mock_send)
        
        assert app_called