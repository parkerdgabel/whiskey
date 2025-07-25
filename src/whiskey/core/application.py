"""Application class for Whiskey's Pythonic DI redesign.

This module provides the Application class which serves as the main entry point
for dependency injection applications, integrating with the fluent API and
providing lifecycle management.
"""

from __future__ import annotations

import asyncio
import inspect
from typing import Any, Callable, TypeVar, Union, Type

from .container import Container
from .builder import ApplicationBuilder, create_app
from .registry import Scope
from .errors import ConfigurationError

T = TypeVar('T')

# Global application instance for decorators
_current_application: 'Application' = None


class Application:
    """Main application class with lifecycle management and decorator support.
    
    This class provides the main entry point for Whiskey applications,
    integrating the fluent configuration API with lifecycle management
    and convenience decorators.
    
    Examples:
        Using the fluent builder:
        
        >>> app = Application.builder() \\
        ...     .service('database', DatabaseImpl).as_singleton() \\
        ...     .service(EmailService, EmailService) \\
        ...     .build_app()
        
        Using decorators:
        
        >>> app = Application()
        >>> 
        >>> @app.service
        >>> class DatabaseService:
        ...     pass
        >>> 
        >>> @app.singleton
        >>> class CacheService:
        ...     pass
    """
    
    def __init__(self, container: Container = None):
        """Initialize a new Application.
        
        Args:
            container: Optional Container instance (creates new one if None)
        """
        self.container = container or Container()
        self._startup_callbacks: list[Callable] = getattr(container, '_startup_callbacks', [])
        self._shutdown_callbacks: list[Callable] = getattr(container, '_shutdown_callbacks', [])
        self._error_handlers: dict[Type[Exception], Callable] = getattr(container, '_error_handlers', {})
        self._middleware: list[Callable] = getattr(container, '_middleware', [])
        self._is_running = False
    
    @classmethod
    def builder(cls) -> ApplicationBuilder:
        """Create a new ApplicationBuilder for fluent configuration.
        
        Returns:
            ApplicationBuilder instance
        """
        return create_app()
    
    @classmethod
    def create(cls) -> ApplicationBuilder:
        """Alias for builder() method."""
        return cls.builder()
    
    # Decorator methods for service registration
    
    def service(self, 
                cls: Type[T] = None, 
                *,
                key: str | type = None,
                name: str = None,
                scope: Scope = Scope.TRANSIENT,
                tags: set[str] = None,
                condition: Callable[[], bool] = None,
                lazy: bool = False) -> Union[Type[T], Callable[[Type[T]], Type[T]]]:
        """Decorator to register a class as a service.
        
        Args:
            cls: The class to register (when used without parentheses)
            key: Optional service key (defaults to class)
            name: Optional name for named services
            scope: Service scope (default: transient)
            tags: Set of tags for categorization
            condition: Optional registration condition
            lazy: Whether to use lazy resolution
            
        Returns:
            The registered class (for decorator chaining)
            
        Examples:
            >>> @app.service
            >>> class DatabaseService:
            ...     pass
            
            >>> @app.service(name="primary", scope=Scope.SINGLETON)
            >>> class DatabaseService:
            ...     pass
        """
        def decorator(cls: Type[T]) -> Type[T]:
            service_key = key or cls
            
            self.container.register(
                service_key,
                cls,
                scope=scope,
                name=name,
                condition=condition,
                tags=tags or set(),
                lazy=lazy
            )
            
            return cls
        
        if cls is None:
            # Used with parentheses: @app.service(...)
            return decorator
        else:
            # Used without parentheses: @app.service
            return decorator(cls)
    
    def singleton(self, 
                  cls: Type[T] = None, 
                  *,
                  key: str | type = None,
                  name: str = None,
                  tags: set[str] = None,
                  condition: Callable[[], bool] = None,
                  lazy: bool = False) -> Union[Type[T], Callable[[Type[T]], Type[T]]]:
        """Decorator to register a class as a singleton service."""
        return self.service(
            cls,
            key=key,
            name=name,
            scope=Scope.SINGLETON,
            tags=tags,
            condition=condition,
            lazy=lazy
        )
    
    def scoped(self,
               cls: Type[T] = None,
               *,
               scope_name: str = 'default',
               key: str | type = None,
               name: str = None,
               tags: set[str] = None,
               condition: Callable[[], bool] = None,
               lazy: bool = False) -> Union[Type[T], Callable[[Type[T]], Type[T]]]:
        """Decorator to register a class as a scoped service."""
        return self.service(
            cls,
            key=key,
            name=name,
            scope=Scope.SCOPED,
            tags=tags,
            condition=condition,
            lazy=lazy
        )
    
    def factory(self,
                func: Callable = None,
                *,
                key: str | type = None,
                name: str = None,
                scope: Scope = Scope.TRANSIENT,
                tags: set[str] = None,
                condition: Callable[[], bool] = None,
                lazy: bool = False) -> Union[Callable, Callable[[Callable], Callable]]:
        """Decorator to register a function as a factory.
        
        Args:
            func: The factory function to register
            key: Service key (required)
            name: Optional name for named services
            scope: Service scope (default: transient)
            tags: Set of tags for categorization
            condition: Optional registration condition
            lazy: Whether to use lazy resolution
            
        Returns:
            The registered function
            
        Examples:
            >>> @app.factory(key='database')
            >>> def create_database():
            ...     return DatabaseImpl()
        """
        def decorator(func: Callable) -> Callable:
            if key is None:
                raise ConfigurationError("Factory decorator requires 'key' parameter")
            
            self.container.register(
                key,
                func,
                scope=scope,
                name=name,
                condition=condition,
                tags=tags or set(),
                lazy=lazy
            )
            
            return func
        
        if func is None:
            return decorator
        else:
            return decorator(func)
    
    def component(self,
                  target: Union[Type[T], Callable] = None,
                  *,
                  key: str | type = None,
                  name: str = None,
                  scope: Scope = Scope.TRANSIENT,
                  tags: set[str] = None,
                  condition: Callable[[], bool] = None,
                  lazy: bool = False) -> Union[Any, Callable]:
        """General-purpose component decorator for classes or functions.
        
        This decorator automatically determines whether to register as a
        service (for classes) or factory (for functions).
        """
        def decorator(target: Union[Type[T], Callable]) -> Union[Type[T], Callable]:
            if inspect.isclass(target):
                # Register as service
                return self.service(
                    target,
                    key=key,
                    name=name,
                    scope=scope,
                    tags=tags,
                    condition=condition,
                    lazy=lazy
                )
            elif callable(target):
                # Register as factory
                if key is None:
                    raise ConfigurationError("Factory registration requires 'key' parameter")
                
                return self.factory(
                    target,
                    key=key,
                    name=name,
                    scope=scope,
                    tags=tags,
                    condition=condition,
                    lazy=lazy
                )
            else:
                raise ConfigurationError(f"Cannot register {type(target)} as component")
        
        if target is None:
            return decorator
        else:
            return decorator(target)
    
    # Conditional decorators
    
    def when_env(self, var_name: str, expected_value: str = None):
        """Decorator factory for environment-based conditional registration."""
        import os
        if expected_value is None:
            condition = lambda: var_name in os.environ
        else:
            condition = lambda: os.environ.get(var_name) == expected_value
        
        def decorator_factory(decorator_name: str, **kwargs):
            def decorator(target):
                kwargs['condition'] = condition
                return getattr(self, decorator_name)(target, **kwargs)
            return decorator
        
        # Return a helper object that provides all decorator types
        return ConditionalDecoratorHelper(self, condition)
    
    def when_debug(self):
        """Decorator factory for debug mode conditional registration."""
        import os
        condition = lambda: os.environ.get('DEBUG', '').lower() in ('true', '1', 'yes')
        return ConditionalDecoratorHelper(self, condition)
    
    def when_production(self):
        """Decorator factory for production mode conditional registration."""
        import os
        condition = lambda: os.environ.get('ENV', '').lower() in ('prod', 'production')
        return ConditionalDecoratorHelper(self, condition)
    
    # Lifecycle methods
    
    async def startup(self) -> None:
        """Start the application and run startup callbacks."""
        if self._is_running:
            return
        
        self._is_running = True
        
        # Run startup callbacks
        for callback in self._startup_callbacks:
            if asyncio.iscoroutinefunction(callback):
                await callback()
            else:
                callback()
    
    async def shutdown(self) -> None:
        """Shutdown the application and run cleanup callbacks."""
        if not self._is_running:
            return
        
        self._is_running = False
        
        # Run shutdown callbacks
        for callback in reversed(self._shutdown_callbacks):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
            except Exception as e:
                # Log error but don't stop shutdown process
                print(f"Error in shutdown callback: {e}")
        
        # Clear container caches
        self.container.clear_caches()
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.startup()
        return self
    
    async def __aexit__(self, *args):
        """Async context manager exit."""
        await self.shutdown()
    
    # Function calling methods
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Call a function with dependency injection."""
        return await self.container.call(func, *args, **kwargs)
    
    def call_sync(self, func: Callable, *args, **kwargs) -> Any:
        """Call a function with dependency injection (synchronous)."""
        return self.container.call_sync(func, *args, **kwargs)
    
    async def invoke(self, func: Callable, **overrides) -> Any:
        """Invoke a function with full dependency injection."""
        return await self.container.invoke(func, **overrides)
    
    def wrap_function(self, func: Callable) -> Callable:
        """Wrap a function to always use dependency injection."""
        return self.container.wrap_with_injection(func)
    
    # Convenience methods
    
    def resolve(self, key: str | type, **kwargs) -> Any:
        """Resolve a service from the container."""
        return self.container.resolve_sync(key, **kwargs)
    
    async def resolve_async(self, key: str | type, **kwargs) -> Any:
        """Resolve a service asynchronously."""
        return await self.container.resolve(key, **kwargs)
    
    def configure(self, config_func: Callable[['Application'], None]) -> 'Application':
        """Apply a configuration function to this application."""
        config_func(self)
        return self
    
    # Dictionary-like access to container
    
    def __getitem__(self, key: str | type) -> Any:
        """Get a service using dict-like syntax."""
        return self.container[key]
    
    def __setitem__(self, key: str | type, value: Any) -> None:
        """Register a service using dict-like syntax."""
        self.container[key] = value
    
    def __contains__(self, key: str | type) -> bool:
        """Check if a service is registered."""
        return key in self.container


class ConditionalDecoratorHelper:
    """Helper class for conditional decorators."""
    
    def __init__(self, app: Application, condition: Callable[[], bool]):
        self.app = app
        self.condition = condition
    
    def service(self, cls: Type[T] = None, **kwargs) -> Union[Type[T], Callable[[Type[T]], Type[T]]]:
        """Conditionally register a service."""
        kwargs['condition'] = self.condition
        return self.app.service(cls, **kwargs)
    
    def singleton(self, cls: Type[T] = None, **kwargs) -> Union[Type[T], Callable[[Type[T]], Type[T]]]:
        """Conditionally register a singleton."""
        kwargs['condition'] = self.condition
        return self.app.singleton(cls, **kwargs)
    
    def factory(self, func: Callable = None, **kwargs) -> Union[Callable, Callable[[Callable], Callable]]:
        """Conditionally register a factory."""
        kwargs['condition'] = self.condition
        return self.app.factory(func, **kwargs)
    
    def component(self, target = None, **kwargs):
        """Conditionally register a component."""
        kwargs['condition'] = self.condition
        return self.app.component(target, **kwargs)


# Global application instance management
def set_current_app(app: Application) -> None:
    """Set the current global application instance."""
    global _current_application
    _current_application = app


def get_current_app() -> Application | None:
    """Get the current global application instance."""
    return _current_application


def create_default_app() -> Application:
    """Create a default application instance."""
    app = Application()
    set_current_app(app)
    return app