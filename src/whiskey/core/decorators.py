"""Global decorators for component registration and dependency injection.

This module provides Flask-style global decorators that work with a default
application instance, making it easy to build simple applications without
explicit application management. All decorators support both sync and async
functions and handle automatic dependency injection based on type hints.

Decorators:
    @component: Register a transient component (new instance per resolution)
    @singleton: Register a singleton component (one instance per app)
    @factory: Register a factory function for component creation
    @scoped: Register a scoped component (one instance per scope)
    @inject: Enable automatic dependency injection for functions
    
    @on_startup: Register startup callbacks
    @on_shutdown: Register shutdown callbacks  
    @on_error: Register error handlers
    
    @when_env: Conditional registration based on environment variable
    @when_debug: Register only in debug mode
    @when_production: Register only in production

Functions:
    resolve: Synchronously resolve a component
    resolve_async: Asynchronously resolve a component
    call: Call a function with dependency injection
    call_sync: Synchronously call with injection
    invoke: Invoke a function with full injection
    wrap_function: Wrap a function to enable injection
    get_app: Get or create the default application
    configure_app: Configure the default application

Example:
    >>> from whiskey import component, singleton, inject
    >>> 
    >>> @singleton
    ... class Database:
    ...     def __init__(self):
    ...         self.connected = True
    >>> 
    >>> @component
    ... class UserService:
    ...     def __init__(self, db: Database):
    ...         self.db = db  # Auto-injected
    >>> 
    >>> @inject
    ... async def get_user(user_id: int, service: UserService):
    ...     # user_id must be provided, component is auto-injected
    ...     return await service.fetch_user(user_id)
    
Note:
    These decorators use a default global application instance. For more
    control or multiple applications, use app-specific decorators instead.
"""

from __future__ import annotations

import asyncio
import inspect
from functools import wraps
from typing import Any, Callable, TypeVar

from .application import Whiskey, create_default_app
from .registry import Scope

T = TypeVar("T")

# Lazy initialization of default app
_default_app: Whiskey = None


def _get_default_app() -> Whiskey:
    """Get or create the default application instance."""
    global _default_app
    if _default_app is None:
        _default_app = create_default_app()
    return _default_app


# Global component registration decorators


def component(
    cls: type[T] | None = None,
    *,
    key: str | type | None = None,
    name: str | None = None,
    scope: Scope = Scope.TRANSIENT,
    tags: set[str] | None = None,
    condition: Callable[[], bool] | None = None,
    lazy: bool = False,
    app: Whiskey = None,
) -> type[T] | Callable[[type[T]], type[T]]:
    """Global decorator to register a class as a component.

    Uses the default application instance unless 'app' is specified.

    Args:
        cls: The class to register (when used without parentheses)
        key: Optional component key (defaults to class)
        name: Optional name for named components
        scope: Component scope (default: transient)
        tags: Set of tags for categorization
        condition: Optional registration condition
        lazy: Whether to use lazy resolution
        app: Optional Whiskey instance (uses default if None)

    Returns:
        The registered class (for decorator chaining)

    Examples:
        >>> @component
        >>> class DatabaseService:
        ...     pass

        >>> @component(scope=Scope.SINGLETON, tags={'infrastructure'})
        >>> class CacheService:
        ...     pass
    """
    def decorator(cls: type[T]) -> type[T]:
        # Validate that target is a class
        if not inspect.isclass(cls):
            raise TypeError("@component decorator can only be applied to classes")
        target_app = app or _get_default_app()
        return target_app.component(
            cls, key=key, name=name, scope=scope, tags=tags, condition=condition, lazy=lazy
        )
    
    if cls is None:
        return decorator
    else:
        return decorator(cls)


def singleton(
    cls: type[T] | None = None,
    *,
    key: str | type | None = None,
    name: str | None = None,
    tags: set[str] | None = None,
    condition: Callable[[], bool] | None = None,
    lazy: bool = False,
    app: Whiskey = None,
) -> type[T] | Callable[[type[T]], type[T]]:
    """Global decorator to register a class as a singleton component."""
    target_app = app or _get_default_app()
    return target_app.singleton(cls, key=key, name=name, tags=tags, condition=condition, lazy=lazy)


def scoped(
    scope_name: str = "default",
    *,
    key: str | type | None = None,
    name: str | None = None,
    tags: set[str] | None = None,
    condition: Callable[[], bool] | None = None,
    lazy: bool = False,
    app: Whiskey = None,
) -> Callable[[type[T]], type[T]]:
    """Global decorator to register a class as a scoped component."""
    target_app = app or _get_default_app()
    
    def decorator(cls: type[T]) -> type[T]:
        return target_app.scoped(
            cls, scope_name=scope_name, key=key, name=name, tags=tags, condition=condition, lazy=lazy
        )
    
    return decorator


