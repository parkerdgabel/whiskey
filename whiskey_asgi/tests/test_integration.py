"""Integration tests for ASGI extension."""

import asyncio
import json

import pytest
from whiskey import Whiskey, component, inject, singleton

from whiskey_asgi import Request, asgi_extension


class TestIntegration:
    """Integration tests for real-world scenarios."""

    @pytest.mark.asyncio
    async def test_full_application_flow(self):
        """Test a complete application with routes, middleware, and DI."""
        app = Whiskey()
        app.use(asgi_extension)
        
        # Services
        @app.singleton
        class Database:
            def __init__(self):
                self.users = {
                    "1": {"id": "1", "name": "Alice"},
                    "2": {"id": "2", "name": "Bob"},
                }
            
            def get_user(self, user_id):
                return self.users.get(user_id)
            
            def list_users(self):
                return list(self.users.values())
        
        @app.component
        class UserService:
            def __init__(self, db: Database):
                self.db = db
            
            def get_user(self, user_id):
                user = self.db.get_user(user_id)
                if not user:
                    raise ValueError(f"User {user_id} not found")
                return user
            
            def list_users(self):
                return self.db.list_users()
        
        # Middleware
        request_count = 0
        
        @app.middleware(priority=10)
        async def counting_middleware(call_next, request: Request):
            nonlocal request_count
            request_count += 1
            response = await call_next(request)
            return response
        
        # Routes
        @app.get("/users")
        @inject
        async def list_users(service: UserService):
            return service.list_users()
        
        @app.get("/users/{user_id}")
        @inject
        async def get_user(user_id: str, service: UserService):
            try:
                return service.get_user(user_id)
            except ValueError as e:
                return {"error": str(e)}, 404
        
        @app.post("/users/{user_id}")
        @inject
        async def update_user(user_id: str, request: Request, service: UserService):
            data = await request.json()
            user = service.get_user(user_id)
            user.update(data)
            return user
        
        # Helper to make requests
        async def make_request(method, path, body=None):
            scope = {
                "type": "http",
                "method": method,
                "path": path,
                "headers": [[b"content-type", b"application/json"]] if body else [],
            }
            
            async def receive():
                if body:
                    return {
                        "type": "http.request",
                        "body": json.dumps(body).encode() if body else b"",
                        "more_body": False
                    }
                return {"type": "http.request", "body": b"", "more_body": False}
            
            sent_messages = []
            
            async def send(message):
                sent_messages.append(message)
            
            await app.asgi(scope, receive, send)
            
            # Parse response
            status = sent_messages[0]["status"]
            body_bytes = sent_messages[1]["body"]
            body = json.loads(body_bytes) if body_bytes else None
            return status, body
        
        # Test listing users
        status, body = await make_request("GET", "/users")
        assert status == 200
        assert len(body) == 2
        assert any(u["name"] == "Alice" for u in body)
        
        # Test getting specific user
        status, body = await make_request("GET", "/users/1")
        assert status == 200
        assert body == {"id": "1", "name": "Alice"}
        
        # Test non-existent user
        status, body = await make_request("GET", "/users/999")
        assert status == 404
        assert "error" in body
        
        # Test updating user
        status, body = await make_request("POST", "/users/1", {"name": "Alice Updated"})
        assert status == 200
        assert body["name"] == "Alice Updated"
        
        # Verify middleware ran
        assert request_count == 4  # 4 requests made

    @pytest.mark.asyncio
    async def test_websocket_chat_room(self):
        """Test WebSocket chat room implementation."""
        app = Whiskey()
        app.use(asgi_extension)
        
        # Chat room manager
        @app.singleton
        class ChatRoom:
            def __init__(self):
                self.connections = {}
                self.messages = []
            
            def add_connection(self, room_id, ws):
                if room_id not in self.connections:
                    self.connections[room_id] = []
                self.connections[room_id].append(ws)
            
            def remove_connection(self, room_id, ws):
                if room_id in self.connections:
                    self.connections[room_id].remove(ws)
            
            async def broadcast(self, room_id, message, sender_ws=None):
                self.messages.append((room_id, message))
                if room_id in self.connections:
                    for ws in self.connections[room_id]:
                        if ws != sender_ws:
                            await ws.send(message)
        
        @app.websocket("/chat/{room_id}")
        @inject
        async def chat_handler(websocket, room_id: str, chat_room: ChatRoom):
            await websocket.accept()
            chat_room.add_connection(room_id, websocket)
            
            try:
                await chat_room.broadcast(room_id, f"User joined room {room_id}")
                
                async for message in websocket:
                    await chat_room.broadcast(room_id, message, websocket)
            finally:
                chat_room.remove_connection(room_id, websocket)
                await chat_room.broadcast(room_id, f"User left room {room_id}")
        
        # Simulate WebSocket connection
        scope = {
            "type": "websocket",
            "path": "/chat/general",
        }
        
        messages_to_receive = [
            {"type": "websocket.receive", "text": "Hello everyone!"},
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
        
        await app.asgi(scope, receive, send)
        
        # Check WebSocket interaction
        assert sent_messages[0]["type"] == "websocket.accept"
        
        # Check chat room recorded messages
        chat_room = await app.container.resolve(ChatRoom)
        assert len(chat_room.messages) == 3
        assert chat_room.messages[0] == ("general", "User joined room general")
        assert chat_room.messages[1] == ("general", "Hello everyone!")
        assert chat_room.messages[2] == ("general", "User left room general")

    @pytest.mark.asyncio
    async def test_middleware_chain(self):
        """Test multiple middleware in chain."""
        app = Whiskey()
        app.use(asgi_extension)
        
        # Track middleware execution order
        execution_order = []
        
        @app.middleware(priority=30)
        @inject
        async def first_middleware(call_next, request: Request):
            execution_order.append("first_start")
            response = await call_next(request)
            execution_order.append("first_end")
            return response
        
        @app.middleware(priority=20)
        @inject
        async def second_middleware(call_next, request: Request):
            execution_order.append("second_start")
            response = await call_next(request)
            execution_order.append("second_end")
            return response
        
        @app.middleware(priority=10)
        @inject
        async def third_middleware(call_next, request: Request):
            execution_order.append("third_start")
            response = await call_next(request)
            execution_order.append("third_end")
            return response
        
        @app.get("/test")
        def test_route():
            execution_order.append("handler")
            return {"ok": True}
        
        # Make request
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
        }
        
        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}
        
        sent_messages = []
        
        async def send(message):
            sent_messages.append(message)
        
        await app.asgi(scope, receive, send)
        
        # Check execution order (onion pattern)
        assert execution_order == [
            "first_start",
            "second_start",
            "third_start",
            "handler",
            "third_end",
            "second_end",
            "first_end",
        ]

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling in routes."""
        app = Whiskey()
        app.use(asgi_extension)
        
        @app.get("/error")
        def error_route():
            raise ValueError("Something went wrong")
        
        @app.get("/custom_error")
        def custom_error_route():
            error = RuntimeError("Custom error")
            error.status_code = 418  # I'm a teapot
            raise error
        
        # Test standard error
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/error",
        }
        
        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}
        
        sent_messages = []
        
        async def send(message):
            sent_messages.append(message)
        
        await app.asgi(scope, receive, send)
        
        assert sent_messages[0]["status"] == 500
        body = json.loads(sent_messages[1]["body"])
        assert body["error"] == "Something went wrong"
        
        # Test custom status code
        sent_messages.clear()
        scope["path"] = "/custom_error"
        
        await app.asgi(scope, receive, send)
        
        assert sent_messages[0]["status"] == 418
        body = json.loads(sent_messages[1]["body"])
        assert body["error"] == "Custom error"

    @pytest.mark.asyncio
    async def test_lifespan_integration(self):
        """Test lifespan events with application lifecycle."""
        app = Whiskey()
        app.use(asgi_extension)
        
        events = []
        
        @app.on_startup
        async def startup_handler():
            events.append("app_startup")
        
        @app.on_shutdown
        async def shutdown_handler():
            events.append("app_shutdown")
        
        # Simulate lifespan
        scope = {"type": "lifespan"}
        messages = [
            {"type": "lifespan.startup"},
            {"type": "lifespan.shutdown"},
        ]
        message_index = 0
        
        async def receive():
            nonlocal message_index
            msg = messages[message_index]
            message_index += 1
            return msg
        
        sent_messages = []
        
        async def send(message):
            sent_messages.append(message)
        
        await app.asgi(scope, receive, send)
        
        # Check events fired in order
        assert events == ["app_startup", "app_shutdown"]
        
        # Check ASGI protocol
        assert sent_messages == [
            {"type": "lifespan.startup.complete"},
            {"type": "lifespan.shutdown.complete"},
        ]