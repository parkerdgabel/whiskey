"""Whiskey Authentication and Authorization Extension.

Provides secure, flexible authentication and authorization capabilities
for Whiskey applications with seamless DI integration.
"""

from whiskey_auth.core import (
    AuthenticationError,
    AuthorizationError,
    AuthProvider,
    CurrentUser,
    Permission,
    Role,
    User,
)
from whiskey_auth.decorators import requires_auth, requires_permission, requires_role
from whiskey_auth.extension import auth_extension
from whiskey_auth.password import PasswordHasher
from whiskey_auth.testing import (
    AuthTestClient,
    AuthTestContainer,
    MockAuthProvider,
    TestUser,
    create_test_user,
)

__all__ = [
    "AuthProvider",
    "AuthTestClient",
    "AuthTestContainer",
    "AuthenticationError",
    "AuthorizationError",
    "CurrentUser",
    "MockAuthProvider",
    "PasswordHasher",
    "Permission",
    "Role",
    "TestUser",
    "User",
    "auth_extension",
    "create_test_user",
    "requires_auth",
    "requires_permission",
    "requires_role",
]

__version__ = "0.1.0"
