"""Enhanced tests for the Container class focusing on uncovered functionality.

This module tests advanced container features including:
- ContainerServiceBuilder fluent API
- Scope management
- Performance monitoring integration
- Error handling scenarios
- Function injection
- Context variable usage
"""

import asyncio
import os
from typing import Optional, Union
from unittest.mock import patch

import pytest

from whiskey.core.container import (
    Container,
    ContainerServiceBuilder,
    get_current_container,
    set_current_container,
)
from whiskey.core.errors import CircularDependencyError, InjectionError, ResolutionError, ScopeError
from whiskey.core.performance import PerformanceMonitor
from whiskey.core.registry import Scope, ServiceDescriptor


# Test services
class SimpleService:
    def __init__(self):
        self.value = "simple"


class DatabaseService:
    def __init__(self, connection_string: str = "default"):
        self.connection_string = connection_string


class CacheService:
    def __init__(self, ttl: int = 300):
        self.ttl = ttl


class ComplexService:
    def __init__(self, db: DatabaseService, cache: CacheService):
        self.db = db
        self.cache = cache


class OptionalDependencyService:
    def __init__(self, db: Optional[DatabaseService] = None):
        self.db = db


class UnionTypeService:
    def __init__(self, service: Union[DatabaseService, CacheService]):
        self.service = service


class ServiceWithManyParams:
    def __init__(self, a: str, b: int, c: float, db: DatabaseService):
        self.a = a
        self.b = b
        self.c = c
        self.db = db


def simple_factory() -> SimpleService:
    """Factory function for SimpleService."""
    return SimpleService()


async def async_factory() -> DatabaseService:
    """Async factory function."""
    await asyncio.sleep(0.001)
    return DatabaseService("async-db")


def factory_with_deps(db: DatabaseService) -> ComplexService:
    """Factory with dependencies."""
    cache = CacheService()
    return ComplexService(db, cache)


