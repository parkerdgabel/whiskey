"""Tests for the testing utilities themselves."""

import pytest

from whiskey_auth import (
    AuthTestClient,
    AuthTestContainer,
    MockAuthProvider,
    create_test_user,
)
from whiskey_auth.core import AuthContext
from whiskey_auth.testing import (
    assert_authenticated,
    assert_has_permission,
    assert_has_role,
    assert_lacks_permission,
    assert_lacks_role,
    assert_not_authenticated,
)


class TestTestUser:
    """Test the TestUser creation utility."""

    def test_create_test_user_defaults(self):
        """Test creating user with defaults."""
        user = create_test_user()

        assert user.id == 1
        assert user.username == "testuser"
        assert user.email == "testuser@example.com"
        assert user.password_hash == ""
        assert user.is_active is True
        assert user.permissions == []
        assert user.roles == []
        assert user.metadata == {}

    def test_create_test_user_custom(self):
        """Test creating user with custom values."""
        user = create_test_user(
            id=99,
            username="custom",
            email="custom@test.com",
            password="secret123",
            is_active=False,
            permissions=["read", "write"],
            roles=["editor"],
            custom_field="value",
        )

        assert user.id == 99
        assert user.username == "custom"
        assert user.email == "custom@test.com"
        assert user.password_hash != ""  # Password was hashed
        assert user.is_active is False
        assert user.permissions == ["read", "write"]
        assert user.roles == ["editor"]
        assert user.metadata == {"custom_field": "value"}

    def test_create_test_user_password_hashing(self):
        """Test password hashing in test user creation."""
        user1 = create_test_user(password="testpass")
        user2 = create_test_user(password="testpass")

        # Passwords are hashed
        assert user1.password_hash != ""
        assert user2.password_hash != ""
        # Different salts mean different hashes
        assert user1.password_hash != user2.password_hash


class TestMockAuthProvider:
    """Test the MockAuthProvider."""

    @pytest.fixture
    def mock_provider(self):
        """Create mock provider with test users."""
        users = [
            create_test_user(id=1, username="alice", password="alice123"),
            create_test_user(id=2, username="bob", password="bob123"),
        ]
        # Hack to store plaintext passwords for testing
        users[0].password = "alice123"
        users[1].password = "bob123"

        return MockAuthProvider(users=users)

    @pytest.mark.asyncio
    async def test_authenticate_success(self, mock_provider):
        """Test successful authentication."""
        user = await mock_provider.authenticate(username="alice", password="alice123")

        assert user is not None
        assert user.username == "alice"
        assert len(mock_provider.authenticate_calls) == 1

    @pytest.mark.asyncio
    async def test_authenticate_default_password(self, mock_provider):
        """Test authentication with default test password."""
        user = await mock_provider.authenticate(
            username="alice",
            password="password",  # Default test password
        )

        assert user is not None
        assert user.username == "alice"

    @pytest.mark.asyncio
    async def test_authenticate_failure(self, mock_provider):
        """Test failed authentication."""
        # Wrong username
        user = await mock_provider.authenticate(username="charlie", password="password")
        assert user is None

        # Wrong password
        user = await mock_provider.authenticate(username="alice", password="wrongpass")
        assert user is None

    @pytest.mark.asyncio
    async def test_get_user(self, mock_provider):
        """Test getting user by ID."""
        user = await mock_provider.get_user(1)
        assert user is not None
        assert user.username == "alice"
        assert len(mock_provider.get_user_calls) == 1

        # Non-existent user
        user = await mock_provider.get_user(999)
        assert user is None

    @pytest.mark.asyncio
    async def test_call_tracking(self, mock_provider):
        """Test that calls are tracked."""
        await mock_provider.authenticate(username="test1", password="pass1")
        await mock_provider.authenticate(username="test2", password="pass2")
        await mock_provider.get_user(1)
        await mock_provider.get_user(2)

        assert len(mock_provider.authenticate_calls) == 2
        assert mock_provider.authenticate_calls[0]["username"] == "test1"
        assert mock_provider.authenticate_calls[1]["username"] == "test2"

        assert len(mock_provider.get_user_calls) == 2
        assert mock_provider.get_user_calls[0] == 1
        assert mock_provider.get_user_calls[1] == 2


