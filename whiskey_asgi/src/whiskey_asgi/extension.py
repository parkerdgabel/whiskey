"""ASGI extension for Whiskey applications."""

from __future__ import annotations

import asyncio
import functools
import json
import re
from dataclasses import dataclass, field
<<<<<<< HEAD
from re import Pattern
from typing import Any, Callable, Dict, List, Optional, Tuple, Union, TYPE_CHECKING

from .types import ASGIReceive, ASGISend, Scope

if TYPE_CHECKING:
    from whiskey import Whiskey

=======
from typing import Any, Callable, Dict, List, Optional, Pattern, Tuple, Union

from whiskey import Application, inject

from .types import ASGIReceive, ASGISend, Scope

>>>>>>> origin/main

@dataclass
class RouteMetadata:
    """Metadata for an HTTP route."""
<<<<<<< HEAD

=======
>>>>>>> origin/main
    func: Callable
    path: str
    methods: List[str]
    name: Optional[str] = None
    pattern: Optional[Pattern[str]] = None
    param_names: List[str] = field(default_factory=list)
<<<<<<< HEAD

=======
    
>>>>>>> origin/main
    def __post_init__(self):
        """Convert path to regex pattern."""
        if self.pattern is None:
            self.pattern, self.param_names = self._path_to_pattern(self.path)
<<<<<<< HEAD

=======
    
>>>>>>> origin/main
    def _path_to_pattern(self, path: str) -> Tuple[Pattern[str], List[str]]:
        """Convert a path with parameters to a regex pattern."""
        param_names = []
        pattern_parts = []
<<<<<<< HEAD

=======
        
>>>>>>> origin/main
        for part in path.split("/"):
            if part.startswith("{") and part.endswith("}"):
                # Parameter
                param_name = part[1:-1]
                param_names.append(param_name)
                pattern_parts.append(r"([^/]+)")
            else:
                # Literal
                pattern_parts.append(re.escape(part))
<<<<<<< HEAD

        pattern = "^" + "/".join(pattern_parts) + "$"
        return re.compile(pattern), param_names

=======
        
        pattern = "^" + "/".join(pattern_parts) + "$"
        return re.compile(pattern), param_names
    
>>>>>>> origin/main
    def match(self, path: str, method: str) -> Optional[Dict[str, str]]:
        """Check if this route matches the given path and method."""
        if method not in self.methods:
            return None
<<<<<<< HEAD

        match = self.pattern.match(path)
        if not match:
            return None

=======
        
        match = self.pattern.match(path)
        if not match:
            return None
        
>>>>>>> origin/main
        # Extract parameters
        params = {}
        for i, name in enumerate(self.param_names):
            params[name] = match.group(i + 1)
<<<<<<< HEAD

=======
        
>>>>>>> origin/main
        return params


@dataclass
class MiddlewareMetadata:
    """Metadata for middleware."""
<<<<<<< HEAD

=======
>>>>>>> origin/main
    func: Callable
    name: Optional[str] = None
    priority: int = 0


@dataclass
class WebSocketMetadata:
    """Metadata for WebSocket handlers."""
<<<<<<< HEAD

=======
>>>>>>> origin/main
    func: Callable
    path: str
    name: Optional[str] = None
    pattern: Optional[Pattern[str]] = None
    param_names: List[str] = field(default_factory=list)
<<<<<<< HEAD

=======
    
>>>>>>> origin/main
    def __post_init__(self):
        """Convert path to regex pattern."""
        if self.pattern is None:
            self.pattern, self.param_names = RouteMetadata._path_to_pattern(None, self.path)


class Request:
    """HTTP request object for dependency injection."""
<<<<<<< HEAD

=======
    
>>>>>>> origin/main
    def __init__(self, scope: Scope, receive: ASGIReceive):
        self.scope = scope
        self._receive = receive
        self._body: Optional[bytes] = None
        self._json: Optional[Any] = None
        self._form: Optional[Dict[str, Any]] = None
        self.route_params: Dict[str, str] = {}
