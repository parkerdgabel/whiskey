"""ASGI extension for Whiskey applications."""

from __future__ import annotations

import asyncio
import functools
import json
import re
from dataclasses import dataclass, field
from re import Pattern
from typing import TYPE_CHECKING, Any, Callable

from .types import ASGIReceive, ASGISend, Scope

if TYPE_CHECKING:
    from whiskey import Whiskey


@dataclass
class RouteMetadata:
    """Metadata for an HTTP route."""

    func: Callable
    path: str
    methods: list[str]
    name: str | None = None
    pattern: Pattern[str] | None = None
    param_names: list[str] = field(default_factory=list)

    def __post_init__(self):
        """Convert path to regex pattern."""
        if self.pattern is None:
            self.pattern, self.param_names = self._path_to_pattern(self.path)

    def _path_to_pattern(self, path: str) -> tuple[Pattern[str], list[str]]:
        """Convert a path with parameters to a regex pattern."""
        param_names = []
        pattern_parts = []

        for part in path.split("/"):
            if part.startswith("{") and part.endswith("}"):
                # Parameter
                param_name = part[1:-1]
                param_names.append(param_name)
                pattern_parts.append(r"([^/]+)")
            else:
                # Literal
                pattern_parts.append(re.escape(part))

        pattern = "^" + "/".join(pattern_parts) + "$"
        return re.compile(pattern), param_names

    def match(self, path: str, method: str) -> dict[str, str] | None:
        """Check if this route matches the given path and method."""
        if method not in self.methods:
            return None

        match = self.pattern.match(path)
        if not match:
            return None

        # Extract parameters
        params = {}
        for i, name in enumerate(self.param_names):
            params[name] = match.group(i + 1)

        return params


@dataclass
class MiddlewareMetadata:
    """Metadata for middleware."""

    func: Callable
    name: str | None = None
    priority: int = 0


@dataclass
class WebSocketMetadata:
    """Metadata for WebSocket handlers."""

    func: Callable
    path: str
    name: str | None = None
    pattern: Pattern[str] | None = None
    param_names: list[str] = field(default_factory=list)

    def __post_init__(self):
        """Convert path to regex pattern."""
        if self.pattern is None:
            self.pattern, self.param_names = RouteMetadata._path_to_pattern(None, self.path)


class Request:
    """HTTP request object for dependency injection."""

    def __init__(self, scope: Scope, receive: ASGIReceive):
        self.scope = scope
        self._receive = receive
        self._body: bytes | None = None
        self._json: Any | None = None
        self._form: dict[str, Any] | None = None
        self.route_params: dict[str, str] = {}

    @property
    def method(self) -> str:
        """HTTP method."""
        return self.scope["method"]

    @property
    def path(self) -> str:
        """Request path."""
        return self.scope["path"]

    @property
    def query_string(self) -> bytes:
        """Raw query string."""
        return self.scope.get("query_string", b"")

    @property
    def headers(self) -> dict[str, str]:
        """Request headers as a dict."""
        headers = {}
        for name, value in self.scope.get("headers", []):
            headers[name.decode("latin-1").lower()] = value.decode("latin-1")
        return headers

    @property
    def cookies(self) -> dict[str, str]:
        """Parse cookies from headers."""
        cookie_header = self.headers.get("cookie", "")
        cookies = {}
        if cookie_header:
            for cookie in cookie_header.split("; "):
                if "=" in cookie:
                    name, value = cookie.split("=", 1)
                    cookies[name] = value
        return cookies

    async def body(self) -> bytes:
        """Get the raw body bytes."""
        if self._body is None:
            body = b""
            while True:
                message = await self._receive()
                if message["type"] == "http.request":
                    body += message.get("body", b"")
                    if not message.get("more_body", False):
                        break
            self._body = body
        return self._body

    async def json(self) -> Any:
        """Parse body as JSON."""
        if self._json is None:
            body = await self.body()
            if body:
                self._json = json.loads(body)
            else:
                self._json = None
        return self._json

    async def form(self) -> dict[str, Any]:
        """Parse body as form data."""
        if self._form is None:
            # Simplified form parsing - real implementation would handle multipart
            body = await self.body()
            self._form = {}
            if body:
                for item in body.decode("utf-8").split("&"):
                    if "=" in item:
                        key, value = item.split("=", 1)
                        self._form[key] = value
        return self._form


