"""Tests for asgi_extension function."""

import asyncio

import pytest
from whiskey import Whiskey, inject

from whiskey_asgi import asgi_extension
from whiskey_asgi.extension import ASGIHandler, ASGIManager, Request


class TestASGIExtension:
    """Test asgi_extension functionality."""

    def test_extension_setup(self):
        """Test that extension properly sets up the application."""
        app = Whiskey()
        app.use(asgi_extension)
        
        # Check that ASGI components are added
        assert hasattr(app, "asgi_manager")
        assert isinstance(app.asgi_manager, ASGIManager)
        
        assert hasattr(app, "asgi")
        assert isinstance(app.asgi, ASGIHandler)
        
        # Check that scope method exists
        assert hasattr(app, "scope")
        assert hasattr(app.container, "scope")

    def test_route_decorators_added(self):
        """Test that route decorators are added to the application."""
        app = Whiskey()
        app.use(asgi_extension)
        
        # Check HTTP method decorators
        for method in ["route", "get", "post", "put", "delete", "patch", "head", "options"]:
            assert hasattr(app, method)
            assert callable(getattr(app, method))
        
        # Check WebSocket decorator
        assert hasattr(app, "websocket")
        assert callable(app.websocket)
        
        # Check middleware decorator
        assert hasattr(app, "middleware")
        assert callable(app.middleware)

    def test_route_decorator_usage(self):
        """Test using route decorators."""
        app = Whiskey()
        app.use(asgi_extension)
        
        # Use various decorators
        @app.get("/")
        def index():
            return {"message": "index"}
        
        @app.post("/users")
        def create_user():
            return {"message": "created"}
        
        @app.route("/custom", methods=["GET", "POST"])
        def custom():
            return {"message": "custom"}
        
        # Check routes were registered
        assert len(app.asgi_manager.routes) == 3
        
        # Check first route
        route1 = app.asgi_manager.routes[0]
        assert route1.path == "/"
        assert route1.methods == ["GET"]
        assert route1.func() == {"message": "index"}
        
        # Check second route
        route2 = app.asgi_manager.routes[1]
        assert route2.path == "/users"
        assert route2.methods == ["POST"]
        
        # Check custom route
        route3 = app.asgi_manager.routes[2]
        assert route3.path == "/custom"
        assert route3.methods == ["GET", "POST"]

    def test_websocket_decorator_usage(self):
        """Test using WebSocket decorator."""
        app = Whiskey()
        app.use(asgi_extension)
        
        @app.websocket("/ws")
        async def ws_handler(websocket):
            await websocket.accept()
            await websocket.send("Hello")
        
        @app.websocket("/chat/{room}")
        async def chat_handler(websocket, room):
            await websocket.accept()
            await websocket.send(f"Welcome to {room}")
        
        # Check WebSockets were registered
        assert len(app.asgi_manager.websockets) == 2
        
        ws1 = app.asgi_manager.websockets[0]
        assert ws1.path == "/ws"
        assert ws1.func is ws_handler
        
        ws2 = app.asgi_manager.websockets[1]
        assert ws2.path == "/chat/{room}"
        assert ws2.func is chat_handler

    def test_middleware_decorator_usage(self):
        """Test using middleware decorator."""
        app = Whiskey()
        app.use(asgi_extension)
        
        @app.middleware(priority=10)
        async def auth_middleware(call_next, request):
            # Add auth header
            response = await call_next(request)
            return response
        
        @app.middleware(priority=5)
        async def logging_middleware(call_next, request):
            # Log request
            response = await call_next(request)
            return response
        
        # Check middleware were registered
        assert len(app.asgi_manager.middleware) == 2
        
        # Should be sorted by priority (highest first)
        mid1 = app.asgi_manager.middleware[0]
        assert mid1.priority == 10
        assert mid1.func is auth_middleware
        
        mid2 = app.asgi_manager.middleware[1]
        assert mid2.priority == 5
        assert mid2.func is logging_middleware

    def test_runner_registration(self):
        """Test that ASGI runner is registered."""
        app = Whiskey()
        app.use(asgi_extension)
        
        # Check runner is registered via run_asgi method
        assert hasattr(app, "run_asgi")
        assert callable(app.run_asgi)
        
        # Check backward compatibility method
        assert hasattr(app, "run_asgi")
        assert callable(app.run_asgi)

    def test_named_routes(self):
        """Test routes with custom names."""
        app = Whiskey()
        app.use(asgi_extension)
        
        @app.get("/users", name="user_list")
        def list_users():
            return []
        
        @app.get("/users/{id}", name="user_detail")
        def get_user(id):
            return {"id": id}
        
        # Check names
        route1 = app.asgi_manager.routes[0]
        assert route1.name == "user_list"
        
        route2 = app.asgi_manager.routes[1]
        assert route2.name == "user_detail"

    def test_route_with_dependency_injection(self):
        """Test that routes work with dependency injection."""
        app = Whiskey()
        app.use(asgi_extension)
        
        # Service to inject
        class Database:
            def get_data(self):
                return {"data": "from_db"}
        
        app.container[Database] = Database()
        
        @app.get("/data")
        @inject
        async def get_data(db: Database):
            return db.get_data()
        
        # Route should be registered
        route = app.asgi_manager.routes[0]
        assert route.path == "/data"
        # The function should have the inject wrapper
        assert hasattr(route.func, "__wrapped__")

    @pytest.mark.asyncio
    async def test_request_scope_isolation(self):
        """Test that request scope provides isolation."""
        app = Whiskey()
        app.use(asgi_extension)
        
        # Track requests
        requests_seen = []
        
        @app.get("/track")
        @inject
        async def track_request(request: Request):
            requests_seen.append(request)
            return {"path": request.path}
        
        # Simulate concurrent requests
        async def simulate_request(path):
            scope = {
                "type": "http",
                "method": "GET",
                "path": path,
            }
            
            async def receive():
                return {"type": "http.request", "body": b"", "more_body": False}
            
            sent_messages = []
            
            async def send(message):
                sent_messages.append(message)
            
            await app.asgi(scope, receive, send)
            return sent_messages
        
        # Run concurrent requests
        results = await asyncio.gather(
            simulate_request("/track"),
            simulate_request("/track"),
        )
        
        # Each request should have its own Request instance
        assert len(requests_seen) == 2
        assert requests_seen[0] is not requests_seen[1]

    def test_all_http_methods(self):
        """Test all HTTP method decorators."""
        app = Whiskey()
        app.use(asgi_extension)
        
        methods = {
            "get": "GET",
            "post": "POST",
            "put": "PUT",
            "delete": "DELETE",
            "patch": "PATCH",
            "head": "HEAD",
            "options": "OPTIONS",
        }
        
        for decorator_name, http_method in methods.items():
            decorator = getattr(app, decorator_name)
            
            @decorator(f"/{decorator_name}")
            def handler():
                return {"method": http_method}
            
            # Set function name to avoid conflicts
            handler.__name__ = f"{decorator_name}_handler"
        
        # Check all routes were registered
        assert len(app.asgi_manager.routes) == len(methods)
        
        for i, (decorator_name, http_method) in enumerate(methods.items()):
            route = app.asgi_manager.routes[i]
            assert route.path == f"/{decorator_name}"
            assert route.methods == [http_method]