<<<<<<< HEAD

=======
    
>>>>>>> origin/main
    @property
    def method(self) -> str:
        """HTTP method."""
        return self.scope["method"]
<<<<<<< HEAD

=======
    
>>>>>>> origin/main
    @property
    def path(self) -> str:
        """Request path."""
        return self.scope["path"]
<<<<<<< HEAD

=======
    
>>>>>>> origin/main
    @property
    def query_string(self) -> bytes:
        """Raw query string."""
        return self.scope.get("query_string", b"")
<<<<<<< HEAD

=======
    
>>>>>>> origin/main
    @property
    def headers(self) -> Dict[str, str]:
        """Request headers as a dict."""
        headers = {}
        for name, value in self.scope.get("headers", []):
            headers[name.decode("latin-1").lower()] = value.decode("latin-1")
        return headers
<<<<<<< HEAD

=======
    
>>>>>>> origin/main
    @property
    def cookies(self) -> Dict[str, str]:
        """Parse cookies from headers."""
        cookie_header = self.headers.get("cookie", "")
        cookies = {}
        if cookie_header:
            for cookie in cookie_header.split("; "):
                if "=" in cookie:
                    name, value = cookie.split("=", 1)
                    cookies[name] = value
        return cookies
<<<<<<< HEAD

=======
    
>>>>>>> origin/main
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
<<<<<<< HEAD

=======
    
>>>>>>> origin/main
    async def json(self) -> Any:
        """Parse body as JSON."""
        if self._json is None:
            body = await self.body()
            if body:
                self._json = json.loads(body)
            else:
                self._json = None
        return self._json
<<<<<<< HEAD

=======
    
>>>>>>> origin/main
    async def form(self) -> Dict[str, Any]:
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
<<<<<<< HEAD

=======
    
>>>>>>> origin/main
    def __init__(self, scope: Scope, receive: ASGIReceive, send: ASGISend):
        self.scope = scope
        self._receive = receive
        self._send = send
        self.route_params: Dict[str, str] = {}
        self._accepted = False
<<<<<<< HEAD

=======
    
>>>>>>> origin/main
    @property
    def path(self) -> str:
        """WebSocket path."""
        return self.scope["path"]
<<<<<<< HEAD

=======
    
>>>>>>> origin/main
    @property
    def headers(self) -> Dict[str, str]:
        """Request headers as a dict."""
        headers = {}
        for name, value in self.scope.get("headers", []):
            headers[name.decode("latin-1").lower()] = value.decode("latin-1")
        return headers
<<<<<<< HEAD

    async def accept(self, subprotocol: Optional[str] = None) -> None:
        """Accept the WebSocket connection."""
        await self._send(
            {
                "type": "websocket.accept",
                "subprotocol": subprotocol or "",
            }
        )
        self._accepted = True

=======
    
    async def accept(self, subprotocol: Optional[str] = None) -> None:
        """Accept the WebSocket connection."""
        await self._send({
            "type": "websocket.accept",
            "subprotocol": subprotocol or "",
        })
        self._accepted = True
    
>>>>>>> origin/main
    async def send(self, data: Union[str, bytes]) -> None:
        """Send data to the client."""
        if not self._accepted:
            raise RuntimeError("WebSocket not accepted")
<<<<<<< HEAD

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

=======
        
        if isinstance(data, str):
            await self._send({
                "type": "websocket.send",
                "text": data,
            })
        else:
            await self._send({
                "type": "websocket.send",
                "bytes": data,
            })
    
>>>>>>> origin/main
    async def receive(self) -> Union[str, bytes]:
        """Receive data from the client."""
        if not self._accepted:
            raise RuntimeError("WebSocket not accepted")
<<<<<<< HEAD

=======
        
>>>>>>> origin/main
        while True:
            message = await self._receive()
            if message["type"] == "websocket.receive":
                if "text" in message:
                    return message["text"]
                elif "bytes" in message:
                    return message["bytes"]
            elif message["type"] == "websocket.disconnect":
                raise ConnectionError("WebSocket disconnected")
