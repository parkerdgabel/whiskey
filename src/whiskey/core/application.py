<<<<<<< HEAD
"""Rich IoC application framework with lifecycle management and events.

This module provides the Whiskey class, which extends the basic Container
with a complete application framework including lifecycle management, event
handling, component discovery, and extension support. It serves as the main
entry point for building full-featured dependency injection applications.

Key Features:
    - Complete application lifecycle (startup, ready, shutdown)
    - Event-driven architecture with wildcard patterns
    - Component decorators (@app.component, @app.singleton)
    - Background task management (@app.task)
    - Error handling (@app.on_error)
    - Extension system for plugins
    - Conditional registration based on environment

Classes:
    Whiskey: Main application class with rich IoC features

Functions:
    create_default_app: Create the default application instance
    _conditional_decorator: Helper for conditional component registration

Example:
    >>> app = Whiskey()
    >>> 
    >>> # Register components with decorators
    >>> @app.singleton
    ... class Database:
    ...     async def initialize(self):
    ...         await self.connect()
    >>> 
    >>> @app.component
    ... class EmailService:
    ...     def __init__(self, db: Database):
    ...         self.db = db
    >>> 
    >>> # Lifecycle hooks
    >>> @app.on_startup
    ... async def configure():
    ...     print("Application starting...")
    >>> 
    >>> # Run the application
    >>> async with app:
    ...     service = await app.resolve(EmailService)
    
See Also:
    - whiskey.core.container: Base container functionality
    - whiskey.core.decorators: Global decorators
    - whiskey.core.discovery: Component discovery system
"""
=======
"""Rich IoC application container with lifecycle management."""
>>>>>>> origin/main

from __future__ import annotations

import asyncio
<<<<<<< HEAD
import inspect
from typing import Any, Callable, Type, TypeVar, Union

from .container import Container
from .errors import ConfigurationError
from .registry import Scope

T = TypeVar("T")

# Global application instance for decorators
_current_application: Whiskey = None


