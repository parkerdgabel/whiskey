"""Tests for Container syntactic sugar features."""

import pytest

from whiskey import Container


class SampleService:
    def __init__(self):
        self.value = 42


class DependentService:
    def __init__(self, test: SampleService):
        self.test = test


class TestContainerSyntacticSugar:
    """Test syntactic sugar methods for Container."""

    @pytest.fixture
    def container(self):
        c = Container()
        c.register_singleton(SampleService, SampleService)
        c.register(DependentService, DependentService)
        return c

    def test_getitem_access(self, container):
        """Test dict-like [] access."""
        service = container[SampleService]
        assert isinstance(service, SampleService)
        assert service.value == 42

        # Same instance for singleton
        service2 = container[SampleService]
        assert service is service2

    def test_getitem_not_found(self, container):
        """Test [] access raises for missing service."""
        with pytest.raises(KeyError):
            _ = container[str]

    def test_get_method(self, container):
        """Test get() method with defaults."""
        # Existing service
        service = container.get(SampleService)
        assert isinstance(service, SampleService)

        # Non-existent service returns None
        missing = container.get(str)
        assert missing is None

        # Non-existent service with default
        missing = container.get(str, default="not found")
        assert missing == "not found"

    def test_get_with_name(self, container):
        """Test get() with named services."""
        container.register(SampleService, SampleService, name="special")

        # Get named service
        service = container.get(SampleService, name="special")
        assert isinstance(service, SampleService)

        # Different from unnamed
        unnamed = container.get(SampleService)
        assert service is not unnamed  # Different instances

    async def test_aget_method(self, container):
        """Test async get() method."""
        # Existing service
        service = await container.aget(SampleService)
        assert isinstance(service, SampleService)

        # Non-existent returns None
        missing = await container.aget(str)
        assert missing is None

        # With default
        missing = await container.aget(str, default="async not found")
        assert missing == "async not found"

    def test_contains_operator(self, container):
        """Test 'in' operator."""
        assert SampleService in container
        assert DependentService in container
        assert str not in container
        assert int not in container

    def test_contains_with_named(self, container):
        """Test 'in' operator with named services."""
        container.register(SampleService, SampleService, name="named")

        # Tuple syntax for named services
        assert (SampleService, "named") in container
        assert (SampleService, "other") not in container
        assert (str, "any") not in container

    def test_len(self, container):
        """Test len() function."""
        # Initial services
        assert len(container) == 2

        # Add more
        container.register(str, instance="hello")
        assert len(container) == 3

        # Child container includes parent services
        child = container.create_child()
        assert len(child) == 3

        child.register(int, instance=42)
        assert len(child) == 4
        assert len(container) == 3  # Parent unchanged

    def test_iteration(self, container):
        """Test iteration over container."""
        keys = list(container)
        assert len(keys) == 2
        assert SampleService in keys
        assert DependentService in keys

    def test_dict_methods(self, container):
        """Test dict-like methods."""
        # keys()
        keys = list(container.keys())
        assert len(keys) == 2
        assert SampleService in keys

        # values()
        values = list(container.values())
        assert len(values) == 2
        assert all(hasattr(v, "service_type") for v in values)

        # items()
        items = list(container.items())
        assert len(items) == 2
        for key, desc in items:
            assert desc.service_type == key or isinstance(key, str)

    def test_sync_context_manager(self):
        """Test sync context manager."""
        with Container() as container:
            container.register_singleton(SampleService, SampleService)
            service = container[SampleService]
            assert isinstance(service, SampleService)
            assert not container._is_disposed

        # After context, container is disposed
        assert container._is_disposed

        # Cannot use after disposal
        with pytest.raises(Exception):
            _ = container[SampleService]

    async def test_async_context_manager(self):
        """Test async context manager."""
        async with Container() as container:
            container.register_singleton(SampleService, SampleService)
            service = await container.resolve(SampleService)
            assert isinstance(service, SampleService)
            assert not container._is_disposed

        # After context, container is disposed
        assert container._is_disposed

        # Cannot use after disposal
        with pytest.raises(Exception):
            await container.resolve(SampleService)

    def test_parent_child_sugar(self, container):
        """Test syntactic sugar with parent-child relationships."""
        child = container.create_child()

        # Child can access parent services
        assert SampleService in child
        service = child[SampleService]
        assert isinstance(service, SampleService)

        # Same singleton instance
        parent_service = container[SampleService]
        assert service is parent_service

        # Child override
        child.register_singleton(SampleService, SampleService)
        child_service = child[SampleService]
        assert child_service is not parent_service

    def test_chaining_registrations(self):
        """Test that registration methods return container for chaining."""
        container = (
            Container()
            .register_singleton(SampleService, SampleService)
            .register(DependentService, DependentService)
            .register(str, instance="hello")
        )

        assert len(container) == 3
        assert container[str] == "hello"