<<<<<<< HEAD

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

=======
    
    async def close(self, code: int = 1000, reason: str = "") -> None:
        """Close the WebSocket connection."""
        await self._send({
            "type": "websocket.close",
            "code": code,
            "reason": reason,
        })
    
    def __aiter__(self):
        """Allow async iteration over messages."""
        return self
    
>>>>>>> origin/main
    async def __anext__(self) -> Union[str, bytes]:
        """Get next message."""
        try:
            return await self.receive()
        except ConnectionError:
            raise StopAsyncIteration


class ASGIManager:
    """Manages ASGI routes, middleware, and WebSockets."""
<<<<<<< HEAD

    def __init__(self, app: Whiskey):
=======
    
    def __init__(self, app: Application):
>>>>>>> origin/main
        self.app = app
        self.routes: List[RouteMetadata] = []
        self.middleware: List[MiddlewareMetadata] = []
        self.websockets: List[WebSocketMetadata] = []
        self.before_request: List[Callable] = []
        self.after_request: List[Callable] = []
        self.error_handlers: Dict[int, Callable] = {}
<<<<<<< HEAD

    def add_route(self, metadata: RouteMetadata) -> None:
        """Add a route."""
        self.routes.append(metadata)

=======
    
    def add_route(self, metadata: RouteMetadata) -> None:
        """Add a route."""
        self.routes.append(metadata)
    
>>>>>>> origin/main
    def add_middleware(self, metadata: MiddlewareMetadata) -> None:
        """Add middleware."""
        self.middleware.append(metadata)
        # Sort by priority (higher priority first)
        self.middleware.sort(key=lambda m: m.priority, reverse=True)
<<<<<<< HEAD

    def add_websocket(self, metadata: WebSocketMetadata) -> None:
        """Add a WebSocket handler."""
        self.websockets.append(metadata)

=======
    
    def add_websocket(self, metadata: WebSocketMetadata) -> None:
        """Add a WebSocket handler."""
        self.websockets.append(metadata)
    
>>>>>>> origin/main
    def find_route(self, path: str, method: str) -> Optional[Tuple[RouteMetadata, Dict[str, str]]]:
        """Find a matching route."""
        for route in self.routes:
            params = route.match(path, method)
            if params is not None:
                return route, params
        return None
<<<<<<< HEAD

=======
    
>>>>>>> origin/main
    def find_websocket(self, path: str) -> Optional[Tuple[WebSocketMetadata, Dict[str, str]]]:
        """Find a matching WebSocket handler."""
        for ws in self.websockets:
            match = ws.pattern.match(path)
            if match:
                params = {}
                for i, name in enumerate(ws.param_names):
                    params[name] = match.group(i + 1)
                return ws, params
        return None
<<<<<<< HEAD

=======
    
>>>>>>> origin/main
    def create_asgi_handler(self) -> ASGIHandler:
        """Create the ASGI handler."""
        return ASGIHandler(self)


class ASGIHandler:
    """ASGI 3.0 compliant handler."""
<<<<<<< HEAD

    def __init__(self, manager: ASGIManager):
        self.manager = manager
        self.app = manager.app

=======
    
    def __init__(self, manager: ASGIManager):
        self.manager = manager
        self.app = manager.app
    
>>>>>>> origin/main
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
<<<<<<< HEAD

=======
    
>>>>>>> origin/main
    async def handle_lifespan(self, scope: Scope, receive: ASGIReceive, send: ASGISend) -> None:
        """Handle ASGI lifespan protocol."""
        message = await receive()
        assert message["type"] == "lifespan.startup"
<<<<<<< HEAD

=======
        
>>>>>>> origin/main
        try:
            # Run application startup
            await self.app.startup()
            await send({"type": "lifespan.startup.complete"})
        except Exception as exc:
            await send({"type": "lifespan.startup.failed", "message": str(exc)})
            raise
<<<<<<< HEAD

        # Wait for shutdown
        message = await receive()
        assert message["type"] == "lifespan.shutdown"

