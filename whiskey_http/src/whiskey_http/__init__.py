"""HTTP client extension for Whiskey applications.

The whiskey-http extension provides a declarative, feature-rich HTTP client
system for Whiskey applications. It enables easy registration of HTTP clients
with advanced features like retry logic, circuit breakers, and interceptors.

Key Features:
    - Declarative client registration with @app.http_client()
    - Automatic dependency injection integration
    - Request/response interceptors for cross-cutting concerns
    - Configurable retry with exponential/linear/constant backoff
    - Circuit breaker pattern for fault tolerance
    - Full async/await support
    - Type-safe with protocols and type hints

Quick Start:
    Basic usage example::

        from whiskey import Whiskey
        from whiskey_http import http_extension

        app = Whiskey()
        app.use(http_extension)

        @app.http_client("api", base_url="https://api.example.com")
        class APIClient:
            headers = {"X-API-Version": "v1"}

        @app.component
        class UserService:
            def __init__(self, api: APIClient):
                self.api = api

            async def get_users(self):
                response = await self.api.get("/users")
                return response.json()

Advanced Features:
    Configure retry and circuit breaker::

        @app.http_client(
            "resilient_api",
            base_url="https://api.example.com",
            retry={
                "attempts": 3,
                "backoff": "exponential",
                "on_status": [429, 500, 502, 503]
            },
            circuit_breaker={
                "failure_threshold": 5,
                "recovery_timeout": 60.0
            }
        )
        class ResilientAPIClient:
            pass

    Add interceptors::

        @app.http_client("api")
        class APIClient:
            @app.request_interceptor
            async def add_request_id(self, request):
                request.headers["X-Request-ID"] = generate_id()
                return request

            @app.response_interceptor
            async def log_response(self, response):
                logger.info(f"{response.status_code} - {response.url}")
                return response

See Also:
    - HTTPClientConfig: Configuration options for clients
    - RetryConfig: Retry behavior configuration
    - CircuitBreakerConfig: Circuit breaker configuration
    - HTTPClient: Protocol for client implementations
"""

from .extension import http_extension
from .types import (
    CircuitBreakerConfig,
    HTTPClient,
    HTTPClientConfig,
    RequestInterceptor,
    ResponseInterceptor,
    RetryConfig,
)

__all__ = [
    "CircuitBreakerConfig",
    "HTTPClient",
    "HTTPClientConfig",
    "RequestInterceptor",
    "ResponseInterceptor",
    "RetryConfig",
    "http_extension",
]
