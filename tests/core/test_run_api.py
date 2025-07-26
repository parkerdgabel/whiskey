"""Tests for the standardized run API."""

import asyncio
import pytest
from typing import Annotated

from whiskey import Whiskey, component, inject, Inject


@component
class TestService:
    def __init__(self):
        self.initialized = False
        self.value = 42
    
    async def initialize(self):
        self.initialized = True
        await asyncio.sleep(0.01)  # Simulate async work


class TestRunAPI:
    """Test the standardized run API."""
    
    def test_run_sync_function(self):
        """Test running a simple sync function."""
        app = Whiskey()
        
        def main():
            return "Hello, World!"
        
        result = app.run(main)
        assert result == "Hello, World!"
    
    def test_run_sync_function_with_args(self):
        """Test running a sync function with arguments."""
        app = Whiskey()
        
        def main(name, greeting="Hello"):
            return f"{greeting}, {name}!"
        
        result = app.run(main, name="Alice")
        assert result == "Hello, Alice!"
        
        result = app.run(main, name="Bob", greeting="Hi")
        assert result == "Hi, Bob!"
    
    def test_run_async_function(self):
        """Test running an async function."""
        app = Whiskey()
        
        async def main():
            await asyncio.sleep(0.01)
            return "Async result"
        
        result = app.run(main)
        assert result == "Async result"
    
    def test_run_with_dependency_injection(self):
        """Test running a function with dependency injection."""
        app = Whiskey()
        
        @inject
        async def main(service: TestService):
            await service.initialize()
            return service.value
        
        result = app.run(main)
        assert result == 42
    
    def test_run_with_lifecycle(self):
        """Test that run handles application lifecycle."""
        app = Whiskey()
        
        startup_called = False
        shutdown_called = False
        
        @app.on_startup
        async def startup():
            nonlocal startup_called
            startup_called = True
        
        @app.on_shutdown
        async def shutdown():
            nonlocal shutdown_called  
            shutdown_called = True
        
        def main():
            return "Done"
        
        result = app.run(main)
        
        assert startup_called
        assert shutdown_called
        assert result == "Done"
    
    def test_run_without_main_raises_error(self):
        """Test that run without main and no runners raises error."""
        app = Whiskey()
        
        with pytest.raises(RuntimeError, match="No main callable provided and no runners found"):
            app.run()
    
    def test_register_runner(self):
        """Test registering a custom runner."""
        app = Whiskey()
        
        runner_called = False
        runner_kwargs = {}
        
        def custom_runner(**kwargs):
            nonlocal runner_called, runner_kwargs
            runner_called = True
            runner_kwargs = kwargs
            return "Runner result"
        
        app.register_runner("custom", custom_runner)
        
        # Should have the runner as a method
        assert hasattr(app, "run_custom")
        
        # Running without main should use the runner
        result = app.run(foo="bar", baz=123)
        
        assert runner_called
        assert runner_kwargs == {"foo": "bar", "baz": 123}
        assert result == "Runner result"
    
    def test_multiple_runners(self):
        """Test with multiple registered runners."""
        app = Whiskey()
        
        def cli_runner(**kwargs):
            return "CLI"
        
        def asgi_runner(**kwargs):
            return "ASGI"
        
        # Register in order
        app.register_runner("cli", cli_runner)
        app.register_runner("asgi", asgi_runner)
        
        # Should use first registered runner
        result = app.run()
        assert result == "CLI"
        
        # Can call specific runners
        assert app.run_cli() == "CLI"
        assert app.run_asgi() == "ASGI"
    
    def test_run_mode_parameter(self):
        """Test explicit mode parameter."""
        app = Whiskey()
        
        async def async_main():
            return "async"
        
        def sync_main():
            return "sync"
        
        # Force async mode on sync function
        result = app.run(sync_main, mode="async")
        assert result == "sync"
        
        # Force sync mode on async function (will still work)
        result = app.run(async_main, mode="sync")
        assert result == "async"
    
    @pytest.mark.asyncio
    async def test_lifespan_context_async(self):
        """Test lifespan context manager in async context."""
        app = Whiskey()
        
        startup_called = False
        shutdown_called = False
        
        @app.on_startup
        async def startup():
            nonlocal startup_called
            startup_called = True
        
        @app.on_shutdown
        async def shutdown():
            nonlocal shutdown_called
            shutdown_called = True
        
        async with app.lifespan:
            assert startup_called
            assert not shutdown_called
            
            # Should be able to resolve services
            service = await app.resolve_async(TestService)
            assert isinstance(service, TestService)
        
        assert shutdown_called
    
    def test_lifespan_context_sync(self):
        """Test lifespan context manager in sync context."""
        app = Whiskey()
        
        startup_called = False
        shutdown_called = False
        
        @app.on_startup
        async def startup():
            nonlocal startup_called
            startup_called = True
        
        @app.on_shutdown
        async def shutdown():
            nonlocal shutdown_called
            shutdown_called = True
        
        with app.lifespan:
            assert startup_called
            assert not shutdown_called
            
            # Should be able to resolve services
            service = app.resolve(TestService)
            assert isinstance(service, TestService)
        
        assert shutdown_called
    
    def test_run_handles_exceptions(self):
        """Test that run properly handles exceptions."""
        app = Whiskey()
        
        def failing_main():
            raise ValueError("Test error")
        
        # Sync functions that don't need injection are called directly
        # so they raise the original exception
        with pytest.raises(ValueError, match="Test error"):
            app.run(failing_main)
        
        # Async version
        async def async_failing_main():
            raise RuntimeError("Async error")
        
        # The container wraps exceptions in ResolutionError
        from whiskey.core.errors import ResolutionError
        with pytest.raises(ResolutionError) as exc_info:
            app.run(async_failing_main)
        
        # Check the original exception is preserved
        assert isinstance(exc_info.value.cause, RuntimeError)
        assert str(exc_info.value.cause) == "Async error"
    
    def test_run_with_startup_tasks(self):
        """Test run with background tasks started during startup."""
        app = Whiskey()
        
        task_executed = False
        
        @app.on_startup
        async def startup():
            async def background_task():
                nonlocal task_executed
                await asyncio.sleep(0.01)
                task_executed = True
            
            # Start task during startup
            asyncio.create_task(background_task())
        
        async def main():
            # Wait a bit for background task
            await asyncio.sleep(0.02)
            return "Done"
        
        result = app.run(main)
        
        assert result == "Done"
        assert task_executed
    
    def test_runner_with_lifecycle(self):
        """Test that runners properly handle lifecycle."""
        app = Whiskey()
        
        lifecycle_events = []
        
        @app.on_startup
        async def startup():
            lifecycle_events.append("startup")
        
        @app.on_shutdown  
        async def shutdown():
            lifecycle_events.append("shutdown")
        
        def test_runner(**kwargs):
            async def runner_main():
                async with app.lifespan:
                    lifecycle_events.append("runner")
                    return "OK"
            
            return asyncio.run(runner_main())
        
        app.register_runner("test", test_runner)
        
        result = app.run()
        
        assert result == "OK"
        assert lifecycle_events == ["startup", "runner", "shutdown"]
    
    def test_run_none_main(self):
        """Test running with None as main (long-running app simulation)."""
        app = Whiskey()
        
        # Add a simple runner that returns immediately
        def test_runner(**kwargs):
            return "Runner executed"
        
        app.register_runner("test", test_runner)
        
        # When no main is provided, it should use the registered runner
        result = app.run()
        assert result == "Runner executed"