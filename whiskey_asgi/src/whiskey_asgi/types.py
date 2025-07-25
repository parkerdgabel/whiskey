"""Type definitions for ASGI."""

from typing import Any, Awaitable, Callable, Dict, List, Tuple, TypedDict, Union

# ASGI types
Scope = Dict[str, Any]
Message = Dict[str, Any]
ASGIReceive = Callable[[], Awaitable[Message]]
ASGISend = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, ASGIReceive, ASGISend], Awaitable[None]]

# HTTP types
Headers = List[Tuple[bytes, bytes]]


class HTTPScope(TypedDict, total=False):
    """HTTP connection scope."""

    type: str  # "http"
    asgi: Dict[str, Any]
    http_version: str
    method: str
    scheme: str
    path: str
    query_string: bytes
    headers: Headers
    server: Tuple[str, int]
    client: Tuple[str, int]
    state: Dict[str, Any]


class WebSocketScope(TypedDict, total=False):
    """WebSocket connection scope."""

    type: str  # "websocket"
    asgi: Dict[str, Any]
    http_version: str
    scheme: str
    path: str
    query_string: bytes
    headers: Headers
    server: Tuple[str, int]
    client: Tuple[str, int]
    subprotocols: List[str]
    state: Dict[str, Any]


class LifespanScope(TypedDict):
    """Lifespan scope."""

    type: str  # "lifespan"
    asgi: Dict[str, Any]
    state: Dict[str, Any]