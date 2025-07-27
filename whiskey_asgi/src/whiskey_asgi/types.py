"""Type definitions for ASGI."""

from collections.abc import Awaitable
from typing import Any, Callable, TypedDict

# ASGI types
Scope = dict[str, Any]
Message = dict[str, Any]
ASGIReceive = Callable[[], Awaitable[Message]]
ASGISend = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, ASGIReceive, ASGISend], Awaitable[None]]

# HTTP types
Headers = list[tuple[bytes, bytes]]


class HTTPScope(TypedDict, total=False):
    """HTTP connection scope."""

    type: str  # "http"
    asgi: dict[str, Any]
    http_version: str
    method: str
    scheme: str
    path: str
    query_string: bytes
    headers: Headers
    server: tuple[str, int]
    client: tuple[str, int]
    state: dict[str, Any]


class WebSocketScope(TypedDict, total=False):
    """WebSocket connection scope."""

    type: str  # "websocket"
    asgi: dict[str, Any]
    http_version: str
    scheme: str
    path: str
    query_string: bytes
    headers: Headers
    server: tuple[str, int]
    client: tuple[str, int]
    subprotocols: list[str]
    state: dict[str, Any]


class LifespanScope(TypedDict):
    """Lifespan scope."""

    type: str  # "lifespan"
    asgi: dict[str, Any]
    state: dict[str, Any]
