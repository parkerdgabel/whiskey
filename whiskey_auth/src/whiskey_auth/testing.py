"""Testing utilities for Whiskey Auth."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Type
from datetime import datetime

import pytest

from whiskey import Container, Whiskey
from whiskey_auth.core import (
    AuthContext,
    AuthProvider,
    Permission,
    Role,
    User,
)
from whiskey_auth.password import PasswordHasher


@dataclass
class TestUser:
    """Test user for authentication testing."""
    id: int
    username: str
    email: str = ""
    password_hash: str = ""
    is_active: bool = True
    permissions: list[str] = field(default_factory=list)
    roles: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def create_test_user(
    id: int = 1,
    username: str = "testuser",
    email: str | None = None,
    password: str | None = None,
    is_active: bool = True,
    permissions: list[str] | None = None,
    roles: list[str] | None = None,
    **kwargs
) -> TestUser:
    """Create a test user with sensible defaults.
    
    Args:
        id: User ID
        username: Username
        email: Email address (defaults to username@example.com)
        password: Plain text password (will be hashed)
        is_active: Whether user is active
        permissions: List of permission names
        roles: List of role names
        **kwargs: Additional metadata
        
    Returns:
        TestUser instance
    """
    if email is None:
        email = f"{username}@example.com"
    
    password_hash = ""
    if password:
        hasher = PasswordHasher()
        # Sync wrapper for testing
        import asyncio
        password_hash = asyncio.run(hasher.hash(password))
    
    return TestUser(
        id=id,
        username=username,
        email=email,
        password_hash=password_hash,
        is_active=is_active,
        permissions=permissions or [],
        roles=roles or [],
        metadata=kwargs
    )


class MockAuthProvider(AuthProvider):
    """Mock authentication provider for testing."""
    
    def __init__(self, users: list[User] | None = None):
        """Initialize mock provider.
        
        Args:
            users: List of users that can authenticate
        """
        self.users = users or []
        self.authenticate_calls = []
        self.get_user_calls = []
    
    async def authenticate(self, **credentials) -> User | None:
        """Mock authenticate method."""
        self.authenticate_calls.append(credentials)
        
        # Simple username/password check
        username = credentials.get("username")
        password = credentials.get("password")
        
        if username and password:
            for user in self.users:
                if user.username == username:
                    # Simple password check (in real tests, might verify hash)
                    if hasattr(user, "password") and user.password == password:
                        return user
                    elif password == "password":  # Default test password
                        return user
        
        return None
    
    async def get_user(self, user_id: Any) -> User | None:
        """Mock get_user method."""
        self.get_user_calls.append(user_id)
        
        for user in self.users:
            if user.id == user_id:
                return user
        
        return None


class AuthTestClient:
    """Test client for auth-protected endpoints."""
    
    def __init__(self, app: Whiskey | None = None):
        """Initialize test client.
        
        Args:
            app: Whiskey application instance
        """
        self.app = app
        self._auth_context: AuthContext | None = None
    
    def authenticate_as(self, user: User | None) -> AuthTestClient:
        """Set the authenticated user for subsequent requests.
        
        Args:
            user: User to authenticate as (None to clear auth)
            
        Returns:
            Self for chaining
        """
        if user:
            self._auth_context = AuthContext(
                user=user,
                provider="test",
                authenticated_at=datetime.now()
            )
        else:
            self._auth_context = None
        
        return self
    
    def with_permissions(self, *permissions: str) -> AuthTestClient:
        """Add permissions to the current auth context.
        
        Args:
            *permissions: Permission names to add
            
        Returns:
            Self for chaining
        """
        if self._auth_context and self._auth_context.user:
            # Add permissions to user
            user_perms = getattr(self._auth_context.user, "permissions", [])
            for perm in permissions:
                if perm not in user_perms:
                    user_perms.append(perm)
            self._auth_context.user.permissions = user_perms
        
        return self
    
    def with_roles(self, *roles: str) -> AuthTestClient:
        """Add roles to the current auth context.
        
        Args:
            *roles: Role names to add
            
        Returns:
            Self for chaining
        """
        if self._auth_context and self._auth_context.user:
            # Add roles to user
            user_roles = getattr(self._auth_context.user, "roles", [])
            for role in roles:
                if role not in user_roles:
                    user_roles.append(role)
            self._auth_context.user.roles = user_roles
        
        return self
    
    async def call(self, func, *args, **kwargs):
        """Call a function with the current auth context.
        
        Args:
            func: Function to call
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Function result
        """
        # Inject auth context
        if self._auth_context:
            kwargs["__auth_context__"] = self._auth_context
        
        # Call function
        return await func(*args, **kwargs)


class AuthTestContainer(Container):
    """Test container with auth mocking support."""
    
    def __init__(self, *args, **kwargs):
        """Initialize test container."""
        super().__init__(*args, **kwargs)
        self._test_auth_context: AuthContext | None = None
        self._test_user: User | None = None
    
    def set_test_user(self, user: User | None) -> None:
        """Set the test user for CurrentUser injection.
        
        Args:
            user: Test user (None to clear)
        """
        self._test_user = user
        if user:
            self._test_auth_context = AuthContext(
                user=user,
                provider="test",
                authenticated_at=datetime.now()
            )
        else:
            self._test_auth_context = None
    
    async def resolve(self, type_hint: Type[T], **kwargs) -> T:
        """Resolve with test user support."""
        # Handle CurrentUser/User types
        if type_hint.__name__ in ("CurrentUser", "User"):
            return self._test_user
        
        # Handle AuthContext
        if type_hint is AuthContext and self._test_auth_context:
            return self._test_auth_context
        
        # Default resolution
        return await super().resolve(type_hint, **kwargs)


# Pytest fixtures
@pytest.fixture
def test_user():
    """Create a test user."""
    return create_test_user(
        id=1,
        username="testuser",
        email="test@example.com",
        password="testpass123"
    )


@pytest.fixture
def admin_user():
    """Create an admin test user."""
    return create_test_user(
        id=2,
        username="admin",
        email="admin@example.com",
        password="adminpass123",
        permissions=["admin", "read", "write", "delete"],
        roles=["admin"]
    )


@pytest.fixture
def auth_client():
    """Create an auth test client."""
    return AuthTestClient()


@pytest.fixture
def mock_auth_provider(test_user, admin_user):
    """Create a mock auth provider."""
    return MockAuthProvider(users=[test_user, admin_user])


@pytest.fixture
def auth_test_container():
    """Create a test container with auth support."""
    return AuthTestContainer()


# Test helpers
def assert_authenticated(auth_context: AuthContext, user: User | None = None):
    """Assert that auth context is authenticated.
    
    Args:
        auth_context: Auth context to check
        user: Expected user (optional)
    """
    assert auth_context.is_authenticated, "User should be authenticated"
    if user:
        assert auth_context.user.id == user.id, f"Expected user {user.id}, got {auth_context.user.id}"


def assert_not_authenticated(auth_context: AuthContext):
    """Assert that auth context is not authenticated.
    
    Args:
        auth_context: Auth context to check
    """
    assert not auth_context.is_authenticated, "User should not be authenticated"


def assert_has_permission(auth_context: AuthContext, permission: str | Permission):
    """Assert that user has a permission.
    
    Args:
        auth_context: Auth context to check
        permission: Permission to check
    """
    assert auth_context.has_permission(permission), f"User should have permission: {permission}"


def assert_lacks_permission(auth_context: AuthContext, permission: str | Permission):
    """Assert that user lacks a permission.
    
    Args:
        auth_context: Auth context to check
        permission: Permission to check
    """
    assert not auth_context.has_permission(permission), f"User should not have permission: {permission}"


def assert_has_role(auth_context: AuthContext, role: str | Role):
    """Assert that user has a role.
    
    Args:
        auth_context: Auth context to check
        role: Role to check
    """
    assert auth_context.has_role(role), f"User should have role: {role}"


def assert_lacks_role(auth_context: AuthContext, role: str | Role):
    """Assert that user lacks a role.
    
    Args:
        auth_context: Auth context to check
        role: Role to check
    """
    assert not auth_context.has_role(role), f"User should not have role: {role}"