=======
        
        # Wait for shutdown
        message = await receive()
        assert message["type"] == "lifespan.shutdown"
        
>>>>>>> origin/main
        try:
            # Run application shutdown
            await self.app.shutdown()
            await send({"type": "lifespan.shutdown.complete"})
        except Exception as exc:
            await send({"type": "lifespan.shutdown.failed", "message": str(exc)})
            raise
<<<<<<< HEAD

=======
    
>>>>>>> origin/main
    async def handle_http(self, scope: Scope, receive: ASGIReceive, send: ASGISend) -> None:
        """Handle HTTP requests."""
        # Create request
        request = Request(scope, receive)
<<<<<<< HEAD

=======
        
>>>>>>> origin/main
        # Find route
        route_info = self.manager.find_route(request.path, request.method)
        if not route_info:
            await self.send_error(send, 404, "Not Found")
            return
<<<<<<< HEAD

        route, params = route_info
        request.route_params = params

=======
        
        route, params = route_info
        request.route_params = params
        
>>>>>>> origin/main
        # Create request-scoped container
        async with self.app.container.scope("request"):
            # Register request in container
            self.app.container[Request] = request
<<<<<<< HEAD

            try:
                # Build middleware chain
                handler = route.func

                # Apply middleware in reverse order (first registered = outermost)
                for middleware in reversed(self.manager.middleware):
                    handler = self.wrap_middleware(middleware.func, handler)

=======
            
            try:
                # Build middleware chain
                handler = route.func
                
                # Apply middleware in reverse order (first registered = outermost)
                for middleware in reversed(self.manager.middleware):
                    handler = self.wrap_middleware(middleware.func, handler)
                
>>>>>>> origin/main
                # Execute handler with DI
                if hasattr(handler, "__wrapped__") or asyncio.iscoroutinefunction(handler):
                    # Has @inject or is async
                    result = await self.app.container.resolve(handler, **params)
                else:
                    # Sync function without @inject
                    result = handler(**params)
<<<<<<< HEAD

                # Send response
                await self.send_response(send, result)

=======
                
                # Send response
                await self.send_response(send, result)
                
>>>>>>> origin/main
            except Exception as exc:
                # Error handling
                status = getattr(exc, "status_code", 500)
                message = str(exc)
                await self.send_error(send, status, message)
<<<<<<< HEAD

=======
    
>>>>>>> origin/main
    async def handle_websocket(self, scope: Scope, receive: ASGIReceive, send: ASGISend) -> None:
        """Handle WebSocket connections."""
        # Find WebSocket handler
        ws_info = self.manager.find_websocket(scope["path"])
        if not ws_info:
<<<<<<< HEAD
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

=======
            await send({
                "type": "websocket.close",
                "code": 1001,
                "reason": "No handler found",
            })
            return
        
        handler, params = ws_info
        
        # Create WebSocket object
        websocket = WebSocket(scope, receive, send)
        websocket.route_params = params
        
>>>>>>> origin/main
        # Create request-scoped container
        async with self.app.container.scope("request"):
            # Register WebSocket in container
            self.app.container[WebSocket] = websocket
<<<<<<< HEAD

            try:
                # Execute handler with DI
                if hasattr(handler.func, "__wrapped__") or asyncio.iscoroutinefunction(
                    handler.func
                ):
=======
            
            try:
                # Execute handler with DI
                if hasattr(handler.func, "__wrapped__") or asyncio.iscoroutinefunction(handler.func):
>>>>>>> origin/main
                    await self.app.container.resolve(handler.func, websocket=websocket, **params)
                else:
                    handler.func(websocket=websocket, **params)
            except Exception as exc:
                # Ensure connection is closed on error
                if websocket._accepted:
                    await websocket.close(1011, str(exc))
                else:
<<<<<<< HEAD
                    await send(
                        {
                            "type": "websocket.close",
                            "code": 1011,
                            "reason": str(exc),
                        }
                    )

    def wrap_middleware(self, middleware: Callable, next_handler: Callable) -> Callable:
        """Wrap a handler with middleware."""

