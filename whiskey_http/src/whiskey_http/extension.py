"""HTTP client extension for Whiskey applications."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

import httpx

from whiskey import Container

from .types import (
    CircuitBreakerConfig,
    HTTPClient,
    HTTPClientConfig,
    RetryConfig,
)

if TYPE_CHECKING:
    from whiskey import Whiskey


@dataclass
class CircuitBreakerState:
    """State for circuit breaker pattern."""

    failure_count: int = 0
    last_failure_time: float | None = None
    state: str = "closed"  # "closed", "open", "half_open"
    half_open_calls: int = 0


class HTTPClientManager:
    """Manages HTTP client implementations and configurations."""

    def __init__(self, container: Container):
        self.container = container
        self._configs: dict[str, HTTPClientConfig] = {}
        self._client_classes: dict[str, type] = {}
        self._interceptors: dict[str, dict[str, list[Callable]]] = {}
        self._circuit_breakers: dict[str, CircuitBreakerState] = {}

    def register_config(self, config: HTTPClientConfig) -> None:
        """Register an HTTP client configuration."""
        self._configs[config.name] = config

        # Initialize interceptor lists
        if config.name not in self._interceptors:
            self._interceptors[config.name] = {"request": [], "response": []}

        # Initialize circuit breaker if configured
        if config.circuit_breaker:
            self._circuit_breakers[config.name] = CircuitBreakerState()

    def register_class(self, name: str, client_class: type) -> None:
        """Register a client class."""
        self._client_classes[name] = client_class

    def add_request_interceptor(self, client_name: str, interceptor: Callable) -> None:
        """Add a request interceptor for a client."""
        if client_name not in self._interceptors:
            self._interceptors[client_name] = {"request": [], "response": []}
        self._interceptors[client_name]["request"].append(interceptor)

    def add_response_interceptor(self, client_name: str, interceptor: Callable) -> None:
        """Add a response interceptor for a client."""
        if client_name not in self._interceptors:
            self._interceptors[client_name] = {"request": [], "response": []}
        self._interceptors[client_name]["response"].append(interceptor)

    def get_client(self, name: str) -> HTTPClient:
        """Get or create an HTTP client instance."""
        key = f"http.client.instance.{name}"

        if key not in self.container:
            if name not in self._configs:
                raise ValueError(f"HTTP client '{name}' not configured")

            # Create client instance
            config = self._configs[name]
            client = WhiskeyHTTPClient(config, self)
            self.container[key] = client

            # Also register by class if a class was registered
            if name in self._client_classes:
                self.container[self._client_classes[name]] = client

        return self.container[key]


class WhiskeyHTTPClient:
    """Default HTTP client implementation using httpx."""

    def __init__(self, config: HTTPClientConfig, manager: HTTPClientManager):
        self.config = config
        self.manager = manager

        # Create httpx client
        self._client = httpx.AsyncClient(
            base_url=config.base_url,
            headers=config.headers,
            timeout=config.timeout,
            verify=config.verify_ssl,
            follow_redirects=config.follow_redirects,
            auth=config.auth,
            cookies=config.cookies,
            params=config.params,
        )

    async def __aenter__(self):
        """Enter async context."""
        await self._client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context."""
        await self._client.__aexit__(exc_type, exc_val, exc_tb)

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
        """Make an HTTP request with interceptors and retry logic."""
        # Build request
        request = self._client.build_request(
            method=method,
            url=url,
            params=params,
            headers=headers,
            json=json,
            data=data,
            files=files,
            timeout=timeout,
            **kwargs,
        )

        # Apply request interceptors
        interceptors = self.manager._interceptors.get(self.config.name, {}).get("request", [])
        for interceptor in interceptors:
            if asyncio.iscoroutinefunction(interceptor):
                request = await interceptor(request)
            else:
                request = interceptor(request)

        # Check circuit breaker
        if self.config.circuit_breaker:
            breaker = self.manager._circuit_breakers[self.config.name]
            if not self._can_make_request(breaker):
                raise httpx.HTTPError("Circuit breaker is open")

        # Execute request with retry logic
        response = await self._execute_with_retry(request)

        # Apply response interceptors
        response_interceptors = self.manager._interceptors.get(self.config.name, {}).get(
            "response", []
        )
        for interceptor in response_interceptors:
            if asyncio.iscoroutinefunction(interceptor):
                response = await interceptor(response)
            else:
                response = interceptor(response)

        return response

    async def _execute_with_retry(self, request: httpx.Request) -> httpx.Response:
        """Execute request with retry logic."""
        retry_config = self.config.retry
        if not retry_config:
            return await self._execute_request(request)

        last_exception = None
        for attempt in range(retry_config.attempts):
            try:
                response = await self._execute_request(request)

                # Check if we should retry based on status code
                if (
                    response.status_code in retry_config.on_status
                    and attempt < retry_config.attempts - 1
                ):
                    await self._wait_before_retry(attempt, retry_config)
                    continue

                return response

            except Exception as e:
                last_exception = e

                # Check if we should retry based on exception type
                should_retry = any(
                    isinstance(e, exc_type) for exc_type in retry_config.on_exception
                )

                if should_retry and attempt < retry_config.attempts - 1:
                    await self._wait_before_retry(attempt, retry_config)
                    continue

                raise

        # All retries exhausted
        if last_exception:
            raise last_exception
        else:
            raise httpx.HTTPError(f"Request failed after {retry_config.attempts} attempts")

    async def _execute_request(self, request: httpx.Request) -> httpx.Response:
        """Execute a single request and update circuit breaker state."""
        try:
            response = await self._client.send(request)

            # Update circuit breaker on success
            if self.config.circuit_breaker:
                self._on_request_success()

            response.raise_for_status()
            return response

        except Exception:
            # Update circuit breaker on failure
            if self.config.circuit_breaker:
                self._on_request_failure()
            raise

    async def _wait_before_retry(self, attempt: int, retry_config: RetryConfig) -> None:
        """Calculate and wait before retry."""
        if retry_config.backoff == "exponential":
            delay = min(retry_config.initial_delay * (2**attempt), retry_config.max_delay)
        elif retry_config.backoff == "linear":
            delay = min(retry_config.initial_delay * (attempt + 1), retry_config.max_delay)
        else:  # constant
            delay = retry_config.initial_delay

        await asyncio.sleep(delay)

    def _can_make_request(self, breaker: CircuitBreakerState) -> bool:
        """Check if request can be made based on circuit breaker state."""
        if breaker.state == "closed":
            return True

        if breaker.state == "open":
            # Check if we should transition to half-open
            if (
                time.time() - breaker.last_failure_time
            ) > self.config.circuit_breaker.recovery_timeout:
                breaker.state = "half_open"
                breaker.half_open_calls = 0
                return True
            return False

        # Half-open state
        if breaker.half_open_calls < self.config.circuit_breaker.half_open_max_calls:
            breaker.half_open_calls += 1
            return True
        return False

    def _on_request_success(self) -> None:
        """Handle successful request for circuit breaker."""
        breaker = self.manager._circuit_breakers[self.config.name]

        if breaker.state == "half_open":
            # Transition back to closed
            breaker.state = "closed"
            breaker.failure_count = 0
            breaker.last_failure_time = None

    def _on_request_failure(self) -> None:
        """Handle failed request for circuit breaker."""
        breaker = self.manager._circuit_breakers[self.config.name]

        breaker.failure_count += 1
        breaker.last_failure_time = time.time()

        if breaker.failure_count >= self.config.circuit_breaker.failure_threshold:
            breaker.state = "open"

    # Convenience methods
    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        """Make a GET request."""
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        """Make a POST request."""
        return await self.request("POST", url, **kwargs)

    async def put(self, url: str, **kwargs: Any) -> httpx.Response:
        """Make a PUT request."""
        return await self.request("PUT", url, **kwargs)

    async def patch(self, url: str, **kwargs: Any) -> httpx.Response:
        """Make a PATCH request."""
        return await self.request("PATCH", url, **kwargs)

    async def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        """Make a DELETE request."""
        return await self.request("DELETE", url, **kwargs)

    async def head(self, url: str, **kwargs: Any) -> httpx.Response:
        """Make a HEAD request."""
        return await self.request("HEAD", url, **kwargs)

    async def options(self, url: str, **kwargs: Any) -> httpx.Response:
        """Make an OPTIONS request."""
        return await self.request("OPTIONS", url, **kwargs)


