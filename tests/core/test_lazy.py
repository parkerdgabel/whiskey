"""Tests for lazy resolution functionality."""

import asyncio
import gc

import pytest

from whiskey.core.container import Container, _current_container
from whiskey.core.errors import ResolutionError
from whiskey.core.lazy import Lazy, LazyDescriptor, lazy_inject


class TestLazy:
    """Test the Lazy wrapper class."""

    def test_lazy_creation(self):
        """Test creating a Lazy wrapper."""

        class MyService:
            pass

        lazy = Lazy(MyService)
        assert lazy._component_type is MyService
        assert lazy._name is None
        assert not lazy._resolved
        assert not lazy.is_resolved

    def test_lazy_with_name(self):
        """Test creating a Lazy wrapper with a name."""

        class MyService:
            pass

        lazy = Lazy(MyService, name="special")
        assert lazy._name == "special"

    def test_lazy_resolution(self):
        """Test lazy resolution of a service."""

        class MyService:
            def __init__(self):
                self.value = 42

        container = Container()
        container.register(MyService, MyService())

        # Create lazy with explicit container
        lazy = Lazy(MyService, container=container)

        # Should not be resolved yet
        assert not lazy.is_resolved

        # Access value triggers resolution
        value = lazy.value
        assert isinstance(value, MyService)
        assert value.value == 42
        assert lazy.is_resolved

        # Second access returns cached value
        value2 = lazy.value
        assert value2 is value

    def test_lazy_attribute_proxy(self):
        """Test that lazy proxies attribute access."""

        class MyService:
            def __init__(self):
                self.data = "test data"

            def process(self):
                return "processed"

        container = Container()
        container.register(MyService, MyService())

        lazy = Lazy(MyService, container=container)

        # Should not be resolved yet
        assert not lazy.is_resolved

        # Access attribute through proxy
        assert lazy.data == "test data"
        assert lazy.is_resolved

        # Method access also works
        assert lazy.process() == "processed"

    def test_lazy_with_current_container(self):
        """Test lazy resolution using current container."""

        class MyService:
            def __init__(self):
                self.id = "service-123"

        container = Container()
        container.register(MyService, MyService())

        # Set current container
        token = _current_container.set(container)
        try:
            # Create lazy without explicit container
            lazy = Lazy(MyService)

            # Should resolve from current container
            value = lazy.value
            assert value.id == "service-123"
        finally:
            _current_container.reset(token)

    def test_lazy_no_container_error(self):
        """Test error when no container is available."""

        class MyService:
            pass

        lazy = Lazy(MyService)

        with pytest.raises(RuntimeError, match="No container available"):
            _ = lazy.value

    def test_lazy_circular_resolution_detection(self):
        """Test circular resolution detection."""

        class MyService:
            pass

        container = Container()
        lazy = Lazy(MyService, container=container)

        # Simulate circular resolution
        lazy._resolving = True

        with pytest.raises(RuntimeError, match="Circular lazy resolution detected"):
            lazy._resolve()

    def test_lazy_container_garbage_collected(self):
        """Test error when container is garbage collected."""

        class MyService:
            pass

        container = Container()
        lazy = Lazy(MyService, container=container)

        # Force garbage collection of container
        del container
        gc.collect()

        # The error message might be different if weakref returns None
        with pytest.raises(
            RuntimeError, match="(Container has been garbage collected|No container available)"
        ):
            _ = lazy.value

    def test_lazy_in_async_context_error(self):
        """Test error when resolving lazy in async context."""

        class MyService:
            pass

        container = Container()
        container.register(MyService, MyService())
        lazy = Lazy(MyService, container=container)

        async def try_resolve():
            # This should fail because we're in an async context
            with pytest.raises(
                RuntimeError, match="Cannot resolve Lazy values synchronously in async context"
            ):
                _ = lazy.value

        asyncio.run(try_resolve())

    def test_lazy_repr(self):
        """Test string representation of Lazy."""

        class MyService:
            def __repr__(self):
                return "MyService()"

        container = Container()
        container.register(MyService, MyService())

        # Unresolved lazy
        lazy = Lazy(MyService, container=container)
        assert repr(lazy) == "Lazy[MyService](unresolved)"

        # With name
        lazy_named = Lazy(MyService, name="special", container=container)
        assert repr(lazy_named) == "Lazy[MyService](unresolved, name='special')"

        # Resolved lazy
        _ = lazy.value
        assert repr(lazy) == "Lazy[MyService](resolved=MyService())"

    def test_lazy_bool(self):
        """Test boolean conversion of Lazy."""

        class MyService:
            pass

        class FalsyService:
            def __bool__(self):
                return False

        container = Container()
        container.register(MyService, MyService())
        container.register(FalsyService, FalsyService())

        # Unresolved lazy is always truthy
        lazy_true = Lazy(MyService, container=container)
        assert bool(lazy_true)  # Does NOT trigger resolution
        assert not lazy_true.is_resolved  # Still unresolved

        # Resolve and check again
        _ = lazy_true.value
        assert lazy_true.is_resolved
        assert bool(lazy_true)  # Now checks the instance

        # Falsy service - unresolved is still truthy
        lazy_false = Lazy(FalsyService, container=container)
        assert bool(lazy_false)  # Unresolved is truthy
        assert not lazy_false.is_resolved

        # Resolve and check again
        _ = lazy_false.value
        assert lazy_false.is_resolved
        assert not bool(lazy_false)  # Now it's falsy

    def test_lazy_multiple_access(self):
        """Test multiple accesses to lazy value."""
        call_count = 0

        class MyService:
            def __init__(self):
                nonlocal call_count
                call_count += 1
                self.id = call_count

        container = Container()
        container.register(MyService, MyService)  # Register as factory

        lazy = Lazy(MyService, container=container)

        # First access
        value1 = lazy.value
        assert value1.id == 1
        assert call_count == 1

        # Second access should return cached value
        value2 = lazy.value
        assert value2 is value1
        assert call_count == 1  # Should not create new instance