class WebSocket:
    """WebSocket connection object."""

    def __init__(self, scope: Scope, receive: ASGIReceive, send: ASGISend):
        self.scope = scope
        self._receive = receive
        self._send = send
        self.route_params: dict[str, str] = {}
        self._accepted = False

    @property
    def path(self) -> str:
        """WebSocket path."""
        return self.scope["path"]

    @property
    def headers(self) -> dict[str, str]:
        """Request headers as a dict."""
        headers = {}
        for name, value in self.scope.get("headers", []):
            headers[name.decode("latin-1").lower()] = value.decode("latin-1")
        return headers

    async def accept(self, subprotocol: str | None = None) -> None:
        """Accept the WebSocket connection."""
        message = {"type": "websocket.accept"}
        if subprotocol:
            message["subprotocol"] = subprotocol
        await self._send(message)
        self._accepted = True

    async def send(self, data: str | bytes) -> None:
        """Send data to the client."""
        if not self._accepted:
            raise RuntimeError("WebSocket not accepted")

        if isinstance(data, str):
            await self._send(
                {
                    "type": "websocket.send",
                    "text": data,
                }
            )
        else:
            await self._send(
                {
                    "type": "websocket.send",
                    "bytes": data,
                }
            )

    async def receive(self) -> str | bytes:
        """Receive data from the client."""
        if not self._accepted:
            raise RuntimeError("WebSocket not accepted")

        while True:
            message = await self._receive()
            if message["type"] == "websocket.receive":
                if "text" in message:
                    return message["text"]
                elif "bytes" in message:
                    return message["bytes"]
            elif message["type"] == "websocket.disconnect":
                raise ConnectionError("WebSocket disconnected")

    async def close(self, code: int = 1000, reason: str = "") -> None:
        """Close the WebSocket connection."""
        await self._send(
            {
                "type": "websocket.close",
                "code": code,
                "reason": reason,
            }
        )

    def __aiter__(self):
        """Allow async iteration over messages."""
        return self

    async def __anext__(self) -> str | bytes:
        """Get next message."""
        try:
            return await self.receive()
        except ConnectionError:
            raise StopAsyncIteration from None


class ASGIManager:
    """Manages ASGI routes, middleware, and WebSockets."""

    def __init__(self, app: Whiskey):
        self.app = app
        self.routes: list[RouteMetadata] = []
        self.middleware: list[MiddlewareMetadata] = []
        self.websockets: list[WebSocketMetadata] = []
        self.before_request: list[Callable] = []
        self.after_request: list[Callable] = []
        self.error_handlers: dict[int, Callable] = {}

    def add_route(self, metadata: RouteMetadata) -> None:
        """Add a route."""
        self.routes.append(metadata)

    def add_middleware(self, metadata: MiddlewareMetadata) -> None:
        """Add middleware."""
        self.middleware.append(metadata)
        # Sort by priority (higher priority first)
        self.middleware.sort(key=lambda m: m.priority, reverse=True)

    def add_websocket(self, metadata: WebSocketMetadata) -> None:
        """Add a WebSocket handler."""
        self.websockets.append(metadata)

    def find_route(self, path: str, method: str) -> tuple[RouteMetadata, dict[str, str]] | None:
        """Find a matching route."""
        for route in self.routes:
            params = route.match(path, method)
            if params is not None:
                return route, params
        return None

    def find_websocket(self, path: str) -> tuple[WebSocketMetadata, dict[str, str]] | None:
        """Find a matching WebSocket handler."""
        for ws in self.websockets:
            match = ws.pattern.match(path)
            if match:
                params = {}
                for i, name in enumerate(ws.param_names):
                    params[name] = match.group(i + 1)
                return ws, params
        return None

    def create_asgi_handler(self) -> ASGIHandler:
        """Create the ASGI handler."""
        return ASGIHandler(self)


