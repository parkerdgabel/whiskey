"""Comprehensive tests for the Container class."""

import asyncio
from typing import Optional

import pytest

from whiskey import Container
from whiskey.core.container import _current_container, get_current_container, set_current_container
from whiskey.core.errors import CircularDependencyError, ResolutionError
from whiskey.core.registry import Scope
from whiskey.core.types import Disposable, Initializable


# Test components/services
class SimpleService:
    """Simple test service."""

    def __init__(self):
        self.value = "simple"


class DatabaseService:
    """Service representing a database."""

    def __init__(self, connection_string: str = "sqlite://"):
        self.connection_string = connection_string


class CacheService:
    """Service representing a cache."""

    def __init__(self, ttl: int = 300):
        self.ttl = ttl


class DependentService:
    """Service with dependencies."""

    def __init__(self, simple: SimpleService):
        self.simple = simple


class ComplexService:
    """Service with multiple dependencies."""

    def __init__(self, db: DatabaseService, cache: CacheService):
        self.db = db
        self.cache = cache


class OptionalDependencyService:
    """Service with optional dependency."""

    def __init__(self, db: Optional[DatabaseService] = None):
        self.db = db


class CircularServiceA:
    """First service in circular dependency."""

    def __init__(self, b: "CircularServiceB"):
        self.b = b


class CircularServiceB:
    """Second service in circular dependency."""

    def __init__(self, a: CircularServiceA):
        self.a = a


# Factory functions
def simple_factory() -> SimpleService:
    """Factory that creates SimpleService."""
    return SimpleService()


async def async_factory() -> DatabaseService:
    """Async factory function."""
    await asyncio.sleep(0.001)
    return DatabaseService("async://")


def factory_with_deps(simple: SimpleService) -> DependentService:
    """Factory with dependencies."""
    return DependentService(simple)


class TestContainerBasics:
    """Test basic Container functionality."""

    @pytest.fixture
    def container(self):
        """Create a test container with compatibility methods."""
        from whiskey.core.testing import add_test_compatibility_methods
        container = Container()
        add_test_compatibility_methods(container)
        return container

    @pytest.mark.unit
    def test_container_creation(self):
        """Test container can be created."""
        container = Container()
        assert container is not None
        assert len(container) == 0

    @pytest.mark.unit
    def test_dict_like_interface(self, container):
        """Test dict-like interface."""
        # Set item
        container[SimpleService] = SimpleService()

        # Check contains
        assert SimpleService in container
        assert DependentService not in container
        
        # Check contains with type key
        container[str] = "test"
        assert str in container
        
        # Check contains with unregistered string key
        assert "nonexistent" not in container

        # Get item
        service = container[SimpleService]
        assert isinstance(service, SimpleService)

        # Delete item
        del container[SimpleService]
        assert SimpleService not in container

    @pytest.mark.unit
    def test_dict_methods(self, container):
        """Test dict-like methods."""
        container[SimpleService] = SimpleService
        container[DependentService] = DependentService

        # keys()
        keys = list(container.keys())
        assert SimpleService in keys
        assert DependentService in keys

        # items()
        items = list(container.items())
        assert len(items) == 2

        # len()
        assert len(container) == 2

        # iter()
        for key in container:
            assert key in [SimpleService, DependentService]

        # clear()
        container.clear()
        assert len(container) == 0


