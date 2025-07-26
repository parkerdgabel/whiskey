"""Whiskey Auth extension configuration."""

from __future__ import annotations

import inspect
from typing import Any, Callable, Type, TypeVar, get_args, get_origin

from whiskey import Whiskey, singleton, Container

from whiskey_auth.core import (
    AuthContext,
    AuthProvider,
    CurrentUser,
    Permission,
    Role,
    User,
)
from whiskey_auth.decorators import requires_auth, requires_permission, requires_role
from whiskey_auth.middleware import AuthenticationMiddleware, create_auth_context
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
    
    # Register auth context as scoped
    app.container.scoped(AuthContext)
    
    # Add extension methods
    app.user_model = lambda cls: _register_user_model(app, cls)
    app.auth_provider = lambda name=None: _create_auth_provider_decorator(app, registry, name)
    app.permissions = lambda cls: _register_permissions(app, cls)
    app.role = lambda name: _create_role_decorator(app, name)
    
    # Add auth decorators
    app.requires_auth = requires_auth
    app.requires_permission = requires_permission
    app.requires_role = requires_role
    
    # Add CurrentUser resolver
    _register_current_user_resolver(app)
    
    # Add middleware hook
    @app.on_startup
    async def setup_auth_middleware():
        """Setup authentication middleware."""
        if hasattr(app, "_middleware_stack"):
            # Add auth middleware if ASGI extension is present
            auth_middleware = await app.container.resolve(AuthenticationMiddleware)
            app._middleware_stack.append(auth_middleware)


def _register_user_model(app: Whiskey, cls: Type[T]) -> Type[T]:
    """Register user model class.
    
    Args:
        app: Whiskey application
        cls: User model class
        
    Returns:
        The registered class
    """
    # Store user model type for later use
    app.container["__auth_user_model__"] = cls
    
    # Register factory if class has __init__
    if hasattr(cls, "__init__") and not inspect.isabstract(cls):
        app.container[cls] = cls
    
    return cls


def _create_auth_provider_decorator(
    app: Whiskey,
    registry: ProviderRegistry,
    name: str | None
) -> Callable[[Type[AuthProvider]], Type[AuthProvider]]:
    """Create auth provider registration decorator.
    
    Args:
        app: Whiskey application
        registry: Provider registry
        name: Optional provider name
        
    Returns:
        Decorator function
    """
    def decorator(cls: Type[AuthProvider]) -> Type[AuthProvider]:
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
        provider_name = name or cls.__name__.lower().replace("auth", "").replace("provider", "")
        registry.register(provider_name, cls)
        
        return cls
    
    return decorator


def _register_permissions(app: Whiskey, cls: Type) -> Type:
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
    
    # Store permissions
    app.container["__auth_permissions__"] = permissions
    
    # Make permissions available on class
    for name, perm in permissions.items():
        setattr(cls, name, perm)
    
    return cls


def _create_role_decorator(app: Whiskey, name: str) -> Callable[[Type], Type]:
    """Create role registration decorator.
    
    Args:
        app: Whiskey application
        name: Role name
        
    Returns:
        Decorator function
    """
    def decorator(cls: Type) -> Type:
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
        role = Role(
            name=name,
            permissions=permissions,
            inherits=inherits,
            description=description
        )
        
        # Store role
        roles = app.container.get("__auth_roles__", {})
        roles[name] = role
        app.container["__auth_roles__"] = roles
        
        return cls
    
    return decorator


def _register_current_user_resolver(app: Whiskey) -> None:
    """Register CurrentUser type resolver.
    
    This allows CurrentUser to be injected into functions and classes.
    """
    async def resolve_current_user(container: Container) -> User | None:
        """Resolve current user from auth context."""
        try:
            auth_context = await container.resolve(AuthContext)
            return auth_context.user if auth_context.is_authenticated else None
        except Exception:
            return None
    
    # Register resolver for CurrentUser type and its variations
    app.container._resolvers[CurrentUser] = resolve_current_user
    app.container._resolvers[User] = resolve_current_user
    
    # Also handle Optional[CurrentUser] and similar
    def is_current_user_type(tp: type) -> bool:
        """Check if type is CurrentUser or related."""
        if tp is CurrentUser or tp is User:
            return True
        
        origin = get_origin(tp)
        if origin is not None:
            args = get_args(tp)
            if args and (CurrentUser in args or User in args):
                return True
        
        return False
    
    # Store type checker for middleware to use
    app.container["__auth_current_user_checker__"] = is_current_user_type