def http_extension(app: Whiskey) -> None:
    """HTTP client extension that adds declarative HTTP client capabilities.

    This extension provides:
    - @app.http_client() decorator for registering HTTP clients
    - Request/response interceptors with @app.request_interceptor and @app.response_interceptor
    - Automatic retry and circuit breaker patterns
    - Integration with Whiskey's DI system

    Example:
        app = Whiskey()
        app.use(http_extension)

        @app.http_client("api", base_url="https://api.example.com")
        class APIClient:
            pass

        @app.component
        class Service:
            def __init__(self, api: APIClient):
                self.api = api

            async def get_data(self):
                response = await self.api.get("/data")
                return response.json()
    """
    # Create HTTP client manager
    manager = HTTPClientManager(app.container)

    # Store manager in app and container
    app.http_manager = manager
    app.container[HTTPClientManager] = manager

    # Current client being configured (for interceptor decorators)
    current_client_name = None

    def http_client(
        name: str,
        base_url: str | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
        verify_ssl: bool = True,
        follow_redirects: bool = True,
        retry: dict[str, Any] | RetryConfig | None = None,
        circuit_breaker: dict[str, Any] | CircuitBreakerConfig | None = None,
        auth: httpx.Auth | Callable | None = None,
        cookies: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ):
        """Decorator to register an HTTP client.

        Args:
            name: Name of the client (used for injection)
            base_url: Base URL for all requests
            headers: Default headers
            timeout: Request timeout in seconds
            verify_ssl: Whether to verify SSL certificates
            follow_redirects: Whether to follow redirects
            retry: Retry configuration
            circuit_breaker: Circuit breaker configuration
            auth: Authentication handler
            cookies: Default cookies
            params: Default query parameters

        Example:
            @app.http_client("github", base_url="https://api.github.com")
            class GitHubClient:
                pass
        """

        def decorator(cls: type) -> type:
            nonlocal current_client_name
            current_client_name = name

            # Convert dict configs to proper types
            retry_config = RetryConfig(**retry) if isinstance(retry, dict) else retry

            if isinstance(circuit_breaker, dict):
                cb_config = CircuitBreakerConfig(**circuit_breaker)
            else:
                cb_config = circuit_breaker

            # Create configuration
            config = HTTPClientConfig(
                name=name,
                base_url=base_url or getattr(cls, "base_url", None),
                headers=headers or getattr(cls, "headers", None),
                timeout=timeout if timeout != 30.0 else getattr(cls, "timeout", 30.0),
                verify_ssl=verify_ssl if not hasattr(cls, "verify_ssl") else cls.verify_ssl,
                follow_redirects=follow_redirects
                if not hasattr(cls, "follow_redirects")
                else cls.follow_redirects,
                retry=retry_config or getattr(cls, "retry", None),
                circuit_breaker=cb_config or getattr(cls, "circuit_breaker", None),
                auth=auth or getattr(cls, "auth", None),
                cookies=cookies or getattr(cls, "cookies", None),
                params=params or getattr(cls, "params", None),
            )

            # Register configuration and class
            manager.register_config(config)
            manager.register_class(name, cls)

            # Register in container for injection
            app.container[cls] = lambda: manager.get_client(name)

            # Process any interceptor decorators that were applied
            for attr_name in dir(cls):
                attr = getattr(cls, attr_name)
                if hasattr(attr, "_is_request_interceptor"):
                    manager.add_request_interceptor(name, attr)
                elif hasattr(attr, "_is_response_interceptor"):
                    manager.add_response_interceptor(name, attr)

            current_client_name = None
            return cls

        return decorator

    def request_interceptor(func: Callable) -> Callable:
        """Decorator to mark a method as a request interceptor.

        The interceptor receives an httpx.Request and should return an httpx.Request.

        Example:
            @app.http_client("api")
            class APIClient:
                @app.request_interceptor
                async def add_auth(self, request):
                    request.headers["Authorization"] = f"Bearer {self.token}"
                    return request
        """
        func._is_request_interceptor = True

        # If we're currently configuring a client, add immediately
        if current_client_name:
            manager.add_request_interceptor(current_client_name, func)

        return func

    def response_interceptor(func: Callable) -> Callable:
        """Decorator to mark a method as a response interceptor.

        The interceptor receives an httpx.Response and should return an httpx.Response.

        Example:
            @app.http_client("api")
            class APIClient:
                @app.response_interceptor
                async def log_response(self, response):
                    logger.info(f"{response.status_code} - {response.url}")
                    return response
        """
        func._is_response_interceptor = True

        # If we're currently configuring a client, add immediately
        if current_client_name:
            manager.add_response_interceptor(current_client_name, func)

        return func

    # Add decorators to app
    app.add_decorator("http_client", http_client)
    app.add_decorator("request_interceptor", request_interceptor)
    app.add_decorator("response_interceptor", response_interceptor)

    # Helper method to get client
    def get_http_client(name: str) -> HTTPClient:
        """Get a configured HTTP client by name."""
        return manager.get_client(name)

    app.get_http_client = get_http_client

    # Register cleanup
    @app.on_shutdown
    async def cleanup_http_clients():
        """Close all HTTP clients on shutdown."""
        for name, _config in manager._configs.items():
            key = f"http.client.instance.{name}"
            if key in app.container:
                client = app.container[key]
                if hasattr(client, "_client"):
                    await client._client.aclose()
