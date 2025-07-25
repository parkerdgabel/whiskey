"""ASGI Request wrapper."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional
from urllib.parse import parse_qs

from .types import ASGIReceive, HTTPScope, Headers


class Request:
    """Wrapper for ASGI HTTP requests."""

    def __init__(self, scope: HTTPScope, receive: ASGIReceive):
        self._scope = scope
        self._receive = receive
        self._body: bytes | None = None
        self._json: Any = None
        self._form: dict[str, Any] | None = None
        self._query_params: dict[str, list[str]] | None = None

    @property
    def method(self) -> str:
        """HTTP method."""
        return self._scope["method"]

    @property
    def path(self) -> str:
        """Request path."""
        return self._scope["path"]

    @property
    def query_string(self) -> bytes:
        """Raw query string."""
        return self._scope.get("query_string", b"")

    @property
    def headers(self) -> Dict[str, str]:
        """Request headers as a dict."""
        if not hasattr(self, "_headers_dict"):
            self._headers_dict = {}
            for name, value in self._scope.get("headers", []):
                name_str = name.decode("latin-1").lower()
                value_str = value.decode("latin-1")
                self._headers_dict[name_str] = value_str
        return self._headers_dict

    @property
    def query_params(self) -> Dict[str, list[str]]:
        """Parsed query parameters."""
        if self._query_params is None:
            self._query_params = parse_qs(self.query_string.decode("utf-8"))
        return self._query_params

    def query_param(self, name: str, default: str | None = None) -> str | None:
        """Get a single query parameter value."""
        values = self.query_params.get(name)
        if values:
            return values[0]
        return default

    @property
    def content_type(self) -> str | None:
        """Content-Type header value."""
        return self.headers.get("content-type")

    @property
    def client(self) -> tuple[str, int] | None:
        """Client address."""
        return self._scope.get("client")

    @property
    def scheme(self) -> str:
        """URL scheme (http/https)."""
        return self._scope.get("scheme", "http")

    @property
    def url(self) -> str:
        """Full URL."""
        host = self.headers.get("host", "localhost")
        query = f"?{self.query_string.decode()}" if self.query_string else ""
        return f"{self.scheme}://{host}{self.path}{query}"

    async def body(self) -> bytes:
        """Get request body as bytes."""
        if self._body is None:
            body_parts = []
            while True:
                message = await self._receive()
                assert message["type"] == "http.request"
                
                body = message.get("body", b"")
                if body:
                    body_parts.append(body)
                
                if not message.get("more_body", False):
                    break
            
            self._body = b"".join(body_parts)
        
        return self._body

    async def text(self) -> str:
        """Get request body as text."""
        body = await self.body()
        encoding = "utf-8"
        
        # Try to get encoding from content-type
        content_type = self.content_type
        if content_type and "charset=" in content_type:
            encoding = content_type.split("charset=")[-1].split(";")[0].strip()
        
        return body.decode(encoding)

    async def json(self) -> Any:
        """Get request body as JSON."""
        if self._json is None:
            text = await self.text()
            self._json = json.loads(text) if text else None
        return self._json

    async def form(self) -> Dict[str, Any]:
        """Get form data (application/x-www-form-urlencoded)."""
        if self._form is None:
            body = await self.body()
            self._form = parse_qs(body.decode("utf-8"))
        return self._form

    def __repr__(self) -> str:
        return f"<Request {self.method} {self.path}>"