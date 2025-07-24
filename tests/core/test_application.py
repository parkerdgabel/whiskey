"""Tests for the Application IoC container."""

import asyncio
from typing import Any

import pytest

from whiskey.core.application import Application, ApplicationConfig
from whiskey.core.decorators import inject
from whiskey.core.events import Event, EventBus
from whiskey.core.types import Disposable, Initializable
from ..conftest import AsyncInitService, DisposableService, SimpleService


class TestApplicationConfig:
    """Test ApplicationConfig data class."""
    
    @pytest.mark.unit
    def test_default_config(self):
        """Test default configuration values."""
        config = ApplicationConfig()
        
        assert config.name == "WhiskeyApp"
        assert config.version == "0.1.0"
        assert config.debug is False
        assert config.auto_discover is True
        assert config.module_scan_paths == []
    
    @pytest.mark.unit
    def test_custom_config(self):
        """Test custom configuration."""
        config = ApplicationConfig(
            name="TestApp",
            version="2.0.0",
            debug=True,
            auto_discover=False,
            module_scan_paths=["src", "tests"]
        )
        
        assert config.name == "TestApp"
        assert config.version == "2.0.0"
        assert config.debug is True
        assert config.auto_discover is False
        assert config.module_scan_paths == ["src", "tests"]


class TestApplication:
    """Test Application container."""
    
    @pytest.mark.unit
    def test_application_creation(self):
        """Test creating application with default config."""
        app = Application()
        
        assert app.config.name == "WhiskeyApp"
        assert not app._running
        assert len(app._startup_hooks) == 0
        assert len(app._shutdown_hooks) == 0
    
    @pytest.mark.unit
    def test_application_with_config(self):
        """Test creating application with custom config."""
        config = ApplicationConfig(name="CustomApp", debug=True)
        app = Application(config)
        
        assert app.config.name == "CustomApp"
        assert app.config.debug is True
    
    @pytest.mark.unit
    async def test_core_services_registered(self):
        """Test core services are registered automatically."""
        app = Application()
        
        # Check Application itself is registered
        resolved_app = await app.container.resolve(Application)
        assert resolved_app is app
        
        # Check EventBus is registered
        event_bus = await app.container.resolve(EventBus)
        assert event_bus is app.event_bus
        
        # Check ApplicationConfig is registered
        config = await app.container.resolve(ApplicationConfig)
        assert config is app.config
    
    @pytest.mark.unit
    async def test_service_decorator(self):
        """Test @service decorator registers services."""
        app = Application()
        
        @app.service
        class TestService:
            value = "test"
        
        # Service should be registered
        service = await app.container.resolve(TestService)
        assert service.value == "test"
        
        # Should be singleton
        service2 = await app.container.resolve(TestService)
        assert service is service2
    
    @pytest.mark.unit
    async def test_service_with_lifecycle(self):
        """Test service with initialize and dispose methods."""
        app = Application()
        
        init_called = False
        dispose_called = False
        
        @app.service
        class LifecycleService(Initializable, Disposable):
            async def initialize(self):
                nonlocal init_called
                init_called = True
            
            async def dispose(self):
                nonlocal dispose_called
                dispose_called = True
        
        # Lifecycle methods called during startup/shutdown
        async with app.lifespan():
            assert init_called
            assert not dispose_called
        
        assert dispose_called
    
    @pytest.mark.unit
    async def test_lazy_service(self):
        """Test lazy service initialization."""
        app = Application()
        
        init_called = False
        
        @app.service(lazy=True)
        class LazyService(Initializable):
            async def initialize(self):
                nonlocal init_called
                init_called = True
        
        # Lazy service not initialized on startup
        async with app.lifespan():
            assert not init_called
    
    @pytest.mark.unit
    async def test_named_service(self):
        """Test named service registration."""
        app = Application()
        
        @app.service(name="primary")
        class NamedService:
            value = "primary"
        
        # Resolve by name
        service = await app.container.resolve(NamedService, name="primary")
        assert service.value == "primary"
    
    @pytest.mark.unit
    def test_startup_hook(self):
        """Test startup hook registration."""
        app = Application()
        
        async def startup_task():
            pass
        
        decorated = app.on_startup(startup_task)
        
        assert decorated is startup_task
        assert startup_task in app._startup_hooks
    
    @pytest.mark.unit
    def test_shutdown_hook(self):
        """Test shutdown hook registration."""
        app = Application()
        
        async def shutdown_task():
            pass
        
        decorated = app.on_shutdown(shutdown_task)
        
        assert decorated is shutdown_task
        assert shutdown_task in app._shutdown_hooks
    
    @pytest.mark.unit
    async def test_startup_shutdown_lifecycle(self):
        """Test startup and shutdown lifecycle."""
        app = Application()
        
        startup_called = False
        shutdown_called = False
        
        @app.on_startup
        async def on_start():
            nonlocal startup_called
            startup_called = True
        
        @app.on_shutdown
        async def on_stop():
            nonlocal shutdown_called
            shutdown_called = True
        
        # Run lifecycle
        await app.startup()
        assert startup_called
        assert app._running
        
        await app.shutdown()
        assert shutdown_called
        assert not app._running
    
    @pytest.mark.unit
    async def test_background_task(self):
        """Test background task registration and execution."""
        app = Application()
        
        execution_count = 0
        
        @app.task(interval=0.05, run_immediately=True)
        async def periodic_task():
            nonlocal execution_count
            execution_count += 1
        
        async with app.lifespan():
            # Should run immediately
            await asyncio.sleep(0.01)
            assert execution_count == 1
            
            # Should run again after interval
            await asyncio.sleep(0.06)
            assert execution_count >= 2
    
    @pytest.mark.unit
    async def test_task_with_dependencies(self):
        """Test background task with dependency injection."""
        app = Application()
        
        app.container.register_singleton(SimpleService)
        
        task_service = None
        
        @app.task(run_immediately=True)
        async def task_with_deps(service: SimpleService):
            nonlocal task_service
            task_service = service
        
        async with app.lifespan():
            await asyncio.sleep(0.01)
            assert task_service is not None
            assert isinstance(task_service, SimpleService)
    
    @pytest.mark.unit
    async def test_task_error_handling(self):
        """Test task error handling doesn't crash app."""
        app = Application()
        
        error_count = 0
        
        @app.task(interval=0.05, run_immediately=False)
        async def failing_task():
            nonlocal error_count
            error_count += 1
            raise ValueError("Task failed")
        
        async with app.lifespan():
            await asyncio.sleep(0.1)
            # Task should have tried to run despite errors
            assert error_count >= 1
    
    @pytest.mark.unit
    def test_event_handler_registration(self):
        """Test event handler registration."""
        app = Application()
        
        @app.on("test_event")
        async def handle_test_event(event):
            pass
        
        # Handler should be registered with event bus
        assert len(app.event_bus._handlers["test_event"]) == 1
    
    @pytest.mark.unit
    async def test_event_handler_with_di(self):
        """Test event handler with dependency injection."""
        app = Application()
        
        app.container.register_singleton(SimpleService)
        
        handler_called = False
        handler_service = None
        
        @app.on("test_event")
        async def handle_with_deps(event, service: SimpleService):
            nonlocal handler_called, handler_service
            handler_called = True
            handler_service = service
        
        # Start event bus
        await app.event_bus.start()
        
        # Emit event
        await app.event_bus.emit("test_event", {"data": "test"})
        await asyncio.sleep(0.01)
        
        assert handler_called
        assert isinstance(handler_service, SimpleService)
        
        await app.event_bus.stop()
    
    @pytest.mark.unit
    async def test_middleware_registration(self):
        """Test middleware registration and execution."""
        app = Application()
        
        middleware_called = False
        
        @app.middleware
        class TestMiddleware:
            async def process(self, event: Any, next_handler):
                nonlocal middleware_called
                middleware_called = True
                return await next_handler(event)
        
        async with app.lifespan():
            # Middleware should be registered
            assert len(app.event_bus._middleware) == 1
            
            # Test middleware is called
            @app.on("test_event")
            async def handler(event):
                return "handled"
            
            result = await app.event_bus.emit("test_event", {})
            await asyncio.sleep(0.01)
            
            assert middleware_called
    
    @pytest.mark.unit
    async def test_multiple_startup_hooks_order(self):
        """Test multiple startup hooks execute in order."""
        app = Application()
        
        call_order = []
        
        @app.on_startup
        async def first_startup():
            call_order.append("first")
        
        @app.on_startup
        async def second_startup():
            call_order.append("second")
        
        await app.startup()
        
        assert call_order == ["first", "second"]
    
    @pytest.mark.unit
    async def test_shutdown_hooks_reverse_order(self):
        """Test shutdown hooks execute in reverse order."""
        app = Application()
        
        call_order = []
        
        @app.on_shutdown
        async def first_shutdown():
            call_order.append("first")
        
        @app.on_shutdown
        async def second_shutdown():
            call_order.append("second")
        
        await app.shutdown()
        
        # Should be reverse order
        assert call_order == ["second", "first"]
    
    @pytest.mark.unit
    async def test_lifespan_context_manager(self):
        """Test lifespan context manager."""
        app = Application()
        
        startup_called = False
        shutdown_called = False
        
        @app.on_startup
        async def on_start():
            nonlocal startup_called
            startup_called = True
        
        @app.on_shutdown
        async def on_stop():
            nonlocal shutdown_called
            shutdown_called = True
        
        async with app.lifespan():
            assert startup_called
            assert not shutdown_called
            assert app._running
        
        assert shutdown_called
        assert not app._running
    
    @pytest.mark.unit
    async def test_background_task_cancellation(self):
        """Test background tasks are cancelled on shutdown."""
        app = Application()
        
        task_cancelled = False
        
        @app.task(interval=10)  # Long interval
        async def long_running_task():
            try:
                await asyncio.sleep(100)
            except asyncio.CancelledError:
                nonlocal task_cancelled
                task_cancelled = True
                raise
        
        await app.startup()
        assert len(app._background_tasks) == 1
        
        await app.shutdown()
        assert task_cancelled
    
    @pytest.mark.unit
    async def test_container_disposal_on_shutdown(self):
        """Test container is disposed on shutdown."""
        app = Application()
        
        # Register a disposable service
        app.container.register_singleton(DisposableService)
        
        async with app.lifespan():
            service = await app.container.resolve(DisposableService)
            assert not service.disposed
        
        # Container should have disposed all services
        assert service.disposed
    
    @pytest.mark.unit
    def test_service_decorator_direct_call(self):
        """Test service decorator can be called directly."""
        app = Application()
        
        class DirectService:
            value = "direct"
        
        # Direct call syntax
        app.service(DirectService)
        
        # Should be registered
        assert app.container.has(DirectService)
    
    @pytest.mark.unit
    def test_middleware_decorator_direct_call(self):
        """Test middleware decorator can be called directly."""
        app = Application()
        
        class DirectMiddleware:
            async def process(self, event, next_handler):
                return await next_handler(event)
        
        # Direct call syntax
        app.middleware(DirectMiddleware)
        
        # Should be registered
        assert app.container.has(DirectMiddleware)