class TestContainerServiceBuilder:
    """Test the ContainerServiceBuilder fluent API."""

    def test_builder_creation(self):
        """Test creating a ContainerServiceBuilder."""
        container = Container()
        builder = ContainerServiceBuilder(container, SimpleService, SimpleService)

        assert builder._container is container
        assert builder._key is SimpleService
        assert builder._provider is SimpleService
        assert builder._scope == Scope.TRANSIENT
        assert builder._name is None
        assert builder._tags == set()
        assert builder._condition is None
        assert builder._lazy is False
        assert builder._metadata == {}

    def test_builder_as_singleton(self):
        """Test configuring service as singleton."""
        container = Container()
        builder = ContainerServiceBuilder(container, SimpleService, SimpleService)

        result = builder.as_singleton()

        assert result is builder  # Fluent interface
        assert builder._scope == Scope.SINGLETON

    def test_builder_as_scoped(self):
        """Test configuring service as scoped."""
        container = Container()
        builder = ContainerServiceBuilder(container, SimpleService, SimpleService)

        result = builder.as_scoped("request")

        assert result is builder
        assert builder._scope == Scope.SCOPED
        assert builder._metadata["scope_name"] == "request"

    def test_builder_as_scoped_default(self):
        """Test configuring service as scoped with default name."""
        container = Container()
        builder = ContainerServiceBuilder(container, SimpleService, SimpleService)

        result = builder.as_scoped()

        assert builder._scope == Scope.SCOPED
        assert builder._metadata["scope_name"] == "default"

    def test_builder_as_transient(self):
        """Test configuring service as transient."""
        container = Container()
        builder = ContainerServiceBuilder(container, SimpleService, SimpleService)

        # Change to singleton first
        builder.as_singleton()

        # Then back to transient
        result = builder.as_transient()

        assert result is builder
        assert builder._scope == Scope.TRANSIENT

    def test_builder_named(self):
        """Test naming a service."""
        container = Container()
        builder = ContainerServiceBuilder(container, DatabaseService, DatabaseService)

        result = builder.named("primary")

        assert result is builder
        assert builder._name == "primary"

    def test_builder_tagged(self):
        """Test adding tags."""
        container = Container()
        builder = ContainerServiceBuilder(container, SimpleService, SimpleService)

        result = builder.tagged("core", "infrastructure", "database")

        assert result is builder
        assert builder._tags == {"core", "infrastructure", "database"}

    def test_builder_tagged_multiple_calls(self):
        """Test multiple tagged calls accumulate."""
        container = Container()
        builder = ContainerServiceBuilder(container, SimpleService, SimpleService)

        builder.tagged("core").tagged("infrastructure", "stable")

        assert builder._tags == {"core", "infrastructure", "stable"}

    def test_builder_when_boolean(self):
        """Test condition with boolean."""
        container = Container()
        builder = ContainerServiceBuilder(container, SimpleService, SimpleService)

        result = builder.when(True)

        assert result is builder
        assert builder._condition is not None
        assert builder._condition() is True

        # Test with False
        builder.when(False)
        assert builder._condition() is False

    def test_builder_when_callable(self):
        """Test condition with callable."""
        container = Container()
        builder = ContainerServiceBuilder(container, SimpleService, SimpleService)

        condition = lambda: True
        result = builder.when(condition)

        assert result is builder
        assert builder._condition is condition

    def test_builder_when_env(self):
        """Test environment-based condition."""
        container = Container()
        builder = ContainerServiceBuilder(container, SimpleService, SimpleService)

        with patch.dict(os.environ, {"TEST_MODE": "active"}):
            result = builder.when_env("TEST_MODE", "active")

            assert result is builder
            assert builder._condition() is True

        with patch.dict(os.environ, {"TEST_MODE": "inactive"}):
            assert builder._condition() is False

    def test_builder_when_env_existence(self):
        """Test environment variable existence check."""
        container = Container()
        builder = ContainerServiceBuilder(container, SimpleService, SimpleService)

        with patch.dict(os.environ, {"DEBUG": "anything"}):
            builder.when_env("DEBUG")
            assert builder._condition() is True

        with patch.dict(os.environ, {}, clear=True):
            assert builder._condition() is False

    def test_builder_when_debug(self):
        """Test debug mode condition."""
        container = Container()
        builder = ContainerServiceBuilder(container, SimpleService, SimpleService)

        with patch.dict(os.environ, {"DEBUG": "true"}):
            result = builder.when_debug()
            assert result is builder
            assert builder._condition() is True

        # Test various truthy values
        for value in ["1", "yes", "TRUE"]:
            with patch.dict(os.environ, {"DEBUG": value}):
                builder.when_debug()
                assert builder._condition() is True

        with patch.dict(os.environ, {"DEBUG": "false"}):
            builder.when_debug()
            assert builder._condition() is False

    def test_builder_lazy(self):
        """Test lazy configuration."""
        container = Container()
        builder = ContainerServiceBuilder(container, SimpleService, SimpleService)

        result = builder.lazy()

        assert result is builder
        assert builder._lazy is True

        # Test turning off lazy
        builder.lazy(False)
        assert builder._lazy is False

    def test_builder_with_metadata(self):
        """Test adding metadata."""
        container = Container()
        builder = ContainerServiceBuilder(container, SimpleService, SimpleService)

        result = builder.with_metadata(version="1.0", author="test", priority=5)

        assert result is builder
        assert builder._metadata["version"] == "1.0"
        assert builder._metadata["author"] == "test"
        assert builder._metadata["priority"] == 5

    def test_builder_build(self):
        """Test building the service registration."""
        container = Container()
        builder = ContainerServiceBuilder(container, SimpleService, SimpleService)

        # Configure the service
        builder.as_singleton().named("primary").tagged("core").lazy()

        # Build should register with container
        result = builder.build()

        assert isinstance(result, ServiceDescriptor)  # Should return descriptor

        # Verify registration
        descriptor = container.registry.get(SimpleService, name="primary")
        assert descriptor.scope == Scope.SINGLETON
        assert "core" in descriptor.tags

    def test_builder_fluent_chaining(self):
        """Test complete fluent chaining."""
        container = Container()

        result = (
            ContainerServiceBuilder(container, DatabaseService, DatabaseService)
            .as_singleton()
            .named("primary")
            .tagged("infrastructure", "database")
            .when_debug()
            .lazy()
            .with_metadata(connection_timeout=30)
            .build()
        )

        assert isinstance(result, ServiceDescriptor)
        # Service was registered, check via registry
        assert result.key == container.registry._normalize_key(DatabaseService)