class TestRegistration:
    """Test service registration."""

    @pytest.fixture
    def container(self):
        """Create a test container with compatibility methods."""
        from whiskey.core.testing import add_test_compatibility_methods
        container = Container()
        add_test_compatibility_methods(container)
        return container

    @pytest.mark.unit
    async def test_register_instance(self, container):
        """Test registering an instance."""
        instance = SimpleService()
        container[SimpleService] = instance

        resolved = await container.resolve(SimpleService)
        assert resolved is instance

    @pytest.mark.unit
    async def test_register_class(self, container):
        """Test registering a class."""
        container[SimpleService] = SimpleService

        resolved1 = await container.resolve(SimpleService)
        resolved2 = await container.resolve(SimpleService)

        # Should create new instances
        assert isinstance(resolved1, SimpleService)
        assert isinstance(resolved2, SimpleService)
        assert resolved1 is not resolved2

    @pytest.mark.unit
    async def test_register_factory(self, container):
        """Test registering a factory."""
        container[SimpleService] = simple_factory

        resolved = await container.resolve(SimpleService)
        assert isinstance(resolved, SimpleService)

    @pytest.mark.unit
    async def test_async_factory(self, container):
        """Test async factory."""
        container[DatabaseService] = async_factory

        resolved = await container.resolve(DatabaseService)
        assert isinstance(resolved, DatabaseService)
        assert resolved.connection_string == "async://"

    @pytest.mark.unit
    def test_resolve_sync_with_async_factory_error(self, container):
        """Test error when resolving async factory synchronously."""
        container["service"] = async_factory

        with pytest.raises(RuntimeError, match="Cannot resolve async factory"):
            container.resolve_sync("service")

    @pytest.mark.unit
    async def test_singleton(self, container):
        """Test singleton registration."""
        container.singleton(SimpleService)

        resolved1 = await container.resolve(SimpleService)
        resolved2 = await container.resolve(SimpleService)

        assert resolved1 is resolved2

    @pytest.mark.unit
    async def test_singleton_instance(self, container):
        """Test singleton with instance."""
        instance = SimpleService()
        container.singleton(SimpleService, instance=instance)

        resolved = await container.resolve(SimpleService)
        assert resolved is instance

    @pytest.mark.unit
    def test_register_with_metadata(self, container):
        """Test registration with metadata."""
        container.register(
            SimpleService, SimpleService(), metadata={"version": "1.0", "author": "test"}
        )

        # Metadata should be stored in descriptor
        descriptor = container.registry.get(SimpleService)
        assert descriptor.metadata["version"] == "1.0"
        assert descriptor.metadata["author"] == "test"

    @pytest.mark.unit
    def test_register_with_tuple_key(self, container):
        """Test setting with tuple key for named services."""
        instance = SimpleService()

        # Set with name
        container[SimpleService, "primary"] = instance

        # Should be retrievable by type and name
        retrieved = container.resolve_sync(SimpleService, name="primary")
        assert retrieved is instance

    @pytest.mark.unit
    def test_duplicate_registration(self, container):
        """Test duplicate registration overwrites."""
        instance1 = SimpleService()
        instance2 = SimpleService()

        container.register(SimpleService, instance1)
        container.register(SimpleService, instance2)  # Should overwrite

        result = container.resolve_sync(SimpleService)
        assert result is instance2

    @pytest.mark.unit
    def test_register_none_provider(self, container):
        """Test registering with None provider."""
        # Should handle None provider
        container.register("null_service", None)

        result = container.resolve_sync("null_service")
        assert result is None


class TestResolution:
    """Test dependency resolution."""

    @pytest.fixture
    def container(self):
        """Create a test container with compatibility methods."""
        from whiskey.core.testing import add_test_compatibility_methods
        container = Container()
        add_test_compatibility_methods(container)
        return container

    @pytest.mark.unit
    async def test_dependency_injection(self, container):
        """Test automatic dependency injection."""
        container[SimpleService] = SimpleService
        container[DependentService] = DependentService

        resolved = await container.resolve(DependentService)
        assert isinstance(resolved, DependentService)
        assert isinstance(resolved.simple, SimpleService)

    @pytest.mark.unit
    async def test_factory_with_dependencies(self, container):
        """Test factory with dependencies."""
        container[SimpleService] = SimpleService
        container.factory(DependentService, factory_with_deps)

        resolved = await container.resolve(DependentService)
        assert isinstance(resolved, DependentService)
        assert isinstance(resolved.simple, SimpleService)

    @pytest.mark.unit
    async def test_unregistered_concrete_class(self, container):
        """Test resolving unregistered concrete class."""
        # Should be able to create simple classes without registration
        resolved = await container.resolve(SimpleService)
        assert isinstance(resolved, SimpleService)

    @pytest.mark.unit
    async def test_missing_service(self, container):
        """Test resolving missing abstract service."""
        from abc import ABC, abstractmethod

        class AbstractService(ABC):
            @abstractmethod
            def do_something(self):
                pass

        with pytest.raises(KeyError, match="AbstractService not registered"):
            await container.resolve(AbstractService)

    @pytest.mark.unit
    async def test_circular_dependency(self, container):
        """Test circular dependency detection."""
        container[CircularServiceA] = CircularServiceA
        container[CircularServiceB] = CircularServiceB

        # Should raise CircularDependencyError since forward reference can be resolved
        with pytest.raises(CircularDependencyError):
            await container.resolve(CircularServiceA)

    @pytest.mark.unit
    def test_resolve_sync(self, container):
        """Test synchronous resolution."""
        container[SimpleService] = SimpleService()

        # Should work outside async context
        resolved = container.resolve_sync(SimpleService)
        assert isinstance(resolved, SimpleService)

    @pytest.mark.unit
    def test_resolve_with_overrides(self, container):
        """Test resolution with overrides."""
        container.register(DatabaseService, DatabaseService)
        container.register(CacheService, CacheService)  # Register cache service too
        container.register(ComplexService, ComplexService)

        # Resolve with override
        custom_db = DatabaseService("custom")
        service = container.resolve_sync(ComplexService, overrides={"db": custom_db})

        assert service.db is custom_db
        assert service.db.connection_string == "custom"

    @pytest.mark.unit
    def test_optional_dependency(self, container):
        """Test optional dependency resolution."""
        container.register(OptionalDependencyService, OptionalDependencyService)
        # Don't register DatabaseService

        # Should resolve with None for optional
        service = container.resolve_sync(OptionalDependencyService)
        assert service.db is None

    @pytest.mark.unit
    def test_resolve_non_existent(self, container):
        """Test resolving non-existent service."""

        class Service:
            pass

        with pytest.raises(ResolutionError):
            container.resolve_sync(Service)


