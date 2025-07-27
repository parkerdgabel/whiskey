"""Tests for auth extension setup."""

import asyncio
from typing import ClassVar

import pytest

from whiskey import Whiskey
from whiskey_auth import (
    AuthProvider,
    Permission,
    Role,
    auth_extension,
    create_test_user,
)
from whiskey_auth.core import AuthContext
from whiskey_auth.providers import ProviderRegistry


class TestAuthExtension:
    """Test auth extension configuration."""

    def test_extension_adds_methods(self):
        """Test that extension adds required methods to app."""
        app = Whiskey()

        # Before extension
        assert not hasattr(app, "user_model")
        assert not hasattr(app, "auth_provider")
        assert not hasattr(app, "permissions")
        assert not hasattr(app, "role")

        # Apply extension
        app.use(auth_extension)

        # After extension
        assert hasattr(app, "user_model")
        assert hasattr(app, "auth_provider")
        assert hasattr(app, "permissions")
        assert hasattr(app, "role")
        assert hasattr(app, "requires_auth")
        assert hasattr(app, "requires_permission")
        assert hasattr(app, "requires_role")

    def test_extension_registers_components(self):
        """Test that extension registers required components."""
        app = Whiskey()
        app.use(auth_extension)

        # Check provider registry is registered
        assert ProviderRegistry in app.container
        registry = app.container[ProviderRegistry]
        assert isinstance(registry, ProviderRegistry)

        # Check AuthContext is registered
        assert AuthContext in app.container

    def test_user_model_decorator(self):
        """Test @app.user_model decorator."""
        app = Whiskey()
        app.use(auth_extension)

        @app.user_model
        class MyUser:
            id: int
            username: str
            email: str

        # Check user model is stored in metadata
        assert app._auth_metadata["user_model"] is MyUser

        # Check class is registered in container
        assert MyUser in app.container

    def test_auth_provider_decorator(self):
        """Test @app.auth_provider decorator."""
        app = Whiskey()
        app.use(auth_extension)

        @app.auth_provider
        class MyAuthProvider(AuthProvider):
            async def authenticate(self, **credentials):
                return None

        # Check provider is registered in container
        assert AuthProvider in app.container

        # Check provider is registered in registry
        registry = app.container[ProviderRegistry]
        assert "myauth" in registry.list_providers()

    def test_auth_provider_with_name(self):
        """Test @app.auth_provider with custom name."""
        app = Whiskey()
        app.use(auth_extension)

        @app.auth_provider("custom")
        class CustomProvider(AuthProvider):
            async def authenticate(self, **credentials):
                return None

        # Check named registration
        assert (AuthProvider, "custom") in app.container

        # Check registry
        registry = app.container[ProviderRegistry]
        assert "custom" in registry.list_providers()

    def test_permissions_decorator(self):
        """Test @app.permissions decorator."""
        app = Whiskey()
        app.use(auth_extension)

        @app.permissions
        class Perms:
            READ = "read"
            WRITE = "write"
            DELETE = Permission("delete", "Can delete resources")

        # Check permissions are stored
        perms = app._auth_metadata["permissions"]
        assert len(perms) == 3
        assert all(isinstance(p, Permission) for p in perms.values())

        # Check permissions are available on class
        assert isinstance(Perms.READ, Permission)
        assert Perms.READ.name == "read"
        assert Perms.DELETE.description == "Can delete resources"

    def test_role_decorator(self):
        """Test @app.role decorator."""
        app = Whiskey()
        app.use(auth_extension)

        # First define some permissions
        @app.permissions
        class Perms:
            READ = "read"
            WRITE = "write"

        # Define role
        @app.role("editor")
        class EditorRole:
            permissions: ClassVar = {"read", "write"}
            description: ClassVar = "Can read and write"

        # Check role is stored
        roles = app._auth_metadata.get("roles", {})
        assert "editor" in roles

        role = roles["editor"]
        assert isinstance(role, Role)
        assert role.name == "editor"
        assert len(role.permissions) == 2
        assert role.description == "Can read and write"

    def test_role_inheritance(self):
        """Test role inheritance."""
        app = Whiskey()
        app.use(auth_extension)

        @app.role("reader")
        class ReaderRole:
            permissions: ClassVar = {"read"}

        @app.role("writer")
        class WriterRole:
            permissions: ClassVar = {"write"}
            inherits: ClassVar = ["reader"]

        roles = app._auth_metadata.get("roles", {})

        # Check both roles exist
        assert "reader" in roles
        assert "writer" in roles

    @pytest.mark.asyncio
    async def test_current_user_resolver(self):
        """Test CurrentUser type resolution."""
        app = Whiskey()
        app.use(auth_extension)

        # Create test user
        user = create_test_user(username="testuser")

        # Create auth context
        auth_context = AuthContext(user=user)
        app.container[AuthContext] = auth_context

        # Test CurrentUser resolution works
        from whiskey_auth import CurrentUser

        # CurrentUser should resolve to the authenticated user
        resolved = await app.container.resolve(CurrentUser)
        assert resolved == user

    @pytest.mark.asyncio
    async def test_current_user_resolver_no_auth(self):
        """Test CurrentUser resolution without auth."""
        app = Whiskey()
        app.use(auth_extension)

        # No auth context
        from whiskey_auth import CurrentUser

        # CurrentUser should resolve to None when not authenticated
        resolved = await app.container.resolve(CurrentUser)
        assert resolved is None

    def test_current_user_type_checker(self):
        """Test CurrentUser type checking function."""
        app = Whiskey()
        app.use(auth_extension)

        # Get type checker
        is_current_user = app._auth_metadata["current_user_checker"]
        assert callable(is_current_user)

        # Test various types
        from typing import Optional

        from whiskey_auth.core import CurrentUser

        assert is_current_user(CurrentUser)

        # Test with Optional
        assert is_current_user(Optional[CurrentUser])

    @pytest.mark.asyncio
    async def test_startup_hook_with_middleware(self):
        """Test startup hook adds middleware when ASGI is present."""
        app = Whiskey()

        # Simulate ASGI extension by adding asgi_manager
        class MockAsgiManager:
            def __init__(self):
                self.middlewares = []

            def add_middleware(self, metadata):
                self.middlewares.append(metadata)

        app.asgi_manager = MockAsgiManager()

        # Apply auth extension
        app.use(auth_extension)

        # Mock the ASGI MiddlewareMetadata class
        class MiddlewareMetadata:
            def __init__(self, func, name, priority):
                self.func = func
                self.name = name
                self.priority = priority

        # Temporarily replace the import
        import sys

        sys.modules["whiskey_asgi"] = type(sys)("whiskey_asgi")
        sys.modules["whiskey_asgi.extension"] = type(sys)("extension")
        sys.modules["whiskey_asgi.extension"].MiddlewareMetadata = MiddlewareMetadata

        # Register AuthenticationMiddleware
        from whiskey_auth.middleware import AuthenticationMiddleware

        app.container.singleton(AuthenticationMiddleware)

        # Execute startup hooks directly from the callbacks list
        for callback in app._startup_callbacks:
            if asyncio.iscoroutinefunction(callback):
                await callback()
            else:
                callback()

        # Check middleware was added
        assert len(app.asgi_manager.middlewares) > 0
        assert any(m.name == "auth" for m in app.asgi_manager.middlewares)

    def test_decorators_added_to_app(self):
        """Test auth decorators are added to app."""
        app = Whiskey()
        app.use(auth_extension)

        # Import decorators to compare
        from whiskey_auth.decorators import requires_auth, requires_permission, requires_role

        # Check they're the same functions
        assert app.requires_auth is requires_auth
        assert app.requires_permission is requires_permission
        assert app.requires_role is requires_role