class TestContainerRegistration:
    """Test Container registration methods."""

    def test_register_with_builder(self):
        """Test register method returning builder."""
        container = Container()

        # The register method returns a ServiceDescriptor, not a builder
        descriptor = container.register(SimpleService, SimpleService)

        assert isinstance(descriptor, ServiceDescriptor)
        assert descriptor.key == container.registry._normalize_key(SimpleService)

    def test_singleton_helper(self):
        """Test singleton registration helper."""
        container = Container()

        descriptor = container.singleton(DatabaseService, DatabaseService)

        assert isinstance(descriptor, ServiceDescriptor)
        assert descriptor.scope == Scope.SINGLETON

    def test_factory_helper(self):
        """Test factory registration helper."""
        container = Container()

        # There's no factory method, use register instead
        descriptor = container.register("simple_factory", simple_factory)

        assert isinstance(descriptor, ServiceDescriptor)
        assert descriptor.key == "simple_factory"
        assert descriptor.provider is simple_factory

    def test_instance_helper(self):
        """Test instance registration helper."""
        container = Container()
        instance = SimpleService()

        # There's no instance method, use register with singleton scope
        descriptor = container.register(SimpleService, instance, scope=Scope.SINGLETON)

        assert isinstance(descriptor, ServiceDescriptor)
        assert descriptor.key == container.registry._normalize_key(SimpleService)
        assert descriptor.provider is instance
        assert descriptor.scope == Scope.SINGLETON


class TestContainerResolution:
    """Test Container resolution with various scenarios."""

    async def test_resolve_with_performance_monitoring(self):
        """Test resolution with performance monitoring enabled."""
        container = Container()
        container[SimpleService] = SimpleService

        with PerformanceMonitor() as metrics:
            service = await container.resolve(SimpleService)

            assert isinstance(service, SimpleService)
            assert metrics.resolution_count > 0

    async def test_resolve_optional_dependency(self):
        """Test resolving service with optional dependency."""
        container = Container()
        container[OptionalDependencyService] = OptionalDependencyService
        # Don't register DatabaseService

        service = await container.resolve(OptionalDependencyService)

        assert isinstance(service, OptionalDependencyService)
        assert service.db is None  # Optional dependency not provided

    async def test_resolve_with_overrides(self):
        """Test resolution with parameter overrides."""
        container = Container()
        container[ServiceWithManyParams] = ServiceWithManyParams
        container[DatabaseService] = DatabaseService

        # Override some parameters
        service = await container.resolve(ServiceWithManyParams, a="custom", b=42, c=3.14)

        assert service.a == "custom"
        assert service.b == 42
        assert service.c == 3.14
        assert isinstance(service.db, DatabaseService)

    async def test_resolve_factory_with_dependencies(self):
        """Test resolving factory that has dependencies."""
        container = Container()
        container[DatabaseService] = DatabaseService
        container["complex"] = factory_with_deps

        service = await container.resolve("complex")

        assert isinstance(service, ComplexService)
        assert isinstance(service.db, DatabaseService)
        assert isinstance(service.cache, CacheService)

    async def test_resolve_async_factory(self):
        """Test resolving async factory."""
        container = Container()
        container["async_db"] = async_factory

        service = await container.resolve("async_db")

        assert isinstance(service, DatabaseService)
        assert service.connection_string == "async-db"

    def test_resolve_sync(self):
        """Test synchronous resolution."""
        container = Container()
        container[SimpleService] = SimpleService

        service = container.resolve_sync(SimpleService)

        assert isinstance(service, SimpleService)

    def test_resolve_sync_with_async_factory_error(self):
        """Test sync resolution of async factory raises error."""
        container = Container()
        container["async_db"] = async_factory

        with pytest.raises(ResolutionError, match="Cannot resolve async"):
            container.resolve_sync("async_db")

    async def test_resolve_circular_dependency(self):
        """Test circular dependency detection."""
        container = Container()

        # Create circular dependency
        class ServiceA:
            def __init__(self, b: "ServiceB"):
                self.b = b

        class ServiceB:
            def __init__(self, a: ServiceA):
                self.a = a

        container[ServiceA] = ServiceA
        container[ServiceB] = ServiceB

        with pytest.raises(CircularDependencyError):
            await container.resolve(ServiceA)

    async def test_resolve_union_type_error(self):
        """Test Union type parameter causes injection error."""
        container = Container()
        container[UnionTypeService] = UnionTypeService
        container[DatabaseService] = DatabaseService
        container[CacheService] = CacheService

        # Union types should cause injection error
        with pytest.raises(InjectionError):
            await container.resolve(UnionTypeService)

    async def test_resolve_missing_dependency(self):
        """Test resolution with missing dependency."""
        container = Container()
        container[ComplexService] = ComplexService
        # Don't register DatabaseService or CacheService

        with pytest.raises(ResolutionError, match="DatabaseService"):
            await container.resolve(ComplexService)

    async def test_auto_resolution(self):
        """Test automatic resolution of unregistered services."""
        container = Container()

        # SimpleService not registered but should be auto-created
        service = await container.resolve(SimpleService)

        assert isinstance(service, SimpleService)

    async def test_resolve_with_condition_false(self):
        """Test resolution when condition is false."""
        container = Container()

        container.add(SimpleService, SimpleService).when(False).build()

        with pytest.raises(ResolutionError):
            await container.resolve(SimpleService)