class TestScopes:
    """Test container scope management."""

    @pytest.fixture
    def container(self):
        """Create a test container with compatibility methods."""
        from whiskey.core.testing import add_test_compatibility_methods
        container = Container()
        add_test_compatibility_methods(container)
        return container

    @pytest.mark.unit
    def test_enter_scope(self, container):
        """Test entering a scope."""
        container.register(SimpleService, SimpleService, scope=Scope.SCOPED, scope_name="request")

        # Enter scope
        scope = container.enter_scope("request")
        assert scope is not None
        assert scope.name == "request"

    @pytest.mark.unit
    def test_exit_scope(self, container):
        """Test exiting a scope."""
        container.register(SimpleService, SimpleService, scope=Scope.SCOPED, scope_name="request")

        # Enter and exit scope
        container.enter_scope("request")
        container.exit_scope("request")

        # Scope should be removed
        assert "request" not in container._scopes

    @pytest.mark.unit
    def test_scope_context_manager(self, container):
        """Test using scope as context manager."""
        container.register(SimpleService, SimpleService, scope=Scope.SCOPED, scope_name="request")

        with container.scope("request") as scope:
            # Should be able to resolve in scope
            instance = container.resolve_sync(SimpleService)
            assert instance is not None

        # Scope should be cleaned up
        assert "request" not in container._scopes

    @pytest.mark.unit
    async def test_scope_async_context_manager(self, container):
        """Test using scope as async context manager."""
        container.register(SimpleService, SimpleService, scope=Scope.SCOPED, scope_name="session")

        async with container.scope("session") as scope:
            # Should be able to resolve in scope
            instance = await container.resolve(SimpleService)
            assert instance is not None

        # Scope should be cleaned up
        assert "session" not in container._scopes


class TestLifecycle:
    """Test container lifecycle management."""

    @pytest.fixture
    def container(self):
        """Create a test container with compatibility methods."""
        from whiskey.core.testing import add_test_compatibility_methods
        container = Container()
        add_test_compatibility_methods(container)
        return container

    @pytest.mark.unit
    async def test_initialize_service(self, container):
        """Test initializing a service."""
        initialized = False

        class Service(Initializable):
            async def initialize(self):
                nonlocal initialized
                initialized = True

        service = Service()
        await container._initialize_service(service)

        assert initialized

    @pytest.mark.unit
    async def test_dispose_service(self, container):
        """Test disposing a service."""
        disposed = False

        class Service(Disposable):
            async def dispose(self):
                nonlocal disposed
                disposed = True

        service = Service()
        await container._dispose_service(service)
        assert disposed

    @pytest.mark.unit
    async def test_startup_hooks(self, container):
        """Test startup hooks."""
        startup_called = False

        def startup_hook():
            nonlocal startup_called
            startup_called = True

        container.on_startup(startup_hook)
        await container.startup()

        assert startup_called

    @pytest.mark.unit
    async def test_shutdown_hooks(self, container):
        """Test shutdown hooks."""
        shutdown_called = False

        def shutdown_hook():
            nonlocal shutdown_called
            shutdown_called = True

        container.on_shutdown(shutdown_hook)
        await container.shutdown()

        assert shutdown_called

    @pytest.mark.unit
    async def test_async_startup_hook(self, container):
        """Test async startup hook."""
        async_called = False

        async def async_startup():
            nonlocal async_called
            async_called = True
            await asyncio.sleep(0)

        container.on_startup(async_startup)
        await container.startup()

        assert async_called

    @pytest.mark.unit
    async def test_context_manager(self):
        """Test container as context manager."""
        with Container() as container:
            container[SimpleService] = SimpleService
            resolved = container.resolve_sync(SimpleService)
            assert isinstance(resolved, SimpleService)

    @pytest.mark.unit
    async def test_async_context_manager(self):
        """Test container as async context manager."""
        async with Container() as container:
            container[SimpleService] = SimpleService
            resolved = await container.resolve(SimpleService)
            assert isinstance(resolved, SimpleService)


