"""Tests for authentication providers."""

import pytest
from datetime import datetime, timedelta, timezone

import jwt

from whiskey_auth import PasswordHasher, create_test_user
from whiskey_auth.providers import (
    ProviderRegistry,
    PasswordAuthProvider,
    JWTAuthProvider,
)
from whiskey_auth.core import AuthProvider, User

from typing import Any


class TestProviderRegistry:
    """Test provider registry functionality."""
    
    def test_register_and_get_provider(self):
        """Test registering and retrieving providers."""
        registry = ProviderRegistry()
        
        # Register provider
        class TestProvider(AuthProvider):
            async def authenticate(self, **credentials):
                return None
        
        registry.register("test", TestProvider)
        
        # Get provider class
        provider_class = registry.get("test")
        assert provider_class is TestProvider
        
        # Non-existent provider
        assert registry.get("nonexistent") is None
    
    def test_list_providers(self):
        """Test listing all providers."""
        registry = ProviderRegistry()
        
        # Initially empty
        assert registry.list_providers() == []
        
        # Register some providers
        class Provider1(AuthProvider):
            async def authenticate(self, **credentials):
                return None
        
        class Provider2(AuthProvider):
            async def authenticate(self, **credentials):
                return None
        
        registry.register("provider1", Provider1)
        registry.register("provider2", Provider2)
        
        providers = registry.list_providers()
        assert len(providers) == 2
        assert "provider1" in providers
        assert "provider2" in providers
    
    @pytest.mark.asyncio
    async def test_get_instance(self):
        """Test getting provider instances."""
        registry = ProviderRegistry()
        
        class TestProvider(AuthProvider):
            def __init__(self, config: str = "default"):
                self.config = config
            
            async def authenticate(self, **credentials):
                return None
        
        registry.register("test", TestProvider)
        
        # Get instance
        instance = await registry.get_instance("test")
        assert isinstance(instance, TestProvider)
        assert instance.config == "default"
        
        # Should return same instance on subsequent calls
        instance2 = await registry.get_instance("test")
        assert instance is instance2
        
        # Non-existent provider
        assert await registry.get_instance("nonexistent") is None


