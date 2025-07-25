"""Comprehensive tests for the scopes module."""

import asyncio
import threading
from contextvars import ContextVar
from unittest.mock import AsyncMock, Mock

import pytest

from whiskey import Container, Scope
from whiskey.core.application import Whiskey
from whiskey.core.registry import Scope as RegistryScope
from whiskey.core.scopes import ContextVarScope, ScopeManager, SingletonScope, TransientScope


# Test services
class SimpleService:
    """Simple test service."""

    def __init__(self):
        self.id = id(self)
        self.disposed = False

    def dispose(self):
        """Dispose method for testing."""
        self.disposed = True


class AsyncDisposableService:
    """Service with async disposal."""

    def __init__(self):
        self.id = id(self)
        self.disposed = False

    async def dispose(self):
        """Async dispose method."""
        await asyncio.sleep(0)
        self.disposed = True


class TestBasicScope:
    """Test basic Scope functionality."""

    def test_scope_creation(self):
        """Test scope creation."""
        scope = Scope("test")
        assert scope.name == "test"
        assert scope._instances == {}

    def test_scope_get_set(self):
        """Test getting and setting in scope."""
        scope = Scope("test")

        instance = SimpleService()
        scope.set(SimpleService, instance)

        retrieved = scope.get(SimpleService)
        assert retrieved is instance

    def test_scope_get_missing(self):
        """Test getting missing service."""
        scope = Scope("test")
        assert scope.get(str) is None

    def test_scope_contains(self):
        """Test checking if key exists in scope."""
        scope = Scope("test")
        
        assert SimpleService not in scope
        
        scope.set(SimpleService, SimpleService())
        assert SimpleService in scope

    def test_scope_clear(self):
        """Test clearing scope."""
        scope = Scope("test")
        
        instance1 = SimpleService()
        instance2 = SimpleService()
        
        scope.set("service1", instance1)
        scope.set("service2", instance2)
        
        assert len(scope._instances) == 2
        
        scope.clear()
        assert len(scope._instances) == 0

    def test_scope_context_manager(self):
        """Test scope as context manager."""
        scope = Scope("test")
        instance = SimpleService()
        
        with scope:
            scope.set(SimpleService, instance)
            assert scope.get(SimpleService) is instance
        
        # Should be cleared after exiting
        assert scope.get(SimpleService) is None
        assert instance.disposed

    async def test_scope_async_context_manager(self):
        """Test scope as async context manager."""
        scope = Scope("test")
        instance = AsyncDisposableService()
        
        async with scope:
            scope.set(AsyncDisposableService, instance)
            assert scope.get(AsyncDisposableService) is instance
        
        # Should be cleared after exiting
        assert scope.get(AsyncDisposableService) is None
        assert instance.disposed

    def test_scope_enter_exit(self):
        """Test manual enter/exit."""
        scope = Scope("test")
        
        scope.__enter__()
        scope.set("key", "value")
        assert scope.get("key") == "value"
        
        scope.__exit__(None, None, None)
        assert scope.get("key") is None

    async def test_async_disposal(self):
        """Test async disposal of services."""
        scope = Scope("test")
        
        sync_service = SimpleService()
        async_service = AsyncDisposableService()
        
        scope.set("sync", sync_service)
        scope.set("async", async_service)
        
        # Dispose all
        await scope._dispose_instances()
        
        assert sync_service.disposed
        assert async_service.disposed


class TestSingletonScope:
    """Test SingletonScope functionality."""

    def test_singleton_scope_creation(self):
        """Test creating singleton scope."""
        scope = SingletonScope()
        assert scope.name == "singleton"
        assert isinstance(scope._instances, dict)

    def test_singleton_persistence(self):
        """Test that singleton scope persists instances."""
        scope = SingletonScope()
        
        instance = SimpleService()
        scope.set(SimpleService, instance)
        
        # Should persist across context manager usage
        with scope:
            assert scope.get(SimpleService) is instance
        
        # Still there after exiting
        assert scope.get(SimpleService) is instance

    def test_singleton_scope_no_auto_clear(self):
        """Test that singleton scope doesn't auto-clear."""
        scope = SingletonScope()
        instance = SimpleService()
        
        with scope:
            scope.set(SimpleService, instance)
        
        # Should not be disposed
        assert not instance.disposed
        assert scope.get(SimpleService) is instance