class TestCallMethods:
    """Test container call methods."""

    @pytest.fixture
    def container(self):
        """Create a test container with compatibility methods."""
        from whiskey.core.testing import add_test_compatibility_methods
        container = Container()
        add_test_compatibility_methods(container)
        return container

    @pytest.mark.unit
    def test_call_sync(self, container):
        """Test calling function with injection."""

        class Service:
            def __init__(self):
                self.value = 42

        container.register(Service, Service())

        def func(service: Service, x: int):
            return service.value + x

        result = container.call_sync(func, x=10)
        assert result == 52

    @pytest.mark.unit
    async def test_call_async(self, container):
        """Test calling async function with injection."""

        class Service:
            def __init__(self):
                self.value = 42

        container.register(Service, Service())

        async def func(service: Service, x: int):
            await asyncio.sleep(0)
            return service.value + x

        result = await container.call(func, x=10)
        assert result == 52

    @pytest.mark.unit
    def test_invoke_sync(self, container):
        """Test invoking function with full injection."""

        class Service:
            def __init__(self):
                self.value = 42

        container.register(Service, Service())

        def func(service: Service):
            return service.value

        result = container.call_sync(func)
        assert result == 42

    @pytest.mark.unit
    async def test_invoke_async(self, container):
        """Test invoking async function with full injection."""

        class Service:
            def __init__(self):
                self.value = 42

        container.register(Service, Service())

        async def func(service: Service):
            return service.value

        result = await container.invoke(func)
        assert result == 42


class TestGlobalState:
    """Test global container state management."""

    @pytest.mark.unit
    def test_get_current_container(self):
        """Test getting current container."""
        container = Container()

        # Set current container
        token = _current_container.set(container)

        try:
            current = get_current_container()
            assert current is container
        finally:
            _current_container.reset(token)

    @pytest.mark.unit
    def test_set_current_container(self):
        """Test setting current container."""
        container = Container()

        token = set_current_container(container)

        try:
            current = get_current_container()
            assert current is container
        finally:
            _current_container.reset(token)

    @pytest.mark.unit
    def test_no_current_container(self):
        """Test when no current container is set."""
        # Ensure no container is set
        _current_container.set(None)

        current = get_current_container()
        assert current is None


class TestEdgeCases:
    """Test edge cases and error scenarios."""

    @pytest.fixture
    def container(self):
        """Create a test container with compatibility methods."""
        from whiskey.core.testing import add_test_compatibility_methods
        container = Container()
        add_test_compatibility_methods(container)
        return container

    @pytest.mark.unit
    def test_circular_dependency_detection(self, container):
        """Test circular dependency detection."""

        class ServiceA:
            def __init__(self, b: "ServiceB"):
                self.b = b

        class ServiceB:
            def __init__(self, a: ServiceA):
                self.a = a

        container.register(ServiceA, ServiceA)
        container.register(ServiceB, ServiceB)

        # Should raise TypeError for forward reference since ServiceB is function-local
        with pytest.raises(TypeError, match="Cannot resolve forward reference"):
            container.resolve_sync(ServiceA)

    @pytest.mark.unit
    def test_invalid_dict_key(self, container):
        """Test error on invalid dict key."""
        with pytest.raises(ValueError, match="Invalid key type"):
            container[123] = "invalid"
            
    @pytest.mark.unit 
    def test_invalid_tuple_key_length(self, container):
        """Test tuple key with wrong length raises error."""
        with pytest.raises(ValueError, match="Tuple key must have exactly 2 elements"):
            container[("type", "name", "extra")] = "value"
            
    @pytest.mark.unit
    def test_invalid_tuple_key_types(self, container):
        """Test tuple key with wrong types raises error."""
        with pytest.raises(ValueError, match="Tuple key must be"):
            container[(123, "name")] = "value"

    @pytest.mark.unit
    def test_get_unregistered_key(self, container):
        """Test getting unregistered key."""
        with pytest.raises(KeyError):
            _ = container[SimpleService]

    @pytest.mark.unit
    def test_del_unregistered_key(self, container):
        """Test deleting unregistered key."""
        with pytest.raises(KeyError):
            del container[SimpleService]
            
    @pytest.mark.unit
    def test_del_service_clears_scope_caches(self, container):
        """Test deleting service clears scope caches."""
        # Register a service
        container.register("test_key", lambda: "value")
        
        # Populate scoped cache
        container._scoped_caches["test_scope"] = {"test_key": "cached"}
        
        # Delete the service
        del container["test_key"]
        
        # Should be removed from scope cache
        assert "test_key" not in container._scoped_caches.get("test_scope", {})
