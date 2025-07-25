"""Whiskey ASGI extension - ASGI web framework integration."""

from typing import TYPE_CHECKING

from .extension import asgi_extension, Request, WebSocket

if TYPE_CHECKING:
    from whiskey import Application


__all__ = [
    "asgi_extension",
    "Request",
    "WebSocket",
]