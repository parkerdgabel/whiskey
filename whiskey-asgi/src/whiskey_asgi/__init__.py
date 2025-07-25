"""Whiskey ASGI extension - ASGI web framework integration."""

from typing import TYPE_CHECKING

from .app import ASGIApp
from .builder import ASGIApplicationBuilder, asgi
from .middleware import Middleware, middleware
from .request import Request
from .response import Response
from .routing import Route, Router

if TYPE_CHECKING:
    from whiskey import Application


def asgi_extension(app: "Application") -> None:
    """ASGI extension that adds web framework capabilities to Whiskey.
    
    Usage:
        from whiskey import Application
        from whiskey_asgi import asgi_extension, ASGIApp
        
        app = Application()
        app.extend(asgi_extension)
        
        # Get the ASGI app
        asgi_app = await app.container.resolve(ASGIApp)
    """
    # Register ASGIApp as a factory that gets the Application instance
    def create_asgi_app(app: Application) -> ASGIApp:
        return ASGIApp(app)
    
    app.container.register_singleton(ASGIApp, factory=create_asgi_app)


# For backwards compatibility
extend = asgi_extension


__all__ = [
    "asgi_extension",
    "extend",
    "ASGIApp",
    "ASGIApplicationBuilder",
    "Request",
    "Response",
    "Route",
    "Router",
    "Middleware",
    "asgi",
    "middleware",
]