class TestTransientScope:
    """Test TransientScope functionality."""

    def test_transient_scope_creation(self):
        """Test creating transient scope."""
        scope = TransientScope()
        assert scope.name == "transient"

    def test_transient_no_storage(self):
        """Test that transient scope doesn't store instances."""
        scope = TransientScope()
        
        instance = SimpleService()
        scope.set(SimpleService, instance)
        
        # Should always return None
        assert scope.get(SimpleService) is None

    def test_transient_contains_always_false(self):
        """Test that transient scope never contains keys."""
        scope = TransientScope()
        
        scope.set(SimpleService, SimpleService())
        assert SimpleService not in scope


class TestContextVarScope:
    """Test ContextVarScope for async isolation."""

    def test_context_var_scope_creation(self):
        """Test creating context var scope."""
        scope = ContextVarScope("request")
        assert scope.name == "request"
        assert isinstance(scope._context_var, ContextVar)

    async def test_async_isolation(self):
        """Test that ContextVarScope provides async isolation."""
        scope = ContextVarScope("test")
        results = []

        async def task(value: int):
            instance = SimpleService()
            instance.value = value
            scope.set(SimpleService, instance)
            
            # Yield to allow other tasks to run
            await asyncio.sleep(0.01)
            
            # Should get back our own instance
            retrieved = scope.get(SimpleService)
            results.append(retrieved.value if retrieved else None)

        # Run tasks concurrently
        await asyncio.gather(
            task(1),
            task(2),
            task(3)
        )

        # Each task should have gotten its own value
        assert sorted(results) == [1, 2, 3]

    def test_context_var_scope_context_manager(self):
        """Test ContextVarScope as context manager."""
        scope = ContextVarScope("test")
        
        with scope:
            instance = SimpleService()
            scope.set(SimpleService, instance)
            assert scope.get(SimpleService) is instance
        
        # Should be cleared after exiting
        assert scope.get(SimpleService) is None

    async def test_nested_contexts(self):
        """Test nested context var scopes."""
        scope = ContextVarScope("test")
        
        outer_instance = SimpleService()
        outer_instance.value = "outer"
        
        with scope:
            scope.set(SimpleService, outer_instance)
            assert scope.get(SimpleService).value == "outer"
            
            inner_instance = SimpleService()
            inner_instance.value = "inner"
            
            with scope:
                scope.set(SimpleService, inner_instance)
                assert scope.get(SimpleService).value == "inner"
            
            # Back to outer context
            assert scope.get(SimpleService).value == "outer"
        
        # Completely cleared
        assert scope.get(SimpleService) is None

    def test_thread_isolation(self):
        """Test that ContextVarScope provides thread isolation."""
        scope = ContextVarScope("test")
        results = {}

        def thread_task(thread_id: int):
            instance = SimpleService()
            instance.value = thread_id
            scope.set(SimpleService, instance)
            
            # Sleep to ensure other threads run
            import time
            time.sleep(0.01)
            
            # Should get back our own instance
            retrieved = scope.get(SimpleService)
            results[thread_id] = retrieved.value if retrieved else None

        # Run in multiple threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=thread_task, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Each thread should have gotten its own value
        assert results == {0: 0, 1: 1, 2: 2}


class TestScopeManager:
    """Test ScopeManager functionality."""

    def test_scope_manager_creation(self):
        """Test creating scope manager."""
        manager = ScopeManager()
        assert isinstance(manager._scopes, dict)

    def test_add_scope(self):
        """Test adding scope to manager."""
        manager = ScopeManager()
        scope = Scope("custom")
        
        manager.add_scope("custom", scope)
        assert manager.get_scope("custom") is scope

    def test_get_scope_missing(self):
        """Test getting missing scope."""
        manager = ScopeManager()
        assert manager.get_scope("missing") is None

    def test_has_scope(self):
        """Test checking if scope exists."""
        manager = ScopeManager()
        scope = Scope("test")
        
        assert not manager.has_scope("test")
        
        manager.add_scope("test", scope)
        assert manager.has_scope("test")

    def test_remove_scope(self):
        """Test removing scope."""
        manager = ScopeManager()
        scope = Scope("test")
        
        manager.add_scope("test", scope)
        assert manager.has_scope("test")
        
        manager.remove_scope("test")
        assert not manager.has_scope("test")

    def test_clear_all_scopes(self):
        """Test clearing all scopes."""
        manager = ScopeManager()
        
        manager.add_scope("scope1", Scope("scope1"))
        manager.add_scope("scope2", Scope("scope2"))
        
        assert len(manager._scopes) == 2
        
        manager.clear()
        assert len(manager._scopes) == 0


