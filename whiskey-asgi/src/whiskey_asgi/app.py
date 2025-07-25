"""ASGI application wrapper for Whiskey framework."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from whiskey import Application, ScopeType

from .request import Request
from .response import Response
from .routing import Router
from .types import ASGIReceive, ASGISend, Scope

if TYPE_CHECKING:
    from .middleware import Middleware


class ASGIApp:
    """ASGI 3.0 compliant application wrapper for Whiskey."""

    def __init__(self, app: Application | None = None):
        self.app = app or Application()
        self.router = Router()
        self._middleware: list[Middleware] = []
        self._lifespan_handlers: dict[str, list[Callable]] = {
            "startup": [],
            "shutdown": [],
        }

    async def __call__(
        self,
        scope: Scope,
        receive: ASGIReceive,
        send: ASGISend,
    ) -> None:
        """ASGI 3.0 application interface."""
        if scope["type"] == "lifespan":
            await self._handle_lifespan(scope, receive, send)
        elif scope["type"] == "http":
            await self._handle_http(scope, receive, send)
        elif scope["type"] == "websocket":
            await self._handle_websocket(scope, receive, send)
        else:
            raise RuntimeError(f"Unknown scope type: {scope['type']}")

    async def _handle_lifespan(
        self,
        scope: Scope,
        receive: ASGIReceive,
        send: ASGISend,
    ) -> None:
        """Handle ASGI lifespan protocol."""
        message = await receive()
        assert message["type"] == "lifespan.startup"

        try:
            # Run Whiskey app startup
            await self.app.startup()
            
            # Run additional startup handlers
            for handler in self._lifespan_handlers["startup"]:
                await handler()
            
            await send({"type": "lifespan.startup.complete"})
        except Exception as exc:
            await send({"type": "lifespan.startup.failed", "message": str(exc)})
            raise

        # Wait for shutdown
        message = await receive()
        assert message["type"] == "lifespan.shutdown"

        try:
            # Run shutdown handlers
            for handler in self._lifespan_handlers["shutdown"]:
                await handler()
            
            # Run Whiskey app shutdown
            await self.app.shutdown()
            
            await send({"type": "lifespan.shutdown.complete"})
        except Exception as exc:
            await send({"type": "lifespan.shutdown.failed", "message": str(exc)})
            raise

    async def _handle_http(
        self,
        scope: Scope,
        receive: ASGIReceive,
        send: ASGISend,
    ) -> None:
        """Handle HTTP requests."""
        # Create request-scoped container
        request_container = self.app.container.create_child()
        
        # Create request and response objects
        request = Request(scope, receive)
        response = Response(send)
        
        # Register request in the container for injection
        request_container.register(
            Request,
            instance=request,
            scope=ScopeType.REQUEST,
        )
        request_container.register(
            Response,
            instance=response,
            scope=ScopeType.REQUEST,
        )
        
        # Enter request scope
        async with request_container.scope_manager.get_scope(ScopeType.REQUEST).enter():
            try:
                # Apply middleware chain
                handler = self._build_middleware_chain(self._route_handler)
                await handler(request, response)
            finally:
                # Ensure response is sent
                if not response.started:
                    await response.send_error(500, "Internal Server Error")
                elif not response.complete:
                    await response.end()
                
                # Cleanup
                await request_container.dispose()

    async def _handle_websocket(
        self,
        scope: Scope,
        receive: ASGIReceive,
        send: ASGISend,
    ) -> None:
        """Handle WebSocket connections."""
        # WebSocket support can be added in a future version
        await send({
            "type": "websocket.close",
            "code": 1001,
            "reason": "WebSocket not implemented",
        })

    async def _route_handler(self, request: Request, response: Response) -> None:
        """Route the request to the appropriate handler."""
        handler = await self.router.resolve(request)
        if handler:
            # Inject dependencies and call handler
            result = await self.app.container.resolve(handler, request=request)
            
            # Handle different return types
            if isinstance(result, Response):
                # Copy the returned response
                response._status = result._status
                response._headers = result._headers
                await response.send(result._body)
            elif isinstance(result, dict):
                await response.json(result)
            elif isinstance(result, str):
                await response.text(result)
            elif result is not None:
                await response.text(str(result))
        else:
            await response.send_error(404, "Not Found")

    def _build_middleware_chain(
        self,
        handler: Callable[[Request, Response], Awaitable[None]],
    ) -> Callable[[Request, Response], Awaitable[None]]:
        """Build the middleware chain."""
        for middleware in reversed(self._middleware):
            handler = middleware.wrap(handler)
        return handler

    def add_middleware(self, middleware: Middleware) -> None:
        """Add a middleware to the application."""
        self._middleware.append(middleware)

    def on_startup(self, handler: Callable[[], Awaitable[None]]) -> None:
        """Register a startup handler."""
        self._lifespan_handlers["startup"].append(handler)

    def on_shutdown(self, handler: Callable[[], Awaitable[None]]) -> None:
        """Register a shutdown handler."""
        self._lifespan_handlers["shutdown"].append(handler)

    # Routing methods delegate to router
    def route(self, path: str, methods: list[str] | None = None):
        """Decorator to register a route."""
        return self.router.route(path, methods)

    def get(self, path: str):
        """Register a GET route."""
        return self.router.get(path)

    def post(self, path: str):
        """Register a POST route."""
        return self.router.post(path)

    def put(self, path: str):
        """Register a PUT route."""
        return self.router.put(path)

    def delete(self, path: str):
        """Register a DELETE route."""
        return self.router.delete(path)

    def patch(self, path: str):
        """Register a PATCH route."""
        return self.router.patch(path)