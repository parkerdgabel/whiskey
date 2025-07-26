"""Whiskey class for Whiskey's Pythonic DI framework.

This module provides the Whiskey class which serves as the main entry point
for dependency injection applications, integrating with the fluent API and
providing lifecycle management.
"""

from __future__ import annotations

import asyncio
import inspect
from typing import Any, Callable, Type, TypeVar, Union

from .builder import WhiskeyBuilder, create_app
from .container import Container
from .errors import ConfigurationError
from .registry import Scope

T = TypeVar("T")

# Global application instance for decorators
_current_application: Whiskey = None


class Whiskey:
    """Main Whiskey class with lifecycle management and decorator support.
    
    This class provides the main entry point for Whiskey applications,
    integrating the fluent configuration API with lifecycle management
    and convenience decorators.
    
    Examples:
        Using the fluent builder:
        
        >>> app = Whiskey.builder() \\
        ...     .component('database', DatabaseImpl).as_singleton() \\
        ...     .component(EmailService, EmailService) \\
        ...     .build_app()
        
        Using decorators:
        
        >>> app = Whiskey()
        >>> 
        >>> @app.component
        >>> class DatabaseService:
        ...     pass
        >>> 
        >>> @app.singleton
        >>> class CacheService:
        ...     pass
    """

    def __init__(self, container: Container = None, name: str = None):
        """Initialize a new Application.

        Args:
            container: Optional Container instance (creates new one if None)
            name: Optional name for the application (defaults to "Whiskey")
        """
        self.container = container if container is not None else Container()
        self.name = name if name is not None else "Whiskey"
        
        # Initialize callbacks - if container has them, use them; otherwise create new
        if hasattr(self.container, "_startup_callbacks"):
            self._startup_callbacks = self.container._startup_callbacks
        else:
            self._startup_callbacks = []

        if hasattr(self.container, "_shutdown_callbacks"):
            self._shutdown_callbacks = self.container._shutdown_callbacks
        else:
            self._shutdown_callbacks = []

        if hasattr(self.container, "_error_handlers"):
            self._error_handlers = self.container._error_handlers
        else:
            self._error_handlers = {}

        if hasattr(self.container, "_middleware"):
            self._middleware = self.container._middleware
        else:
            self._middleware = []

        self._is_running = False
        # Add hooks for lifecycle compatibility
        self._hooks = {
            "before_startup": self._startup_callbacks,
            "after_shutdown": self._shutdown_callbacks,
            "tasks": []
        }

    @classmethod
    def builder(cls) -> WhiskeyBuilder:
        """Create a new WhiskeyBuilder for fluent configuration.

        Returns:
            WhiskeyBuilder instance
        """
        return create_app()

    @classmethod
    def create(cls) -> WhiskeyBuilder:
        """Alias for builder() method."""
        return cls.builder()

    # Direct registration methods
    
    def register(self, key: str | type, provider: Any, **kwargs) -> None:
        """Register a service directly.
        
        Args:
            key: Service key
            provider: Service provider
            **kwargs: Additional registration options
        """
        if provider is None:
            raise ValueError("Provider cannot be None")
        self.container.register(key, provider, **kwargs)
    
    def transient(self, key: str | type, provider: Any = None, **kwargs) -> None:
        """Register a transient service.
        
        Args:
            key: Service key
            provider: Service provider (uses key if None and key is a type)
            **kwargs: Additional registration options
        """
        if provider is None and isinstance(key, type):
            provider = key
        self.container.register(key, provider, scope=Scope.TRANSIENT, **kwargs)
    
    # Decorator methods for component registration

    def component(
        self,
        cls: Type[T] = None,
        *,
        key: str | type = None,
        name: str = None,
        scope: Scope = Scope.TRANSIENT,
        tags: set[str] = None,
        condition: Callable[[], bool] = None,
        lazy: bool = False,
        metadata: dict = None,
        priority: int = None,
    ) -> Union[Type[T], Callable[[Type[T]], Type[T]]]:
        """Decorator to register a class as a component.

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
            >>> @app.component
            >>> class DatabaseService:
            ...     pass

            >>> @app.component(name="primary", scope=Scope.SINGLETON)
            >>> class DatabaseService:
            ...     pass
        """

        def decorator(cls: Type[T]) -> Type[T]:
            # Check if it's a function (not a class) and key is missing
            if not inspect.isclass(cls) and key is None:
                raise ConfigurationError("Factory functions require a 'key' parameter")

            # If name is provided, use it as the key
            if name is not None:
                component_key = name
                registration_name = None
            else:
                component_key = key or cls
                registration_name = name

            # Prepare kwargs for registration
            registration_kwargs = {
                "scope": scope,
                "name": registration_name,
                "condition": condition,
                "tags": tags or set(),
                "lazy": lazy,
                "allow_override": True,  # Allow decorators to override registrations
            }
            
            # Add metadata if provided
            if metadata is not None:
                registration_kwargs["metadata"] = metadata
            if priority is not None:
                registration_kwargs.setdefault("metadata", {})["priority"] = priority
            
            self.container.register(
                component_key,
                cls,
                **registration_kwargs
            )

            return cls

        if cls is None:
            # Used with parentheses: @app.service(...)
            return decorator
        else:
            # Used without parentheses: @app.service
            return decorator(cls)

    def singleton(
        self,
        cls: Type[T] = None,
        *,
        key: str | type = None,
        name: str = None,
        tags: set[str] = None,
        condition: Callable[[], bool] = None,
        lazy: bool = False,
        instance: Any = None,
    ) -> Union[Type[T], Callable[[Type[T]], Type[T]]]:
        """Decorator to register a class as a singleton service."""
        # If instance is provided, register it directly
        if instance is not None:
            component_key = key or cls or type(instance)
            self.container.register(
                component_key,
                instance,
                scope=Scope.SINGLETON,
                name=name,
                tags=tags or set(),
                condition=condition,
                lazy=lazy,
            )
            return cls or type(instance)
        
        return self.component(
            cls,
            key=key,
            name=name,
            scope=Scope.SINGLETON,
            tags=tags,
            condition=condition,
            lazy=lazy,
        )

    def scoped(
        self,
        cls: Type[T] = None,
        *,
        scope_name: str = "default",
        key: str | type = None,
        name: str = None,
        tags: set[str] = None,
        condition: Callable[[], bool] = None,
        lazy: bool = False,
    ) -> Union[Type[T], Callable[[Type[T]], Type[T]]]:
        """Decorator to register a class as a scoped service."""
        return self.component(
            cls, key=key, name=name, scope=Scope.SCOPED, tags=tags, condition=condition, lazy=lazy
        )

    def factory(
        self,
        key: str | type,
        func: Callable,
        *,
        name: str = None,
        scope: Scope = Scope.TRANSIENT,
        tags: set[str] = None,
        condition: Callable[[], bool] = None,
        lazy: bool = False,
    ) -> None:
        """Register a function as a factory.

        Args:
            key: Service key (required for factories)
            func: The factory function to register
            name: Optional name for named services
            scope: Service scope (default: transient)
            tags: Set of tags for categorization
            condition: Optional registration condition
            lazy: Whether to use lazy resolution
        """
        self.container.register(
            key,
            func,
            scope=scope,
            name=name,
            condition=condition,
            tags=tags or set(),
            lazy=lazy,
        )

    # Decorator aliases
    
    @property
    def provider(self):
        """Alias for component decorator."""
        return self.component
    
    @property
    def managed(self):
        """Alias for component decorator (transient scope)."""
        return self.component
    
    @property  
    def system(self):
        """Alias for singleton decorator."""
        return self.singleton
    
    @property
    def inject(self):
        """Decorator for dependency injection in functions."""
        def decorator(func: Callable) -> Callable:
            return self.wrap_function(func)
        return decorator
    
    # Lifecycle decorators
    
    @property
    def on_startup(self):
        """Decorator to register startup callbacks."""
        def decorator(func: Callable) -> Callable:
            # Add to startup callbacks
            self._startup_callbacks.append(func)
            # If app is already running, execute immediately  
            if self._is_running:
                if asyncio.iscoroutinefunction(func):
                    # Create a task for immediate execution
                    task = asyncio.create_task(func())
                    self._hooks.setdefault("startup_tasks", []).append(task)
                else:
                    func()
            return func
        return decorator
    
    @property
    def on_shutdown(self):
        """Decorator to register shutdown callbacks."""
        def decorator(func: Callable) -> Callable:
            self._shutdown_callbacks.append(func)
            return func
        return decorator
    
    @property
    def on_error(self):
        """Decorator to register error handlers."""
        def decorator(func: Callable) -> Callable:
            # Register as a generic error handler
            self._error_handlers[Exception] = func
            return func
        return decorator
    
    @property
    def task(self):
        """Decorator to register background tasks."""
        def decorator(interval: float = None, **kwargs):
            def inner(func: Callable) -> Callable:
                # Store task metadata
                func._task_interval = interval
                func._task_kwargs = kwargs
                self._hooks.setdefault("tasks", []).append(func)
                return func
            return inner
        return decorator
    
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
                kwargs["condition"] = condition
                return getattr(self, decorator_name)(target, **kwargs)

            return decorator

        # Return a helper object that provides all decorator types
        return ConditionalDecoratorHelper(self, condition)

    def when_debug(self):
        """Decorator factory for debug mode conditional registration."""
        import os

        condition = lambda: os.environ.get("DEBUG", "").lower() in ("true", "1", "yes")
        return ConditionalDecoratorHelper(self, condition)

    def when_production(self):
        """Decorator factory for production mode conditional registration."""
        import os

        condition = lambda: os.environ.get("ENV", "").lower() in ("prod", "production")
        return ConditionalDecoratorHelper(self, condition)

    # Lifecycle methods

    async def startup(self) -> None:
        """Start the application and run startup callbacks."""
        if self._is_running:
            return

        try:
            self._is_running = True
            
            # Initialize all services that implement Initializable
            for descriptor in self.container.registry.list_all():
                # Get or create instance
                instance = await self.container.resolve(descriptor.service_type)
                # Initialize if it implements Initializable
                if hasattr(instance, 'initialize') and callable(getattr(instance, 'initialize')):
                    await instance.initialize()

            # Run startup callbacks
            for callback in self._startup_callbacks:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
            
            # Start background tasks
            if "tasks" in self._hooks:
                for task_func in self._hooks["tasks"]:
                    if hasattr(task_func, "_task_interval"):
                        interval = task_func._task_interval
                        if interval:
                            # Create a periodic task
                            async def run_periodic():
                                while self._is_running:
                                    await task_func()
                                    await asyncio.sleep(interval)
                            
                            task = asyncio.create_task(run_periodic())
                            self._hooks.setdefault("running_tasks", []).append(task)
        except Exception:
            # If startup fails, reset running state
            self._is_running = False
            raise

    async def shutdown(self) -> None:
        """Shutdown the application and run cleanup callbacks."""
        if not self._is_running:
            return

        self._is_running = False
        
        # Cancel running tasks
        if "running_tasks" in self._hooks:
            for task in self._hooks["running_tasks"]:
                task.cancel()
            # Wait for tasks to finish cancellation
            await asyncio.gather(*self._hooks["running_tasks"], return_exceptions=True)
            self._hooks["running_tasks"].clear()

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
        
        # Dispose all services that implement Disposable
        disposed_instances = set()
        for descriptor in self.container.registry.list_all():
            if descriptor.scope == Scope.SINGLETON:
                try:
                    # Get singleton instance if it exists
                    instance = self.container.resolve_sync(descriptor.service_type)
                    if instance not in disposed_instances and hasattr(instance, 'dispose') and callable(getattr(instance, 'dispose')):
                        await instance.dispose()
                        disposed_instances.add(instance)
                except Exception:
                    # Continue disposal even if one fails
                    pass

        # Clear container caches
        self.container.clear_caches()

    # Aliases for compatibility
    async def start(self) -> None:
        """Alias for startup."""
        await self.startup()

    async def stop(self) -> None:
        """Alias for shutdown."""
        await self.shutdown()

    async def emit(self, event: str, *args, **kwargs) -> None:
        """Emit an event to all registered handlers."""
        # Handle error events specially
        if event == "error" and args:
            error = args[0]
            # Check for specific error type first, then fallback to Exception
            handler = None
            if type(error) in self._error_handlers:
                handler = self._error_handlers[type(error)]
            elif Exception in self._error_handlers:
                handler = self._error_handlers[Exception]
            
            if handler:
                if asyncio.iscoroutinefunction(handler):
                    await handler(error)
                else:
                    handler(error)
        
        # Handle regular events
        if event in self._hooks:
            for handler in self._hooks[event]:
                if asyncio.iscoroutinefunction(handler):
                    await handler(*args, **kwargs)
                else:
                    handler(*args, **kwargs)
        
        # Handle wildcard handlers
        if "*" in self._hooks:
            for handler in self._hooks["*"]:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event, *args, **kwargs)
                else:
                    handler(event, *args, **kwargs)

    async def __aenter__(self):
        """Async context manager entry."""
        await self.startup()
        return self

    async def __aexit__(self, *args):
        """Async context manager exit."""
        # Wait for any pending startup tasks
        if "startup_tasks" in self._hooks:
            await asyncio.gather(*self._hooks["startup_tasks"])
            self._hooks["startup_tasks"].clear()
        await self.shutdown()
    
    def __enter__(self):
        """Sync context manager entry."""
        # Run startup synchronously
        try:
            loop = asyncio.get_running_loop()
            # We're already in an event loop
            raise RuntimeError("Cannot use sync context manager in async context")
        except RuntimeError:
            # No event loop, we can create one
            asyncio.run(self.startup())
        return self
    
    def __exit__(self, *args):
        """Sync context manager exit."""
        try:
            loop = asyncio.get_running_loop()
            # We're already in an event loop
            raise RuntimeError("Cannot use sync context manager in async context")
        except RuntimeError:
            # No event loop, we can create one
            asyncio.run(self.shutdown())

    # Function calling methods

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Call a function with dependency injection (synchronous)."""
        return self.container.call_sync(func, *args, **kwargs)
    
    async def call_async(self, func: Callable, *args, **kwargs) -> Any:
        """Call a function with dependency injection (asynchronous)."""
        return await self.container.call(func, *args, **kwargs)

    def call_sync(self, func: Callable, *args, **kwargs) -> Any:
        """Call a function with dependency injection (synchronous)."""
        return self.container.call_sync(func, *args, **kwargs)
    
    def invoke(self, func: Callable, **overrides) -> Any:
        """Invoke a function with full dependency injection (synchronous)."""
        return self.container.invoke_sync(func, **overrides)

    async def invoke_async(self, func: Callable, **overrides) -> Any:
        """Invoke a function with full dependency injection (asynchronous)."""
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

    def configure(self, config_func: Callable[[Whiskey], None]) -> Whiskey:
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
    
    # Extension methods
    
    def use(self, middleware: Callable) -> Whiskey:
        """Add middleware to the application."""
        self._middleware.append(middleware)
        # Execute immediately if it's an extension function
        middleware(self)
        return self
    
    def on(self, event: str, handler: Callable = None) -> Union[Whiskey, Callable]:
        """Register an event handler.
        
        Can be used as a method or decorator:
            app.on("event", handler)
            @app.on("event")
            def handler(): ...
        """
        if handler is None:
            # Used as decorator
            def decorator(func: Callable) -> Callable:
                self._hooks.setdefault(event, []).append(func)
                return func
            return decorator
        else:
            # Used as method
            self._hooks.setdefault(event, []).append(handler)
            return self
    
    @property
    def hook(self):
        """Decorator to register a hook."""
        def decorator(name: str):
            def inner(func: Callable) -> Callable:
                self._hooks.setdefault(name, []).append(func)
                return func
            return inner
        return decorator
    
    def extend(self, extension: Callable) -> Whiskey:
        """Apply an extension to the application."""
        extension(self)
        return self
    
    def add_decorator(self, name: str, decorator: Callable) -> Whiskey:
        """Add a custom decorator method."""
        setattr(self, name, decorator)
        return self
    
    def add_singleton(self, key: str | type, provider: Any = None, *, instance: Any = None, **kwargs) -> None:
        """Add a singleton service."""
        # If instance is provided as keyword arg, use it as provider
        if instance is not None:
            provider = instance
        elif provider is None and isinstance(key, type):
            provider = key
        self.container.register(key, provider, scope=Scope.SINGLETON, **kwargs)
    
    def add_transient(self, key: str | type, provider: Any = None, **kwargs) -> None:
        """Add a transient service."""
        if provider is None and isinstance(key, type):
            provider = key
        self.container.register(key, provider, scope=Scope.TRANSIENT, **kwargs)
    
    @property
    def builder(self) -> ComponentBuilder:
        """Get a component builder for this container."""
        from .builder import ComponentBuilder
        # Return a builder that adds to this container
        return ComponentBuilder(self, None, None)


class ConditionalDecoratorHelper:
    """Helper class for conditional decorators."""

    def __init__(self, app: Whiskey, condition: Callable[[], bool]):
        self.app = app
        self.condition = condition

    def __call__(self, target=None, **kwargs):
        """Make the helper callable as a decorator."""
        kwargs["condition"] = self.condition
        
        # If target is already registered, preserve its scope and other attributes
        if target in self.app.container:
            try:
                descriptor = self.app.container.registry.get(target)
                kwargs.setdefault("scope", descriptor.scope)
                kwargs.setdefault("tags", descriptor.tags)
                kwargs.setdefault("lazy", descriptor.lazy)
            except KeyError:
                pass
        
        return self.app.component(target, **kwargs)

    def service(
        self, cls: Type[T] = None, **kwargs
    ) -> Union[Type[T], Callable[[Type[T]], Type[T]]]:
        """Conditionally register a service."""
        kwargs["condition"] = self.condition
        return self.app.component(cls, **kwargs)

    def singleton(
        self, cls: Type[T] = None, **kwargs
    ) -> Union[Type[T], Callable[[Type[T]], Type[T]]]:
        """Conditionally register a singleton."""
        kwargs["condition"] = self.condition
        return self.app.singleton(cls, **kwargs)

    def factory(
        self, func: Callable = None, **kwargs
    ) -> Union[Callable, Callable[[Callable], Callable]]:
        """Conditionally register a factory."""
        kwargs["condition"] = self.condition
        return self.app.factory(func, **kwargs)

    def component(self, target=None, **kwargs):
        """Conditionally register a component."""
        kwargs["condition"] = self.condition
        return self.app.component(target, **kwargs)


# Global application instance management
def set_current_app(app: Whiskey) -> None:
    """Set the current global application instance."""
    global _current_application
    _current_application = app


def get_current_app() -> Whiskey | None:
    """Get the current global application instance."""
    return _current_application


def create_default_app() -> Whiskey:
    """Create a default application instance."""
    app = Whiskey()
    set_current_app(app)
    return app
