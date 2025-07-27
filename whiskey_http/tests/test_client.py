"""Tests for HTTP client functionality."""

from unittest.mock import Mock, patch

import httpx
import pytest

from whiskey import Whiskey
from whiskey_http import http_extension


@pytest.fixture
def app():
    """Create a Whiskey app with HTTP extension."""
    app = Whiskey()
    app.use(http_extension)
    return app


@pytest.mark.asyncio
async def test_basic_http_methods(app):
    """Test basic HTTP methods work correctly."""

    @app.http_client("test", base_url="https://httpbin.org")
    class TestClient:
        pass

    client = app.get_http_client("test")

    # Mock the internal httpx client
    with patch.object(client._client, "send") as mock_send:
        mock_response = httpx.Response(200, json={"success": True})
        mock_send.return_value = mock_response

        # Test various HTTP methods
        await client.get("/test")
        assert mock_send.call_args[0][0].method == "GET"

        await client.post("/test", json={"data": "value"})
        assert mock_send.call_args[0][0].method == "POST"

        await client.put("/test")
        assert mock_send.call_args[0][0].method == "PUT"

        await client.delete("/test")
        assert mock_send.call_args[0][0].method == "DELETE"


@pytest.mark.asyncio
async def test_request_interceptor(app):
    """Test request interceptors are called."""
    interceptor_called = False

    @app.http_client("test", base_url="https://test.com")
    class TestClient:
        @app.request_interceptor
        def add_header(self, request):
            nonlocal interceptor_called
            interceptor_called = True
            request.headers["X-Test"] = "value"
            return request

    client = app.get_http_client("test")

    with patch.object(client._client, "send") as mock_send:
        mock_response = httpx.Response(200)
        mock_send.return_value = mock_response

        await client.get("/test")

        assert interceptor_called
        # Check header was added
        sent_request = mock_send.call_args[0][0]
        assert sent_request.headers.get("X-Test") == "value"


@pytest.mark.asyncio
async def test_response_interceptor(app):
    """Test response interceptors are called."""
    interceptor_called = False

    @app.http_client("test", base_url="https://test.com")
    class TestClient:
        @app.response_interceptor
        async def log_response(self, response):
            nonlocal interceptor_called
            interceptor_called = True
            return response

    client = app.get_http_client("test")

    with patch.object(client._client, "send") as mock_send:
        mock_response = httpx.Response(200)
        mock_send.return_value = mock_response

        response = await client.get("/test")

        assert interceptor_called
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_retry_on_status_code(app):
    """Test retry logic for status codes."""

    @app.http_client(
        "test",
        base_url="https://test.com",
        retry={"attempts": 3, "backoff": "constant", "initial_delay": 0.1, "on_status": [500]},
    )
    class TestClient:
        pass

    client = app.get_http_client("test")

    # Mock to return 500 twice, then 200
    call_count = 0

    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            response = httpx.Response(500)
            response.raise_for_status = Mock(
                side_effect=httpx.HTTPStatusError("", request=Mock(), response=response)
            )
            return response
        return httpx.Response(200)

    with patch.object(client._client, "send", side_effect=side_effect):
        response = await client.get("/test")
        assert response.status_code == 200
        assert call_count == 3  # Should have retried twice


@pytest.mark.asyncio
async def test_retry_on_exception(app):
    """Test retry logic for exceptions."""

    @app.http_client(
        "test",
        base_url="https://test.com",
        retry={
            "attempts": 2,
            "backoff": "constant",
            "initial_delay": 0.1,
            "on_exception": [httpx.ConnectError],
        },
    )
    class TestClient:
        pass

    client = app.get_http_client("test")

    # Mock to raise exception once, then succeed
    call_count = 0

    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise httpx.ConnectError("Connection failed")
        return httpx.Response(200)

    with patch.object(client._client, "send", side_effect=side_effect):
        response = await client.get("/test")
        assert response.status_code == 200
        assert call_count == 2


@pytest.mark.asyncio
async def test_circuit_breaker_opens(app):
    """Test circuit breaker opens after threshold."""

    @app.http_client(
        "test",
        base_url="https://test.com",
        circuit_breaker={"failure_threshold": 2, "recovery_timeout": 1.0},
    )
    class TestClient:
        pass

    client = app.get_http_client("test")

    # Mock to always fail
    def side_effect(*args, **kwargs):
        response = httpx.Response(500)
        response.raise_for_status = Mock(
            side_effect=httpx.HTTPStatusError("", request=Mock(), response=response)
        )
        return response

    with patch.object(client._client, "send", side_effect=side_effect):
        # First two requests should fail normally
        for _ in range(2):
            with pytest.raises(httpx.HTTPStatusError):
                await client.get("/test")

        # Third request should fail with circuit breaker open
        with pytest.raises(httpx.HTTPError, match="Circuit breaker is open"):
            await client.get("/test")


@pytest.mark.asyncio
async def test_dependency_injection(app):
    """Test HTTP clients can be injected."""

    @app.http_client("api", base_url="https://api.example.com")
    class APIClient:
        pass

    @app.component
    class Service:
        def __init__(self, api: APIClient):
            self.api = api

    # Resolve service
    service = await app.container.resolve(Service)
    assert service.api is not None
    assert hasattr(service.api, "get")
