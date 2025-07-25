"""Optional application class for managing lifecycle."""

from __future__ import annotations

import asyncio
import signal
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Callable

from whiskey.core.container import Container
from whiskey.core.decorators import set_default_container
from whiskey.core.types import Disposable, Initializable


@dataclass
class ApplicationConfig:
    """Simple application configuration."""
    name: str = "Whiskey Application"
    extensions: list[Callable[[Application], None]] = field(default_factory=list)


class Application:
    """Optional application class for lifecycle management.
    
    This class is optional - you can use the Container directly for simple cases.
    The Application adds:
    - Lifecycle management (startup/shutdown)
    - Extension support
    - Background task management
    
    Example:
        app = Application()
        
        @app.service
        class DatabaseService:
            async def initialize(self):
                print("Connecting to database...")
                
        async with app.lifespan():
            # Services are initialized
            # Use your application
            pass
        # Services are disposed
    """
    
    def __init__(self, config: ApplicationConfig | None = None):
        self.config = config or ApplicationConfig()
        self.container = Container()
        self._startup_hooks: list[Callable] = []
        self._shutdown_hooks: list[Callable] = []
        self._background_tasks: list[asyncio.Task] = []
        
        # Set as default container
        set_default_container(self.container)
        
        # Apply extensions from config
        for extension in self.config.extensions:
            extension(self)
            
    def extend(self, extension: Callable[[Application], None]) -> Application:
        """Apply an extension function."""
        extension(self)
        return self
        
    def use(self, *extensions: Callable[[Application], None]) -> Application:
        """Apply multiple extensions."""
        for extension in extensions:
            self.extend(extension)
        return self
        
    def service(self, cls: type | None = None, **kwargs):
        """Register a service and handle its lifecycle.
        
        Can be used as a decorator or called directly.
        """
        def register(service_cls: type) -> type:
            # Register with container
            self.container.register(service_cls, service_cls, **kwargs)
            
            # Add lifecycle hooks if present
            if issubclass(service_cls, Initializable):
                async def init():
                    await self._initialize_service(service_cls)
                self.on_startup(init)
            if issubclass(service_cls, Disposable):
                async def dispose():
                    await self._dispose_service(service_cls)
                self.on_shutdown(dispose)
                
            return service_cls
            
        if cls is None:
            return register
        return register(cls)
        
    def on_startup(self, func: Callable) -> Callable:
        """Register a startup hook."""
        self._startup_hooks.append(func)
        return func
        
    def on_shutdown(self, func: Callable) -> Callable:
        """Register a shutdown hook."""
        self._shutdown_hooks.append(func)
        return func
        
    def task(self, func: Callable) -> Callable:
        """Register a background task."""
        self.on_startup(lambda: self._start_background_task(func))
        return func
        
    async def startup(self) -> None:
        """Run startup hooks."""
        for hook in self._startup_hooks:
            if asyncio.iscoroutinefunction(hook):
                await hook()
            else:
                hook()
                
    async def shutdown(self) -> None:
        """Run shutdown hooks and cancel tasks."""
        # Cancel background tasks
        for task in self._background_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
                
        # Run shutdown hooks
        for hook in reversed(self._shutdown_hooks):
            if asyncio.iscoroutinefunction(hook):
                await hook()
            else:
                hook()
                
    @asynccontextmanager
    async def lifespan(self):
        """Context manager for application lifecycle."""
        await self.startup()
        try:
            yield self
        finally:
            await self.shutdown()
            
    async def _initialize_service(self, service_type: type) -> None:
        """Initialize a service."""
        service = await self.container.resolve(service_type)
        if hasattr(service, 'initialize'):
            await service.initialize()
            
    async def _dispose_service(self, service_type: type) -> None:
        """Dispose a service."""
        try:
            service = await self.container.resolve(service_type)
            if hasattr(service, 'dispose'):
                await service.dispose()
        except KeyError:
            pass  # Service not instantiated
            
    def _start_background_task(self, func: Callable) -> None:
        """Start a background task."""
        async def run_task():
            if asyncio.iscoroutinefunction(func):
                await func()
            else:
                func()
                
        task = asyncio.create_task(run_task())
        self._background_tasks.append(task)
        
    def run(self, main: Callable | None = None) -> None:
        """Run the application with optional main function."""
        async def run_async():
            # Set up signal handlers
            loop = asyncio.get_event_loop()
            
            def signal_handler():
                loop.create_task(self.shutdown())
                loop.stop()
                
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, signal_handler)
                
            async with self.lifespan():
                if main:
                    if asyncio.iscoroutinefunction(main):
                        await main()
                    else:
                        main()
                else:
                    # Keep running until signal
                    await asyncio.Event().wait()
                    
        asyncio.run(run_async())