class TestAuthTestClient:
    """Test the AuthTestClient."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return AuthTestClient()

    @pytest.fixture
    def test_user(self):
        """Create test user."""
        return create_test_user(username="testuser", permissions=["read"], roles=["user"])

    def test_authenticate_as(self, client, test_user):
        """Test setting authenticated user."""
        # Initially no auth
        assert client._auth_context is None

        # Set user
        client.authenticate_as(test_user)
        assert client._auth_context is not None
        assert client._auth_context.user == test_user
        assert client._auth_context.provider == "test"

        # Clear auth
        client.authenticate_as(None)
        assert client._auth_context is None

    def test_with_permissions(self, client, test_user):
        """Test adding permissions."""
        client.authenticate_as(test_user)

        # Initial permissions
        assert test_user.permissions == ["read"]

        # Add permissions
        client.with_permissions("write", "delete")
        assert "write" in test_user.permissions
        assert "delete" in test_user.permissions
        assert "read" in test_user.permissions  # Original still there

    def test_with_roles(self, client, test_user):
        """Test adding roles."""
        client.authenticate_as(test_user)

        # Initial roles
        assert test_user.roles == ["user"]

        # Add roles
        client.with_roles("admin", "moderator")
        assert "admin" in test_user.roles
        assert "moderator" in test_user.roles
        assert "user" in test_user.roles  # Original still there

    def test_chaining(self, client, test_user):
        """Test method chaining."""
        result = client.authenticate_as(test_user).with_permissions("write").with_roles("editor")

        assert result is client  # Returns self
        assert "write" in test_user.permissions
        assert "editor" in test_user.roles

    @pytest.mark.asyncio
    async def test_call_with_auth(self, client, test_user):
        """Test calling function with auth context."""
        client.authenticate_as(test_user)

        async def test_func(message: str, **kwargs) -> dict:
            auth_context = kwargs.get("__auth_context__")
            return {
                "message": message,
                "has_auth": auth_context is not None,
                "user": auth_context.user.username if auth_context else None,
            }

        result = await client.call(test_func, "Hello")

        assert result["message"] == "Hello"
        assert result["has_auth"] is True
        assert result["user"] == "testuser"


class TestAuthTestContainer:
    """Test the AuthTestContainer."""

    @pytest.fixture
    def container(self):
        """Create test container."""
        return AuthTestContainer()

    @pytest.fixture
    def test_user(self):
        """Create test user."""
        return create_test_user(username="containeruser")

    def test_set_test_user(self, container, test_user):
        """Test setting test user."""
        # Initially no user
        assert container._test_user is None
        assert container._test_auth_context is None

        # Set user
        container.set_test_user(test_user)
        assert container._test_user == test_user
        assert container._test_auth_context is not None
        assert container._test_auth_context.user == test_user

        # Clear user
        container.set_test_user(None)
        assert container._test_user is None
        assert container._test_auth_context is None

    @pytest.mark.asyncio
    async def test_resolve_current_user(self, container, test_user):
        """Test resolving CurrentUser type."""
        from whiskey_auth.core import User as UserType

        # No user set
        resolved = await container.resolve(UserType)
        assert resolved is None

        # With user set
        container.set_test_user(test_user)
        resolved = await container.resolve(UserType)
        assert resolved == test_user

    @pytest.mark.asyncio
    async def test_resolve_auth_context(self, container, test_user):
        """Test resolving AuthContext."""
        # No user set - would normally create empty context
        # but our test container returns None for simplicity

        # With user set
        container.set_test_user(test_user)
        resolved = await container.resolve(AuthContext)
        assert resolved is not None
        assert resolved.user == test_user
        assert resolved.is_authenticated is True


class TestAssertionHelpers:
    """Test assertion helper functions."""

    def test_assert_authenticated(self):
        """Test authentication assertions."""
        user = create_test_user(username="testuser")
        auth_context = AuthContext(user=user)

        # Should not raise
        assert_authenticated(auth_context)
        assert_authenticated(auth_context, user)

        # Should raise on empty context
        empty_context = AuthContext()
        with pytest.raises(AssertionError):
            assert_authenticated(empty_context)

    def test_assert_not_authenticated(self):
        """Test not authenticated assertion."""
        empty_context = AuthContext()
        assert_not_authenticated(empty_context)  # Should not raise

        user = create_test_user()
        auth_context = AuthContext(user=user)
        with pytest.raises(AssertionError):
            assert_not_authenticated(auth_context)

    def test_permission_assertions(self):
        """Test permission assertions."""
        user = create_test_user(permissions=["read", "write"])
        auth_context = AuthContext(user=user)

        # Has permissions
        assert_has_permission(auth_context, "read")
        assert_has_permission(auth_context, "write")

        # Lacks permissions
        assert_lacks_permission(auth_context, "delete")
        assert_lacks_permission(auth_context, "admin")

        # Wrong assertions should fail
        with pytest.raises(AssertionError):
            assert_has_permission(auth_context, "delete")

        with pytest.raises(AssertionError):
            assert_lacks_permission(auth_context, "read")

    def test_role_assertions(self):
        """Test role assertions."""
        user = create_test_user(roles=["user", "editor"])
        auth_context = AuthContext(user=user)

        # Has roles
        assert_has_role(auth_context, "user")
        assert_has_role(auth_context, "editor")

        # Lacks roles
        assert_lacks_role(auth_context, "admin")
        assert_lacks_role(auth_context, "moderator")

        # Wrong assertions should fail
        with pytest.raises(AssertionError):
            assert_has_role(auth_context, "admin")

        with pytest.raises(AssertionError):
            assert_lacks_role(auth_context, "user")
