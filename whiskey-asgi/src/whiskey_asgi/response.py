"""ASGI Response wrapper."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

from .types import ASGISend, Headers


class Response:
    """Wrapper for ASGI HTTP responses."""

    def __init__(self, send: ASGISend):
        self._send = send
        self._status: int = 200
        self._headers: Dict[str, str] = {}
        self._body: bytes = b""
        self.started = False
        self.complete = False

    @property
    def status(self) -> int:
        """Response status code."""
        return self._status

    @status.setter
    def status(self, value: int) -> None:
        """Set response status code."""
        if self.started:
            raise RuntimeError("Cannot change status after response started")
        self._status = value

    def header(self, name: str, value: str) -> None:
        """Set a response header."""
        if self.started:
            raise RuntimeError("Cannot set headers after response started")
        self._headers[name.lower()] = value

    def headers(self, headers: Dict[str, str]) -> None:
        """Set multiple response headers."""
        for name, value in headers.items():
            self.header(name, value)

    async def _start_response(self) -> None:
        """Send the response start event."""
        if self.started:
            return

        # Convert headers to ASGI format
        headers: Headers = []
        for name, value in self._headers.items():
            headers.append((name.encode("latin-1"), value.encode("latin-1")))

        await self._send({
            "type": "http.response.start",
            "status": self._status,
            "headers": headers,
        })
        self.started = True

    async def write(self, data: bytes) -> None:
        """Write bytes to the response body."""
        if self.complete:
            raise RuntimeError("Response already complete")

        await self._start_response()
        
        if data:
            await self._send({
                "type": "http.response.body",
                "body": data,
                "more_body": True,
            })

    async def end(self, data: bytes = b"") -> None:
        """End the response."""
        if self.complete:
            return

        await self._start_response()
        
        await self._send({
            "type": "http.response.body",
            "body": data,
            "more_body": False,
        })
        self.complete = True

    async def send(self, data: bytes | str) -> None:
        """Send the complete response."""
        if isinstance(data, str):
            data = data.encode("utf-8")
            if "content-type" not in self._headers:
                self.header("content-type", "text/plain; charset=utf-8")
        
        self._body = data
        await self.end(data)

    async def text(self, text: str, status: int = 200) -> None:
        """Send a text response."""
        self.status = status
        self.header("content-type", "text/plain; charset=utf-8")
        await self.send(text)

    async def html(self, html: str, status: int = 200) -> None:
        """Send an HTML response."""
        self.status = status
        self.header("content-type", "text/html; charset=utf-8")
        await self.send(html)

    async def json(self, data: Any, status: int = 200) -> None:
        """Send a JSON response."""
        self.status = status
        self.header("content-type", "application/json")
        json_str = json.dumps(data, ensure_ascii=False)
        await self.send(json_str)

    async def redirect(self, url: str, status: int = 302) -> None:
        """Send a redirect response."""
        self.status = status
        self.header("location", url)
        await self.send(b"")

    async def send_error(self, status: int, message: str) -> None:
        """Send an error response."""
        self.status = status
        self.header("content-type", "text/plain; charset=utf-8")
        await self.send(message)

    def __repr__(self) -> str:
        return f"<Response {self._status}>"