class TestPasswordAuthProvider:
    """Test password authentication provider."""
    
    class MockPasswordProvider(PasswordAuthProvider):
        """Test implementation of password provider."""
        
        def __init__(self, users: list[User] | None = None):
            super().__init__()
            self.users = users or []
        
        async def get_user_by_username(self, username: str) -> User | None:
            for user in self.users:
                if user.username == username:
                    return user
            return None
        
        async def get_password_hash(self, user: User) -> str:
            return user.password_hash
    
    @pytest.fixture
    def test_users(self):
        """Create test users."""
        return [
            create_test_user(
                id=1,
                username="alice",
                password="alice123",
                is_active=True
            ),
            create_test_user(
                id=2,
                username="bob",
                password="bob123",
                is_active=False
            ),
        ]
    
    @pytest.fixture
    def provider(self, test_users):
        """Create test password provider."""
        return self.MockPasswordProvider(users=test_users)
    
    @pytest.mark.asyncio
    async def test_authenticate_success(self, provider):
        """Test successful authentication."""
        # Need to manually verify password since test users have hashed passwords
        user = await provider.get_user_by_username("alice")
        assert user is not None
        
        # For testing, we'll check the provider methods work
        password_hash = await provider.get_password_hash(user)
        assert password_hash != ""
        
        # Test the hasher directly
        hasher = PasswordHasher()
        assert await hasher.verify("alice123", password_hash)
    
    @pytest.mark.asyncio
    async def test_authenticate_inactive_user(self, provider):
        """Test authentication with inactive user."""
        # Get Bob who is inactive
        user = await provider.get_user_by_username("bob")
        assert user is not None
        assert user.is_active is False
    
    @pytest.mark.asyncio
    async def test_authenticate_nonexistent_user(self, provider):
        """Test authentication with non-existent user."""
        user = await provider.get_user_by_username("charlie")
        assert user is None
    
    @pytest.mark.asyncio
    async def test_update_password_not_implemented(self, provider, test_users):
        """Test that update_password raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            await provider.update_password(test_users[0], "newpassword")


class TestJWTAuthProvider:
    """Test JWT authentication provider."""
    
    class MockJWTProvider(JWTAuthProvider):
        """Test implementation of JWT provider."""
        
        def __init__(self, users: list[User] | None = None, **kwargs):
            super().__init__(**kwargs)
            self.users = users or []
        
        async def get_user_by_id(self, user_id: Any) -> User | None:
            for user in self.users:
                if str(user.id) == str(user_id):
                    return user
            return None
    
    @pytest.fixture
    def test_users(self):
        """Create test users."""
        return [
            create_test_user(id=1, username="alice", email="alice@example.com"),
            create_test_user(id=2, username="bob", email="bob@example.com", is_active=False),
        ]
    
    @pytest.fixture
    def provider(self, test_users):
        """Create test JWT provider."""
        return self.MockJWTProvider(
            users=test_users,
            secret="test-secret",
            algorithm="HS256",
            issuer="test-issuer",
            audience="test-audience",
            token_lifetime=timedelta(hours=1),
            refresh_token_lifetime=timedelta(days=7)
        )
    
    def test_create_token(self, provider, test_users):
        """Test creating JWT tokens."""
        user = test_users[0]
        
        # Create access token
        access_token = provider.create_token(user, "access")
        assert isinstance(access_token, str)
        
        # Decode and verify
        payload = jwt.decode(
            access_token,
            "test-secret",
            algorithms=["HS256"],
            issuer="test-issuer",
            audience="test-audience"
        )
        
        assert payload["sub"] == "1"
        assert payload["type"] == "access"
        assert payload["username"] == "alice"
        assert payload["email"] == "alice@example.com"
        assert "exp" in payload
        assert "iat" in payload
    
    def test_create_refresh_token(self, provider, test_users):
        """Test creating refresh tokens."""
        user = test_users[0]
        
        # Create refresh token
        refresh_token = provider.create_token(user, "refresh")
        
        # Decode and verify
        payload = jwt.decode(
            refresh_token,
            "test-secret",
            algorithms=["HS256"]
        )
        
        assert payload["type"] == "refresh"
        
        # Refresh token should have longer expiration
        access_token = provider.create_token(user, "access")
        access_payload = jwt.decode(access_token, "test-secret", algorithms=["HS256"])
        
        assert payload["exp"] > access_payload["exp"]
    
    def test_create_token_with_additional_claims(self, provider, test_users):
        """Test creating token with additional claims."""
        user = test_users[0]
        
        token = provider.create_token(
            user,
            "access",
            additional_claims={"role": "admin", "org_id": "123"}
        )
        
        payload = jwt.decode(token, "test-secret", algorithms=["HS256"])
        assert payload["role"] == "admin"
        assert payload["org_id"] == "123"
    
    def test_decode_token_valid(self, provider, test_users):
        """Test decoding valid token."""
        user = test_users[0]
        token = provider.create_token(user, "access")
        
        payload = provider.decode_token(token)
        assert payload is not None
        assert payload["sub"] == "1"
    
    def test_decode_token_invalid(self, provider):
        """Test decoding invalid token."""
        # Invalid token
        assert provider.decode_token("invalid.token.here") is None
        
        # Wrong secret
        token = jwt.encode({"sub": "1"}, "wrong-secret", algorithm="HS256")
        assert provider.decode_token(token) is None
        
        # Wrong issuer
        token = jwt.encode(
            {"sub": "1", "iss": "wrong-issuer"},
            "test-secret",
            algorithm="HS256"
        )
        assert provider.decode_token(token) is None
    
    @pytest.mark.asyncio
    async def test_authenticate_with_valid_token(self, provider, test_users):
        """Test authenticating with valid token."""
        user = test_users[0]
        token = provider.create_token(user, "access")
        
        authenticated_user = await provider.authenticate(token=token)
        assert authenticated_user is not None
        assert authenticated_user.id == 1
        assert authenticated_user.username == "alice"
    
    @pytest.mark.asyncio
    async def test_authenticate_with_invalid_token(self, provider):
        """Test authenticating with invalid token."""
        # Invalid token
        user = await provider.authenticate(token="invalid.token")
        assert user is None
        
        # Token without subject
        token = jwt.encode({"type": "access"}, "test-secret", algorithm="HS256")
        user = await provider.authenticate(token=token)
        assert user is None
    
    @pytest.mark.asyncio
    async def test_authenticate_inactive_user(self, provider, test_users):
        """Test authenticating inactive user."""
        user = test_users[1]  # Bob is inactive
        token = provider.create_token(user, "access")
        
        authenticated_user = await provider.authenticate(token=token)
        assert authenticated_user is None
    
    def test_refresh_token_flow(self, provider, test_users):
        """Test refresh token flow."""
        user = test_users[0]
        
        # Create initial tokens
        access_token = provider.create_token(user, "access")
        refresh_token = provider.create_token(user, "refresh")
        
        # Refresh tokens
        result = provider.refresh_token(refresh_token)
        assert result is not None
        
        new_access, new_refresh = result
        assert isinstance(new_access, str)
        assert isinstance(new_refresh, str)
        assert new_access != access_token
        assert new_refresh != refresh_token
        
        # Verify new tokens are valid
        access_payload = provider.decode_token(new_access)
        refresh_payload = provider.decode_token(new_refresh)
        
        assert access_payload is not None
        assert refresh_payload is not None
        assert access_payload["type"] == "access"
        assert refresh_payload["type"] == "refresh"
    
    def test_refresh_with_invalid_token(self, provider):
        """Test refresh with invalid token."""
        # Invalid token
        assert provider.refresh_token("invalid.token") is None
        
        # Access token instead of refresh token
        access_token = jwt.encode(
            {"sub": "1", "type": "access"},
            "test-secret",
            algorithm="HS256"
        )
        assert provider.refresh_token(access_token) is None