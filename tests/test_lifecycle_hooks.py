"""Test lifecycle hooks implementation for Phase 3.1.

This test demonstrates the expected behavior for lifecycle hooks:
- initialize() method called after component instantiation
- dispose() method called before component cleanup
- Both async and sync methods supported
- Error handling for hook failures
"""

import asyncio

import pytest

from whiskey.core.application import Whiskey
from whiskey.core.errors import ResolutionError


class ComponentWithSyncHooks:
    """Component with synchronous lifecycle hooks."""

    def __init__(self):
        self.initialized = False
        self.disposed = False
        self.value = "test"

    def initialize(self):
        """Called after instantiation."""
        self.initialized = True
        self.value = "initialized"

    def dispose(self):
        """Called before disposal."""
        self.disposed = True
        self.value = "disposed"


class ComponentWithAsyncHooks:
    """Component with asynchronous lifecycle hooks."""

    def __init__(self):
        self.initialized = False
        self.disposed = False
        self.setup_data = None
        self.cleanup_data = None

    async def initialize(self):
        """Called after instantiation."""
        await asyncio.sleep(0)  # Simulate async work
        self.initialized = True
        self.setup_data = "async_initialized"

    async def dispose(self):
        """Called before disposal."""
        await asyncio.sleep(0)  # Simulate async work
        self.disposed = True
        self.cleanup_data = "async_disposed"


class ComponentWithBothHooks:
    """Component with both initialize and dispose hooks."""

    def __init__(self):
        self.lifecycle_events = []

    def initialize(self):
        self.lifecycle_events.append("initialized")

    def dispose(self):
        self.lifecycle_events.append("disposed")


class ComponentWithDependencies:
    """Component with dependencies that has lifecycle hooks."""

    def __init__(self, simple: ComponentWithSyncHooks):
        self.simple = simple
        self.initialized = False

    def initialize(self):
        # Should be called after dependencies are injected
        self.initialized = True
        assert self.simple is not None
        assert self.simple.initialized  # Dependency should be initialized first


class ComponentWithFailingInitialize:
    """Component whose initialize method fails."""

    def __init__(self):
        self.initialized = False

    def initialize(self):
        raise RuntimeError("Initialize failed")


class ComponentWithFailingDispose:
    """Component whose dispose method fails."""

    def __init__(self):
        pass

    def dispose(self):
        raise RuntimeError("Dispose failed")


@pytest.mark.unit
class TestLifecycleHooks:
    """Test basic lifecycle hook functionality."""

    def test_sync_initialize_hook_called(self):
        """Initialize hook should be called after instantiation."""
        app = Whiskey()
        app.singleton(ComponentWithSyncHooks)

        component = app.resolve(ComponentWithSyncHooks)

        # Component should be initialized
        assert component.initialized is True
        assert component.value == "initialized"

    async def test_async_initialize_hook_called(self):
        """Async initialize hook should be called after instantiation."""
        app = Whiskey()
        app.singleton(ComponentWithAsyncHooks)

        component = await app.resolve_async(ComponentWithAsyncHooks)

        # Component should be initialized
        assert component.initialized is True
        assert component.setup_data == "async_initialized"

    def test_dispose_hook_called_on_singleton_cleanup(self):
        """Dispose hook should be called when singleton is cleaned up."""
        app = Whiskey()
        app.singleton(ComponentWithSyncHooks)

        # Resolve component
        component = app.resolve(ComponentWithSyncHooks)
        assert component.initialized is True
        assert component.disposed is False

        # Cleanup singletons (this would happen during app shutdown)
        app.container.clear_singletons()

        # Component should be disposed
        assert component.disposed is True
        assert component.value == "disposed"

    async def test_async_dispose_hook_called(self):
        """Async dispose hook should be called during cleanup."""
        app = Whiskey()
        app.singleton(ComponentWithAsyncHooks)

        # Resolve component
        component = await app.resolve_async(ComponentWithAsyncHooks)
        assert component.initialized is True
        assert component.disposed is False

        # Cleanup singletons
        await app.container.clear_singletons_async()

        # Component should be disposed
        assert component.disposed is True
        assert component.cleanup_data == "async_disposed"

    def test_both_hooks_called_in_order(self):
        """Both initialize and dispose hooks should be called in proper order."""
        app = Whiskey()
        app.singleton(ComponentWithBothHooks)

        # Resolve and check initialize
        component = app.resolve(ComponentWithBothHooks)
        assert component.lifecycle_events == ["initialized"]

        # Cleanup and check dispose
        app.container.clear_singletons()
        assert component.lifecycle_events == ["initialized", "disposed"]

    def test_hooks_called_for_dependencies_first(self):
        """Dependencies should be initialized before dependent components."""
        app = Whiskey()
        app.singleton(ComponentWithSyncHooks)
        app.singleton(ComponentWithDependencies)

        component = app.resolve(ComponentWithDependencies)

        # Both component and its dependency should be initialized
        assert component.initialized is True
        assert component.simple.initialized is True

    def test_transient_components_no_dispose(self):
        """Transient components should not have dispose called automatically."""
        app = Whiskey()
        app.component(ComponentWithSyncHooks)  # Transient

        component = app.resolve(ComponentWithSyncHooks)

        # Should be initialized
        assert component.initialized is True

        # Clear singletons (shouldn't affect transient)
        app.container.clear_singletons()

        # Should not be disposed (transient components are not tracked)
        assert component.disposed is False

    def test_scoped_component_dispose_on_scope_exit(self):
        """Scoped components should be disposed when scope exits."""
        app = Whiskey()
        app.scoped(ComponentWithSyncHooks, scope_name="request")

        # Enter scope
        with app.container.scope("request"):
            component = app.resolve(ComponentWithSyncHooks)

            assert component.initialized is True
            assert component.disposed is False

        # After scope exit, component should be disposed
        assert component.disposed is True


