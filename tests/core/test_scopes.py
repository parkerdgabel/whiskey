"""Comprehensive tests for the scopes module."""

import asyncio
import threading
from contextvars import ContextVar

from whiskey import Container, Scope
from whiskey.core.application import Whiskey
from whiskey.core.registry import Scope as RegistryScope
from whiskey.core.scopes import ContextVarScope, Scope, ScopeManager, ScopeType


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

    def test_scope_has_instance(self):
        """Test checking if instance exists in scope."""
        scope = Scope("test")

        assert scope.get(SimpleService) is None

        scope.set(SimpleService, SimpleService())
        assert scope.get(SimpleService) is not None

    def test_scope_sync_disposal_in_clear(self):
        """Test that clear() handles sync disposal properly."""
        scope = Scope("test")

        sync_service = SimpleService()
        scope.set(SimpleService, sync_service)

        # Clear should dispose sync services
        scope.clear()

        assert sync_service.disposed
        assert scope.get(SimpleService) is None

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

        # Use async context manager which calls disposal
        async with scope:
            pass

        assert sync_service.disposed
        assert async_service.disposed


class TestScopeType:
    """Test ScopeType constants."""

    def test_scope_type_constants(self):
        """Test that ScopeType has the expected constants."""
        assert ScopeType.SINGLETON == "singleton"
        assert ScopeType.TRANSIENT == "transient"

    def test_scope_type_usage_with_container(self):
        """Test using ScopeType constants with container."""
        from whiskey.core.registry import Scope as RegistryScope

        # ScopeType constants should match RegistryScope values
        assert RegistryScope.SINGLETON.value == ScopeType.SINGLETON
        assert RegistryScope.TRANSIENT.value == ScopeType.TRANSIENT


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
        await asyncio.gather(task(1), task(2), task(3))

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

            # Nested context will clear the scope when exiting
            with scope:
                scope.set(SimpleService, inner_instance)
                assert scope.get(SimpleService).value == "inner"

            # After inner context exits, scope is cleared (ContextVarScope doesn't restore)
            assert scope.get(SimpleService) is None

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
        container = Container()
        manager = ScopeManager(container, "test_scope")

        assert manager.container is container
        assert manager.scope_name == "test_scope"
        assert manager.scope_instance is None

    def test_scope_manager_context(self):
        """Test ScopeManager as context manager."""
        # Mock container with scope management methods
        from unittest.mock import Mock

        container = Mock()
        test_scope = Scope("test")
        container.enter_scope = Mock(return_value=test_scope)
        container.exit_scope = Mock()

        with ScopeManager(container, "test") as scope:
            assert scope is test_scope
            container.enter_scope.assert_called_once_with("test")

        # Should call exit_scope after context
        container.exit_scope.assert_called_once_with("test")

    async def test_scope_manager_async_context(self):
        """Test ScopeManager as async context manager."""
        # Mock container with scope management methods
        from unittest.mock import Mock

        container = Mock()
        test_scope = Scope("test")
        container.enter_scope = Mock(return_value=test_scope)
        container.exit_scope = Mock()

        async with ScopeManager(container, "test") as scope:
            assert scope is test_scope
            container.enter_scope.assert_called_once_with("test")

        # Should call exit_scope after context
        container.exit_scope.assert_called_once_with("test")


class TestContainerScopeIntegration:
    """Test scope integration with Container.

    Note: These tests are placeholder tests. The current Container implementation
    doesn't have built-in scope management methods like enter_scope, exit_scope, or scope().
    These would need to be implemented in Container for full scope support.
    """

    def test_scoped_registration(self):
        """Test that services can be registered with scope metadata."""
        container = Container()

        # Register service with custom scope - this works for metadata
        container.register(
            SimpleService, SimpleService, scope=RegistryScope.SCOPED, scope_name="request"
        )

        # Verify the registration has the scope metadata
        descriptor = container.registry.get(SimpleService)
        assert descriptor.scope == RegistryScope.SCOPED
        # Note: scope_name is passed to register but not stored in ComponentDescriptor

    def test_singleton_scope_behavior(self):
        """Test singleton scope behavior."""
        container = Container()

        # Register as singleton
        container.register(SimpleService, SimpleService, scope=RegistryScope.SINGLETON)

        # Multiple resolutions should return same instance
        instance1 = container.resolve_sync(SimpleService)
        instance2 = container.resolve_sync(SimpleService)

        assert instance1 is instance2
        assert instance1.id == instance2.id

    def test_transient_scope_behavior(self):
        """Test transient scope behavior."""
        container = Container()

        # Register as transient (default)
        container.register(SimpleService, SimpleService, scope=RegistryScope.TRANSIENT)

        # Multiple resolutions should return different instances
        instance1 = container.resolve_sync(SimpleService)
        instance2 = container.resolve_sync(SimpleService)

        assert instance1 is not instance2
        assert instance1.id != instance2.id


class TestWhiskeyScopeIntegration:
    """Test scope integration with Whiskey application."""

    def test_app_scoped_decorator(self):
        """Test @app.scoped decorator."""
        app = Whiskey()

        @app.scoped(scope_name="request")
        class RequestService:
            pass

        # Should be registered with the scope metadata
        descriptor = app.container.registry.get(RequestService)
        assert descriptor.scope == RegistryScope.SCOPED
        # Note: scope_name is not stored in ComponentDescriptor

    def test_app_resolve_with_scoped_service(self):
        """Test resolving scoped services through app."""
        app = Whiskey()

        @app.scoped(scope_name="session")
        class SessionService:
            def __init__(self):
                self.id = id(self)

        # Scoped services require an active scope to be resolved
        # Without scope management exposed in Container, we can't resolve scoped services
        import pytest

        from whiskey.core.errors import ScopeError

        with pytest.raises(ScopeError, match="Scope 'default' is not active"):
            app.resolve(SessionService)


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
        import pytest

        scope = Scope("test")

        class BadService:
            def dispose(self):
                raise RuntimeError("Disposal failed")

        bad_service = BadService()
        good_service = SimpleService()

        scope.set("bad", bad_service)
        scope.set("good", good_service)

        # The current implementation doesn't handle exceptions during disposal
        # It will raise on the first disposal error
        with pytest.raises(RuntimeError, match="Disposal failed"), scope:
            pass

        # Due to the exception, good_service won't be disposed
        assert not good_service.disposed

    async def test_async_disposal_with_exception(self):
        """Test async disposal with exception."""
        import pytest

        scope = Scope("test")

        class BadAsyncService:
            async def dispose(self):
                raise RuntimeError("Async disposal failed")

        bad_service = BadAsyncService()
        good_service = AsyncDisposableService()

        scope.set("bad", bad_service)
        scope.set("good", good_service)

        # The current implementation doesn't handle exceptions during disposal
        # It will raise on the first disposal error
        with pytest.raises(RuntimeError, match="Async disposal failed"):
            async with scope:
                pass

        # Due to the exception, good_service won't be disposed
        assert not good_service.disposed

    def test_context_var_scope_no_context(self):
        """Test ContextVarScope when no context is set."""
        scope = ContextVarScope("test")

        # Should handle gracefully - default is empty dict
        assert scope.get(SimpleService) is None

        # Should be able to set and get
        instance = SimpleService()
        scope.set(SimpleService, instance)
        assert scope.get(SimpleService) is instance