class TestLazyInject:
    """Test the lazy_inject factory function."""

    def test_lazy_inject_basic(self):
        """Test lazy_inject factory function."""

        class MyService:
            pass

        lazy = lazy_inject(MyService)
        assert isinstance(lazy, Lazy)
        assert lazy._component_type is MyService
        assert lazy._name is None

    def test_lazy_inject_with_name(self):
        """Test lazy_inject with name."""

        class MyService:
            pass

        lazy = lazy_inject(MyService, name="custom")
        assert lazy._name == "custom"


class TestLazyEdgeCases:
    """Test edge cases for lazy resolution."""

    def test_lazy_with_none_instance(self):
        """Test lazy resolution returning None."""
        container = Container()
        # Register a factory that returns None
        container.register("nullable", lambda: None)

        lazy = Lazy("nullable", container=container)
        assert lazy.value is None
        assert lazy.is_resolved

    def test_lazy_getattr_on_none(self):
        """Test attribute access on None value."""
        container = Container()
        # Register a factory that returns None
        container.register("nullable", lambda: None)

        lazy = Lazy("nullable", container=container)

        with pytest.raises(AttributeError):
            _ = lazy.some_attribute

    def test_lazy_resolution_error_propagation(self):
        """Test that resolution errors are propagated."""

        class UnregisteredService:
            pass

        container = Container()
        # Don't register the service

        lazy = Lazy(UnregisteredService, container=container)

        with pytest.raises(ResolutionError):
            _ = lazy.value

        # Should not be marked as resolved
        assert not lazy.is_resolved

    def test_lazy_with_initialization_error(self):
        """Test lazy with service that fails to initialize."""

        class FailingService:
            def __init__(self):
                raise ValueError("Initialization failed")

        container = Container()
        container.register(FailingService, FailingService)

        lazy = Lazy(FailingService, container=container)

        with pytest.raises(
            ResolutionError, match="Failed to instantiate FailingService: Initialization failed"
        ):
            _ = lazy.value

        # Should not be marked as resolved
        assert not lazy.is_resolved


class TestLazyDescriptor:
    """Test the LazyDescriptor class."""

    def test_lazy_descriptor_basic(self):
        """Test basic LazyDescriptor functionality."""

        class Database:
            def query(self, sql):
                return f"Result of: {sql}"

        class MyService:
            database: LazyDescriptor[Database] = LazyDescriptor(Database)

            def __init__(self):
                self.container = Container()
                self.container.register(Database, Database())

        service = MyService()

        # Access creates Lazy instance
        lazy = service.database
        assert isinstance(lazy, Lazy)
        assert lazy._component_type is Database

        # Access value through lazy
        result = service.database.value.query("SELECT * FROM users")
        assert result == "Result of: SELECT * FROM users"

    def test_lazy_descriptor_with_name(self):
        """Test LazyDescriptor with named dependency."""

        class Cache:
            pass

        class MyService:
            cache: LazyDescriptor[Cache] = LazyDescriptor(Cache, name="redis")

            def __init__(self):
                self._container = Container()
                self._container.register(Cache, Cache(), name="redis")

        service = MyService()
        lazy = service.cache
        assert lazy._name == "redis"

    def test_lazy_descriptor_caching(self):
        """Test that LazyDescriptor caches Lazy instances."""

        class Database:
            pass

        class MyService:
            db: LazyDescriptor[Database] = LazyDescriptor(Database)

            def __init__(self):
                self.container = Container()

        service = MyService()

        # Multiple accesses should return same Lazy instance
        lazy1 = service.db
        lazy2 = service.db
        assert lazy1 is lazy2

    def test_lazy_descriptor_class_access(self):
        """Test accessing LazyDescriptor on class."""

        class Database:
            pass

        class MyService:
            db: LazyDescriptor[Database] = LazyDescriptor(Database)

        # Accessing on class returns descriptor itself
        descriptor = MyService.db
        assert isinstance(descriptor, LazyDescriptor)
        assert descriptor._component_type is Database

    def test_lazy_descriptor_no_container(self):
        """Test LazyDescriptor with current container."""

        class Database:
            pass

        class MyService:
            db: LazyDescriptor[Database] = LazyDescriptor(Database)

        container = Container()
        container.register(Database, Database())

        token = _current_container.set(container)
        try:
            service = MyService()
            lazy = service.db
            assert isinstance(lazy.value, Database)
        finally:
            _current_container.reset(token)
