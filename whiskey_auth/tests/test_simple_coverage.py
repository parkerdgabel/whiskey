"""Simple tests to ensure code coverage for whiskey_auth."""

from typing import ClassVar

import pytest

from whiskey import Whiskey
from whiskey_auth import (
    AuthProvider,
    Permission,
    Role,
    create_test_user,
)
from whiskey_auth.core import AuthContext, AuthenticationError, AuthorizationError
from whiskey_auth.extension import (
    _create_auth_provider_decorator,
    _create_role_decorator,
    _register_current_user_resolver,
    _register_permissions,
    _register_user_model,
)
from whiskey_auth.middleware import AuthenticationMiddleware, create_auth_context
from whiskey_auth.providers import JWTAuthProvider, ProviderRegistry


class TestExtensionFunctions:
    """Test extension helper functions directly."""

    def test_register_user_model(self):
        """Test user model registration."""
        app = Whiskey()

        class User:
            id: int
            username: str

        result = _register_user_model(app, User)

        assert result is User
        assert app.container.get("__auth_user_model__") is User

    def test_create_auth_provider_decorator(self):
        """Test auth provider decorator creation."""
        app = Whiskey()
        registry = ProviderRegistry()

        decorator = _create_auth_provider_decorator(app, registry, "test")

        class TestProvider(AuthProvider):
            async def authenticate(self, **credentials):
                return None

        result = decorator(TestProvider)

        assert result is TestProvider
        assert "test" in registry.list_providers()

    def test_register_permissions(self):
        """Test permission registration."""
        app = Whiskey()

        class Perms:
            READ = "read"
            WRITE = Permission("write", "Can write")

        result = _register_permissions(app, Perms)

        assert result is Perms
        perms = app.container.get("__auth_permissions__")
        assert len(perms) == 2
        assert isinstance(Perms.READ, Permission)
        assert Perms.WRITE.description == "Can write"

    def test_create_role_decorator(self):
        """Test role decorator creation."""
        app = Whiskey()

        decorator = _create_role_decorator(app, "admin")

        class AdminRole:
            permissions: ClassVar[list[str]] = ["read", "write"]
            description: ClassVar[str] = "Administrator"

        result = decorator(AdminRole)

        assert result is AdminRole
        roles = app.container.get("__auth_roles__")
        assert "admin" in roles
        assert roles["admin"].name == "admin"

    @pytest.mark.asyncio
    async def test_register_current_user_resolver(self):
        """Test current user resolver registration."""
        app = Whiskey()
        _register_current_user_resolver(app)

        # Check resolver is registered
        from whiskey_auth.core import User

        assert User in app.container._resolvers

        # Test resolver with no auth
        resolver = app.container._resolvers[User]
        result = await resolver(app.container)
        assert result is None

        # Test resolver with auth
        user = create_test_user()
        auth_context = AuthContext(user=user)
        app.container[AuthContext] = auth_context

        result = await resolver(app.container)
        assert result == user


class TestMiddlewareFunctions:
    """Test middleware helper functions."""

    @pytest.mark.asyncio
    async def test_create_auth_context(self):
        """Test auth context creation."""
        # Empty context
        ctx = await create_auth_context()
        assert not ctx.is_authenticated

        # With user
        user = create_test_user()
        ctx = await create_auth_context(user=user, provider_name="test")
        assert ctx.is_authenticated
        assert ctx.user == user
        assert ctx.provider == "test"

    def test_authentication_middleware_init(self):
        """Test middleware initialization."""
        registry = ProviderRegistry()

        middleware = AuthenticationMiddleware(
            registry,
            header_name="X-Auth",
            header_prefix="Token",
            cookie_name="auth_cookie",
            query_param="auth_token",
        )

        assert middleware.registry is registry
        assert middleware.header_name == "X-Auth"
        assert middleware.header_prefix == "Token"
        assert middleware.cookie_name == "auth_cookie"
        assert middleware.query_param == "auth_token"

    def test_middleware_parse_cookies(self):
        """Test cookie parsing."""
        registry = ProviderRegistry()
        middleware = AuthenticationMiddleware(registry)

        # Test various cookie formats
        cookies = middleware._parse_cookies(b"session=abc123")
        assert cookies == {"session": "abc123"}

        cookies = middleware._parse_cookies(b"a=1; b=2; c=3")
        assert cookies == {"a": "1", "b": "2", "c": "3"}

        cookies = middleware._parse_cookies(b"")
        assert cookies == {}

    def test_middleware_parse_query_string(self):
        """Test query string parsing."""
        registry = ProviderRegistry()
        middleware = AuthenticationMiddleware(registry)

        params = middleware._parse_query_string("token=abc123")
        assert params == {"token": "abc123"}

        params = middleware._parse_query_string("a=1&b=2&c=3")
        assert params == {"a": "1", "b": "2", "c": "3"}

        params = middleware._parse_query_string("")
        assert params == {}


