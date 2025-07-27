"""Whiskey ASGI extension - ASGI web framework integration."""

from typing import TYPE_CHECKING

from .extension import Request, WebSocket, asgi_extension

if TYPE_CHECKING:
    from whiskey import Whiskey


__all__ = [
    "Request",
    "WebSocket",
    "asgi_extension",
]