class Whiskey:
    """Main Whiskey class with lifecycle management and decorator support.
    
    This class provides the main entry point for Whiskey applications,
    integrating container functionality with lifecycle management
    and convenience decorators.
    
    Examples:
        Direct instantiation:
        
        >>> app = Whiskey()
        >>> app.singleton(DatabaseService)
        >>> app.component(EmailService)
        
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

        self._is_running = False
        # Add hooks for lifecycle compatibility
        self._hooks = {
            "before_startup": self._startup_callbacks,
            "after_shutdown": self._shutdown_callbacks,
            "tasks": []
        }

    # Builder pattern removed - use Whiskey() or Whiskey.create() directly

    @classmethod
    def create(cls, container: Container = None, name: str = None) -> 'Whiskey':
        """Create a new Whiskey application.
        
        Args:
            container: Optional Container instance (creates new one if None)
            name: Optional name for the application
            
        Returns:
            New Whiskey instance
        """
        return cls(container=container, name=name)

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

    # Removed decorator aliases - use component() and singleton() directly
    
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

        # Return a conditional decorator
        return _conditional_decorator(self, condition)

    def when_debug(self):
        """Decorator factory for debug mode conditional registration."""
        import os

        condition = lambda: os.environ.get("DEBUG", "").lower() in ("true", "1", "yes")
        return _conditional_decorator(self, condition)

    def when_production(self):
        """Decorator factory for production mode conditional registration."""
        import os

        condition = lambda: os.environ.get("ENV", "").lower() in ("prod", "production")
        return _conditional_decorator(self, condition)

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
    
    # Standardized run API
    
    def run(self, main: Callable = None, *, mode: str = "auto", **kwargs) -> Any:
        """Execute a callable within the Whiskey IoC context.
        
        This is the standardized way to run programs with Whiskey. It handles:
        - Application lifecycle (startup/shutdown)
        - Dependency injection for the main callable
        - Async/sync execution based on the callable
        - Extension-specific runners (CLI, ASGI, etc.)
        
        Args:
            main: The main callable to execute. If None, will attempt to find
                  an appropriate runner based on registered extensions.
            mode: Execution mode - "auto", "sync", or "async". Auto detects
                  based on the callable.
            **kwargs: Additional arguments passed to the main callable or runner.
            
        Returns:
            The result of executing the main callable.
            
        Examples:
            # Run a simple function
            app.run(lambda: print("Hello"))
            
            # Run an async function with DI
            @inject
            async def main(db: Database):
                await db.connect()
                
            app.run(main)
            
            # Let extensions handle execution
            app.use(cli_extension)
            app.run()  # Will run CLI
        """
        # Determine execution mode
        if mode == "auto":
            if main is not None:
                mode = "async" if asyncio.iscoroutinefunction(main) else "sync"
            else:
                # Check for registered runners
                runners = self._find_runners()
                if runners:
                    # Use the first available runner
                    return runners[0](**kwargs)
                else:
                    raise RuntimeError("No main callable provided and no runners found")
        
        # Execute with lifecycle management
        if mode == "async":
            try:
                # Check if we're already in an event loop (e.g., pytest-asyncio)
                loop = asyncio.get_running_loop()
                # We're in a loop, schedule as a task
                return loop.run_until_complete(self._run_async(main, **kwargs))
            except RuntimeError:
                # No loop, create one
                return asyncio.run(self._run_async(main, **kwargs))
        else:
            return self._run_sync(main, **kwargs)
    
    async def _run_async(self, main: Callable, **kwargs) -> Any:
        """Run an async callable with lifecycle management."""
        async with self:
            if main is None:
                # Just run the application until interrupted
                try:
                    await asyncio.Event().wait()
                except KeyboardInterrupt:
                    pass
                return None
            
            # Execute the main callable with DI
            return await self.call_async(main, **kwargs)
    
    def _run_sync(self, main: Callable, **kwargs) -> Any:
        """Run a sync callable with lifecycle management."""
        async def wrapper():
            async with self:
                if main is None:
                    return None
                # Handle both sync and async functions
                if asyncio.iscoroutinefunction(main):
                    # It's an async function, await it
                    return await self.call_async(main, **kwargs)
                elif hasattr(main, '__wrapped__') or self._needs_injection(main):
                    # Sync function that needs injection
                    return await self.call_async(main, **kwargs)
                else:
                    # Plain sync function, just call it
                    return main(**kwargs)
        
        try:
            # Check if we're already in an event loop
            loop = asyncio.get_running_loop()
            # We're in a loop, schedule as a task
            return loop.run_until_complete(wrapper())
        except RuntimeError:
            # No loop, create one
            return asyncio.run(wrapper())
    
    def _needs_injection(self, func: Callable) -> bool:
        """Check if a function might need dependency injection."""
        import inspect
        if not callable(func):
            return False
        
        try:
            sig = inspect.signature(func)
            # Check if any parameters have type annotations that might be injectable
            for param in sig.parameters.values():
                if param.annotation != param.empty and param.annotation not in (str, int, float, bool, list, dict, tuple, set):
                    # Has a complex type annotation, might need injection
                    return True
            return False
        except:
            return False
    
    def _find_runners(self) -> List[Callable]:
        """Find available runners from extensions."""
        runners = []
        
        # Check for known runner methods added by extensions
        runner_attrs = ['run_cli', 'run_asgi', 'run_worker', 'run_scheduler']
        for attr in runner_attrs:
            if hasattr(self, attr):
                runners.append(getattr(self, attr))
        
        # Check for custom runners registered via hooks
        if 'runners' in self._hooks:
            runners.extend(self._hooks['runners'])
        
        return runners
    
    def register_runner(self, name: str, runner: Callable) -> None:
        """Register a custom runner.
        
        Extensions can use this to register their own runners that will be
        available via app.run() when no main callable is provided.
        
        Args:
            name: Name of the runner (e.g., "cli", "asgi")
            runner: Callable that runs the application
            
        Example:
            def my_runner(**kwargs):
                # Custom runner logic
                pass
                
            app.register_runner("custom", my_runner)
        """
        self._hooks.setdefault('runners', []).append(runner)
        # Also set as attribute for direct access
        setattr(self, f'run_{name}', runner)

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
    
    @property
    def lifespan(self):
        """Context manager for application lifecycle.
        
        Can be used in both sync and async contexts:
        
        async with app.lifespan():
            # Async context
            await app.resolve(Service)
            
        with app.lifespan():
            # Sync context (requires no running event loop)
            app.resolve_sync(Service)
        """
        return self
    
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
        return self.container.call_sync(func, **overrides)

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
    
    def use(self, extension: Callable[..., None], **kwargs) -> Whiskey:
        """Apply an extension to the application with optional configuration.
        
        Extensions are functions that add functionality to the Whiskey instance.
        They are executed immediately when called.
        
        Args:
            extension: Function that takes a Whiskey instance and optional kwargs
            **kwargs: Configuration options passed to the extension
            
        Returns:
            Self for chaining
            
        Example:
            def jobs_extension(app: Whiskey, worker_pool_size: int = 4, **kwargs) -> None:
                app.jobs = JobManager(worker_pool_size=worker_pool_size)
                app.add_decorator("job", job_decorator)
            
            app = Whiskey()
            app.use(jobs_extension, worker_pool_size=8, auto_start=False)
        """
        extension(self, **kwargs)
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
    
    def extend(self, *extensions: Callable, **kwargs) -> Whiskey:
        """Apply one or more extensions to the application.
        
        Args:
            *extensions: Extension functions to apply
            **kwargs: Configuration passed to all extensions
            
        Returns:
            Self for chaining
            
        Example:
            app.extend(jobs_extension, auth_extension, worker_pool_size=8)
        """
        for extension in extensions:
            extension(self, **kwargs)
        return self
    
    def add_decorator(self, name: str, decorator: Callable) -> Whiskey:
        """Add a custom decorator method."""
        setattr(self, name, decorator)
        return self
    
    # Removed add_singleton and add_transient - use singleton() and transient() instead
    
    # Removed builder property - use direct registration methods instead


def _conditional_decorator(app: Whiskey, condition: Callable[[], bool]):
    """Create a conditional decorator."""
    def decorator(target=None, **kwargs):
        kwargs["condition"] = condition
        return app.component(target, **kwargs)
    
    # Add methods for different registration types
    decorator.component = lambda target=None, **kw: app.component(target, condition=condition, **kw)
    decorator.singleton = lambda target=None, **kw: app.singleton(target, condition=condition, **kw)
    decorator.factory = lambda key, func, **kw: app.factory(key, func, condition=condition, **kw)
    
    return decorator


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
=======
import functools
import signal
from collections import defaultdict
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Set

from whiskey.core.container import Container
from whiskey.core.decorators import set_default_container
from whiskey.core.types import Disposable, Initializable


@dataclass
class ApplicationConfig:
    """Application configuration."""
    name: str = "Whiskey Application"
    extensions: list[Callable[[Application], None]] = field(default_factory=list)
    debug: bool = False


@dataclass 
class ComponentMetadata:
    """Metadata for registered components."""
    component_type: type
    name: str | None = None
    priority: int = 0
    requires: Set[type] = field(default_factory=set)
    provides: Set[str] = field(default_factory=set)
    tags: Set[str] = field(default_factory=set)
    critical: bool = False
    health_check: Callable | None = None


class Application:
    """Rich IoC container for building any Python application.
    
    Features:
    - Rich lifecycle phases with hooks
    - Built-in event emitter
    - Component metadata and decorators
    - Extension system
    - Background task management
    
    Example:
        app = Application()
        
        @app.component
        @app.priority(10)
        class DatabaseService:
            async def initialize(self):
                print("Connecting to database...")
                
        @app.on("user.created")
        async def send_welcome_email(user):
            print(f"Welcome {user.name}!")
            
        async with app.lifespan():
            await app.emit("user.created", {"name": "Alice"})
    """
    
    def __init__(self, config: ApplicationConfig | None = None):
        self.config = config or ApplicationConfig()
        self.container = Container()
        
        # Lifecycle hooks
        self._hooks: Dict[str, List[Callable]] = defaultdict(list)
        self._background_tasks: List[asyncio.Task] = []
        
        # Event system
        self._event_handlers: Dict[str, List[Callable]] = defaultdict(list)
        
        # Component metadata
        self._component_metadata: Dict[type, ComponentMetadata] = {}
        
        # Extension hooks
        self._lifecycle_phases = [
            "configure", "register", "before_startup", "startup", 
            "after_startup", "ready", "before_shutdown", "shutdown", 
            "after_shutdown", "error"
        ]
        self._component_decorators: Dict[str, Callable] = {}
        self._resolver_hooks: List[Callable] = []
        
        # Set as default container
        set_default_container(self.container)
        
        # Apply extensions from config
        for extension in self.config.extensions:
            extension(self)
    
    # Extension methods
    
    def extend(self, extension: Callable[[Application], None]) -> Application:
        """Apply an extension function."""
        extension(self)
        return self
        
    def use(self, *extensions: Callable[[Application], None]) -> Application:
        """Apply multiple extensions."""
        for extension in extensions:
            self.extend(extension)
        return self
    
    # Component registration with new names
    
    def component(self, cls: type | None = None, **kwargs):
        """Register a component (most generic).
        
        Can be used as a decorator or called directly.
        """
        def register(component_cls: type) -> type:
            # Create metadata
            metadata = ComponentMetadata(
                component_type=component_cls,
                name=kwargs.get("name"),
            )
            self._component_metadata[component_cls] = metadata
            
            # Register with container
            self.container.register(component_cls, component_cls, **kwargs)
            
            # Add lifecycle hooks if present
            if issubclass(component_cls, Initializable):
                async def init():
                    await self._initialize_component(component_cls)
                self.on_startup(init)
                
            if issubclass(component_cls, Disposable):
                async def dispose():
                    await self._dispose_component(component_cls)
                self.on_shutdown(dispose)
            
            # Fire registration event during configure phase
            async def emit_event():
                await self.emit("component.registered", {
                    "type": component_cls,
                    "metadata": metadata
                })
            self.on_configure(emit_event)
            
            return component_cls
            
        if cls is None:
            return register
        return register(cls)
    
    # Aliases for specific use cases
    provider = component  # Provides a service/resource
    managed = component   # Managed component with lifecycle
    system = component    # System-level component
    
    # Legacy compatibility
    service = component
    
    # Component metadata decorators
    
    def priority(self, level: int):
        """Set component startup/shutdown priority."""
        def decorator(cls: type) -> type:
            # Ensure metadata exists
            if cls not in self._component_metadata:
                self._component_metadata[cls] = ComponentMetadata(component_type=cls)
            self._component_metadata[cls].priority = level
            return cls
        return decorator
    
    def requires(self, *dependencies: type):
        """Declare component dependencies."""
        def decorator(cls: type) -> type:
            # Ensure metadata exists
            if cls not in self._component_metadata:
                self._component_metadata[cls] = ComponentMetadata(component_type=cls)
            self._component_metadata[cls].requires.update(dependencies)
            return cls
        return decorator
    
    def provides(self, *capabilities: str):
        """Declare what the component provides."""
        def decorator(cls: type) -> type:
            # Ensure metadata exists
            if cls not in self._component_metadata:
                self._component_metadata[cls] = ComponentMetadata(component_type=cls)
            self._component_metadata[cls].provides.update(capabilities)
            return cls
        return decorator
    
    def critical(self, cls: type) -> type:
        """Mark component as critical (must start or app fails)."""
        # Ensure metadata exists
        if cls not in self._component_metadata:
            self._component_metadata[cls] = ComponentMetadata(component_type=cls)
        self._component_metadata[cls].critical = True
        return cls
    
    def health_check(self, func: Callable) -> Callable:
        """Register a health check for the component."""
        # This would be used by the health extension
        return func
    
    # Rich lifecycle phases
    
    def on_configure(self, func: Callable) -> Callable:
        """Hook called after app creation, before components."""
        self._hooks["configure"].append(func)
        return func
    
    def on_register(self, func: Callable) -> Callable:
        """Hook called during component registration."""
        self._hooks["register"].append(func)
        return func
    
    def before_startup(self, func: Callable) -> Callable:
        """Hook called before startup begins."""
        self._hooks["before_startup"].append(func)
        return func
        
    def on_startup(self, func: Callable) -> Callable:
        """Hook called during startup."""
        self._hooks["startup"].append(func)
        return func
    
    def after_startup(self, func: Callable) -> Callable:
        """Hook called after all startup complete."""
        self._hooks["after_startup"].append(func)
        return func
    
    def on_ready(self, func: Callable) -> Callable:
        """Hook called when application is fully ready."""
        self._hooks["ready"].append(func)
        return func
    
    def before_shutdown(self, func: Callable) -> Callable:
        """Hook called before shutdown begins."""
        self._hooks["before_shutdown"].append(func)
        return func
        
    def on_shutdown(self, func: Callable) -> Callable:
        """Hook called during shutdown."""
        self._hooks["shutdown"].append(func)
        return func
    
    def after_shutdown(self, func: Callable) -> Callable:
        """Hook called after shutdown complete."""
        self._hooks["after_shutdown"].append(func)
        return func
    
    def on_error(self, func: Callable) -> Callable:
        """Hook called on any lifecycle error."""
        self._hooks["error"].append(func)
        return func
    
    # Event system
    
    def on(self, event: str):
        """Register an event handler.
        
        Supports @inject for automatic dependency injection:
            @app.on("user.created")
            @inject
            async def handle_user(event_data: dict, email_service: EmailService):
                await email_service.send_welcome(event_data["user"])
        """
        def decorator(func: Callable) -> Callable:
            self._event_handlers[event].append(func)
            return func
        return decorator
    
    def emits(self, event: str):
        """Decorator that emits an event with the function's return value.
        
        Example:
            @app.emits("user.created")
            async def create_user(name: str) -> dict:
                user = await db.create_user(name)
                return {"id": user.id, "name": user.name}
                # Automatically emits "user.created" with the returned dict
        """
        def decorator(func: Callable) -> Callable:
            if asyncio.iscoroutinefunction(func):
                @functools.wraps(func)
                async def async_wrapper(*args, **kwargs):
                    result = await func(*args, **kwargs)
                    if result is not None:
                        await self.emit(event, result)
                    return result
                return async_wrapper
            else:
                @functools.wraps(func)
                def sync_wrapper(*args, **kwargs):
                    result = func(*args, **kwargs)
                    if result is not None:
                        # We need to emit asynchronously but we're in a sync context
                        # Create a task to emit the event
                        loop = asyncio.get_event_loop()
                        loop.create_task(self.emit(event, result))
                    return result
                return sync_wrapper
        return decorator
    
    async def emit(self, event: str, data: Any = None) -> None:
        """Emit an event to all handlers."""
        # Direct handlers
        handlers = self._event_handlers.get(event, [])
        
        # Wildcard handlers (e.g., "user.*" matches "user.created")
        for pattern, pattern_handlers in self._event_handlers.items():
            if "*" in pattern:
                prefix = pattern.replace("*", "")
                if event.startswith(prefix):
                    handlers.extend(pattern_handlers)
        
        # Execute all handlers
        for handler in handlers:
            try:
                # Check if handler uses @inject
                if hasattr(handler, "__wrapped__"):
                    # The handler is wrapped by @inject, call it directly
                    # @inject will handle the dependency resolution
                    if asyncio.iscoroutinefunction(handler):
                        await handler(data) if data is not None else await handler()
                    else:
                        handler(data) if data is not None else handler()
                else:
                    # Regular handler without injection
                    if asyncio.iscoroutinefunction(handler):
                        await handler(data) if data is not None else await handler()
                    else:
                        handler(data) if data is not None else handler()
            except Exception as e:
                # Fire error event
                await self._handle_error(e, f"event.{event}")
    
    # Background tasks
    
    def task(self, func: Callable) -> Callable:
        """Register a background task."""
        self.on_startup(lambda: self._start_background_task(func))
        return func
    
    # Main entry point
    
    def main(self, func: Callable) -> Callable:
        """Decorator to mark the main entry point.
        
        Example:
            @app.main
            @inject
            async def main(db: Database, config: Config):
                await db.connect(config.database_url)
                print("Application started!")
            
            app.run()  # Will automatically run the decorated main
        """
        self._main_func = func
        return func
    
    # Lifecycle execution
    
    async def startup(self) -> None:
        """Execute startup lifecycle."""
        try:
            # Configure phase
            await self._run_hooks("configure")
            
            # Before startup
            await self._run_hooks("before_startup")
            
            # Main startup
            await self._run_hooks("startup")
            
            # After startup
            await self._run_hooks("after_startup")
            
            # Ready
            await self._run_hooks("ready")
            await self.emit("application.ready")
            
        except Exception as e:
            await self._handle_error(e, "startup")
            raise
    
    async def shutdown(self) -> None:
        """Execute shutdown lifecycle."""
        try:
            # Before shutdown
            await self._run_hooks("before_shutdown")
            await self.emit("application.stopping")
            
            # Cancel background tasks
            for task in self._background_tasks:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            # Main shutdown
            await self._run_hooks("shutdown")
            
            # After shutdown
            await self._run_hooks("after_shutdown")
            
        except Exception as e:
            await self._handle_error(e, "shutdown")
            raise
    
    @asynccontextmanager
    async def lifespan(self):
        """Context manager for application lifecycle."""
        await self.startup()
        try:
            yield self
        finally:
            await self.shutdown()
    
    # Internal methods
    
    async def _run_hooks(self, phase: str) -> None:
        """Run all hooks for a lifecycle phase."""
        hooks = self._hooks.get(phase, [])
        for hook in hooks:
            # Check if hook uses @inject
            if hasattr(hook, "__wrapped__"):
                # The hook is wrapped by @inject, call it directly
                if asyncio.iscoroutinefunction(hook):
                    await hook()
                else:
                    hook()
            else:
                # Regular hook without injection
                if asyncio.iscoroutinefunction(hook):
                    await hook()
                else:
                    hook()
    
    async def _handle_error(self, error: Exception, phase: str) -> None:
        """Handle lifecycle errors."""
        error_data = {
            "error": error,
            "phase": phase,
            "message": str(error)
        }
        
        # Run error hooks
        for hook in self._hooks.get("error", []):
            try:
                if asyncio.iscoroutinefunction(hook):
                    await hook(error_data)
                else:
                    hook(error_data)
            except:
                pass  # Don't let error handlers cause more errors
        
        # Emit error event
        try:
            await self.emit("application.error", error_data)
        except:
            pass
    
    async def _initialize_component(self, component_type: type) -> None:
        """Initialize a component."""
        component = await self.container.resolve(component_type)
        if hasattr(component, 'initialize'):
            await component.initialize()
            
    async def _dispose_component(self, component_type: type) -> None:
        """Dispose a component."""
        try:
            component = await self.container.resolve(component_type)
            if hasattr(component, 'dispose'):
                await component.dispose()
        except KeyError:
            pass  # Component not instantiated
            
    def _start_background_task(self, func: Callable) -> None:
        """Start a background task with DI support."""
        async def run_task():
            try:
                # Check if task uses @inject
                if hasattr(func, "__wrapped__"):
                    # The task is wrapped by @inject, call it directly
                    if asyncio.iscoroutinefunction(func):
                        await func()
                    else:
                        func()
                else:
                    # Regular task without injection
                    if asyncio.iscoroutinefunction(func):
                        await func()
                    else:
                        func()
            except Exception as e:
                await self._handle_error(e, "background_task")
                
        task = asyncio.create_task(run_task())
        self._background_tasks.append(task)
    
    # Extension API for advanced extensions
    
    def add_lifecycle_phase(self, name: str, before: str | None = None, after: str | None = None) -> None:
        """Add a new lifecycle phase."""
        if before:
            idx = self._lifecycle_phases.index(before)
            self._lifecycle_phases.insert(idx, name)
        elif after:
            idx = self._lifecycle_phases.index(after)
            self._lifecycle_phases.insert(idx + 1, name)
        else:
            self._lifecycle_phases.append(name)
    
    def add_decorator(self, name: str, decorator_factory: Callable) -> None:
        """Add a new component decorator."""
        self._component_decorators[name] = decorator_factory
        # Make it available as an attribute
        setattr(self, name, decorator_factory)
    
    def add_resolver_hook(self, hook: Callable) -> None:
        """Add a hook that's called before resolving components."""
        self._resolver_hooks.append(hook)
    
    # Scope management
    
    def add_scope(self, name: str, scope_class: type) -> None:
        """Add a custom scope to the container.
        
        Example:
            from whiskey.core.scopes import Scope
            
            class ConversationScope(Scope):
                def __init__(self):
                    super().__init__("conversation")
            
            app.add_scope("conversation", ConversationScope)
        """
        self.container.register_scope(name, scope_class)
    
    def get_scope(self, name: str) -> Any:
        """Get a registered scope instance."""
        return self.container.get_scope(name)
    
    def get_metadata(self, component_type: type) -> ComponentMetadata | None:
        """Get metadata for a component."""
        return self._component_metadata.get(component_type)
    
    def get_components_by_tag(self, tag: str) -> List[type]:
        """Get all components with a specific tag."""
        return [
            comp_type for comp_type, metadata in self._component_metadata.items()
            if tag in metadata.tags
        ]
    
    def get_components_providing(self, capability: str) -> List[type]:
        """Get all components providing a capability."""
        return [
            comp_type for comp_type, metadata in self._component_metadata.items()
            if capability in metadata.provides
        ]
    
    # Running the application
        
    def run(self, main: Callable | None = None) -> None:
        """Run the application with optional main function.
        
        If the main function uses @inject, dependencies will be resolved.
        Otherwise, the app instance is passed as the first argument.
        
        If no main is provided but one was registered with @app.main,
        that function will be used.
        
        Example:
            @inject
            async def main(db: Database, cache: Cache):
                # Dependencies are auto-injected
                pass
                
            app.run(main)
            
        Or with decorator:
            @app.main
            @inject
            async def startup(db: Database):
                await db.connect()
                
            app.run()  # Uses the decorated main
        """
        async def run_async():
            # Set up signal handlers
            loop = asyncio.get_event_loop()
            
            def signal_handler():
                loop.create_task(self.shutdown())
                loop.stop()
                
            for sig in (signal.SIGTERM, signal.SIGINT):
                try:
                    loop.add_signal_handler(sig, signal_handler)
                except NotImplementedError:
                    # Windows doesn't support add_signal_handler
                    pass
                    
            async with self.lifespan():
                # Use provided main or fallback to registered one
                main_func = main or getattr(self, '_main_func', None)
                
                if main_func:
                    # Make Application instance available for injection
                    self.container[Application] = self
                    
                    # Check if main uses @inject (has __wrapped__ attribute)
                    if hasattr(main_func, "__wrapped__"):
                        # The main is wrapped by @inject, call it directly
                        if asyncio.iscoroutinefunction(main_func):
                            await main_func()
                        else:
                            main_func()
                    else:
                        # No injection - pass app as first argument for backward compatibility
                        if asyncio.iscoroutinefunction(main_func):
                            await main_func(self)
                        else:
                            main_func(self)
                else:
                    # Keep running until signal
                    await asyncio.Event().wait()
                    
        asyncio.run(run_async())
>>>>>>> origin/main
