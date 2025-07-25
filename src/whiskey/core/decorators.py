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
    """Get or create the default container."""
    global _default_container
    if _default_container is None:
        _default_container = Container()
    return _default_container


def set_default_container(container: Container) -> None:
    """Set the default container."""
    global _default_container
    _default_container = container


def provide(cls: type[T]) -> type[T]:
    """Register a class with the current or default container."""
    container = get_current_container() or get_default_container()
    container[cls] = cls
    return cls


def singleton(cls: type[T]) -> type[T]:
    """Register a class as a singleton."""
    container = get_current_container() or get_default_container()
    container.register(cls, scope="singleton")
    return cls


def factory(service_type: type[T]) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Register a factory function for a service type."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        container = get_current_container() or get_default_container()
        container.register_factory(service_type, func)
        return func
    return decorator


def inject(func: F) -> F:
    """Inject dependencies into a function.
    
    This decorator automatically resolves and injects dependencies based on
    the function's type annotations.
    
    Example:
        @inject
        async def process_user(user_service: UserService, db: Database):
            user = await user_service.get_user(123)
            await db.save(user)
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