=======
                    await send({
                        "type": "websocket.close",
                        "code": 1011,
                        "reason": str(exc),
                    })
    
    def wrap_middleware(self, middleware: Callable, next_handler: Callable) -> Callable:
        """Wrap a handler with middleware."""
>>>>>>> origin/main
        @functools.wraps(next_handler)
        async def wrapped(**kwargs):
            # Create call_next function
            async def call_next(request: Request):
                # Execute the next handler
                return await self.app.container.resolve(next_handler, **kwargs)
<<<<<<< HEAD

=======
            
>>>>>>> origin/main
            # Execute middleware with DI
            if hasattr(middleware, "__wrapped__") or asyncio.iscoroutinefunction(middleware):
                return await self.app.container.resolve(middleware, call_next=call_next, **kwargs)
            else:
                return middleware(call_next=call_next, **kwargs)
<<<<<<< HEAD

        return wrapped

=======
        
        return wrapped
    
>>>>>>> origin/main
    async def send_response(self, send: ASGISend, result: Any) -> None:
        """Send an HTTP response based on the result type."""
        # Handle different return types
        if isinstance(result, tuple) and len(result) == 2:
            # (body, status)
            body, status = result
        else:
            body = result
            status = 200
<<<<<<< HEAD

=======
        
>>>>>>> origin/main
        # Determine content type and body
        if isinstance(body, dict) or isinstance(body, list):
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
<<<<<<< HEAD

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

=======
        
        # Send response
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [
                [b"content-type", content_type.encode("latin-1")],
                [b"content-length", str(len(content)).encode("latin-1")],
            ],
        })
        
        await send({
            "type": "http.response.body",
            "body": content,
        })
    
    async def send_error(self, send: ASGISend, status: int, message: str) -> None:
        """Send an error response."""
        content = json.dumps({"error": message}).encode("utf-8")
        
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [
                [b"content-type", b"application/json"],
                [b"content-length", str(len(content)).encode("latin-1")],
            ],
        })
        
        await send({
            "type": "http.response.body",
            "body": content,
        })


def asgi_extension(app: Application) -> None:
    """ASGI extension that adds web framework capabilities.
    
>>>>>>> origin/main
    This extension provides:
    - HTTP route decorators: @app.get(), @app.post(), etc.
    - WebSocket support: @app.websocket()
    - Middleware: @app.middleware()
    - Request/response handling with dependency injection
    - ASGI 3.0 compliance
<<<<<<< HEAD

    Example:
        app = Application()
        app.use(asgi_extension)

        @app.get("/")
        async def index():
            return {"message": "Hello World"}

=======
    
    Example:
        app = Application()
        app.use(asgi_extension)
        
        @app.get("/")
        async def index():
            return {"message": "Hello World"}
        
>>>>>>> origin/main
        @app.get("/user/{id}")
        @inject
        async def get_user(id: int, service: UserService):
            user = await service.get_user(id)
            return user
<<<<<<< HEAD

=======
        
>>>>>>> origin/main
        # app.asgi is the ASGI handler
        # Run with: uvicorn app:app.asgi
    """
    # Create ASGI manager
    manager = ASGIManager(app)
<<<<<<< HEAD

    # Store manager and create ASGI handler
    app.asgi_manager = manager
    app.asgi = manager.create_asgi_handler()

    # Add request and session scopes to container
    from whiskey.core.scopes import ContextVarScope

    class RequestScope(ContextVarScope):
        """Scope for HTTP requests - isolated per async context."""

        def __init__(self):
            super().__init__("request")

    class SessionScope(ContextVarScope):
        """Scope for HTTP sessions - isolated per async context."""

        def __init__(self):
            super().__init__("session")

    app.add_scope("request", RequestScope)
    app.add_scope("session", SessionScope)