@pytest.mark.unit
class TestLifecycleHookErrorHandling:
    """Test error handling in lifecycle hooks."""

    def test_failing_initialize_propagates_error(self):
        """Failed initialize should prevent component creation."""
        app = Whiskey()
        app.singleton(ComponentWithFailingInitialize)

        # Should raise error during resolution
        with pytest.raises(ResolutionError, match="Initialize failed"):
            app.resolve(ComponentWithFailingInitialize)

    def test_failing_dispose_logged_but_not_raised(self):
        """Failed dispose should be logged but not raise."""
        app = Whiskey()
        app.singleton(ComponentWithFailingDispose)

        # Resolve component (should work)
        component = app.resolve(ComponentWithFailingDispose)
        assert component is not None

        # Dispose failure should not raise (just log)
        # This should not raise an exception
        app.container.clear_singletons()

    def test_no_hooks_still_works(self):
        """Components without hooks should work normally."""

        class SimpleComponent:
            def __init__(self):
                self.value = "simple"

        app = Whiskey()
        app.singleton(SimpleComponent)

        component = app.resolve(SimpleComponent)
        assert component.value == "simple"

        # Cleanup should work without errors
        app.container.clear_singletons()


@pytest.mark.unit
class TestLifecycleHookIntegration:
    """Test integration with existing features."""

    def test_hooks_work_with_factory_components(self):
        """Lifecycle hooks should work with factory-created components."""
        app = Whiskey()

        def create_component():
            return ComponentWithSyncHooks()

        app.factory(ComponentWithSyncHooks, create_component)

        component = app.resolve(ComponentWithSyncHooks)

        # Factory-created component should still be initialized
        assert component.initialized is True

    async def test_hooks_work_with_async_factories(self):
        """Lifecycle hooks should work with async factory-created components."""
        app = Whiskey()

        async def create_async_component():
            return ComponentWithAsyncHooks()

        app.factory(ComponentWithAsyncHooks, create_async_component)

        component = await app.resolve_async(ComponentWithAsyncHooks)

        # Async factory-created component should be initialized
        assert component.initialized is True

    def test_hooks_preserve_component_identity(self):
        """Hooks should not change component identity or type."""
        app = Whiskey()
        app.singleton(ComponentWithSyncHooks)

        component = app.resolve(ComponentWithSyncHooks)

        # Should still be the same type
        assert isinstance(component, ComponentWithSyncHooks)
        assert type(component).__name__ == "ComponentWithSyncHooks"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
