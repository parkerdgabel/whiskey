"""Decorators for Whiskey dependency injection."""

from __future__ import annotations

import functools
import inspect
from typing import Any, Callable, TypeVar, overload

from whiskey.core.container import Container
from whiskey.core.types import ScopeType, ServiceFactory

T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])

# Global default container
_default_container: Container | None = None


def get_default_container() -> Container:
    """Get or create the default container."""
    global _default_container
    if _default_container is None:
        _default_container = Container()
    return _default_container


def set_default_container(container: Container) -> None:
    """Set the default container."""
    global _default_container
    _default_container = container


# @provide decorator

@overload
def provide(cls: type[T]) -> type[T]:
    """Register a class as a transient service."""
    ...


@overload
def provide(
    *,
    scope: ScopeType | str = ScopeType.TRANSIENT,
    name: str | None = None,
    container: Container | None = None,
    **metadata: Any,
) -> Callable[[type[T]], type[T]]:
    """Register a class with specific options."""
    ...


def provide(
    cls: type[T] | None = None,
    *,
    scope: ScopeType | str = ScopeType.TRANSIENT,
    name: str | None = None,
    container: Container | None = None,
    **metadata: Any,
) -> type[T] | Callable[[type[T]], type[T]]:
    """
    Decorator to register a class as a service provider.
    
    Can be used with or without parameters:
    - @provide
    - @provide(scope=ScopeType.SINGLETON)
    """
    def decorator(cls: type[T]) -> type[T]:
        target_container = container or get_default_container()
        target_container.register(
            service_type=cls,
            implementation=cls,
            scope=scope,
            name=name,
            **metadata,
        )
        # Mark class as injectable
        cls.__whiskey_injectable__ = True
        return cls

    if cls is not None:
        # Called without parentheses: @provide
        return decorator(cls)
    else:
        # Called with parentheses: @provide(...)
        return decorator


# @singleton decorator

def singleton(
    cls: type[T] | None = None,
    *,
    name: str | None = None,
    container: Container | None = None,
    **metadata: Any,
) -> type[T] | Callable[[type[T]], type[T]]:
    """
    Decorator to register a class as a singleton service.
    
    Shorthand for @provide(scope=ScopeType.SINGLETON)
    """
    return provide(
        cls,
        scope=ScopeType.SINGLETON,
        name=name,
        container=container,
        **metadata,
    )


# @inject decorator

@overload
def inject(func: F) -> F:
    """Inject dependencies into a function."""
    ...


@overload
def inject(
    *,
    container: Container | None = None,
    **overrides: Any,
) -> Callable[[F], F]:
    """Inject dependencies with specific container or overrides."""
    ...


def inject(
    func: F | None = None,
    *,
    container: Container | None = None,
    **overrides: Any,
) -> F | Callable[[F], F]:
    """
    Decorator to inject dependencies into a function.
    
    Can be used with or without parameters:
    - @inject
    - @inject(container=my_container)
    - @inject(service=mock_service)  # Override specific dependencies
    """
    def decorator(func: F) -> F:
        # Get function signature
        sig = inspect.signature(func)
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Get container
            target_container = container or get_default_container()
            
            # Prepare injection context
            bound = sig.bind_partial(*args, **kwargs)
            bound.apply_defaults()
            
            # Inject missing dependencies
            for param_name, param in sig.parameters.items():
                if param_name not in bound.arguments:
                    # Check for override
                    if param_name in overrides:
                        bound.arguments[param_name] = overrides[param_name]
                    elif param.annotation != param.empty:
                        # Try to resolve from container
                        try:
                            instance = await target_container.resolve(param.annotation)
                            bound.arguments[param_name] = instance
                        except Exception:
                            # Skip if optional or has default
                            if param.default == param.empty:
                                raise
            
            # Call original function
            return await func(*bound.args, **bound.kwargs)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Get container
            target_container = container or get_default_container()
            
            # Prepare injection context
            bound = sig.bind_partial(*args, **kwargs)
            bound.apply_defaults()
            
            # Inject missing dependencies
            for param_name, param in sig.parameters.items():
                if param_name not in bound.arguments:
                    # Check for override
                    if param_name in overrides:
                        bound.arguments[param_name] = overrides[param_name]
                    elif param.annotation != param.empty:
                        # Try to resolve from container
                        try:
                            instance = target_container.resolve_sync(param.annotation)
                            bound.arguments[param_name] = instance
                        except Exception:
                            # Skip if optional or has default
                            if param.default == param.empty:
                                raise
            
            # Call original function
            return func(*bound.args, **bound.kwargs)
        
        # Return appropriate wrapper
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    if func is not None:
        # Called without parentheses: @inject
        return decorator(func)
    else:
        # Called with parentheses: @inject(...)
        return decorator


# Factory registration helpers

def factory(
    service_type: type[T],
    *,
    scope: ScopeType | str = ScopeType.TRANSIENT,
    name: str | None = None,
    container: Container | None = None,
    **metadata: Any,
) -> Callable[[ServiceFactory[T]], ServiceFactory[T]]:
    """
    Decorator to register a factory function.
    
    @factory(DatabaseConnection, scope=ScopeType.SINGLETON)
    def create_db_connection(config: Config) -> DatabaseConnection:
        return DatabaseConnection(config.db_url)
    """
    def decorator(func: ServiceFactory[T]) -> ServiceFactory[T]:
        target_container = container or get_default_container()
        target_container.register(
            service_type=service_type,
            factory=func,
            scope=scope,
            name=name,
            **metadata,
        )
        return func
    
    return decorator


# Named binding helpers

def named(name: str) -> Callable[[type[T]], type[T]]:
    """
    Helper to create named bindings.
    
    @provide
    @named("primary")
    class PrimaryDatabase(Database):
        pass
    """
    def decorator(cls: type[T]) -> type[T]:
        # Store the name in class metadata
        cls.__whiskey_name__ = name
        return cls
    
    return decorator


# Scope helpers

def scoped(scope: ScopeType | str) -> Callable[[type[T]], type[T]]:
    """
    Helper to specify scope.
    
    @provide
    @scoped(ScopeType.REQUEST)
    class RequestService:
        pass
    """
    def decorator(cls: type[T]) -> type[T]:
        # Store the scope in class metadata
        cls.__whiskey_scope__ = scope
        return cls
    
    return decorator