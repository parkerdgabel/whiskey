"""Type definitions for whiskey-http extension.

This module defines all the type annotations, protocols, and configuration
classes used by the whiskey-http extension. It provides a clear contract
for HTTP client implementations and their configurations.

The module uses Pydantic for configuration validation and Python protocols
for defining interfaces, ensuring type safety and runtime validation.

Classes:
    RetryConfig: Configuration for retry behavior
    CircuitBreakerConfig: Configuration for circuit breaker pattern
    HTTPClientConfig: Main configuration for HTTP clients
    HTTPClient: Protocol defining the HTTP client interface

Type Aliases:
    RequestInterceptor: Type for request interceptor functions
    ResponseInterceptor: Type for response interceptor functions
    AsyncRequestInterceptor: Type for async request interceptors
    AsyncResponseInterceptor: Type for async response interceptors

Example:
    Creating configurations for an HTTP client::

        from whiskey_http.types import HTTPClientConfig, RetryConfig

        config = HTTPClientConfig(
            name="api",
            base_url="https://api.example.com",
            headers={"Authorization": "Bearer token"},
            retry=RetryConfig(
                attempts=3,
                backoff="exponential",
                on_status=[500, 502, 503]
            )
        )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, Union, runtime_checkable

import httpx
from pydantic import BaseModel


class RetryConfig(BaseModel):
    """Configuration for retry behavior.

    Defines how HTTP requests should be retried on failure. Supports
    different backoff strategies and can retry on specific status codes
    or exception types.

    Attributes:
        attempts: Maximum number of retry attempts (default: 3)
        backoff: Backoff strategy - "exponential", "linear", or "constant" (default: "exponential")
        initial_delay: Initial delay in seconds before first retry (default: 1.0)
        max_delay: Maximum delay between retries in seconds (default: 60.0)
        on_status: HTTP status codes that trigger retry (default: [500, 502, 503, 504])
        on_exception: Exception types that trigger retry (default: [ConnectError, TimeoutException])

    Example:
        Configure retry with exponential backoff::

            retry = RetryConfig(
                attempts=5,
                backoff="exponential",
                initial_delay=0.5,
                max_delay=30.0,
                on_status=[429, 500, 502, 503, 504],  # Include rate limit
                on_exception=[httpx.ConnectError, httpx.TimeoutException]
            )

        Configure retry with linear backoff for specific errors::

            retry = RetryConfig(
                attempts=3,
                backoff="linear",
                initial_delay=2.0,
                on_status=[503],  # Only retry on service unavailable
            )
    """

    attempts: int = 3
    backoff: str = "exponential"  # "exponential", "linear", "constant"
    initial_delay: float = 1.0
    max_delay: float = 60.0
    on_status: list[int] = field(default_factory=lambda: [500, 502, 503, 504])
    on_exception: list[type[Exception]] = field(
        default_factory=lambda: [httpx.ConnectError, httpx.TimeoutException]
    )


class CircuitBreakerConfig(BaseModel):
    """Configuration for circuit breaker pattern.

    The circuit breaker pattern prevents cascading failures by monitoring
    request failures and temporarily blocking requests when a threshold
    is exceeded. This protects both the client and server from overload.

    Attributes:
        failure_threshold: Number of failures before opening circuit (default: 5)
        recovery_timeout: Seconds to wait before testing recovery (default: 60.0)
        expected_exception: Exception type that triggers the breaker (default: HTTPStatusError)
        half_open_max_calls: Max test calls in half-open state (default: 3)

    Example:
        Configure a circuit breaker for an API client::

            circuit_breaker = CircuitBreakerConfig(
                failure_threshold=3,      # Open after 3 failures
                recovery_timeout=30.0,    # Try recovery after 30s
                expected_exception=httpx.HTTPStatusError,
                half_open_max_calls=1     # One test call during recovery
            )

        Configure for network errors only::

            circuit_breaker = CircuitBreakerConfig(
                failure_threshold=5,
                recovery_timeout=120.0,
                expected_exception=httpx.ConnectError  # Only network failures
            )

    Notes:
        The circuit breaker helps implement the "fail fast" principle,
        preventing resource exhaustion and improving system resilience.
    """

    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    expected_exception: type[Exception] | None = httpx.HTTPStatusError
    half_open_max_calls: int = 3


@dataclass
class HTTPClientConfig:
    """Configuration for an HTTP client.

    Complete configuration for an HTTP client including connection settings,
    default headers, authentication, and resilience patterns. This class
    serves as the primary way to configure client behavior.

    Attributes:
        name: Unique identifier for the client (required)
        base_url: Base URL for all requests (e.g., "https://api.example.com")
        headers: Default headers to include in all requests
        timeout: Request timeout in seconds (default: 30.0)
        verify_ssl: Whether to verify SSL certificates (default: True)
        follow_redirects: Whether to follow redirects (default: True)
        retry: Retry configuration for failed requests
        circuit_breaker: Circuit breaker configuration
        auth: Authentication handler (httpx.Auth or callable)
        cookies: Default cookies to include
        params: Default query parameters

    Example:
        Create a fully configured HTTP client::

            config = HTTPClientConfig(
                name="github",
                base_url="https://api.github.com",
                headers={
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "MyApp/1.0"
                },
                timeout=60.0,
                retry=RetryConfig(attempts=3),
                auth=BearerAuth("ghp_xxxxxxxxxxxx")
            )

        Minimal configuration::

            config = HTTPClientConfig(
                name="simple",
                base_url="https://httpbin.org"
            )

    Notes:
        All settings except 'name' are optional and have sensible defaults.
        The configuration is immutable once created.
    """

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
"""Type for synchronous request interceptor functions."""

ResponseInterceptor = Callable[[httpx.Response], httpx.Response]
"""Type for synchronous response interceptor functions."""

AsyncRequestInterceptor = Callable[[httpx.Request], Union[httpx.Request, httpx.Request]]
"""Type for asynchronous request interceptor functions."""

AsyncResponseInterceptor = Callable[[httpx.Response], Union[httpx.Response, httpx.Response]]
"""Type for asynchronous response interceptor functions."""


@runtime_checkable
class HTTPClient(Protocol):
    """Protocol for HTTP client implementations.

    This protocol defines the interface that all HTTP client implementations
    must follow. It ensures consistency across different client implementations
    and enables type checking for dependency injection.

    The protocol requires all standard HTTP methods to be implemented as
    async methods, following modern Python async/await patterns.

    Example:
        Implementing a custom HTTP client::

            class CustomHTTPClient:
                async def request(self, method: str, url: str, **kwargs) -> httpx.Response:
                    # Custom implementation
                    pass

                async def get(self, url: str, **kwargs) -> httpx.Response:
                    return await self.request("GET", url, **kwargs)

                # ... implement other methods ...

        Type checking with the protocol::

            def process_client(client: HTTPClient) -> None:
                # Type checker ensures client has all required methods
                response = await client.get("/api/data")

    Notes:
        All methods must be async and return httpx.Response objects.
        The protocol is runtime checkable using isinstance().
    """

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
