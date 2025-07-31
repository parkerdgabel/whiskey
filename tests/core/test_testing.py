"""Tests for test compatibility utilities."""

import pytest

from whiskey.core.container import Container
from whiskey.core.testing import (
    ScopeContext,
    ScopeContextManager,
    TestContainer,
    add_test_compatibility_methods,
)


class TestScopeContext:
    """Test ScopeContext class."""

    def test_scope_context_creation(self):
        """Test creating a scope context."""
        context = ScopeContext("test")
        assert context.name == "test"


class TestScopeContextManager:
    """Test ScopeContextManager class."""

    def test_sync_context_manager(self):
        """Test sync context manager."""
        container = Container()
        add_test_compatibility_methods(container)

        with ScopeContextManager(container, "test") as scope:
            assert scope is not None
            assert hasattr(container, "_scopes")
            assert "test" in container._scopes

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        """Test async context manager."""
        container = Container()
        add_test_compatibility_methods(container)

        async with ScopeContextManager(container, "test") as scope:
            assert scope is not None
            assert hasattr(container, "_scopes")
            assert "test" in container._scopes


class TestTestContainer:
    """Test TestContainer class."""

    def test_test_container_creation(self):
        """Test creating a test container."""
        container = TestContainer()
        assert isinstance(container, Container)

    def test_test_container_methods(self):
        """Test test container methods."""
        container = TestContainer()

        # Test register
        container.register("test", lambda: "value")

        # Test resolve - sync resolve for sync factory
        result = container.resolve_sync("test")
        assert result == "value"

    def test_test_container_compat_methods(self):
        """Test compatibility methods."""
        container = TestContainer()

        # Test singleton registration
        container.register_singleton(str, "test")
        assert container[str] == "test"

        # Test factory registration
        container.register_factory(int, lambda: 42)
        assert container[int] == 42