def factory(
    key_or_func=None,
    *,
    key: str | type | None = None,
    name: str | None = None,
    scope: Scope = Scope.TRANSIENT,
    tags: set[str] | None = None,
    condition: Callable[[], bool] | None = None,
    lazy: bool = False,
    app: Whiskey = None,
) -> Callable | Callable[[Callable], Callable]:
    """Improved factory decorator with automatic key inference.
    
    This decorator can be used in multiple ways:
    
    1. With automatic key inference (recommended):
       @factory
       def create_service() -> UserService:
           return UserService()
    
    2. With explicit key:
       @factory(key=UserService)
       def create_service():
           return UserService()
    
    3. With positional key:
       @factory(UserService)
       def create_service():
           return UserService()
    
    4. With options:
       @factory(scope=Scope.SINGLETON)
       def create_cache() -> RedisCache:
           return RedisCache()
    
    Args:
        key_or_func: Either the component key or the factory function
        key: Explicit key for the factory (alternative to positional key)
        name: Optional name for named components
        scope: Component scope (default: transient)
        tags: Set of tags for categorization
        condition: Optional registration condition
        lazy: Whether to use lazy resolution
        app: Optional Whiskey instance (uses default if None)
    
    Returns:
        The decorated function
    """
    # Import here to avoid circular imports
    from .improved_factory import ImprovedFactoryDecorator
    
    decorator = ImprovedFactoryDecorator(
        key_or_func=key_or_func,
        key=key,
        name=name,
        scope=scope,
        tags=tags,
        condition=condition,
        lazy=lazy,
        app=app or _get_default_app(),
    )
    
    # Only pass key_or_func as func if it's a function (not a class)
    func_to_pass = key_or_func if callable(key_or_func) and not inspect.isclass(key_or_func) else None
    return decorator(func_to_pass)


# Alias for backward compatibility
provide = component


# Injection decorator


def inject(
    func: Callable | None = None, *, app: Whiskey = None
) -> Callable | Callable[[Callable], Callable]:
    """Global decorator to enable dependency injection for a function.

    This decorator modifies a function to automatically resolve its
    parameters from the dependency injection container.

    Args:
        func: The function to inject dependencies into
        app: Optional Whiskey instance (uses default if None)

    Returns:
        The wrapped function with automatic injection

    Examples:
        >>> @inject
        >>> def process_data(db: Database, cache: Cache):
        ...     # db and cache are automatically resolved
        ...     return db.query() + cache.get()

        >>> @inject
        >>> async def async_handler(service: MyService):
        ...     return await service.process()
    """

    def decorator(func: Callable) -> Callable:
        target_app = app or _get_default_app()

        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                # Use container's call method with provided args/kwargs
                return await target_app.container.call(func, *args, **kwargs)

            return async_wrapper
        else:

            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                # Use container's call_sync method
                return target_app.container.call_sync(func, *args, **kwargs)

            return sync_wrapper

    if func is None:
        return decorator
    else:
        return decorator(func)


# Conditional decorators


def when_env(var_name: str, expected_value: str | None = None, app: Whiskey = None):
    """Global decorator factory for environment-based conditional registration."""
    target_app = app or _get_default_app()
    return target_app.when_env(var_name, expected_value)


def when_debug(cls_or_app=None, *, app: Whiskey = None):
    """Global decorator factory for debug mode conditional registration."""
    # Handle case where used without parentheses: @when_debug
    if cls_or_app is not None and not isinstance(cls_or_app, Whiskey):
        # Called as @when_debug (without parentheses)
        target_app = app or _get_default_app()
        helper = target_app.when_debug()
        return helper(cls_or_app)
    else:
        # Called as @when_debug() (with parentheses)
        target_app = cls_or_app or app or _get_default_app()
        return target_app.when_debug()


def when_production(cls_or_app=None, *, app: Whiskey = None):
    """Global decorator factory for production mode conditional registration."""
    # Handle case where used without parentheses: @when_production
    if cls_or_app is not None and not isinstance(cls_or_app, Whiskey):
        # Called as @when_production (without parentheses)
        target_app = app or _get_default_app()
        helper = target_app.when_production()
        return helper(cls_or_app)
    else:
        # Called as @when_production() (with parentheses)
        target_app = cls_or_app or app or _get_default_app()
        return target_app.when_production()


# Whiskey lifecycle decorators


