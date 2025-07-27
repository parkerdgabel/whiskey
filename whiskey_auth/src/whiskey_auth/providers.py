"""Authentication provider implementations."""

from __future__ import annotations

from abc import abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from jwt.exceptions import InvalidTokenError

from whiskey_auth.core import AuthProvider, User
from whiskey_auth.password import PasswordHasher


class ProviderRegistry:
    """Registry for authentication providers."""

    def __init__(self):
        """Initialize provider registry."""
        self._providers: dict[str, type[AuthProvider]] = {}
        self._instances: dict[str, AuthProvider] = {}

    def register(self, name: str, provider_class: type[AuthProvider]) -> None:
        """Register an authentication provider.

        Args:
            name: Provider name
            provider_class: Provider class
        """
        self._providers[name] = provider_class

    def get(self, name: str) -> type[AuthProvider] | None:
        """Get provider class by name.

        Args:
            name: Provider name

        Returns:
            Provider class or None if not found
        """
        return self._providers.get(name)

    async def get_instance(self, name: str, container=None) -> AuthProvider | None:
        """Get provider instance by name.

        Args:
            name: Provider name
            container: DI container for resolving dependencies

        Returns:
            Provider instance or None if not found
        """
        if name in self._instances:
            return self._instances[name]

        provider_class = self._providers.get(name)
        if not provider_class:
            return None

        # Create instance
        if container:
            instance = await container.resolve(provider_class)
        else:
            instance = provider_class()

        self._instances[name] = instance
        return instance

    def list_providers(self) -> list[str]:
        """List all registered provider names."""
        return list(self._providers.keys())


class PasswordAuthProvider(AuthProvider):
    """Password-based authentication provider.

    This provider authenticates users using username/password combinations.
    It should be used with a user storage backend (database, etc.).
    """

    def __init__(self, hasher: PasswordHasher | None = None):
        """Initialize password auth provider.

        Args:
            hasher: Password hasher instance
        """
        self.hasher = hasher or PasswordHasher()

    @abstractmethod
    async def get_user_by_username(self, username: str) -> User | None:
        """Get user by username.

        This method must be implemented by subclasses to fetch
        users from storage.

        Args:
            username: Username to look up

        Returns:
            User object or None if not found
        """
        pass

    @abstractmethod
    async def get_password_hash(self, user: User) -> str:
        """Get password hash for user.

        This method must be implemented by subclasses to get
        the stored password hash for a user.

        Args:
            user: User object

        Returns:
            Password hash string
        """
        pass

    async def authenticate(self, username: str, password: str) -> User | None:
        """Authenticate user with username and password.

        Args:
            username: Username
            password: Plain text password

        Returns:
            User object if authentication succeeds, None otherwise
        """
        # Get user by username
        user = await self.get_user_by_username(username)
        if not user:
            return None

        # Check if user is active
        if hasattr(user, "is_active") and not user.is_active:
            return None

        # Get and verify password
        password_hash = await self.get_password_hash(user)
        if not password_hash:
            return None

        # Verify password
        is_valid = await self.hasher.verify(password, password_hash)
        if not is_valid:
            return None

        return user

    async def update_password(self, user: User, new_password: str) -> None:
        """Update user's password.

        This is a helper method that can be overridden by subclasses.

        Args:
            user: User object
            new_password: New plain text password
        """
        await self.hasher.hash(new_password)  # Creates the hash, but subclass should store it
        # Subclasses should implement actual storage update
        raise NotImplementedError("Subclass must implement password update")


