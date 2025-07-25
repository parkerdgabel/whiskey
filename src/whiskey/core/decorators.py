"""Simple decorators for dependency injection."""

from __future__ import annotations

import asyncio
import functools
import inspect
from typing import Any, Callable, TypeVar, get_args, get_origin

from whiskey.core.container import Container, get_current_container

T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])

# Global default container
_default_container: Container | None = None


class Inject:
    """Marker for explicit dependency injection in type annotations.
    
    Used with Annotated to distinguish injection targets from regular type hints:
    
    Example:
        from typing import Annotated
        
        class Service:
            def __init__(self, 
                        # This will be injected
                        db: Annotated[Database, Inject()],
                        # This is just a type hint
                        name: str):
                self.db = db
                self.name = name
    """
    
    def __init__(self, name: str | None = None):
        """Initialize injection marker.
        
        Args:
            name: Optional service name for named dependencies
        """
        self.name = name
    
    def __repr__(self):
        if self.name:
            return f"Inject(name='{self.name}')"
        return "Inject()"


def get_default_container() -> Container:
    """Get or create the default container.
    
    The default container is a global instance used by decorators when
    no explicit container is provided. It's created on first access.
    
    Returns:
        The global default Container instance
        
    Note:
        In applications, prefer using Application.container or explicitly
        passing containers rather than relying on the global default.
    """
    global _default_container
    if _default_container is None:
        _default_container = Container()
    return _default_container


def set_default_container(container: Container) -> None:
    """Set the default container.
    
    Args:
        container: The Container instance to use as the global default
        
    Note:
        This affects all decorators that don't have access to a current container.
    """
    global _default_container
    _default_container = container


def provide(cls: type[T]) -> type[T]:
    """Register a class with the current or default container.
    
    This decorator registers a class for dependency injection with transient scope
    (new instance created for each resolution).
    
    Args:
        cls: The class to register
        
    Returns:
        The original class (unchanged)
        
    Examples:
        >>> @provide
        ... class EmailService:
        ...     def send(self, to: str, message: str):
        ...         # Send email
        ...         pass
        
        >>> # Now EmailService can be injected
        >>> @inject
        ... async def notify(email: Annotated[EmailService, Inject()]):
        ...     await email.send("user@example.com", "Hello!")
    """
    container = get_current_container() or get_default_container()
    container[cls] = cls
    return cls


def singleton(cls: type[T]) -> type[T]:
    """Register a class as a singleton.
    
    This decorator registers a class with singleton scope - only one instance
    will be created and shared across all resolutions.
    
    Args:
        cls: The class to register as a singleton
        
    Returns:
        The original class (unchanged)
        
    Examples:
        >>> @singleton
        ... class Configuration:
        ...     def __init__(self):
        ...         self.settings = load_settings()  # Expensive operation
        
        >>> # Same instance returned every time
        >>> config1 = await container.resolve(Configuration)
        >>> config2 = await container.resolve(Configuration) 
        >>> assert config1 is config2  # True
    """
    container = get_current_container() or get_default_container()
    container.register(cls, scope="singleton")
    return cls


def factory(service_type: type[T]) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Register a factory function for a service type.
    
    This decorator allows you to register a function that creates instances
    of a service type. Useful when construction logic is complex or when
    you need to return different implementations based on configuration.
    
    Args:
        service_type: The type that the factory creates
        
    Returns:
        A decorator that registers the factory function
        
    Examples:
        >>> @factory(Database)
        ... def create_database() -> Database:
        ...     if os.getenv("TEST"):
        ...         return TestDatabase()
        ...     return PostgresDatabase(os.getenv("DATABASE_URL"))
        
        >>> # Database will be created by the factory
        >>> db = await container.resolve(Database)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        container = get_current_container() or get_default_container()
        container.register_factory(service_type, func)
        return func
    return decorator


def inject(func: F) -> F:
    """Decorator that automatically injects dependencies into functions.
    
    This decorator analyzes function parameters and automatically resolves
    dependencies from the container for parameters marked with Inject().
    
    Args:
        func: The function to decorate
        
    Returns:
        The decorated function with automatic dependency injection
        
    Examples:
        Basic usage:
        
        >>> @inject
        ... async def process_user(
        ...     user_id: int,
        ...     db: Annotated[Database, Inject()]
        ... ):
        ...     return await db.get_user(user_id)
        
        With multiple dependencies:
        
        >>> @inject  
        ... async def send_notification(
        ...     message: str,
        ...     email_svc: Annotated[EmailService, Inject()],
        ...     sms_svc: Annotated[SMSService, Inject()],
        ...     user_pref: Annotated[UserPreferences, Inject()]
        ... ):
        ...     if user_pref.email_enabled:
        ...         await email_svc.send(message)
        ...     if user_pref.sms_enabled:
        ...         await sms_svc.send(message)
    
    Note:
        - Only parameters with Annotated[T, Inject()] are injected
        - Parameters with defaults that are callables (like Setting()) are not injected
        - Works with both sync and async functions
        - Maintains the original function signature for IDE support
    """
    sig = inspect.signature(func)
    is_async = asyncio.iscoroutinefunction(func)
    
    if is_async:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Get the current container
            container = get_current_container() or get_default_container()
            
            # Bind provided arguments
            bound = sig.bind_partial(*args, **kwargs)
            bound.apply_defaults()
            
            # Process bound arguments - check for callable defaults after apply_defaults
            for param_name in list(bound.arguments.keys()):
                value = bound.arguments[param_name]
                if callable(value):
                    try:
                        # Call the default to get the value
                        result = value()
                        if asyncio.iscoroutine(result):
                            bound.arguments[param_name] = await result
                        else:
                            bound.arguments[param_name] = result
                    except Exception:
                        # If calling fails, leave as is
                        pass
            
            # Inject missing dependencies
            for param_name, param in sig.parameters.items():
                if param_name not in bound.arguments and param.annotation != param.empty:
                    try:
                        bound.arguments[param_name] = await container.resolve(param.annotation)
                    except KeyError:
                        if param.default == param.empty:
                            raise
            
            return await func(**bound.arguments)
        
        return async_wrapper  # type: ignore
    else:
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Get the current container
            container = get_current_container() or get_default_container()
            
            # Bind provided arguments
            bound = sig.bind_partial(*args, **kwargs)
            bound.apply_defaults()
            
            # Process bound arguments - check for callable defaults after apply_defaults
            for param_name in list(bound.arguments.keys()):
                value = bound.arguments[param_name]
                if callable(value):
                    try:
                        # Call the default to get the value
                        bound.arguments[param_name] = value()
                    except Exception:
                        # If calling fails, leave as is
                        pass
            
            # Inject missing dependencies
            for param_name, param in sig.parameters.items():
                if param_name not in bound.arguments and param.annotation != param.empty:
                    try:
                        # Use resolve_sync for synchronous functions
                        bound.arguments[param_name] = container.resolve_sync(param.annotation)
                    except KeyError:
                        if param.default == param.empty:
                            raise
            
            return func(**bound.arguments)
        
        return sync_wrapper  # type: ignore


def scoped(scope_name: str) -> Callable[[type[T]], type[T]]:
    """Register a class with a custom scope."""
    def decorator(cls: type[T]) -> type[T]:
        container = get_current_container() or get_default_container()
        container.register(cls, scope=scope_name)
        return cls
    return decorator