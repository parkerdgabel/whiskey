"""Application container for IoC lifecycle management."""

from __future__ import annotations

import asyncio
import signal
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Awaitable, Callable

from loguru import logger

from whiskey.core.container import Container
from whiskey.core.decorators import get_default_container, set_default_container
from whiskey.core.events import EventBus
from whiskey.core.types import Disposable, Initializable
# Plugin imports removed - using new extension pattern


@dataclass
class ApplicationConfig:
    """Configuration for the Whiskey application."""
    
    name: str = "WhiskeyApp"
    version: str = "0.1.0"
    debug: bool = False
    auto_discover: bool = True
    module_scan_paths: list[str] = field(default_factory=list)
    # Component scanning
    component_scan_packages: list[str] = field(default_factory=list)
    component_scan_paths: list[str] = field(default_factory=list)
    # Extension configuration
    extensions: list[Callable[[Application], None]] = field(default_factory=list)
    

class Application:
    """
    Main IoC application container that manages the lifecycle of your application.
    
    This is the heart of IoC - the framework controls the flow, not your code.
    """
    
    def __init__(self, config: ApplicationConfig | None = None):
        self.config = config or ApplicationConfig()
        self.container = Container()
        self.event_bus = EventBus()
        self._running = False
        self._startup_hooks: list[Callable[[], Awaitable[None]]] = []
        self._shutdown_hooks: list[Callable[[], Awaitable[None]]] = []
        self._background_tasks: list[asyncio.Task] = []
        
        # Set as default container
        set_default_container(self.container)
        
        # Register core services
        self.container.register_singleton(Application, instance=self)
        self.container.register_singleton(EventBus, instance=self.event_bus)
        self.container.register_singleton(ApplicationConfig, instance=self.config)
    
    # Lifecycle Hooks
    
    def on_startup(self, func: Callable[[], Awaitable[None]]) -> Callable[[], Awaitable[None]]:
        """Register a startup hook."""
        self._startup_hooks.append(func)
        return func
    
    def on_shutdown(self, func: Callable[[], Awaitable[None]]) -> Callable[[], Awaitable[None]]:
        """Register a shutdown hook."""
        self._shutdown_hooks.append(func)
        return func
    
    # Service Registration
    
    def service(
        self,
        service_class: type[Any] | None = None,
        *,
        name: str | None = None,
        lazy: bool = False,
    ):
        """
        Decorator to register a service with IoC lifecycle management.
        
        @app.service
        class EmailService:
            async def initialize(self):
                # Called automatically on startup
                pass
                
            async def dispose(self):
                # Called automatically on shutdown
                pass
        """
        def decorator(cls: type[Any]) -> type[Any]:
            # Register in container
            self.container.register_singleton(cls, implementation=cls, name=name)
            
            # Register lifecycle hooks if present
            if not lazy:
                @self.on_startup
                async def init_service():
                    instance = await self.container.resolve(cls)
                    if isinstance(instance, Initializable):
                        await instance.initialize()
                        logger.info(f"Initialized service: {cls.__name__}")
                
                @self.on_shutdown
                async def dispose_service():
                    instance = await self.container.resolve(cls)
                    if isinstance(instance, Disposable):
                        await instance.dispose()
                        logger.info(f"Disposed service: {cls.__name__}")
            
            return cls
        
        if service_class is not None:
            return decorator(service_class)
        return decorator
    
    # Background Tasks
    
    def task(
        self,
        *,
        interval: float | None = None,
        cron: str | None = None,
        run_immediately: bool = True,
    ):
        """
        Decorator to register background tasks managed by IoC.
        
        @app.task(interval=60)  # Run every 60 seconds
        async def cleanup_old_data(db: Database):
            await db.cleanup()
        """
        def decorator(func: Callable[..., Awaitable[None]]) -> Callable[..., Awaitable[None]]:
            @self.on_startup
            async def start_task():
                # Inject dependencies
                from whiskey.core.decorators import inject
                injected_func = inject(func)
                
                async def task_wrapper():
                    if run_immediately:
                        await injected_func()
                    
                    if interval:
                        while self._running:
                            await asyncio.sleep(interval)
                            if self._running:
                                try:
                                    await injected_func()
                                except Exception as e:
                                    logger.error(f"Task {func.__name__} failed: {e}")
                
                task = asyncio.create_task(task_wrapper())
                self._background_tasks.append(task)
                logger.info(f"Started background task: {func.__name__}")
            
            return func
        
        return decorator
    
    # Event Handlers
    
    def on(self, event: str | type):
        """
        Decorator to register event handlers with automatic DI.
        
        @app.on(UserCreated)
        async def send_welcome_email(event: UserCreated, email_service: EmailService):
            await email_service.send_welcome(event.user)
        """
        def decorator(func: Callable[..., Awaitable[None]]) -> Callable[..., Awaitable[None]]:
            from whiskey.core.decorators import inject
            injected_func = inject(func)
            
            self.event_bus.on(event, injected_func)
            return func
        
        return decorator
    
    # Middleware
    
    def middleware(self, middleware_class: type[Any] | None = None):
        """
        Register middleware that processes all events/requests.
        
        @app.middleware
        class LoggingMiddleware:
            async def process(self, event: Any, next: Callable):
                logger.info(f"Processing: {event}")
                result = await next(event)
                logger.info(f"Completed: {event}")
                return result
        """
        def decorator(cls: type[Any]) -> type[Any]:
            # Register as singleton
            self.container.register_singleton(cls, implementation=cls)
            
            @self.on_startup
            async def register_middleware():
                instance = await self.container.resolve(cls)
                self.event_bus.add_middleware(instance)
            
            return cls
        
        if middleware_class is not None:
            return decorator(middleware_class)
        return decorator
    
    # Component Scanning
    
    async def _scan_components(self):
        """Scan for components using autodiscovery."""
        from whiskey.core.discovery import AutoDiscovery
        
        if not (self.config.component_scan_packages or self.config.component_scan_paths):
            return
        
        logger.info("Auto-discovering components...")
        discovery = AutoDiscovery(self.container)
        
        # Discover packages
        for package in self.config.component_scan_packages:
            discovery.discover_package(package)
        
        # Discover paths
        for path in self.config.component_scan_paths:
            discovery.discover_path(path)
        
        # Get discovered components
        discovered = discovery._discovered
        if discovered:
            logger.info(f"Auto-discovered {len(discovered)} components")
            
            # Initialize components that implement Initializable
            for component_type in discovered:
                try:
                    instance = await self.container.resolve(component_type)
                    if isinstance(instance, Initializable):
                        await instance.initialize()
                        logger.debug(f"Initialized component: {component_type.__name__}")
                except Exception as e:
                    logger.warning(f"Failed to initialize {component_type.__name__}: {e}")
    
    # Module Discovery
    
    async def discover_modules(self):
        """Auto-discover and register modules based on configuration."""
        if not self.config.auto_discover:
            return
        
        import importlib
        import pkgutil
        
        for path in self.config.module_scan_paths:
            logger.info(f"Scanning modules in: {path}")
            
            # Import all Python modules in the path
            for finder, name, ispkg in pkgutil.iter_modules([path]):
                module = importlib.import_module(name)
                logger.debug(f"Loaded module: {name}")
    
    # Application Lifecycle
    
    async def startup(self):
        """Initialize the application."""
        logger.info(f"Starting {self.config.name} v{self.config.version}")
        
        # Start event bus
        await self.event_bus.start()
        
        # Component scanning
        if self.config.component_scan_packages or self.config.component_scan_paths:
            await self._scan_components()
        
        # Apply extensions from config
        if self.config.extensions:
            logger.info(f"Applying {len(self.config.extensions)} extensions...")
            for extension in self.config.extensions:
                self.extend(extension)
        
        # Discover modules
        await self.discover_modules()
        
        # Run startup hooks
        for hook in self._startup_hooks:
            await hook()
        
        self._running = True
        logger.info("Application started successfully")
    
    async def shutdown(self):
        """Shutdown the application gracefully."""
        logger.info("Shutting down application...")
        self._running = False
        
        # Cancel background tasks
        for task in self._background_tasks:
            task.cancel()
        
        # Wait for tasks to complete
        await asyncio.gather(*self._background_tasks, return_exceptions=True)
        
        # Run shutdown hooks
        for hook in reversed(self._shutdown_hooks):
            await hook()
        
        # Stop event bus
        await self.event_bus.stop()
        
        # Dispose container
        await self.container.dispose()
        
        logger.info("Application shutdown complete")
    
    @asynccontextmanager
    async def lifespan(self) -> AsyncIterator[None]:
        """Context manager for application lifecycle."""
        await self.startup()
        try:
            yield
        finally:
            await self.shutdown()
    
    def run(self):
        """Run the application with signal handling."""
        async def main():
            # Setup signal handlers
            loop = asyncio.get_event_loop()
            
            def handle_signal():
                logger.info("Received shutdown signal")
                loop.create_task(self.shutdown())
            
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, handle_signal)
            
            async with self.lifespan():
                # Keep running until shutdown
                while self._running:
                    await asyncio.sleep(1)
        
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            logger.info("Application interrupted")
    
    # Extension Methods
    
    def extend(self, extension: Callable[[Application], None]) -> Application:
        """Extend the application with a function.
        
        The extension function receives the application and can:
        - Register services in the container
        - Add event handlers
        - Register scopes
        - Configure the application
        
        Example:
            def redis_extension(app):
                @app.service
                class RedisClient:
                    pass
            
            app.extend(redis_extension)
        """
        extension(self)
        return self
    
    def use(self, *extensions: Callable[[Application], None]) -> Application:
        """Use multiple extensions at once.
        
        Example:
            app.use(redis_extension, cache_extension, metrics_extension)
        """
        for extension in extensions:
            self.extend(extension)
        return self


# Global app instance for convenience
# Commented out to avoid creating instance on import
# app = Application()