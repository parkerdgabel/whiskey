"""Tests for ASGIHandler class."""

import asyncio
import json

import pytest
from whiskey import Whiskey, inject

from whiskey_asgi.extension import (
    ASGIHandler,
    ASGIManager,
    Request,
    RouteMetadata,
    WebSocket,
    WebSocketMetadata,
)


class TestASGIHandler:
    """Test ASGIHandler functionality."""

    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test ASGIHandler initialization."""
        app = Whiskey()
        manager = ASGIManager(app)
        handler = ASGIHandler(manager)
        
        assert handler.manager is manager
        assert handler.app is app

    @pytest.mark.asyncio
    async def test_unknown_scope_type(self):
        """Test handling unknown scope type."""
        app = Whiskey()
        manager = ASGIManager(app)
        handler = ASGIHandler(manager)
        
        scope = {"type": "unknown"}
        
        async def receive():
            pass
        
        async def send(message):
            pass
        
        with pytest.raises(RuntimeError, match="Unknown scope type: unknown"):
            await handler(scope, receive, send)

    @pytest.mark.asyncio
    async def test_lifespan_success(self):
        """Test successful lifespan handling."""
        app = Whiskey()
        manager = ASGIManager(app)
        handler = ASGIHandler(manager)
        
        # Track lifecycle
        events = []
        
        @app.on_startup
        async def startup():
            events.append("startup")
        
        @app.on_shutdown
        async def shutdown():
            events.append("shutdown")
        
        scope = {"type": "lifespan"}
        messages_to_receive = [
            {"type": "lifespan.startup"},
            {"type": "lifespan.shutdown"},
        ]
        receive_index = 0
        sent_messages = []
        
        async def receive():
            nonlocal receive_index
            msg = messages_to_receive[receive_index]
            receive_index += 1
            return msg
        
        async def send(message):
            sent_messages.append(message)
        
        await handler(scope, receive, send)
        
        # Check lifecycle events
        assert events == ["startup", "shutdown"]
        
        # Check ASGI messages
        assert sent_messages == [
            {"type": "lifespan.startup.complete"},
            {"type": "lifespan.shutdown.complete"},
        ]

    @pytest.mark.asyncio
    async def test_lifespan_startup_failure(self):
        """Test lifespan with startup failure."""
        app = Whiskey()
        manager = ASGIManager(app)
        handler = ASGIHandler(manager)
        
        @app.on_startup
        async def failing_startup():
            raise ValueError("Startup failed")
        
        scope = {"type": "lifespan"}
        sent_messages = []
        
        async def receive():
            return {"type": "lifespan.startup"}
        
        async def send(message):
            sent_messages.append(message)
        
        with pytest.raises(ValueError, match="Startup failed"):
            await handler(scope, receive, send)
        
        # Should send failure message
        assert len(sent_messages) == 1
        assert sent_messages[0]["type"] == "lifespan.startup.failed"
        assert sent_messages[0]["message"] == "Startup failed"

    @pytest.mark.asyncio
    async def test_http_simple_response(self):
        """Test simple HTTP response handling."""
        app = Whiskey()
        manager = ASGIManager(app)
        handler = ASGIHandler(manager)
        
        # Add a simple route
        route = RouteMetadata(
            func=lambda: {"message": "Hello, World!"},
            path="/hello",
            methods=["GET"],
            name="hello"
        )
        manager.add_route(route)
        
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/hello",
        }
        
        sent_messages = []
        
        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}
        
        async def send(message):
            sent_messages.append(message)
        
        await handler(scope, receive, send)
        
        # Check response
        assert len(sent_messages) == 2
        
        # Start response
        start = sent_messages[0]
        assert start["type"] == "http.response.start"
        assert start["status"] == 200
        
        # Find content-type header
        headers = dict(start["headers"])
        assert headers[b"content-type"] == b"application/json"
        
        # Body
        body = sent_messages[1]
        assert body["type"] == "http.response.body"
        assert json.loads(body["body"]) == {"message": "Hello, World!"}

    @pytest.mark.asyncio
    async def test_http_with_params(self):
        """Test HTTP route with parameters."""
        app = Whiskey()
        manager = ASGIManager(app)
        handler = ASGIHandler(manager)
        
        # Route that uses parameters
        def get_user(id):
            return {"user_id": id}
        
        route = RouteMetadata(
            func=get_user,
            path="/users/{id}",
            methods=["GET"],
            name="get_user"
        )
        manager.add_route(route)
        
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/users/123",
        }
        
        sent_messages = []
        
        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}
        
        async def send(message):
            sent_messages.append(message)
        
        await handler(scope, receive, send)
        
        # Check response body
        body_msg = sent_messages[1]
        assert json.loads(body_msg["body"]) == {"user_id": "123"}

    @pytest.mark.asyncio
    async def test_http_with_dependency_injection(self):
        """Test HTTP route with dependency injection."""
        app = Whiskey()
        manager = ASGIManager(app)
        handler = ASGIHandler(manager)
        
        # Service to inject
        class UserService:
            def get_user(self, user_id):
                return {"id": user_id, "name": f"User {user_id}"}
        
        # Register service
        app.container[UserService] = UserService()
        
        # Route with DI
        @inject
        async def get_user(id: str, service: UserService):
            return service.get_user(id)
        
        route = RouteMetadata(
            func=get_user,
            path="/users/{id}",
            methods=["GET"],
            name="get_user"
        )
        manager.add_route(route)
        
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/users/42",
        }
        
        sent_messages = []
        
        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}
        
        async def send(message):
            sent_messages.append(message)
        
        await handler(scope, receive, send)
        
        # Check response
        body_msg = sent_messages[1]
        assert json.loads(body_msg["body"]) == {"id": "42", "name": "User 42"}

    @pytest.mark.asyncio
    async def test_http_request_injection(self):
        """Test Request object injection."""
        app = Whiskey()
        manager = ASGIManager(app)
        handler = ASGIHandler(manager)
        
        # Route that uses Request
        @inject
        async def echo_request(request: Request):
            return {
                "method": request.method,
                "path": request.path,
                "params": request.route_params,
            }
        
        route = RouteMetadata(
            func=echo_request,
            path="/echo/{value}",
            methods=["POST"],
            name="echo"
        )
        manager.add_route(route)
        
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/echo/test123",
        }
        
        sent_messages = []
        
        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}
        
        async def send(message):
            sent_messages.append(message)
        
        await handler(scope, receive, send)
        
        # Check response
        body_msg = sent_messages[1]
        result = json.loads(body_msg["body"])
        assert result == {
            "method": "POST",
            "path": "/echo/test123",
            "params": {"value": "test123"},
        }

    @pytest.mark.asyncio
    async def test_http_404(self):
        """Test 404 response for non-existent route."""
        app = Whiskey()
        manager = ASGIManager(app)
        handler = ASGIHandler(manager)
        
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/nonexistent",
        }
        
        sent_messages = []
        
        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}
        
        async def send(message):
            sent_messages.append(message)
        
        await handler(scope, receive, send)
        
        # Check 404 response
        assert sent_messages[0]["status"] == 404
        body = json.loads(sent_messages[1]["body"])
        assert body["error"] == "Not Found"

    @pytest.mark.asyncio
    async def test_http_response_types(self):
        """Test different response type handling."""
        app = Whiskey()
        manager = ASGIManager(app)
        handler = ASGIHandler(manager)
        
        # Test different return types
        test_cases = [
            # (path, func, expected_body, expected_content_type, expected_status)
            ("/json", lambda: {"key": "value"}, b'{"key": "value"}', b"application/json", 200),
            ("/text", lambda: "Hello", b"Hello", b"text/plain; charset=utf-8", 200),
            ("/bytes", lambda: b"Binary", b"Binary", b"application/octet-stream", 200),
            ("/none", lambda: None, b"", b"text/plain", 200),
            ("/tuple", lambda: ({"status": "created"}, 201), b'{"status": "created"}', b"application/json", 201),
        ]
        
        for path, func, expected_body, expected_content_type, expected_status in test_cases:
            route = RouteMetadata(func=func, path=path, methods=["GET"], name=path)
            manager.add_route(route)
        
        # Test each case
        for path, _, expected_body, expected_content_type, expected_status in test_cases:
            scope = {
                "type": "http",
                "method": "GET",
                "path": path,
            }
            
            sent_messages = []
            
            async def receive():
                return {"type": "http.request", "body": b"", "more_body": False}
            
            async def send(message):
                sent_messages.append(message)
            
            await handler(scope, receive, send)
            
            # Check response
            start = sent_messages[0]
            assert start["status"] == expected_status
            
            headers = dict(start["headers"])
            assert headers[b"content-type"] == expected_content_type
            
            body = sent_messages[1]
            assert body["body"] == expected_body

    @pytest.mark.asyncio
    async def test_websocket_handler(self):
        """Test WebSocket handler."""
        app = Whiskey()
        manager = ASGIManager(app)
        handler = ASGIHandler(manager)
        
        # Track WebSocket events
        events = []
        
        async def ws_handler(websocket: WebSocket):
            events.append("connected")
            await websocket.accept()
            
            # Echo messages
            async for msg in websocket:
                events.append(f"received: {msg}")
                await websocket.send(f"Echo: {msg}")
        
        ws_meta = WebSocketMetadata(
            func=ws_handler,
            path="/ws",
            name="ws"
        )
        manager.add_websocket(ws_meta)
        
        scope = {
            "type": "websocket",
            "path": "/ws",
        }
        
        messages_to_receive = [
            {"type": "websocket.receive", "text": "Hello"},
            {"type": "websocket.receive", "text": "World"},
            {"type": "websocket.disconnect", "code": 1000},
        ]
        receive_index = 0
        sent_messages = []
        
        async def receive():
            nonlocal receive_index
            msg = messages_to_receive[receive_index]
            receive_index += 1
            return msg
        
        async def send(message):
            sent_messages.append(message)
        
        await handler(scope, receive, send)
        
        # Check events
        assert events == ["connected", "received: Hello", "received: World"]
        
        # Check sent messages
        assert sent_messages[0]["type"] == "websocket.accept"
        assert sent_messages[1] == {"type": "websocket.send", "text": "Echo: Hello"}
        assert sent_messages[2] == {"type": "websocket.send", "text": "Echo: World"}

    @pytest.mark.asyncio
    async def test_websocket_no_handler(self):
        """Test WebSocket with no matching handler."""
        app = Whiskey()
        manager = ASGIManager(app)
        handler = ASGIHandler(manager)
        
        scope = {
            "type": "websocket",
            "path": "/nonexistent",
        }
        
        sent_messages = []
        
        async def receive():
            pass
        
        async def send(message):
            sent_messages.append(message)
        
        await handler(scope, receive, send)
        
        # Should close with error
        assert len(sent_messages) == 1
        assert sent_messages[0]["type"] == "websocket.close"
        assert sent_messages[0]["code"] == 1001
        assert sent_messages[0]["reason"] == "No handler found"