class TestProviderImplementations:
    """Test provider implementations."""

    def test_provider_registry_operations(self):
        """Test provider registry."""
        registry = ProviderRegistry()

        class Provider1(AuthProvider):
            async def authenticate(self, **credentials):
                return None

        # Register and get
        registry.register("prov1", Provider1)
        assert registry.get("prov1") is Provider1
        assert registry.get("nonexistent") is None

        # List providers
        assert "prov1" in registry.list_providers()

    @pytest.mark.asyncio
    async def test_provider_registry_get_instance(self):
        """Test getting provider instances."""
        registry = ProviderRegistry()

        class Provider1(AuthProvider):
            async def authenticate(self, **credentials):
                return None

        registry.register("prov1", Provider1)

        # Get instance
        instance = await registry.get_instance("prov1")
        assert isinstance(instance, Provider1)

        # Should cache instance
        instance2 = await registry.get_instance("prov1")
        assert instance is instance2

    def test_jwt_provider_token_operations(self):
        """Test JWT provider token operations."""
        provider = JWTAuthProvider(
            secret="secret", algorithm="HS256", issuer="test", audience="test-app"
        )

        user = create_test_user(id=123, username="testuser", email="test@example.com")

        # Create token
        token = provider.create_token(user, "access")
        assert isinstance(token, str)

        # Decode token
        payload = provider.decode_token(token)
        assert payload is not None
        assert payload["sub"] == "123"
        assert payload["username"] == "testuser"
        assert payload["email"] == "test@example.com"
        assert payload["type"] == "access"

        # Invalid token
        assert provider.decode_token("invalid") is None

    def test_jwt_provider_refresh_token(self):
        """Test JWT refresh token flow."""
        provider = JWTAuthProvider(secret="secret")

        # Create refresh token
        refresh = provider.create_token(type("User", (), {"id": 1})(), "refresh")

        # Refresh
        result = provider.refresh_token(refresh)
        assert result is not None
        access, new_refresh = result
        assert isinstance(access, str)
        assert isinstance(new_refresh, str)


class TestAuthDecoratorsSimple:
    """Simple tests for decorators without full DI."""

    @pytest.mark.asyncio
    async def test_requires_auth_with_context(self):
        """Test requires_auth with direct context."""
        from whiskey_auth.decorators import requires_auth

        @requires_auth
        async def protected(message: str) -> str:
            return f"Protected: {message}"

        # Without auth
        with pytest.raises(AuthenticationError):
            await protected("test", __auth_context__=AuthContext())

        # With auth
        user = create_test_user()
        ctx = AuthContext(user=user)
        result = await protected("test", __auth_context__=ctx)
        assert result == "Protected: test"

    @pytest.mark.asyncio
    async def test_requires_permission_with_context(self):
        """Test requires_permission with direct context."""
        from whiskey_auth.decorators import requires_permission

        @requires_permission("write")
        async def write_func(data: str) -> str:
            return f"Written: {data}"

        # Without permission
        user = create_test_user(permissions=["read"])
        ctx = AuthContext(user=user)

        with pytest.raises(AuthorizationError):
            await write_func("test", __auth_context__=ctx)

        # With permission
        user.permissions.append("write")
        result = await write_func("test", __auth_context__=ctx)
        assert result == "Written: test"


class TestCoreFunctionality:
    """Test core functionality."""

    def test_auth_errors(self):
        """Test authentication errors."""
        err = AuthenticationError("Test error")
        assert str(err) == "Test error"

        err = AuthorizationError("No access")
        assert str(err) == "No access"

    def test_permission_operations(self):
        """Test Permission operations."""
        p1 = Permission("read", "Can read")
        p2 = Permission("read")
        p3 = Permission("write")

        # String representation
        assert str(p1) == "read"

        # Equality
        assert p1 == p2
        assert p1 == "read"
        assert p1 != p3
        assert p1 != "write"

        # Hashing
        perm_set = {p1, p2, p3}
        assert len(perm_set) == 2  # p1 and p2 are same

    def test_role_operations(self):
        """Test Role operations."""
        role = Role(name="editor", permissions={"read", "write"}, description="Editor role")

        assert str(role) == "editor"
        assert role.has_permission("read")
        assert role.has_permission(Permission("write"))
        assert not role.has_permission("delete")

        # Test inheritance
        admin_role = Role(name="admin", permissions={"delete"}, inherits=[role])

        all_perms = admin_role.get_all_permissions()
        assert len(all_perms) == 3  # read, write, delete
        assert admin_role.has_permission("read")  # inherited
        assert admin_role.has_permission("delete")  # own

    def test_auth_context_operations(self):
        """Test AuthContext operations."""
        # Empty context
        ctx = AuthContext()
        assert not ctx.is_authenticated

        # With user
        user = create_test_user(permissions=["read"], roles=["user"])
        ctx = AuthContext(user=user)
        assert ctx.is_authenticated
        assert ctx.has_permission("read")
        assert not ctx.has_permission("write")
        assert ctx.has_role("user")
        assert not ctx.has_role("admin")
