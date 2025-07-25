"""Simple decorators for dependency injection."""

from __future__ import annotations

import asyncio
import functools
import inspect
from typing import Any, Callable, TypeVar

from whiskey.core.conditions import Condition, evaluate_condition
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


def provide(cls: type[T] | None = None, *, name: str | None = None, condition: Condition | bool | None = None) -> type[T] | Callable[[type[T]], type[T]]:
    """Register a class with the current or default container.
    
    This decorator registers a class for dependency injection with transient scope
    (new instance created for each resolution).
    
    Args:
        cls: The class to register (when used without parentheses)
        name: Optional name for named dependencies
        condition: Optional condition for registration
        
    Returns:
        The original class (unchanged) or decorator function
        
    Examples:
        >>> @provide
        ... class EmailService:
        ...     def send(self, to: str, message: str):
        ...         # Send email
        ...         pass
        
        >>> @provide(name="smtp")
        ... class SMTPEmailService:
        ...     def send(self, to: str, message: str):
        ...         # Send via SMTP
        ...         pass
        
        >>> @provide(condition=lambda: os.getenv("ENV") == "dev")
        ... class DevEmailService:
        ...     def send(self, to: str, message: str):
        ...         # Development email service
        ...         pass
        
        >>> # Now EmailService can be injected
        >>> @inject
        ... async def notify(email: Annotated[EmailService, Inject()]):
        ...     await email.send("user@example.com", "Hello!")
    """
    def decorator(cls_to_register: type[T]) -> type[T]:
        # Evaluate condition at decoration time
        if evaluate_condition(condition):
            container = get_current_container() or get_default_container()
            container.register(cls_to_register, scope="transient", name=name)
        return cls_to_register
    
    if cls is not None:
        # Called as @provide without parentheses
        return decorator(cls)
    else:
        # Called as @provide() or @provide(name="...")
        return decorator


def singleton(cls: type[T] | None = None, *, name: str | None = None, condition: Condition | bool | None = None) -> type[T] | Callable[[type[T]], type[T]]:
    """Register a class as a singleton.
    
    This decorator registers a class with singleton scope - only one instance
    will be created and shared across all resolutions.
    
    Args:
        cls: The class to register as a singleton (when used without parentheses)
        name: Optional name for named dependencies
        condition: Optional condition for registration
        
    Returns:
        The original class (unchanged) or decorator function
        
    Examples:
        >>> @singleton
        ... class Configuration:
        ...     def __init__(self):
        ...         self.settings = load_settings()  # Expensive operation
        
        >>> @singleton(name="test")
        ... class TestConfiguration:
        ...     def __init__(self):
        ...         self.settings = load_test_settings()
        
        >>> @singleton(condition=lambda: not os.getenv("TESTING"))
        ... class ProductionConfiguration:
        ...     def __init__(self):
        ...         self.settings = load_prod_settings()
        
        >>> # Same instance returned every time
        >>> config1 = await container.resolve(Configuration)
        >>> config2 = await container.resolve(Configuration) 
        >>> assert config1 is config2  # True
    """
    def decorator(cls_to_register: type[T]) -> type[T]:
        # Evaluate condition at decoration time
        if evaluate_condition(condition):
            container = get_current_container() or get_default_container()
            container.register(cls_to_register, scope="singleton", name=name)
        return cls_to_register
    
    if cls is not None:
        # Called as @singleton without parentheses
        return decorator(cls)
    else:
        # Called as @singleton() or @singleton(name="...")
        return decorator


def factory(service_type: type[T], *, name: str | None = None, condition: Condition | bool | None = None) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Register a factory function for a service type.
    
    This decorator allows you to register a function that creates instances
    of a service type. Useful when construction logic is complex or when
    you need to return different implementations based on configuration.
    
    Args:
        service_type: The type that the factory creates
        name: Optional name for named dependencies
        condition: Optional condition for registration
        
    Returns:
        A decorator that registers the factory function
        
    Examples:
        >>> @factory(Database)
        ... def create_database() -> Database:
        ...     if os.getenv("TEST"):
        ...         return TestDatabase()
        ...     return PostgresDatabase(os.getenv("DATABASE_URL"))
        
        >>> @factory(Database, name="readonly")
        ... def create_readonly_database() -> Database:
        ...     return ReadOnlyDatabase(os.getenv("READONLY_DB_URL"))
        
        >>> @factory(Database, condition=lambda: os.getenv("USE_MOCK_DB"))
        ... def create_mock_database() -> Database:
        ...     return MockDatabase()
        
        >>> # Database will be created by the factory
        >>> db = await container.resolve(Database)
        >>> readonly_db = await container.resolve(Database, name="readonly")
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        # Evaluate condition at decoration time
        if evaluate_condition(condition):
            container = get_current_container() or get_default_container()
            container.register_factory(service_type, func, name=name)
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


def scoped(scope_name: str, *, name: str | None = None, condition: Condition | bool | None = None) -> Callable[[type[T]], type[T]]:
    """Register a class with a custom scope.
    
    Args:
        scope_name: The scope to register the class with
        name: Optional name for named dependencies
        condition: Optional condition for registration
        
    Returns:
        A decorator that registers the class with the specified scope
        
    Examples:
        >>> @scoped("request")
        ... class RequestContext:
        ...     pass
        
        >>> @scoped("session", name="admin")
        ... class AdminSessionContext:
        ...     pass
        
        >>> @scoped("request", condition=lambda: os.getenv("ENABLE_REQUEST_TRACKING"))
        ... class RequestTracker:
        ...     pass
    """
    def decorator(cls: type[T]) -> type[T]:
        # Evaluate condition at decoration time
        if evaluate_condition(condition):
            container = get_current_container() or get_default_container()
            container.register(cls, scope=scope_name, name=name)
        return cls
    return decorator