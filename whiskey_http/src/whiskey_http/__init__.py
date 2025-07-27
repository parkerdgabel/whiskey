"""HTTP client extension for Whiskey applications."""

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