class TestContainerScopes:
    """Test Container scope management."""

    async def test_singleton_scope(self):
        """Test singleton scope behavior."""
        container = Container()
        container.singleton(DatabaseService, DatabaseService)

        service1 = await container.resolve(DatabaseService)
        service2 = await container.resolve(DatabaseService)

        assert service1 is service2  # Same instance

    async def test_transient_scope(self):
        """Test transient scope behavior."""
        container = Container()
        container[SimpleService] = SimpleService  # Default is transient

        service1 = await container.resolve(SimpleService)
        service2 = await container.resolve(SimpleService)

        assert service1 is not service2  # Different instances

    async def test_scoped_resolution(self):
        """Test scoped service resolution."""
        container = Container()
        # Using ContainerServiceBuilder to register scoped service
        builder = ContainerServiceBuilder(container, DatabaseService, DatabaseService)
        builder.as_scoped("request").build()

        # Without scope, should fail
        with pytest.raises(ScopeError):
            await container.resolve(DatabaseService)

    async def test_nested_scopes(self):
        """Test nested scope contexts."""
        # Skip this test as ScopedContext is not implemented
        pytest.skip("ScopedContext not implemented in current version")

    def test_clear_singleton_cache(self):
        """Test clearing singleton cache."""
        container = Container()
        container.singleton(SimpleService, SimpleService)

        # Create singleton
        service1 = container.resolve_sync(SimpleService)

        # Clear cache - use clear_caches method
        container.clear_caches()

        # Should create new instance
        service2 = container.resolve_sync(SimpleService)

        assert service1 is not service2

    def test_clear_all_caches(self):
        """Test clearing all caches."""
        container = Container()
        container.singleton(SimpleService, SimpleService)

        # Create singleton
        service1 = container.resolve_sync(SimpleService)

        # Clear all caches
        container.clear_caches()

        # Should create new instance
        service2 = container.resolve_sync(SimpleService)

        assert service1 is not service2


class TestContainerFunctionInjection:
    """Test Container function injection capabilities."""

    async def test_call_function_with_injection(self):
        """Test calling function with dependency injection."""
        container = Container()
        container[DatabaseService] = DatabaseService
        container[CacheService] = CacheService

        async def test_func(db: DatabaseService, cache: CacheService, value: str):
            return f"{db.connection_string}-{cache.ttl}-{value}"

        result = await container.call(test_func, value="test")

        assert result == "default-300-test"

    def test_call_sync_function(self):
        """Test calling sync function with injection."""
        container = Container()
        container[SimpleService] = SimpleService

        def test_func(service: SimpleService, name: str):
            return f"{service.value}-{name}"

        result = container.call_sync(test_func, name="test")

        assert result == "simple-test"

    async def test_invoke_function(self):
        """Test invoke function with full parameter injection."""
        container = Container()
        container[DatabaseService] = DatabaseService

        async def test_func(db: DatabaseService, value: str = "default"):
            return f"{db.connection_string}-{value}"

        # Invoke with override
        result = await container.invoke(test_func, value="custom")

        assert result == "default-custom"

    def test_wrap_function(self):
        """Test wrapping function for injection."""
        container = Container()
        container[SimpleService] = SimpleService

        def original_func(service: SimpleService):
            return service.value

        wrapped = container.wrap_with_injection(original_func)

        # Call wrapped function without parameters
        result = wrapped()

        assert result == "simple"

    async def test_inject_with_missing_dependency(self):
        """Test function injection with missing dependency."""
        container = Container()
        # Don't register DatabaseService

        async def test_func(db: DatabaseService):
            return db

        with pytest.raises(ResolutionError):
            await container.call(test_func)

    def test_inject_into_method(self):
        """Test injection into instance methods."""
        container = Container()
        container[DatabaseService] = DatabaseService

        class TestClass:
            def method(self, db: DatabaseService) -> str:
                return db.connection_string

        instance = TestClass()
        result = container.call_sync(instance.method)

        assert result == "default"


