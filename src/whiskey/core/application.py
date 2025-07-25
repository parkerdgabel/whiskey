"""Rich IoC application container with lifecycle management."""

from __future__ import annotations

import asyncio
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