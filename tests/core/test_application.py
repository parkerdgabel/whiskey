"""Tests for the Application class and its decorators.

This module tests the Application class which provides decorator-based
service registration and lifecycle management.
"""

import asyncio
import os
import pytest
from typing import Any, Callable
from unittest.mock import Mock, patch

from whiskey.core.application import (
    Application, 
    ConditionalDecoratorHelper,
    set_current_app,
    get_current_app,
    create_default_app
)
from whiskey.core.container import Container
from whiskey.core.registry import Scope
from whiskey.core.errors import ConfigurationError


# Test services for testing
class TestService:
    def __init__(self):
        self.value = "test"


class DatabaseService:
    def __init__(self, connection_string: str = "default"):
        self.connection_string = connection_string


class CacheService:
    def __init__(self):
        self.cache = {}


def create_test_service():
    """Factory function for testing."""
    return TestService()


class TestApplication:
    """Test Application class core functionality."""
    
    def test_application_creation(self):
        """Test basic Application creation."""
        app = Application()
        
        assert app.container is not None
        assert isinstance(app.container, Container)
        assert app._is_running is False
        assert app._startup_callbacks == []
        assert app._shutdown_callbacks == []
        assert app._error_handlers == {}
        assert app._middleware == []
    
    def test_application_with_container(self):
        """Test Application with provided container."""
        container = Container()
        app = Application(container)
        
        assert app.container is container
    
    def test_application_with_container_callbacks(self):
        """Test Application inherits callbacks from container."""
        container = Container()
        
        # Add callbacks to container (as would be done by ApplicationBuilder)
        container._startup_callbacks = [lambda: None]
        container._shutdown_callbacks = [lambda: None]
        container._error_handlers = {ValueError: lambda e: None}
        container._middleware = [lambda: None]
        
        app = Application(container)
        
        assert len(app._startup_callbacks) == 1
        assert len(app._shutdown_callbacks) == 1
        assert ValueError in app._error_handlers
        assert len(app._middleware) == 1
    
    def test_builder_class_method(self):
        """Test Application.builder() class method."""
        from whiskey.core.builder import ApplicationBuilder
        
        builder = Application.builder()
        assert isinstance(builder, ApplicationBuilder)
    
    def test_create_class_method(self):
        """Test Application.create() alias method."""
        from whiskey.core.builder import ApplicationBuilder
        
        builder = Application.create()
        assert isinstance(builder, ApplicationBuilder)
    
    async def test_startup_lifecycle(self):
        """Test application startup lifecycle."""
        app = Application()
        startup_called = False
        
        def startup_callback():
            nonlocal startup_called
            startup_called = True
        
        app._startup_callbacks.append(startup_callback)
        
        assert not app._is_running
        await app.startup()
        
        assert app._is_running
        assert startup_called
        
        # Calling startup again should not re-run callbacks
        startup_called = False
        await app.startup()
        assert not startup_called  # Should not be called again
    
    async def test_startup_with_async_callback(self):
        """Test startup with async callback."""
        app = Application()
        async_called = False
        
        async def async_startup():
            nonlocal async_called
            async_called = True
        
        app._startup_callbacks.append(async_startup)
        await app.startup()
        
        assert async_called
    
    async def test_shutdown_lifecycle(self):
        """Test application shutdown lifecycle."""
        app = Application()
        shutdown_called = False
        
        def shutdown_callback():
            nonlocal shutdown_called
            shutdown_called = True
        
        app._shutdown_callbacks.append(shutdown_callback)
        app._is_running = True
        
        await app.shutdown()
        
        assert not app._is_running
        assert shutdown_called
        
        # Calling shutdown again should not re-run callbacks
        shutdown_called = False
        await app.shutdown()
        assert not shutdown_called
    
    async def test_shutdown_with_async_callback(self):
        """Test shutdown with async callback."""
        app = Application()
        async_called = False
        
        async def async_shutdown():
            nonlocal async_called
            async_called = True
        
        app._shutdown_callbacks.append(async_shutdown)
        app._is_running = True
        
        await app.shutdown()
        assert async_called
    
    async def test_shutdown_callback_order(self):
        """Test shutdown callbacks run in reverse order."""
        app = Application()
        call_order = []
        
        def callback1():
            call_order.append(1)
        
        def callback2():
            call_order.append(2)
        
        def callback3():
            call_order.append(3)
        
        app._shutdown_callbacks.extend([callback1, callback2, callback3])
        app._is_running = True
        
        await app.shutdown()
        
        # Should be called in reverse order
        assert call_order == [3, 2, 1]
    
    async def test_shutdown_error_handling(self):
        """Test shutdown handles callback errors gracefully."""
        app = Application()
        good_callback_called = False
        
        def failing_callback():
            raise RuntimeError("Callback failed")
        
        def good_callback():
            nonlocal good_callback_called
            good_callback_called = True
        
        app._shutdown_callbacks.extend([good_callback, failing_callback])
        app._is_running = True
        
        # Should not raise exception
        await app.shutdown()
        
        # Good callback should still be called despite error
        assert good_callback_called
    
    async def test_container_cache_cleared_on_shutdown(self):
        """Test container caches are cleared on shutdown."""
        app = Application()
        app._is_running = True
        
        # Mock the clear_caches method
        app.container.clear_caches = Mock()
        
        await app.shutdown()
        
        app.container.clear_caches.assert_called_once()
    
    async def test_async_context_manager(self):
        """Test Application as async context manager."""
        app = Application()
        startup_called = False
        shutdown_called = False
        
        def startup_callback():
            nonlocal startup_called
            startup_called = True
        
        def shutdown_callback():
            nonlocal shutdown_called
            shutdown_called = True
        
        app._startup_callbacks.append(startup_callback)
        app._shutdown_callbacks.append(shutdown_callback)
        
        async with app as context_app:
            assert context_app is app
            assert app._is_running
            assert startup_called
            assert not shutdown_called
        
        assert not app._is_running
        assert shutdown_called