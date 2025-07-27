"""Tests for ASGIManager class."""

import pytest
from whiskey import Whiskey

from whiskey_asgi.extension import (
    ASGIManager,
    MiddlewareMetadata,
    RouteMetadata,
    WebSocketMetadata,
)


class TestASGIManager:
    """Test ASGIManager functionality."""

    def test_initialization(self):
        """Test ASGIManager initialization."""
        app = Whiskey()
        manager = ASGIManager(app)
        
        assert manager.app is app
        assert manager.routes == []
        assert manager.middleware == []
        assert manager.websockets == []
        assert manager.before_request == []
        assert manager.after_request == []
        assert manager.error_handlers == {}

    def test_add_route(self):
        """Test adding routes."""
        app = Whiskey()
        manager = ASGIManager(app)
        
        route1 = RouteMetadata(
            func=lambda: "hello",
            path="/hello",
            methods=["GET"],
            name="hello"
        )
        
        route2 = RouteMetadata(
            func=lambda: "world",
            path="/world",
            methods=["POST"],
            name="world"
        )
        
        manager.add_route(route1)
        manager.add_route(route2)
        
        assert len(manager.routes) == 2
        assert manager.routes[0] is route1
        assert manager.routes[1] is route2

    def test_add_middleware(self):
        """Test adding middleware with priority sorting."""
        app = Whiskey()
        manager = ASGIManager(app)
        
        # Add middleware with different priorities
        mid1 = MiddlewareMetadata(func=lambda: 1, name="mid1", priority=10)
        mid2 = MiddlewareMetadata(func=lambda: 2, name="mid2", priority=5)
        mid3 = MiddlewareMetadata(func=lambda: 3, name="mid3", priority=15)
        
        manager.add_middleware(mid2)
        manager.add_middleware(mid1)
        manager.add_middleware(mid3)
        
        # Should be sorted by priority (highest first)
        assert len(manager.middleware) == 3
        assert manager.middleware[0] is mid3  # priority 15
        assert manager.middleware[1] is mid1  # priority 10
        assert manager.middleware[2] is mid2  # priority 5

    def test_add_websocket(self):
        """Test adding WebSocket handlers."""
        app = Whiskey()
        manager = ASGIManager(app)
        
        ws1 = WebSocketMetadata(
            func=lambda ws: None,
            path="/ws",
            name="ws1"
        )
        
        ws2 = WebSocketMetadata(
            func=lambda ws: None,
            path="/chat/{room}",
            name="ws2"
        )
        
        manager.add_websocket(ws1)
        manager.add_websocket(ws2)
        
        assert len(manager.websockets) == 2
        assert manager.websockets[0] is ws1
        assert manager.websockets[1] is ws2

    def test_find_route(self):
        """Test finding matching routes."""
        app = Whiskey()
        manager = ASGIManager(app)
        
        # Add routes
        route1 = RouteMetadata(
            func=lambda: "users",
            path="/users",
            methods=["GET", "POST"],
            name="users"
        )
        
        route2 = RouteMetadata(
            func=lambda: "user",
            path="/users/{id}",
            methods=["GET"],
            name="user"
        )
        
        route3 = RouteMetadata(
            func=lambda: "user_posts",
            path="/users/{id}/posts",
            methods=["GET"],
            name="user_posts"
        )
        
        manager.add_route(route1)
        manager.add_route(route2)
        manager.add_route(route3)
        
        # Test exact match
        result = manager.find_route("/users", "GET")
        assert result is not None
        route, params = result
        assert route is route1
        assert params == {}
        
        # Test parametric match
        result = manager.find_route("/users/123", "GET")
        assert result is not None
        route, params = result
        assert route is route2
        assert params == {"id": "123"}
        
        # Test nested parametric match
        result = manager.find_route("/users/456/posts", "GET")
        assert result is not None
        route, params = result
        assert route is route3
        assert params == {"id": "456"}
        
        # Test method mismatch
        result = manager.find_route("/users/{id}", "DELETE")
        assert result is None
        
        # Test no match
        result = manager.find_route("/products", "GET")
        assert result is None

    def test_find_websocket(self):
        """Test finding matching WebSocket handlers."""
        app = Whiskey()
        manager = ASGIManager(app)
        
        # Add WebSocket handlers
        ws1 = WebSocketMetadata(
            func=lambda ws: None,
            path="/ws",
            name="ws1"
        )
        
        ws2 = WebSocketMetadata(
            func=lambda ws: None,
            path="/chat/{room}",
            name="ws2"
        )
        
        ws3 = WebSocketMetadata(
            func=lambda ws: None,
            path="/chat/{room}/user/{user_id}",
            name="ws3"
        )
        
        manager.add_websocket(ws1)
        manager.add_websocket(ws2)
        manager.add_websocket(ws3)
        
        # Test exact match
        result = manager.find_websocket("/ws")
        assert result is not None
        ws, params = result
        assert ws is ws1
        assert params == {}
        
        # Test parametric match
        result = manager.find_websocket("/chat/general")
        assert result is not None
        ws, params = result
        assert ws is ws2
        assert params == {"room": "general"}
        
        # Test nested parametric match
        result = manager.find_websocket("/chat/private/user/123")
        assert result is not None
        ws, params = result
        assert ws is ws3
        assert params == {"room": "private", "user_id": "123"}
        
        # Test no match
        result = manager.find_websocket("/api/ws")
        assert result is None

    def test_create_asgi_handler(self):
        """Test creating ASGI handler."""
        app = Whiskey()
        manager = ASGIManager(app)
        
        handler = manager.create_asgi_handler()
        
        assert handler is not None
        assert handler.manager is manager
        assert handler.app is app

    def test_route_priority_first_match(self):
        """Test that routes are matched in order (first match wins)."""
        app = Whiskey()
        manager = ASGIManager(app)
        
        # Add overlapping routes
        generic_route = RouteMetadata(
            func=lambda: "generic",
            path="/items/{id}",
            methods=["GET"],
            name="generic"
        )
        
        # This could match /items/special but generic_route is added first
        special_route = RouteMetadata(
            func=lambda: "special",
            path="/items/special",
            methods=["GET"],
            name="special"
        )
        
        manager.add_route(generic_route)
        manager.add_route(special_route)
        
        # First match wins
        result = manager.find_route("/items/special", "GET")
        assert result is not None
        route, params = result
        assert route is generic_route  # First match
        assert params == {"id": "special"}