def on_startup(func: Callable | None = None, *, app: Whiskey = None):
    """Global decorator to register a startup callback.

    Args:
        func: The callback function
        app: Optional Whiskey instance (uses default if None)

    Examples:
        >>> @on_startup
        >>> def initialize_components():
        ...     print("Whiskey starting up...")

        >>> @on_startup
        >>> async def async_startup():
        ...     await setup_async_resources()
    """

    def decorator(func: Callable) -> Callable:
        target_app = app or _get_default_app()
        target_app._startup_callbacks.append(func)
        return func

    if func is None:
        return decorator
    else:
        return decorator(func)


def on_shutdown(func: Callable | None = None, *, app: Whiskey = None):
    """Global decorator to register a shutdown callback."""

    def decorator(func: Callable) -> Callable:
        target_app = app or _get_default_app()
        target_app._shutdown_callbacks.append(func)
        return func

    if func is None:
        return decorator
    else:
        return decorator(func)


def on_error(func: Callable | None = None, *, app: Whiskey = None):
    """Global decorator to register an error handler.

    Args:
        func: The error handler function
        app: Optional Whiskey instance (uses default if None)

    Examples:
        >>> @on_error
        >>> def handle_error(exc: Exception):
        ...     print(f"Handled error: {exc}")
    """

    def decorator(func: Callable) -> Callable:
        target_app = app or _get_default_app()
        # Use Exception as the default error type
        target_app._error_handlers[Exception] = func
        return func

    if func is None:
        return decorator
    else:
        return decorator(func)


# Function calling utilities


async def call(func: Callable, *args, app: Whiskey = None, **kwargs) -> Any:
    """Global function to call a function with dependency injection.

    Args:
        func: The function to call
        *args: Positional arguments
        app: Optional Whiskey instance (uses default if None)
        **kwargs: Keyword arguments (override injection)

    Returns:
        The function's return value

    Examples:
        >>> def process_data(db: Database, user_id: int):
        ...     return db.get_user(user_id)
        >>>
        >>> result = await call(process_data, user_id=123)
    """
    target_app = app or _get_default_app()
    return await target_app.call_async(func, *args, **kwargs)


def call_sync(func: Callable, *args, app: Whiskey = None, **kwargs) -> Any:
    """Global function to call a function with dependency injection (sync)."""
    target_app = app or _get_default_app()
    return target_app.call_sync(func, *args, **kwargs)


def invoke(func: Callable, *, app: Whiskey = None, **overrides) -> Any:
    """Global function to invoke a function with full dependency injection."""
    target_app = app or _get_default_app()
    # For sync functions, call synchronously
    if asyncio.iscoroutinefunction(func):
        # For async functions, return the coroutine from invoke_async
        return target_app.invoke_async(func, **overrides)
    else:
        # For sync functions, use invoke (which is sync in the app)
        return target_app.invoke(func, **overrides)


def wrap_function(func: Callable, *, app: Whiskey = None) -> Callable:
    """Global function to wrap a function with automatic injection.

    Args:
        func: The function to wrap
        app: Optional Whiskey instance (uses default if None)

    Returns:
        Wrapped function that uses automatic injection

    Examples:
        >>> def process_data(db: Database, user_id: int):
        ...     return db.get_user(user_id)
        >>>
        >>> injected_process = wrap_function(process_data)
        >>> result = await injected_process(user_id=123)  # db auto-injected
    """
    target_app = app or _get_default_app()
    return target_app.wrap_function(func)


# Component resolution utilities


def resolve(key: str | type, *, app: Whiskey = None) -> Any:
    """Global function to resolve a component.

    Args:
        key: Component key (string or type)
        app: Optional Whiskey instance (uses default if None)

    Returns:
        The resolved component instance

    Examples:
        >>> database = resolve('database')
        >>> email_service = resolve(EmailService)
    """
    if key is None:
        raise ValueError("Component key cannot be None")
    target_app = app or _get_default_app()
    return target_app.resolve(key)


async def resolve_async(key: str | type, *, app: Whiskey = None) -> Any:
    """Global async function to resolve a component."""
    target_app = app or _get_default_app()
    return await target_app.resolve_async(key)


def get_app() -> Whiskey:
    """Get the default application instance."""
    return _get_default_app()


def configure_app(config_func: Callable[[Whiskey], None]) -> None:
    """Configure the default application.

    Args:
        config_func: Function that configures the application

    Examples:
        >>> def setup_components(app: Whiskey):
        ...     app.container.add_singleton('config', load_config())
        >>>
        >>> configure_app(setup_components)
    """
    app = _get_default_app()
    config_func(app)
