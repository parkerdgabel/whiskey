"""Whiskey Auth extension configuration."""

from __future__ import annotations

import inspect
from typing import Callable, TypeVar, get_args, get_origin

from whiskey import Whiskey
from whiskey_auth.core import (
    AuthContext,
    AuthProvider,
    CurrentUser,
    Permission,
    Role,
)
from whiskey_auth.decorators import requires_auth, requires_permission, requires_role
from whiskey_auth.middleware import AuthenticationMiddleware
from whiskey_auth.providers import ProviderRegistry

T = TypeVar("T")


def auth_extension(app: Whiskey) -> None:
    """Configure Whiskey application with authentication support.

    This extension adds:
    - Authentication provider registration
    - User model configuration
    - Permission and role definitions
    - Auth decorators
    - CurrentUser injection
    - Security middleware

    Args:
        app: Whiskey application instance

    Examples:
        >>> app = Whiskey()
        >>> app.use(auth_extension)
        >>>
        >>> @app.user_model
        >>> class User:
        >>>     id: int
        >>>     username: str
        >>>
        >>> @app.auth_provider
        >>> class MyAuthProvider(AuthProvider):
        >>>     async def authenticate(self, **credentials):
        >>>         # Custom auth logic
        >>>         pass
    """
    # Create provider registry
    registry = ProviderRegistry()
    app.container[ProviderRegistry] = registry

    # Create metadata storage for auth configuration
    app._auth_metadata = {}

    # Register auth context as transient - it will be managed by middleware/tests
    app.container.register(AuthContext, AuthContext)

    # Add extension methods using add_decorator
    app.add_decorator("user_model", lambda cls: _register_user_model(app, cls))

    # Auth provider needs special handling for optional name parameter
    def auth_provider_decorator(name_or_cls=None):
        if name_or_cls is None or isinstance(name_or_cls, str):
            # Called as @app.auth_provider or @app.auth_provider("name")
            return _create_auth_provider_decorator(app, registry, name_or_cls)
        else:
            # Called as @app.auth_provider without parentheses
            return _create_auth_provider_decorator(app, registry, None)(name_or_cls)

    app.add_decorator("auth_provider", auth_provider_decorator)
    app.add_decorator("permissions", lambda cls: _register_permissions(app, cls))

    # Role decorator also needs the name parameter
    def role_decorator(name):
        return _create_role_decorator(app, name)

    app.add_decorator("role", role_decorator)

    # Add auth decorators
    app.add_decorator("requires_auth", requires_auth)
    app.add_decorator("requires_permission", requires_permission)
    app.add_decorator("requires_role", requires_role)

    # Add CurrentUser resolver
    _register_current_user_resolver(app)

    # Add middleware hook
    @app.on_startup
    async def setup_auth_middleware():
        """Setup authentication middleware."""
        if hasattr(app, "asgi_manager"):
            # Add auth middleware if ASGI extension is present
            auth_middleware = await app.container.resolve(AuthenticationMiddleware)
            # Register middleware with ASGI manager
            from whiskey_asgi.extension import MiddlewareMetadata

            metadata = MiddlewareMetadata(
                func=auth_middleware.middleware, name="auth", priority=100
            )
            app.asgi_manager.add_middleware(metadata)


def _register_user_model(app: Whiskey, cls: type[T]) -> type[T]:
    """Register user model class.

    Args:
        app: Whiskey application
        cls: User model class

    Returns:
        The registered class
    """
    # Store user model type for later use
    app._auth_metadata["user_model"] = cls

    # Register factory if class has __init__
    if hasattr(cls, "__init__") and not inspect.isabstract(cls):
        app.container[cls] = cls

    return cls


def _create_auth_provider_decorator(
    app: Whiskey, registry: ProviderRegistry, name: str | None
) -> Callable[[type[AuthProvider]], type[AuthProvider]]:
    """Create auth provider registration decorator.

    Args:
        app: Whiskey application
        registry: Provider registry
        name: Optional provider name

    Returns:
        Decorator function
    """

    def decorator(cls: type[AuthProvider]) -> type[AuthProvider]:
        """Register an authentication provider.

        Args:
            cls: AuthProvider subclass

        Returns:
            The registered class
        """
        # Register in DI container
        if name:
            app.container.singleton((AuthProvider, name), cls)
        else:
            app.container.singleton(AuthProvider, cls)

        # Register in provider registry
        if name:
            provider_name = name
        else:
            # Generate name from class name
            class_name = cls.__name__
            # Remove common suffixes
            if class_name.endswith("AuthProvider"):
                provider_name = class_name[:-12]  # Remove "AuthProvider"
            elif class_name.endswith("Provider"):
                provider_name = class_name[:-8]  # Remove "Provider"
            else:
                provider_name = class_name

            # If we're left with too short a name, keep more of the original
            if len(provider_name) <= 2:
                # For "MyAuthProvider", we want "myauth"
                provider_name = class_name.lower()
                provider_name = provider_name.replace("provider", "")

            provider_name = provider_name.lower()
        registry.register(provider_name, cls)

        return cls

    return decorator


def _register_permissions(app: Whiskey, cls: type) -> type:
    """Register permissions class.

    Args:
        app: Whiskey application
        cls: Class containing permission definitions

    Returns:
        The registered class
    """
    permissions = {}

    # Extract permission definitions
    for name, value in inspect.getmembers(cls):
        if not name.startswith("_"):
            if isinstance(value, str):
                permissions[name] = Permission(value)
            elif isinstance(value, Permission):
                permissions[name] = value

    # Store permissions in metadata
    existing_perms = app._auth_metadata.get("permissions", {})
    existing_perms.update(permissions)
    app._auth_metadata["permissions"] = existing_perms

    # Make permissions available on class
    for name, perm in permissions.items():
        setattr(cls, name, perm)

    return cls


def _create_role_decorator(app: Whiskey, name: str) -> Callable[[type], type]:
    """Create role registration decorator.

    Args:
        app: Whiskey application
        name: Role name

    Returns:
        Decorator function
    """

    def decorator(cls: type) -> type:
        """Register a role definition.

        Args:
            cls: Role class

        Returns:
            The registered class
        """
        # Extract role configuration
        permissions = getattr(cls, "permissions", set())
        inherits = getattr(cls, "inherits", [])
        description = getattr(cls, "description", "")

        # Create Role instance
        role = Role(name=name, permissions=permissions, inherits=inherits, description=description)

        # Store role in metadata
        existing_roles = app._auth_metadata.get("roles", {})
        existing_roles[name] = role
        app._auth_metadata["roles"] = existing_roles

        return cls

    return decorator


def _register_current_user_resolver(app: Whiskey) -> None:
    """Register CurrentUser type resolver.

    This allows CurrentUser to be injected into functions and classes.
    """

    # Register a factory for CurrentUser that pulls from AuthContext
    async def current_user_factory():
        """Factory for CurrentUser injection."""
        try:
            auth_context = await app.container.resolve(AuthContext)
            return auth_context.user if auth_context.is_authenticated else None
        except Exception:
            return None

    app.factory(CurrentUser, current_user_factory)

    # Store type checker for middleware to use
    def is_current_user_type(tp: type) -> bool:
        """Check if type is CurrentUser or related."""
        if tp is CurrentUser:
            return True

        origin = get_origin(tp)
        if origin is not None:
            args = get_args(tp)
            if args and CurrentUser in args:
                return True

        return False

    app._auth_metadata["current_user_checker"] = is_current_user_type
