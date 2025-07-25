"""Application bootstrapping utilities."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Callable, Generic, TypeVar

from whiskey.core.application import Application, ApplicationConfig
from whiskey.core.container import Container

T = TypeVar("T")


class ApplicationBuilder(ABC, Generic[T]):
    """Base class for building applications for specific interfaces."""
    
    def __init__(self, config: ApplicationConfig | None = None):
        self.config = config or ApplicationConfig()
        self._app: Application | None = None
        self._setup_hooks: list[Callable[[Application], None]] = []
        self._async_setup_hooks: list[Callable[[Application], Any]] = []
    
    @property
    def app(self) -> Application:
        """Get or create the application instance."""
        if self._app is None:
            self._app = Application(self.config)
        return self._app
    
    def configure(self, func: Callable[[ApplicationConfig], None]) -> ApplicationBuilder[T]:
        """Configure the application."""
        func(self.config)
        return self
    
    def setup(self, func: Callable[[Application], None]) -> ApplicationBuilder[T]:
        """Add a setup hook that runs during build."""
        self._setup_hooks.append(func)
        return self
    
    def setup_async(self, func: Callable[[Application], Any]) -> ApplicationBuilder[T]:
        """Add an async setup hook that runs during build."""
        self._async_setup_hooks.append(func)
        return self
    
    def extension(self, ext: Callable[[Application], None]) -> ApplicationBuilder[T]:
        """Add an extension to apply during build."""
        self._async_setup_hooks.append(lambda app: ext(app))
        return self
    
    def service(self, service_type: type, **kwargs) -> ApplicationBuilder[T]:
        """Register a service during setup."""
        def register(app: Application):
            app.container.register(service_type, **kwargs)
        self._setup_hooks.append(register)
        return self
    
    @abstractmethod
    async def build_async(self) -> T:
        """Build the interface-specific application asynchronously."""
        ...
    
    def build(self) -> T:
        """Build the interface-specific application synchronously."""
        return asyncio.run(self.build_async())
    
    async def _run_setup(self) -> None:
        """Run all setup hooks."""
        # Run sync setup hooks
        for hook in self._setup_hooks:
            hook(self.app)
        
        # Run async setup hooks
        for hook in self._async_setup_hooks:
            await hook(self.app)
        
        # Initialize the application
        await self.app.startup()


class StandaloneApplicationBuilder(ApplicationBuilder[Application]):
    """Builder for standalone applications (scripts, workers, etc.)."""
    
    async def build_async(self) -> Application:
        """Build a standalone application."""
        await self._run_setup()
        return self.app


def standalone(config: ApplicationConfig | None = None) -> StandaloneApplicationBuilder:
    """Create a builder for a standalone application."""
    return StandaloneApplicationBuilder(config)