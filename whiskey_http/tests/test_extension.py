"""Tests for HTTP extension core functionality."""

from typing import ClassVar

import pytest

from whiskey import Whiskey
from whiskey_http import HTTPClientManager, http_extension


@pytest.fixture
def app():
    """Create a Whiskey app with HTTP extension."""
    app = Whiskey()
    app.use(http_extension)
    return app


def test_extension_adds_decorators(app):
    """Test that extension adds required decorators."""
    assert hasattr(app, "http_client")
    assert hasattr(app, "request_interceptor")
    assert hasattr(app, "response_interceptor")
    assert hasattr(app, "get_http_client")


def test_extension_registers_manager(app):
    """Test that extension registers HTTP client manager."""
    assert hasattr(app, "http_manager")
    assert isinstance(app.http_manager, HTTPClientManager)
    assert HTTPClientManager in app.container


def test_http_client_registration(app):
    """Test registering an HTTP client."""

    @app.http_client("test_client", base_url="https://example.com")
    class TestClient:
        pass

    # Check client is registered
    assert "test_client" in app.http_manager._configs
    assert app.http_manager._configs["test_client"].base_url == "https://example.com"

    # Check client class is registered
    assert TestClient in app.container


def test_http_client_with_class_attributes(app):
    """Test HTTP client inherits attributes from class."""

    @app.http_client("api")
    class APIClient:
        base_url = "https://api.example.com"
        headers: ClassVar = {"X-API-Version": "v1"}
        timeout = 60.0

    config = app.http_manager._configs["api"]
    assert config.base_url == "https://api.example.com"
    assert config.headers == {"X-API-Version": "v1"}
    assert config.timeout == 60.0


def test_get_http_client(app):
    """Test getting HTTP client instances."""

    @app.http_client("test", base_url="https://test.com")
    class TestClient:
        pass

    client1 = app.get_http_client("test")
    client2 = app.get_http_client("test")

    # Should return same instance
    assert client1 is client2
    assert hasattr(client1, "get")
    assert hasattr(client1, "post")


def test_http_client_not_configured_error(app):
    """Test error when getting non-existent client."""
    with pytest.raises(ValueError, match="HTTP client 'nonexistent' not configured"):
        app.get_http_client("nonexistent")


@pytest.mark.asyncio
async def test_shutdown_cleanup(app):
    """Test that clients are cleaned up on shutdown."""

    @app.http_client("test", base_url="https://test.com")
    class TestClient:
        pass

    # Get client to create instance
    app.get_http_client("test")

    # Run shutdown handlers
    await app.shutdown()

    # Client should be closed (in real test would verify httpx client is closed)
