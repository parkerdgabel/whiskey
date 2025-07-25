"""Middleware support for ASGI."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Awaitable, Callable

from .request import Request
from .response import Response

Handler = Callable[[Request, Response], Awaitable[None]]


class Middleware(ABC):
    """Base class for ASGI middleware."""

    @abstractmethod
    def wrap(self, handler: Handler) -> Handler:
        """Wrap a handler with middleware logic."""
        ...


class FunctionMiddleware(Middleware):
    """Middleware that wraps a function."""

    def __init__(self, func: Callable[[Handler], Handler]):
        self.func = func

    def wrap(self, handler: Handler) -> Handler:
        """Wrap the handler."""
        return self.func(handler)


def middleware(func: Callable[[Handler], Handler]) -> Middleware:
    """Create middleware from a function."""
    return FunctionMiddleware(func)