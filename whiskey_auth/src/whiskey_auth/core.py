"""Core authentication and authorization abstractions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, TypeVar, runtime_checkable


class AuthenticationError(Exception):
    """Raised when authentication fails."""

    pass


class AuthorizationError(Exception):
    """Raised when authorization fails."""

    pass


@runtime_checkable
class User(Protocol):
    """Protocol for user objects.

    Any object with an 'id' attribute can be used as a User.
    This allows flexibility in user model design.
    """

    id: Any

    # Optional attributes that enhance functionality
    is_active: bool = True
    permissions: list[str] = field(default_factory=list)
    roles: list[str] = field(default_factory=list)


# Type alias for current user injection
CurrentUser = TypeVar("CurrentUser", bound=User)


class AuthProvider(ABC):
    """Base class for authentication providers.

    Authentication providers handle the process of verifying
    user credentials and returning user objects.
    """

    @abstractmethod
    async def authenticate(self, **credentials) -> User | None:
        """Authenticate user with given credentials.

        Args:
            **credentials: Provider-specific credentials

        Returns:
            User object if authentication succeeds, None otherwise
        """
        pass

    async def get_user(self, user_id: Any) -> User | None:
        """Get user by ID.

        Used for session-based auth and token validation.

        Args:
            user_id: User identifier

        Returns:
            User object if found, None otherwise
        """
        return None


@dataclass
class Permission:
    """Represents a permission in the system."""

    name: str
    description: str = ""

    def __str__(self) -> str:
        return self.name

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other) -> bool:
        if isinstance(other, str):
            return self.name == other
        if isinstance(other, Permission):
            return self.name == other.name
        return False


@dataclass
class Role:
    """Represents a role with permissions."""

    name: str
    permissions: set[Permission | str] = field(default_factory=set)
    inherits: list[Role] = field(default_factory=list)
    description: str = ""

    def __post_init__(self):
        """Normalize permissions to Permission objects."""
        normalized = set()
        for perm in self.permissions:
            if isinstance(perm, str):
                normalized.add(Permission(perm))
            else:
                normalized.add(perm)
        self.permissions = normalized

    def get_all_permissions(self) -> set[Permission]:
        """Get all permissions including inherited ones."""
        all_perms = self.permissions.copy()

        for parent_role in self.inherits:
            all_perms.update(parent_role.get_all_permissions())

        return all_perms

    def has_permission(self, permission: Permission | str) -> bool:
        """Check if role has a specific permission."""
        if isinstance(permission, str):
            permission = Permission(permission)

        return permission in self.get_all_permissions()

    def __str__(self) -> str:
        return self.name

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other) -> bool:
        if isinstance(other, str):
            return self.name == other
        if isinstance(other, Role):
            return self.name == other.name
        return False


@dataclass
class AuthContext:
    """Context for the current authentication state."""

    user: User | None = None
    provider: str | None = None
    authenticated_at: datetime | None = None
    permissions_cache: set[Permission] | None = None
    roles_cache: set[Role] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Set authenticated_at if user is provided but authenticated_at is not."""
        if self.user and not self.authenticated_at:
            self.authenticated_at = datetime.now()

    @property
    def is_authenticated(self) -> bool:
        """Check if user is authenticated."""
        return self.user is not None and getattr(self.user, "is_active", True)

    def has_permission(self, permission: Permission | str) -> bool:
        """Check if user has a specific permission."""
        if not self.is_authenticated:
            return False

        # Check direct permissions on user
        user_perms = getattr(self.user, "permissions", [])
        if permission in user_perms:
            return True

        # Check role-based permissions
        if self.roles_cache:
            for role in self.roles_cache:
                if role.has_permission(permission):
                    return True

        return False

    def has_role(self, role: Role | str) -> bool:
        """Check if user has a specific role."""
        if not self.is_authenticated:
            return False

        user_roles = getattr(self.user, "roles", [])
        return role in user_roles or (self.roles_cache and role in self.roles_cache)