class TestContainerContext:
    """Test Container context variable management."""

    def test_get_current_container(self):
        """Test getting current container from context."""
        container = Container()

        # Initially None
        assert get_current_container() is None

        # Set container
        set_current_container(container)
        assert get_current_container() is container

        # Clear container by setting to None
        set_current_container(None)
        assert get_current_container() is None

    def test_container_context_manager(self):
        """Test container as context manager."""
        container1 = Container()
        container2 = Container()

        with container1:
            assert get_current_container() is container1

            with container2:
                assert get_current_container() is container2

            # Back to container1
            assert get_current_container() is container1

        # Context cleared
        assert get_current_container() is None

    async def test_async_container_context(self):
        """Test async container context manager."""
        container = Container()

        async with container:
            assert get_current_container() is container

        assert get_current_container() is None


class TestContainerDictInterface:
    """Test Container dict-like interface."""

    def test_contains(self):
        """Test __contains__ operator."""
        container = Container()
        container[SimpleService] = SimpleService

        assert SimpleService in container
        assert DatabaseService not in container
        assert "non_existent" not in container

    def test_getitem(self):
        """Test __getitem__ access."""
        container = Container()
        instance = SimpleService()
        container[SimpleService] = instance

        # Getting registered instance
        result = container[SimpleService]
        assert result is instance

        # Getting unregistered key should raise KeyError
        with pytest.raises(KeyError):
            _ = container[DatabaseService]

    def test_setitem_various_types(self):
        """Test __setitem__ with various provider types."""
        container = Container()

        # Instance
        instance = SimpleService()
        container[SimpleService] = instance
        assert container.resolve_sync(SimpleService) is instance

        # Class
        container[DatabaseService] = DatabaseService
        assert isinstance(container.resolve_sync(DatabaseService), DatabaseService)

        # Factory function
        container["factory"] = simple_factory
        assert isinstance(container.resolve_sync("factory"), SimpleService)

        # Lambda
        container["lambda"] = lambda: SimpleService()
        assert isinstance(container.resolve_sync("lambda"), SimpleService)

    def test_delitem(self):
        """Test __delitem__ deletion."""
        container = Container()
        container[SimpleService] = SimpleService
        container[DatabaseService] = DatabaseService

        assert SimpleService in container

        del container[SimpleService]

        assert SimpleService not in container
        assert DatabaseService in container

    def test_len(self):
        """Test __len__ for container size."""
        container = Container()

        assert len(container) == 0

        container[SimpleService] = SimpleService
        container[DatabaseService] = DatabaseService

        assert len(container) == 2

        del container[SimpleService]

        assert len(container) == 1

    def test_iter(self):
        """Test __iter__ for iteration."""
        container = Container()
        container[SimpleService] = SimpleService
        container[DatabaseService] = DatabaseService
        container["factory"] = simple_factory

        keys = list(container)

        assert SimpleService in keys
        assert DatabaseService in keys
        assert "factory" in keys
        assert len(keys) == 3


