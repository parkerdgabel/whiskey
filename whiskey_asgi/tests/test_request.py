"""Tests for Request class."""

import asyncio
import json

import pytest

from whiskey_asgi.extension import Request
from whiskey_asgi.types import Scope


class TestRequest:
    """Test Request functionality."""

    def test_basic_properties(self):
        """Test basic request properties."""
        scope: Scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "query_string": b"foo=bar&baz=qux",
            "headers": [
                [b"host", b"example.com"],
                [b"user-agent", b"TestAgent/1.0"],
                [b"content-type", b"application/json"],
            ],
        }
        
        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}
        
        request = Request(scope, receive)
        
        assert request.method == "GET"
        assert request.path == "/test"
        assert request.query_string == b"foo=bar&baz=qux"
        
        # Headers should be lowercase
        headers = request.headers
        assert headers["host"] == "example.com"
        assert headers["user-agent"] == "TestAgent/1.0"
        assert headers["content-type"] == "application/json"

    def test_route_params(self):
        """Test route parameter storage."""
        scope: Scope = {
            "type": "http",
            "method": "GET",
            "path": "/users/123",
        }
        
        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}
        
        request = Request(scope, receive)
        request.route_params = {"id": "123"}
        
        assert request.route_params == {"id": "123"}

    @pytest.mark.asyncio
    async def test_body_simple(self):
        """Test reading simple request body."""
        scope: Scope = {
            "type": "http",
            "method": "POST",
            "path": "/test",
        }
        
        body_content = b"Hello, World!"
        
        async def receive():
            return {"type": "http.request", "body": body_content, "more_body": False}
        
        request = Request(scope, receive)
        body = await request.body()
        
        assert body == body_content
        
        # Should cache the body
        body2 = await request.body()
        assert body2 == body_content

    @pytest.mark.asyncio
    async def test_body_chunked(self):
        """Test reading chunked request body."""
        scope: Scope = {
            "type": "http",
            "method": "POST",
            "path": "/test",
        }
        
        chunks = [b"Hello", b", ", b"World", b"!"]
        chunk_index = 0
        
        async def receive():
            nonlocal chunk_index
            if chunk_index < len(chunks):
                chunk = chunks[chunk_index]
                chunk_index += 1
                return {
                    "type": "http.request",
                    "body": chunk,
                    "more_body": chunk_index < len(chunks)
                }
        
        request = Request(scope, receive)
        body = await request.body()
        
        assert body == b"Hello, World!"

    @pytest.mark.asyncio
    async def test_json_parsing(self):
        """Test JSON body parsing."""
        scope: Scope = {
            "type": "http",
            "method": "POST",
            "path": "/test",
        }
        
        data = {"name": "Test", "value": 42, "active": True}
        body_content = json.dumps(data).encode("utf-8")
        
        async def receive():
            return {"type": "http.request", "body": body_content, "more_body": False}
        
        request = Request(scope, receive)
        parsed = await request.json()
        
        assert parsed == data
        
        # Should cache the result
        parsed2 = await request.json()
        assert parsed2 == data

    @pytest.mark.asyncio
    async def test_json_empty_body(self):
        """Test JSON parsing with empty body."""
        scope: Scope = {
            "type": "http",
            "method": "POST",
            "path": "/test",
        }
        
        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}
        
        request = Request(scope, receive)
        parsed = await request.json()
        
        assert parsed is None

    @pytest.mark.asyncio
    async def test_form_parsing(self):
        """Test form data parsing."""
        scope: Scope = {
            "type": "http",
            "method": "POST",
            "path": "/test",
        }
        
        form_data = "name=John+Doe&age=30&active=true"
        body_content = form_data.encode("utf-8")
        
        async def receive():
            return {"type": "http.request", "body": body_content, "more_body": False}
        
        request = Request(scope, receive)
        form = await request.form()
        
        assert form == {
            "name": "John+Doe",  # Note: simple parsing doesn't decode
            "age": "30",
            "active": "true"
        }
        
        # Should cache the result
        form2 = await request.form()
        assert form2 == form

    @pytest.mark.asyncio
    async def test_form_empty_body(self):
        """Test form parsing with empty body."""
        scope: Scope = {
            "type": "http",
            "method": "POST",
            "path": "/test",
        }
        
        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}
        
        request = Request(scope, receive)
        form = await request.form()
        
        assert form == {}

    def test_cookies_parsing(self):
        """Test cookie parsing from headers."""
        scope: Scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "headers": [
                [b"cookie", b"session=abc123; user_id=42; preferences=dark_mode"],
            ],
        }
        
        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}
        
        request = Request(scope, receive)
        cookies = request.cookies
        
        assert cookies == {
            "session": "abc123",
            "user_id": "42",
            "preferences": "dark_mode"
        }

    def test_cookies_no_header(self):
        """Test cookie parsing when no cookie header present."""
        scope: Scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "headers": [],
        }
        
        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}
        
        request = Request(scope, receive)
        cookies = request.cookies
        
        assert cookies == {}

    def test_missing_optional_fields(self):
        """Test handling of missing optional scope fields."""
        scope: Scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            # No query_string or headers
        }
        
        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}
        
        request = Request(scope, receive)
        
        assert request.query_string == b""
        assert request.headers == {}