class JWTAuthProvider(AuthProvider):
    """JWT token-based authentication provider.

    This provider authenticates users using JWT tokens.
    """

    def __init__(
        self,
        secret: str,
        algorithm: str = "HS256",
        issuer: str | None = None,
        audience: str | None = None,
        token_lifetime: timedelta = timedelta(hours=24),
        refresh_token_lifetime: timedelta = timedelta(days=30),
    ):
        """Initialize JWT auth provider.

        Args:
            secret: Secret key for signing tokens
            algorithm: JWT algorithm (default: HS256)
            issuer: Token issuer (for validation)
            audience: Token audience (for validation)
            token_lifetime: Access token lifetime
            refresh_token_lifetime: Refresh token lifetime
        """
        self.secret = secret
        self.algorithm = algorithm
        self.issuer = issuer
        self.audience = audience
        self.token_lifetime = token_lifetime
        self.refresh_token_lifetime = refresh_token_lifetime

    @abstractmethod
    async def get_user_by_id(self, user_id: Any) -> User | None:
        """Get user by ID.

        This method must be implemented by subclasses to fetch
        users from storage.

        Args:
            user_id: User ID from token

        Returns:
            User object or None if not found
        """
        pass

    async def authenticate(self, token: str) -> User | None:
        """Authenticate user with JWT token.

        Args:
            token: JWT token string

        Returns:
            User object if authentication succeeds, None otherwise
        """
        try:
            # Decode token
            payload = self.decode_token(token)
            if not payload:
                return None

            # Get user ID from payload
            user_id = payload.get("sub")  # Subject claim
            if not user_id:
                return None

            # Get user by ID
            user = await self.get_user_by_id(user_id)
            if not user:
                return None

            # Check if user is active
            if hasattr(user, "is_active") and not user.is_active:
                return None

            return user

        except Exception:
            return None

    def create_token(
        self,
        user: User,
        token_type: str = "access",
        additional_claims: dict[str, Any] | None = None,
    ) -> str:
        """Create JWT token for user.

        Args:
            user: User object
            token_type: Token type (access or refresh)
            additional_claims: Additional claims to include

        Returns:
            JWT token string
        """
        now = datetime.now(timezone.utc)

        # Determine expiration based on token type
        if token_type == "refresh":
            exp = now + self.refresh_token_lifetime
        else:
            exp = now + self.token_lifetime

        # Build payload
        payload = {
            "sub": str(user.id),  # Subject (user ID)
            "iat": now,  # Issued at
            "exp": exp,  # Expiration
            "type": token_type,  # Token type
        }

        # Add optional claims
        if self.issuer:
            payload["iss"] = self.issuer
        if self.audience:
            payload["aud"] = self.audience

        # Add user info
        if hasattr(user, "username"):
            payload["username"] = user.username
        if hasattr(user, "email"):
            payload["email"] = user.email

        # Add additional claims
        if additional_claims:
            payload.update(additional_claims)

        # Create token
        return jwt.encode(payload, self.secret, algorithm=self.algorithm)

    def decode_token(self, token: str) -> dict[str, Any] | None:
        """Decode and validate JWT token.

        Args:
            token: JWT token string

        Returns:
            Token payload or None if invalid
        """
        try:
            # Decode with validation
            payload = jwt.decode(
                token,
                self.secret,
                algorithms=[self.algorithm],
                issuer=self.issuer,
                audience=self.audience,
            )
            return payload

        except InvalidTokenError:
            return None

    def refresh_token(self, refresh_token: str) -> tuple[str, str] | None:
        """Create new access token from refresh token.

        Args:
            refresh_token: Refresh token string

        Returns:
            Tuple of (access_token, refresh_token) or None if invalid
        """
        # Decode refresh token
        payload = self.decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            return None

        # Get user ID
        user_id = payload.get("sub")
        if not user_id:
            return None

        # Note: In a real implementation, you'd want to:
        # 1. Check if refresh token is in allowlist
        # 2. Get fresh user data
        # 3. Possibly rotate refresh token

        # For now, just create new tokens with same user ID
        user_stub = type("User", (), {"id": user_id})()

        access_token = self.create_token(user_stub, "access")
        new_refresh_token = self.create_token(user_stub, "refresh")

        return access_token, new_refresh_token
