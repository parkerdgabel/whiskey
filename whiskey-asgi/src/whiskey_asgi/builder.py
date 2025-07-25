"""ASGI application builder."""

from __future__ import annotations

from typing import Callable, TYPE_CHECKING

from whiskey import ApplicationConfig
from whiskey.core.bootstrap import ApplicationBuilder

from .app import ASGIApp
from .routing import Router
from . import asgi_extension

if TYPE_CHECKING:
    from .middleware import Middleware


class ASGIApplicationBuilder(ApplicationBuilder[ASGIApp]):
    """Builder for ASGI applications."""
    
    def __init__(self, config: ApplicationConfig | None = None):
        super().__init__(config)
        # Always include the ASGI extension
        self.setup(lambda app: app.extend(asgi_extension))
        self._routes: list[tuple[str, str | list[str], Callable]] = []
        self._middleware: list[Middleware] = []
        self._startup_handlers: list[Callable] = []
        self._shutdown_handlers: list[Callable] = []
    
    def route(self, path: str, handler: Callable, methods: list[str] | None = None) -> ASGIApplicationBuilder:
        """Add a route."""
        self._routes.append((path, methods or ["GET"], handler))
        return self
    
    def get(self, path: str) -> Callable[[Callable], Callable]:
        """Decorator for GET routes."""
        def decorator(handler: Callable) -> Callable:
            self.route(path, handler, ["GET"])
            return handler
        return decorator
    
    def post(self, path: str) -> Callable[[Callable], Callable]:
        """Decorator for POST routes."""
        def decorator(handler: Callable) -> Callable:
            self.route(path, handler, ["POST"])
            return handler
        return decorator
    
    def put(self, path: str) -> Callable[[Callable], Callable]:
        """Decorator for PUT routes."""
        def decorator(handler: Callable) -> Callable:
            self.route(path, handler, ["PUT"])
            return handler
        return decorator
    
    def delete(self, path: str) -> Callable[[Callable], Callable]:
        """Decorator for DELETE routes."""
        def decorator(handler: Callable) -> Callable:
            self.route(path, handler, ["DELETE"])
            return handler
        return decorator
    
    def middleware(self, middleware: Middleware) -> ASGIApplicationBuilder:
        """Add middleware to the application."""
        self._middleware.append(middleware)
        return self
    
    def on_startup(self, handler: Callable) -> ASGIApplicationBuilder:
        """Add a startup handler."""
        self._startup_handlers.append(handler)
        return self
    
    def on_shutdown(self, handler: Callable) -> ASGIApplicationBuilder:
        """Add a shutdown handler."""
        self._shutdown_handlers.append(handler)
        return self
    
    async def build_async(self) -> ASGIApp:
        """Build the ASGI application."""
        # Run setup
        await self._run_setup()
        
        # Get the ASGI app from the container
        asgi_app = await self.app.container.resolve(ASGIApp)
        
        # Apply routes
        for path, methods, handler in self._routes:
            asgi_app.router.add_route(path, handler, methods)
        
        # Apply middleware
        for mw in self._middleware:
            asgi_app.add_middleware(mw)
        
        # Apply lifecycle handlers
        for handler in self._startup_handlers:
            asgi_app.on_startup(handler)
        
        for handler in self._shutdown_handlers:
            asgi_app.on_shutdown(handler)
        
        return asgi_app


def asgi(config: ApplicationConfig | None = None) -> ASGIApplicationBuilder:
    """Create a builder for an ASGI application."""
    return ASGIApplicationBuilder(config)