class TestContainerScopeIntegration:
    """Test scope integration with Container."""

    def test_container_with_scoped_service(self):
        """Test container with scoped service."""
        container = Container()
        
        # Register service with custom scope
        container.register(
            SimpleService,
            SimpleService,
            scope=RegistryScope.SCOPED,
            scope_name="request"
        )
        
        # Enter scope
        request_scope = container.enter_scope("request")
        assert request_scope is not None
        
        # Resolve in scope
        instance1 = container.resolve_sync(SimpleService)
        instance2 = container.resolve_sync(SimpleService)
        
        # Should be same instance within scope
        assert instance1 is instance2
        
        # Exit scope
        container.exit_scope("request")

    def test_scope_context_manager_integration(self):
        """Test using container scope as context manager."""
        container = Container()
        
        container.register(
            SimpleService,
            SimpleService,
            scope=RegistryScope.SCOPED,
            scope_name="session"
        )
        
        instance1 = None
        instance2 = None
        
        with container.scope("session"):
            instance1 = container.resolve_sync(SimpleService)
            instance2 = container.resolve_sync(SimpleService)
            assert instance1 is instance2
        
        # New scope, new instance
        with container.scope("session"):
            instance3 = container.resolve_sync(SimpleService)
            assert instance3 is not instance1

    async def test_async_scope_context_manager(self):
        """Test async scope context manager."""
        container = Container()
        
        container.register(
            SimpleService,
            SimpleService,
            scope=RegistryScope.SCOPED,
            scope_name="request"
        )
        
        async with container.scope("request"):
            instance1 = await container.resolve(SimpleService)
            instance2 = await container.resolve(SimpleService)
            assert instance1 is instance2


class TestWhiskeyScopeIntegration:
    """Test scope integration with Whiskey application."""

    def test_app_scoped_decorator(self):
        """Test @app.scoped decorator."""
        app = Whiskey()
        
        @app.scoped("request")
        class RequestService:
            pass
        
        # Should be registered with scope
        with app.container.scope("request"):
            instance = app.resolve(RequestService)
            assert isinstance(instance, RequestService)

    async def test_request_scope_isolation(self):
        """Test request scope isolation in async context."""
        app = Whiskey()
        
        @app.scoped("request")
        class RequestData:
            def __init__(self):
                self.id = id(self)
                self.data = {}
        
        async def handle_request(request_id: int):
            with app.container.scope("request"):
                data = app.resolve(RequestData)
                data.data["request_id"] = request_id
                
                # Simulate async work
                await asyncio.sleep(0.01)
                
                # Should still have our data
                data2 = app.resolve(RequestData)
                assert data2 is data
                assert data2.data["request_id"] == request_id
        
        # Handle multiple requests concurrently
        await asyncio.gather(
            handle_request(1),
            handle_request(2),
            handle_request(3)
        )


class TestScopeEdgeCases:
    """Test edge cases and error scenarios."""

    def test_scope_with_none_key(self):
        """Test scope with None key."""
        scope = Scope("test")
        
        scope.set(None, "value")
        assert scope.get(None) == "value"

    def test_scope_with_duplicate_key(self):
        """Test overwriting values in scope."""
        scope = Scope("test")
        
        instance1 = SimpleService()
        instance2 = SimpleService()
        
        scope.set(SimpleService, instance1)
        scope.set(SimpleService, instance2)
        
        # Should get the latest
        assert scope.get(SimpleService) is instance2

    def test_disposal_with_exception(self):
        """Test disposal when service raises exception."""
        scope = Scope("test")
        
        class BadService:
            def dispose(self):
                raise RuntimeError("Disposal failed")
        
        bad_service = BadService()
        good_service = SimpleService()
        
        scope.set("bad", bad_service)
        scope.set("good", good_service)
        
        # Should not raise, but should dispose good service
        with scope:
            pass
        
        assert good_service.disposed

    async def test_async_disposal_with_exception(self):
        """Test async disposal with exception."""
        scope = Scope("test")
        
        class BadAsyncService:
            async def dispose(self):
                raise RuntimeError("Async disposal failed")
        
        bad_service = BadAsyncService()
        good_service = AsyncDisposableService()
        
        scope.set("bad", bad_service)
        scope.set("good", good_service)
        
        # Should not raise, but should dispose good service
        async with scope:
            pass
        
        assert good_service.disposed

    def test_context_var_scope_no_context(self):
        """Test ContextVarScope when no context is set."""
        scope = ContextVarScope("test")
        
        # Should handle gracefully
        assert scope.get(SimpleService) is None
        assert SimpleService not in scope
        
        # Should be able to set
        scope.set(SimpleService, SimpleService())
        # But won't persist without context
        assert scope.get(SimpleService) is None