class ASGIHandler:
    """ASGI 3.0 compliant handler."""

    def __init__(self, manager: ASGIManager):
        self.manager = manager
        self.app = manager.app

    async def __call__(self, scope: Scope, receive: ASGIReceive, send: ASGISend) -> None:
        """ASGI 3.0 application interface."""
        if scope["type"] == "lifespan":
            await self.handle_lifespan(scope, receive, send)
        elif scope["type"] == "http":
            await self.handle_http(scope, receive, send)
        elif scope["type"] == "websocket":
            await self.handle_websocket(scope, receive, send)
        else:
            raise RuntimeError(f"Unknown scope type: {scope['type']}")

    async def handle_lifespan(self, scope: Scope, receive: ASGIReceive, send: ASGISend) -> None:
        """Handle ASGI lifespan protocol."""
        message = await receive()
        assert message["type"] == "lifespan.startup"

        try:
            # Run application startup
            await self.app.startup()
            await send({"type": "lifespan.startup.complete"})
        except Exception as exc:
            await send({"type": "lifespan.startup.failed", "message": str(exc)})
            raise

        # Wait for shutdown
        message = await receive()
        assert message["type"] == "lifespan.shutdown"

        try:
            # Run application shutdown
            await self.app.shutdown()
            await send({"type": "lifespan.shutdown.complete"})
        except Exception as exc:
            await send({"type": "lifespan.shutdown.failed", "message": str(exc)})
            raise

    async def handle_http(self, scope: Scope, receive: ASGIReceive, send: ASGISend) -> None:
        """Handle HTTP requests."""
        # Create request
        request = Request(scope, receive)

        # Find route
        route_info = self.manager.find_route(request.path, request.method)
        if not route_info:
            await self.send_error(send, 404, "Not Found")
            return

        route, params = route_info
        request.route_params = params

        # Create request-scoped container
        async with self.app.scope("request"):
            # Register request in container
            self.app.container[Request] = request

            try:
                # Build middleware chain
                handler = route.func

                # Apply middleware in reverse order (first registered = outermost)
                for middleware in reversed(self.manager.middleware):
                    handler = self.wrap_middleware(middleware.func, handler)

                # Execute handler with DI
                if hasattr(handler, "__wrapped__") or asyncio.iscoroutinefunction(handler):
                    # Has @inject or is async
                    result = await self.app.container.call(handler, **params)
                else:
                    # Sync function without @inject
                    result = handler(**params)

                # Send response
                await self.send_response(send, result)

            except Exception as exc:
                # Error handling
                status = getattr(exc, "status_code", 500)
                message = str(exc)
                await self.send_error(send, status, message)

    async def handle_websocket(self, scope: Scope, receive: ASGIReceive, send: ASGISend) -> None:
        """Handle WebSocket connections."""
        # Find WebSocket handler
        ws_info = self.manager.find_websocket(scope["path"])
        if not ws_info:
            await send(
                {
                    "type": "websocket.close",
                    "code": 1001,
                    "reason": "No handler found",
                }
            )
            return

        handler, params = ws_info

        # Create WebSocket object
        websocket = WebSocket(scope, receive, send)
        websocket.route_params = params

        # Create request-scoped container for WebSocket
        async with self.app.scope("request"):
            # Register WebSocket in container
            self.app.container[WebSocket] = websocket

            try:
                # Execute handler with DI
                if hasattr(handler.func, "__wrapped__") or asyncio.iscoroutinefunction(
                    handler.func
                ):
                    await self.app.container.call(handler.func, websocket=websocket, **params)
                else:
                    handler.func(websocket=websocket, **params)
            except Exception as exc:
                # Ensure connection is closed on error
                if websocket._accepted:
                    await websocket.close(1011, str(exc))
                else:
                    await send(
                        {
                            "type": "websocket.close",
                            "code": 1011,
                            "reason": str(exc),
                        }
                    )

    def wrap_middleware(self, middleware: Callable, next_handler: Callable) -> Callable:
        """Wrap a handler with middleware."""

        @functools.wraps(next_handler)
        async def wrapped(**kwargs):
            # Create call_next function
            async def call_next(request: Request):
                # Execute the next handler
                return await self.app.container.call(next_handler, **kwargs)

            # Execute middleware with DI
            if hasattr(middleware, "__wrapped__") or asyncio.iscoroutinefunction(middleware):
                return await self.app.container.call(middleware, call_next=call_next, **kwargs)
            else:
                return middleware(call_next=call_next, **kwargs)

        return wrapped

    async def send_response(self, send: ASGISend, result: Any) -> None:
        """Send an HTTP response based on the result type."""
        # Handle different return types
        if isinstance(result, tuple) and len(result) == 2:
            # (body, status)
            body, status = result
        else:
            body = result
            status = 200

        # Determine content type and body
        if isinstance(body, (dict, list)):
            # JSON response
            content = json.dumps(body).encode("utf-8")
            content_type = "application/json"
        elif isinstance(body, str):
            # Text response
            content = body.encode("utf-8")
            content_type = "text/plain; charset=utf-8"
        elif isinstance(body, bytes):
            # Binary response
            content = body
            content_type = "application/octet-stream"
        elif body is None:
            # Empty response
            content = b""
            content_type = "text/plain"
        else:
            # Convert to string
            content = str(body).encode("utf-8")
            content_type = "text/plain; charset=utf-8"

        # Send response
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    [b"content-type", content_type.encode("latin-1")],
                    [b"content-length", str(len(content)).encode("latin-1")],
                ],
            }
        )

        await send(
            {
                "type": "http.response.body",
                "body": content,
            }
        )

    async def send_error(self, send: ASGISend, status: int, message: str) -> None:
        """Send an error response."""
        content = json.dumps({"error": message}).encode("utf-8")

        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    [b"content-type", b"application/json"],
                    [b"content-length", str(len(content)).encode("latin-1")],
                ],
            }
        )

        await send(
            {
                "type": "http.response.body",
                "body": content,
            }
        )


