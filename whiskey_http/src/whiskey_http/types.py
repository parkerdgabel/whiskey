"""Type definitions for whiskey-http extension."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, Union, runtime_checkable

import httpx
from pydantic import BaseModel


class RetryConfig(BaseModel):
    """Configuration for retry behavior."""

    attempts: int = 3
    backoff: str = "exponential"  # "exponential", "linear", "constant"
    initial_delay: float = 1.0
    max_delay: float = 60.0
    on_status: list[int] = field(default_factory=lambda: [500, 502, 503, 504])
    on_exception: list[type[Exception]] = field(
        default_factory=lambda: [httpx.ConnectError, httpx.TimeoutException]
    )


class CircuitBreakerConfig(BaseModel):
    """Configuration for circuit breaker pattern."""

    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    expected_exception: type[Exception] | None = httpx.HTTPStatusError
    half_open_max_calls: int = 3


@dataclass
class HTTPClientConfig:
    """Configuration for an HTTP client."""

    name: str
    base_url: str | None = None
    headers: dict[str, str] | None = None
    timeout: float = 30.0
    verify_ssl: bool = True
    follow_redirects: bool = True
    retry: RetryConfig | None = None
    circuit_breaker: CircuitBreakerConfig | None = None
    auth: httpx.Auth | Callable | None = None
    cookies: dict[str, str] | None = None
    params: dict[str, Any] | None = None


# Type aliases for interceptors
RequestInterceptor = Callable[[httpx.Request], httpx.Request]
ResponseInterceptor = Callable[[httpx.Response], httpx.Response]
AsyncRequestInterceptor = Callable[[httpx.Request], Union[httpx.Request, httpx.Request]]
AsyncResponseInterceptor = Callable[[httpx.Response], Union[httpx.Response, httpx.Response]]


@runtime_checkable
class HTTPClient(Protocol):
    """Protocol for HTTP client implementations."""

    async def request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        json: Any | None = None,
        data: Any | None = None,
        files: Any | None = None,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make an HTTP request."""
        ...

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        """Make a GET request."""
        ...

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        """Make a POST request."""
        ...

    async def put(self, url: str, **kwargs: Any) -> httpx.Response:
        """Make a PUT request."""
        ...

    async def patch(self, url: str, **kwargs: Any) -> httpx.Response:
        """Make a PATCH request."""
        ...

    async def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        """Make a DELETE request."""
        ...

    async def head(self, url: str, **kwargs: Any) -> httpx.Response:
        """Make a HEAD request."""
        ...

    async def options(self, url: str, **kwargs: Any) -> httpx.Response:
        """Make an OPTIONS request."""
        ...
