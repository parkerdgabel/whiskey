"""Whiskey Authentication and Authorization Extension.

Provides secure, flexible authentication and authorization capabilities
for Whiskey applications with seamless DI integration.
"""

from whiskey_auth.core import (
    AuthProvider,
    CurrentUser,
    User,
    AuthenticationError,
    AuthorizationError,
    Permission,
    Role,
)
from whiskey_auth.extension import auth_extension
from whiskey_auth.decorators import requires_auth, requires_permission, requires_role
from whiskey_auth.password import PasswordHasher

__all__ = [
    # Core
    "auth_extension",
    "AuthProvider",
    "CurrentUser",
    "User",
    "AuthenticationError",
    "AuthorizationError",
    "Permission",
    "Role",
    # Decorators
    "requires_auth",
    "requires_permission", 
    "requires_role",
    # Utilities
    "PasswordHasher",
]

__version__ = "0.1.0"