=======
    
    # Store manager and create ASGI handler
    app.asgi_manager = manager
    app.asgi = manager.create_asgi_handler()
    
    # Add request and session scopes to container
    from whiskey.core.scopes import ContextVarScope
    
    class RequestScope(ContextVarScope):
        """Scope for HTTP requests - isolated per async context."""
        def __init__(self):
            super().__init__("request")
    
    class SessionScope(ContextVarScope):
        """Scope for HTTP sessions - isolated per async context."""
        def __init__(self):
            super().__init__("session")
    
    app.add_scope("request", RequestScope)
    app.add_scope("session", SessionScope)
    
>>>>>>> origin/main
    # Create route decorators
    def create_route_decorator(methods: List[str]):
        def route(path: str, name: Optional[str] = None):
            def decorator(func: Callable) -> Callable:
                metadata = RouteMetadata(
<<<<<<< HEAD
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
=======
                    func=func,
                    path=path,
                    methods=methods,
                    name=name or func.__name__
                )
                manager.add_route(metadata)
                return func
            return decorator
        return route
    
    # Add route decorators
    app.add_decorator("route", lambda path, methods=["GET"], name=None: create_route_decorator(methods)(path, name))
>>>>>>> origin/main
    app.add_decorator("get", create_route_decorator(["GET"]))
    app.add_decorator("post", create_route_decorator(["POST"]))
    app.add_decorator("put", create_route_decorator(["PUT"]))
    app.add_decorator("delete", create_route_decorator(["DELETE"]))
    app.add_decorator("patch", create_route_decorator(["PATCH"]))
    app.add_decorator("head", create_route_decorator(["HEAD"]))
    app.add_decorator("options", create_route_decorator(["OPTIONS"]))
<<<<<<< HEAD

    # WebSocket decorator
    def websocket(path: str, name: Optional[str] = None):
        def decorator(func: Callable) -> Callable:
            metadata = WebSocketMetadata(func=func, path=path, name=name or func.__name__)
            manager.add_websocket(metadata)
            return func

        return decorator

    app.add_decorator("websocket", websocket)

    # Middleware decorator
    def middleware(name: Optional[str] = None, priority: int = 0):
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
            )

        # The ASGI handler already manages lifecycle via the lifespan protocol
        # So we can run uvicorn directly without additional lifecycle management
        uvicorn.run(app.asgi, host=host, port=port, **kwargs)
    
    # Register the ASGI runner with the new standardized API
    app.register_runner("asgi", run_asgi)
    
    # Also make it available as a method for backward compatibility
    app.run_asgi = run_asgi
=======
    
    # WebSocket decorator
    def websocket(path: str, name: Optional[str] = None):
        def decorator(func: Callable) -> Callable:
            metadata = WebSocketMetadata(
                func=func,
                path=path,
                name=name or func.__name__
            )
            manager.add_websocket(metadata)
            return func
        return decorator
    
    app.add_decorator("websocket", websocket)
    
    # Middleware decorator
    def middleware(name: Optional[str] = None, priority: int = 0):
        def decorator(func: Callable) -> Callable:
            metadata = MiddlewareMetadata(
                func=func,
                name=name or func.__name__,
                priority=priority
            )
            manager.add_middleware(metadata)
            return func
        return decorator
    
    app.add_decorator("middleware", middleware)
    
    # Helper methods
    def run_asgi(host: str = "127.0.0.1", port: int = 8000, **kwargs) -> None:
        """Run the ASGI application with uvicorn."""
        try:
            import uvicorn
        except ImportError:
            raise ImportError("uvicorn is required to run ASGI apps. Install with: pip install uvicorn")
        
        uvicorn.run(app.asgi, host=host, port=port, **kwargs)
    
    app.run_asgi = run_asgi
    
    # Enhanced run method
    original_run = app.run
    
    def enhanced_run(main: Optional[Callable] = None) -> None:
        """Enhanced run that can run ASGI server if no main provided."""
        if main is None and hasattr(app, '_main_func'):
            original_run()
        elif main is None and hasattr(app, 'asgi_manager'):
            app.run_asgi()
        else:
            original_run(main)
    
    app.run = enhanced_run
>>>>>>> origin/main