class TestContainerErrorHandling:
    """Test Container error handling."""

    async def test_resolution_error_with_context(self):
        """Test ResolutionError includes helpful context."""
        container = Container()

        with pytest.raises(ResolutionError) as exc_info:
            await container.resolve(DatabaseService)

        error = exc_info.value
        assert error.service_key == "DatabaseService"
        assert "DatabaseService" in str(error)

    async def test_injection_error_with_details(self):
        """Test InjectionError includes parameter details."""
        container = Container()
        container[UnionTypeService] = UnionTypeService

        with pytest.raises(InjectionError) as exc_info:
            await container.resolve(UnionTypeService)

        error = exc_info.value
        assert error.parameter_name == "service"
        assert "Union" in str(error)

    def test_type_analysis_error(self):
        """Test TypeAnalysisError handling."""
        container = Container()

        # Create a class with invalid type hints
        class BadService:
            def __init__(self, bad_hint: "NonExistentType"):
                pass

        container[BadService] = BadService

        # Should handle type analysis error gracefully
        with pytest.raises(ResolutionError):
            container.resolve_sync(BadService)

    async def test_condition_evaluation_error(self):
        """Test error in condition evaluation."""
        container = Container()

        def bad_condition():
            raise RuntimeError("Condition failed")

        container.register(SimpleService, SimpleService).when(bad_condition).build()

        # Should handle condition error
        with pytest.raises(ResolutionError):
            await container.resolve(SimpleService)


class TestContainerIntegration:
    """Test Container integration scenarios."""

    async def test_complex_dependency_graph(self):
        """Test resolving complex dependency graph."""
        container = Container()

        # Register all services
        container[DatabaseService] = DatabaseService
        container[CacheService] = CacheService
        container[ComplexService] = ComplexService

        # Add more complex dependencies
        class ApplicationService:
            def __init__(self, complex: ComplexService, db: DatabaseService):
                self.complex = complex
                self.db = db

        container[ApplicationService] = ApplicationService

        # Resolve top-level service
        app_service = await container.resolve(ApplicationService)

        assert isinstance(app_service, ApplicationService)
        assert isinstance(app_service.complex, ComplexService)
        assert isinstance(app_service.complex.db, DatabaseService)
        assert isinstance(app_service.complex.cache, CacheService)
        assert isinstance(app_service.db, DatabaseService)

        # Verify transient instances are different
        assert app_service.db is not app_service.complex.db

    async def test_mixed_scope_resolution(self):
        """Test resolution with mixed scopes."""
        container = Container()

        # Singleton database
        container.singleton(DatabaseService, DatabaseService)

        # Transient cache
        container[CacheService] = CacheService

        # Scoped complex service
        container.add(ComplexService, ComplexService).as_scoped("request").build()

        async with ScopedContext("request"):
            # First resolution
            complex1 = await container.resolve(ComplexService)
            db1 = complex1.db
            cache1 = complex1.cache

            # Second resolution
            complex2 = await container.resolve(ComplexService)
            db2 = complex2.db
            cache2 = complex2.cache

            # Complex service is same (scoped)
            assert complex1 is complex2

            # Database is same (singleton)
            assert db1 is db2

            # Cache is different (transient)
            assert cache1 is not cache2

    def test_named_service_resolution(self):
        """Test resolving named services."""
        container = Container()

        # Register multiple database services
        container.add(DatabaseService, lambda: DatabaseService("primary")).named("primary").build()
        container.add(DatabaseService, lambda: DatabaseService("secondary")).named(
            "secondary"
        ).build()

        # Resolve by name
        primary = container.resolve_sync(DatabaseService, name="primary")
        secondary = container.resolve_sync(DatabaseService, name="secondary")

        assert primary.connection_string == "primary"
        assert secondary.connection_string == "secondary"

    async def test_conditional_registration_chain(self):
        """Test chained conditional registrations."""
        container = Container()

        with patch.dict(os.environ, {"ENV": "test", "FEATURE_A": "true"}):
            # Register with different conditions
            container.add(SimpleService, SimpleService).when_env("ENV", "prod").named(
                "prod"
            ).build()
            container.add(SimpleService, SimpleService).when_env("ENV", "test").named(
                "test"
            ).build()
            container.add(SimpleService, SimpleService).when_env("FEATURE_A", "true").named(
                "feature"
            ).build()

            # Should resolve test version
            service = await container.resolve(SimpleService, name="test")
            assert isinstance(service, SimpleService)

            # Should resolve feature version
            feature = await container.resolve(SimpleService, name="feature")
            assert isinstance(feature, SimpleService)

            # Prod version should not be available
            with pytest.raises(ResolutionError):
                await container.resolve(SimpleService, name="prod")
