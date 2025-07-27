"""Tests for authentication decorators using testing utilities."""

import pytest

from whiskey import Whiskey, inject
from whiskey_auth import (
    auth_extension,
    AuthenticationError,
    AuthorizationError,
    CurrentUser,
    create_test_user,
    AuthTestClient,
)
from whiskey_auth.decorators import (
    requires_auth,
    requires_permission,
    requires_role,
    requires_all_permissions,
)


class TestDecorators:
    """Test authentication and authorization decorators."""
    
    @pytest.fixture
    def app(self):
        """Create test app."""
        app = Whiskey()
        app.use(auth_extension)
        return app
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return AuthTestClient()
    
    @pytest.fixture
    def users(self):
        """Create test users."""
        return {
            "anonymous": None,
            "basic": create_test_user(
                id=1,
                username="basic",
                email="basic@example.com"
            ),
            "reader": create_test_user(
                id=2,
                username="reader",
                permissions=["read"],
                roles=["reader"]
            ),
            "writer": create_test_user(
                id=3,
                username="writer",
                permissions=["read", "write"],
                roles=["writer"]
            ),
            "admin": create_test_user(
                id=4,
                username="admin",
                permissions=["read", "write", "delete", "admin"],
                roles=["admin", "writer"]
            ),
        }
    
    @pytest.mark.asyncio
    async def test_requires_auth_decorator(self, client, users):
        """Test @requires_auth decorator."""
        @requires_auth
        async def protected_func(message: str, user: CurrentUser) -> str:
            return f"{user.username}: {message}"
        
        # Test without authentication
        with pytest.raises(AuthenticationError) as exc:
            await client.call(protected_func, "Hello")
        assert "Authentication required" in str(exc.value)
        
        # Test with authentication
        client.authenticate_as(users["basic"])
        result = await client.call(protected_func, "Hello")
        assert result == "basic: Hello"
    
    @pytest.mark.asyncio
    async def test_requires_permission_single(self, client, users):
        """Test @requires_permission with single permission."""
        @requires_permission("write")
        async def write_func(data: str, user: CurrentUser) -> dict:
            return {"author": user.username, "data": data}
        
        # Test without permission
        client.authenticate_as(users["reader"])
        with pytest.raises(AuthorizationError) as exc:
            await client.call(write_func, "content")
        assert "lacks required permissions: write" in str(exc.value)
        
        # Test with permission
        client.authenticate_as(users["writer"])
        result = await client.call(write_func, "content")
        assert result["author"] == "writer"
        assert result["data"] == "content"
    
    @pytest.mark.asyncio
    async def test_requires_permission_multiple(self, client, users):
        """Test @requires_permission with multiple permissions (OR logic)."""
        @requires_permission("write", "admin")
        async def flexible_func(user: CurrentUser) -> str:
            return f"Accessed by {user.username}"
        
        # Reader can't access (has neither permission)
        client.authenticate_as(users["reader"])
        with pytest.raises(AuthorizationError):
            await client.call(flexible_func)
        
        # Writer can access (has write)
        client.authenticate_as(users["writer"])
        result = await client.call(flexible_func)
        assert result == "Accessed by writer"
        
        # Admin can access (has admin)
        client.authenticate_as(users["admin"])
        result = await client.call(flexible_func)
        assert result == "Accessed by admin"
    
    @pytest.mark.asyncio
    async def test_requires_role(self, client, users):
        """Test @requires_role decorator."""
        @requires_role("admin")
        async def admin_func(action: str, user: CurrentUser) -> dict:
            return {"admin": user.username, "action": action}
        
        # Test without role
        client.authenticate_as(users["writer"])
        with pytest.raises(AuthorizationError) as exc:
            await client.call(admin_func, "delete_all")
        assert "lacks required roles: admin" in str(exc.value)
        
        # Test with role
        client.authenticate_as(users["admin"])
        result = await client.call(admin_func, "delete_all")
        assert result["admin"] == "admin"
        assert result["action"] == "delete_all"
    
    @pytest.mark.asyncio
    async def test_requires_all_permissions(self, client, users):
        """Test @requires_all_permissions decorator (AND logic)."""
        @requires_all_permissions("read", "write", "delete")
        async def full_access_func(user: CurrentUser) -> str:
            return f"Full access for {user.username}"
        
        # Writer has read and write but not delete
        client.authenticate_as(users["writer"])
        with pytest.raises(AuthorizationError) as exc:
            await client.call(full_access_func)
        assert "lacks required permissions: delete" in str(exc.value)
        
        # Admin has all permissions
        client.authenticate_as(users["admin"])
        result = await client.call(full_access_func)
        assert result == "Full access for admin"
    
    @pytest.mark.asyncio
    async def test_stacked_decorators(self, client, users):
        """Test stacking multiple auth decorators."""
        @requires_auth
        @requires_permission("write")
        @requires_role("writer")
        async def strict_func(user: CurrentUser) -> str:
            return f"Strict access for {user.username}"
        
        # Not authenticated
        with pytest.raises(AuthenticationError):
            await client.call(strict_func)
        
        # Authenticated but no permissions/roles
        client.authenticate_as(users["basic"])
        with pytest.raises(AuthorizationError):
            await client.call(strict_func)
        
        # Has permission but not role
        client.authenticate_as(users["reader"]).with_permissions("write")
        with pytest.raises(AuthorizationError):
            await client.call(strict_func)
        
        # Has everything
        client.authenticate_as(users["writer"])
        result = await client.call(strict_func)
        assert result == "Strict access for writer"
    
    @pytest.mark.asyncio
    async def test_decorator_with_sync_function(self, client, users):
        """Test decorators work with sync functions too."""
        @requires_auth
        def sync_protected(user: CurrentUser) -> str:
            return f"Sync: {user.username}"
        
        # Sync functions need special handling in tests
        # In real apps, the framework handles this
        client.authenticate_as(users["basic"])
        
        # For testing sync functions, we need to handle differently
        from whiskey_auth.core import AuthContext
        auth_context = AuthContext(user=users["basic"])
        
        result = sync_protected(__auth_context__=auth_context)
        assert result == "Sync: basic"
    
    @pytest.mark.asyncio
    async def test_current_user_injection(self, client, users):
        """Test CurrentUser type injection."""
        @requires_auth
        @inject
        async def get_user_info(user: CurrentUser) -> dict:
            return {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "permissions": getattr(user, "permissions", []),
                "roles": getattr(user, "roles", [])
            }
        
        client.authenticate_as(users["admin"])
        info = await client.call(get_user_info)
        
        assert info["id"] == 4
        assert info["username"] == "admin"
        assert "admin" in info["permissions"]
        assert "admin" in info["roles"]