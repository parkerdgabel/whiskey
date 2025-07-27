"""Whiskey ASGI extension - ASGI web framework integration."""

from typing import TYPE_CHECKING

<<<<<<< HEAD
from .extension import Request, WebSocket, asgi_extension

if TYPE_CHECKING:
    from whiskey import Whiskey


__all__ = [
    "Request",
    "WebSocket",
    "asgi_extension",
]
=======
from .extension import asgi_extension, Request, WebSocket

if TYPE_CHECKING:
    from whiskey import Application


__all__ = [
    "asgi_extension",
    "Request",
    "WebSocket",
]
>>>>>>> origin/main
