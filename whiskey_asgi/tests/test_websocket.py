"""Tests for WebSocket class."""

import asyncio

import pytest

from whiskey_asgi.extension import WebSocket
from whiskey_asgi.types import Scope


class TestWebSocket:
    """Test WebSocket functionality."""

    def test_basic_properties(self):
        """Test basic WebSocket properties."""
        scope: Scope = {
            "type": "websocket",
            "path": "/ws",
            "headers": [
                [b"host", b"example.com"],
                [b"upgrade", b"websocket"],
                [b"sec-websocket-key", b"x3JJHMbDL1EzLkh9GBhXDw=="],
            ],
        }
        
        async def receive():
            pass
        
        async def send(message):
            pass
        
        ws = WebSocket(scope, receive, send)
        
        assert ws.path == "/ws"
        assert ws.headers["host"] == "example.com"
        assert ws.headers["upgrade"] == "websocket"
        assert ws._accepted is False

    def test_route_params(self):
        """Test route parameter storage."""
        scope: Scope = {
            "type": "websocket",
            "path": "/ws/room/123",
        }
        
        async def receive():
            pass
        
        async def send(message):
            pass
        
        ws = WebSocket(scope, receive, send)
        ws.route_params = {"room_id": "123"}
        
        assert ws.route_params == {"room_id": "123"}

    @pytest.mark.asyncio
    async def test_accept(self):
        """Test accepting WebSocket connection."""
        scope: Scope = {
            "type": "websocket",
            "path": "/ws",
        }
        
        sent_messages = []
        
        async def receive():
            pass
        
        async def send(message):
            sent_messages.append(message)
        
        ws = WebSocket(scope, receive, send)
        
        # Accept without subprotocol
        await ws.accept()
        
        assert ws._accepted is True
        assert len(sent_messages) == 1
        assert sent_messages[0] == {
            "type": "websocket.accept",
            "subprotocol": "",
        }

    @pytest.mark.asyncio
    async def test_accept_with_subprotocol(self):
        """Test accepting WebSocket with subprotocol."""
        scope: Scope = {
            "type": "websocket",
            "path": "/ws",
        }
        
        sent_messages = []
        
        async def receive():
            pass
        
        async def send(message):
            sent_messages.append(message)
        
        ws = WebSocket(scope, receive, send)
        
        # Accept with subprotocol
        await ws.accept("chat")
        
        assert ws._accepted is True
        assert sent_messages[0] == {
            "type": "websocket.accept",
            "subprotocol": "chat",
        }

    @pytest.mark.asyncio
    async def test_send_text(self):
        """Test sending text data."""
        scope: Scope = {
            "type": "websocket",
            "path": "/ws",
        }
        
        sent_messages = []
        
        async def receive():
            pass
        
        async def send(message):
            sent_messages.append(message)
        
        ws = WebSocket(scope, receive, send)
        
        # Must accept first
        await ws.accept()
        sent_messages.clear()
        
        # Send text
        await ws.send("Hello, World!")
        
        assert len(sent_messages) == 1
        assert sent_messages[0] == {
            "type": "websocket.send",
            "text": "Hello, World!",
        }

    @pytest.mark.asyncio
    async def test_send_bytes(self):
        """Test sending binary data."""
        scope: Scope = {
            "type": "websocket",
            "path": "/ws",
        }
        
        sent_messages = []
        
        async def receive():
            pass
        
        async def send(message):
            sent_messages.append(message)
        
        ws = WebSocket(scope, receive, send)
        
        # Must accept first
        await ws.accept()
        sent_messages.clear()
        
        # Send bytes
        data = b"Binary data"
        await ws.send(data)
        
        assert len(sent_messages) == 1
        assert sent_messages[0] == {
            "type": "websocket.send",
            "bytes": data,
        }

    @pytest.mark.asyncio
    async def test_send_without_accept(self):
        """Test sending data without accepting connection."""
        scope: Scope = {
            "type": "websocket",
            "path": "/ws",
        }
        
        async def receive():
            pass
        
        async def send(message):
            pass
        
        ws = WebSocket(scope, receive, send)
        
        # Should raise error if not accepted
        with pytest.raises(RuntimeError, match="WebSocket not accepted"):
            await ws.send("Hello")

    @pytest.mark.asyncio
    async def test_receive_text(self):
        """Test receiving text data."""
        scope: Scope = {
            "type": "websocket",
            "path": "/ws",
        }
        
        messages = [
            {"type": "websocket.receive", "text": "Hello"},
            {"type": "websocket.receive", "text": "World"},
        ]
        message_index = 0
        
        async def receive():
            nonlocal message_index
            msg = messages[message_index]
            message_index += 1
            return msg
        
        async def send(message):
            pass
        
        ws = WebSocket(scope, receive, send)
        await ws.accept()
        
        # Receive messages
        msg1 = await ws.receive()
        assert msg1 == "Hello"
        
        msg2 = await ws.receive()
        assert msg2 == "World"

    @pytest.mark.asyncio
    async def test_receive_bytes(self):
        """Test receiving binary data."""
        scope: Scope = {
            "type": "websocket",
            "path": "/ws",
        }
        
        data = b"Binary message"
        
        async def receive():
            return {"type": "websocket.receive", "bytes": data}
        
        async def send(message):
            pass
        
        ws = WebSocket(scope, receive, send)
        await ws.accept()
        
        msg = await ws.receive()
        assert msg == data

    @pytest.mark.asyncio
    async def test_receive_disconnect(self):
        """Test handling disconnect during receive."""
        scope: Scope = {
            "type": "websocket",
            "path": "/ws",
        }
        
        async def receive():
            return {"type": "websocket.disconnect", "code": 1001}
        
        async def send(message):
            pass
        
        ws = WebSocket(scope, receive, send)
        await ws.accept()
        
        # Should raise ConnectionError on disconnect
        with pytest.raises(ConnectionError, match="WebSocket disconnected"):
            await ws.receive()

    @pytest.mark.asyncio
    async def test_receive_without_accept(self):
        """Test receiving data without accepting connection."""
        scope: Scope = {
            "type": "websocket",
            "path": "/ws",
        }
        
        async def receive():
            return {"type": "websocket.receive", "text": "Hello"}
        
        async def send(message):
            pass
        
        ws = WebSocket(scope, receive, send)
        
        # Should raise error if not accepted
        with pytest.raises(RuntimeError, match="WebSocket not accepted"):
            await ws.receive()

    @pytest.mark.asyncio
    async def test_close(self):
        """Test closing WebSocket connection."""
        scope: Scope = {
            "type": "websocket",
            "path": "/ws",
        }
        
        sent_messages = []
        
        async def receive():
            pass
        
        async def send(message):
            sent_messages.append(message)
        
        ws = WebSocket(scope, receive, send)
        
        # Close with default code
        await ws.close()
        
        assert len(sent_messages) == 1
        assert sent_messages[0] == {
            "type": "websocket.close",
            "code": 1000,
            "reason": "",
        }

    @pytest.mark.asyncio
    async def test_close_with_code_and_reason(self):
        """Test closing WebSocket with custom code and reason."""
        scope: Scope = {
            "type": "websocket",
            "path": "/ws",
        }
        
        sent_messages = []
        
        async def receive():
            pass
        
        async def send(message):
            sent_messages.append(message)
        
        ws = WebSocket(scope, receive, send)
        
        # Close with custom code and reason
        await ws.close(1001, "Going away")
        
        assert sent_messages[0] == {
            "type": "websocket.close",
            "code": 1001,
            "reason": "Going away",
        }

    @pytest.mark.asyncio
    async def test_async_iteration(self):
        """Test async iteration over WebSocket messages."""
        scope: Scope = {
            "type": "websocket",
            "path": "/ws",
        }
        
        messages = [
            {"type": "websocket.receive", "text": "msg1"},
            {"type": "websocket.receive", "text": "msg2"},
            {"type": "websocket.receive", "bytes": b"msg3"},
            {"type": "websocket.disconnect", "code": 1000},
        ]
        message_index = 0
        
        async def receive():
            nonlocal message_index
            msg = messages[message_index]
            message_index += 1
            return msg
        
        async def send(message):
            pass
        
        ws = WebSocket(scope, receive, send)
        await ws.accept()
        
        # Collect messages via async iteration
        received = []
        async for msg in ws:
            received.append(msg)
        
        assert received == ["msg1", "msg2", b"msg3"]