def asgi_extension(app: Whiskey) -> None:
    """ASGI extension that adds web framework capabilities.

    This extension provides:
    - HTTP route decorators: @app.get(), @app.post(), etc.
    - WebSocket support: @app.websocket()
    - Middleware: @app.middleware()
    - Request/response handling with dependency injection
    - ASGI 3.0 compliance

    Example:
        app = Whiskey()
        app.use(asgi_extension)

        @app.get("/")
        async def index():
            return {"message": "Hello World"}

        @app.get("/user/{id}")
        @inject
        async def get_user(id: int, service: UserService):
            user = await service.get_user(id)
            return user

        # app.asgi is the ASGI handler
        # Run with: uvicorn app:app.asgi
    """
    # Create ASGI manager
    manager = ASGIManager(app)

    # Store manager and create ASGI handler
    app.asgi_manager = manager
    app.asgi = manager.create_asgi_handler()

    # Request and session scopes are now properly managed using the container's scope() method
    # Components registered as @scoped(scope_name="request") will share instances within each request

    # Create route decorators
    def create_route_decorator(methods: list[str]):
        def route(path: str, name: str | None = None):
            def decorator(func: Callable) -> Callable:
                metadata = RouteMetadata(
                    func=func, path=path, methods=methods, name=name or func.__name__
                )
                manager.add_route(metadata)
                return func

            return decorator

        return route

    # Add route decorators
    app.add_decorator(
        "route",
        lambda path, methods=["GET"], name=None: create_route_decorator(methods)(path, name),
    )
    app.add_decorator("get", create_route_decorator(["GET"]))
    app.add_decorator("post", create_route_decorator(["POST"]))
    app.add_decorator("put", create_route_decorator(["PUT"]))
    app.add_decorator("delete", create_route_decorator(["DELETE"]))
    app.add_decorator("patch", create_route_decorator(["PATCH"]))
    app.add_decorator("head", create_route_decorator(["HEAD"]))
    app.add_decorator("options", create_route_decorator(["OPTIONS"]))

    # WebSocket decorator
    def websocket(path: str, name: str | None = None):
        def decorator(func: Callable) -> Callable:
            metadata = WebSocketMetadata(func=func, path=path, name=name or func.__name__)
            manager.add_websocket(metadata)
            return func

        return decorator

    app.add_decorator("websocket", websocket)

    # Middleware decorator
    def middleware(name: str | None = None, priority: int = 0):
        def decorator(func: Callable) -> Callable:
            metadata = MiddlewareMetadata(func=func, name=name or func.__name__, priority=priority)
            manager.add_middleware(metadata)
            return func

        return decorator

    app.add_decorator("middleware", middleware)

    # Helper methods
    def run_asgi(host: str = "127.0.0.1", port: int = 8000, **kwargs) -> None:
        """Run the ASGI application with uvicorn.

        Args:
            host: Host to bind to
            port: Port to bind to
            **kwargs: Additional arguments passed to uvicorn.run()
        """
        try:
            import uvicorn
        except ImportError:
            raise ImportError(
                "uvicorn is required to run ASGI apps. Install with: pip install uvicorn"
            ) from None

        # The ASGI handler already manages lifecycle via the lifespan protocol
        # So we can run uvicorn directly without additional lifecycle management
        uvicorn.run(app.asgi, host=host, port=port, **kwargs)

    # Register the ASGI runner with the new standardized API
    app.register_runner("asgi", run_asgi)

    # Also make it available as a method for backward compatibility
    app.run_asgi = run_asgi
