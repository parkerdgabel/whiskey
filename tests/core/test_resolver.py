"""Tests for the unified resolver system."""

import asyncio
import threading
from typing import Optional

import pytest

from whiskey.core.errors import CircularDependencyError, ResolutionError, ScopeError
from whiskey.core.registry import ComponentRegistry, Scope
from whiskey.core.resolver import (
    AsyncResolver,
    DependencyResolver,
    ResolutionContext,
    ScopeResolver,
    TypeResolver,
    UnifiedResolver,
    create_resolver,
)


# Test fixtures and classes
class Database:
    """Test database class."""

    def __init__(self):
        self.connected = True


class Cache:
    """Test cache class."""

    def __init__(self):
        self.data = {}


class Service:
    """Test service with dependencies."""

    def __init__(self, db: Database, cache: Optional[Cache] = None):
        self.db = db
        self.cache = cache


class CircularA:
    """Class with circular dependency."""

    def __init__(self, b: "CircularB"):
        self.b = b


class CircularB:
    """Class with circular dependency."""

    def __init__(self, a: CircularA):
        self.a = a


async def async_factory() -> Database:
    """Async factory function."""
    await asyncio.sleep(0.001)
    return Database()


@pytest.mark.unit
class TestTypeResolver:
    """Test the TypeResolver component."""

    def test_analyze_type_basic(self):
        """Test basic type analysis."""
        registry = ComponentRegistry()
        registry.register(Database, Database)

        resolver = TypeResolver(registry)

        # Analyze registered type
        result = resolver.analyze_type(Database)
        assert result.decision.value == "inject"
        assert result.type_hint == Database

        # Analyze unregistered type
        result = resolver.analyze_type(Cache)
        assert result.decision.value == "skip"

    def test_analyze_type_optional(self):
        """Test Optional type analysis."""
        registry = ComponentRegistry()
        resolver = TypeResolver(registry)

        result = resolver.analyze_type(Optional[Database])
        assert result.decision.value == "optional"
        assert result.inner_type == Database

    def test_analyze_callable(self):
        """Test callable analysis."""
        registry = ComponentRegistry()
        registry.register(Database, Database)

        resolver = TypeResolver(registry)
        results = resolver.analyze_callable(Service.__init__)

        assert "db" in results
        assert results["db"].decision.value == "inject"
        assert "cache" in results
        assert results["cache"].decision.value == "optional"

    def test_generic_type_resolution(self):
        """Test generic type resolution."""
        from typing import Generic, List, TypeVar

        T = TypeVar("T")

        class Repository(Generic[T]):
            pass

        class UserRepository(Repository[str]):
            pass

        registry = ComponentRegistry()
        resolver = TypeResolver(registry)

        # Register generic implementation
        resolver.register_generic_implementation(Repository[str], UserRepository)

        # Resolve generic
        concrete = resolver.resolve_generic(Repository[str])
        assert concrete == UserRepository

    def test_can_auto_create(self):
        """Test auto-creation checking."""
        registry = ComponentRegistry()
        registry.register(Database, Database)

        resolver = TypeResolver(registry)

        # Can auto-create because dependency is registered
        assert resolver.can_auto_create(Service)

        # Cannot auto-create due to circular dependency
        assert not resolver.can_auto_create(CircularA)


@pytest.mark.unit
class TestDependencyResolver:
    """Test the DependencyResolver component."""

    def test_resolve_dependencies(self):
        """Test dependency resolution."""
        registry = ComponentRegistry()
        registry.register(Database, Database)

        type_resolver = TypeResolver(registry)
        dep_resolver = DependencyResolver(registry, type_resolver)

        # Resolve dependencies for Service
        deps = dep_resolver.resolve_dependencies(Service, {})

        assert "db" in deps
        assert deps["db"] == Database
        assert "cache" in deps
        assert isinstance(deps["cache"], tuple)  # Optional marked as tuple
        assert deps["cache"] == (Cache, True)

    def test_resolve_dependencies_with_overrides(self):
        """Test dependency resolution with overrides."""
        registry = ComponentRegistry()
        type_resolver = TypeResolver(registry)
        dep_resolver = DependencyResolver(registry, type_resolver)

        custom_db = Database()
        deps = dep_resolver.resolve_dependencies(Service, {"db": custom_db})

        assert "db" in deps
        assert deps["db"] is custom_db

    def test_create_instance_class(self):
        """Test instance creation from class."""
        registry = ComponentRegistry()
        type_resolver = TypeResolver(registry)
        dep_resolver = DependencyResolver(registry, type_resolver)

        db = Database()
        instance = dep_resolver.create_instance(Service, {"db": db, "cache": None})

        assert isinstance(instance, Service)
        assert instance.db is db
        assert instance.cache is None

    def test_create_instance_factory(self):
        """Test instance creation from factory."""
        registry = ComponentRegistry()
        type_resolver = TypeResolver(registry)
        dep_resolver = DependencyResolver(registry, type_resolver)

        def factory(db: Database) -> Service:
            return Service(db)

        db = Database()
        instance = dep_resolver.create_instance(factory, {"db": db})

        assert isinstance(instance, Service)
        assert instance.db is db

    def test_circular_dependency_detection(self):
        """Test circular dependency detection."""
        registry = ComponentRegistry()
        type_resolver = TypeResolver(registry)
        dep_resolver = DependencyResolver(registry, type_resolver)

        # Add to resolving stack
        stack = dep_resolver.get_resolving_stack()
        stack.add("ServiceA")

        # Check if already resolving
        assert "ServiceA" in stack

        # Clear stack
        stack.clear()
        assert len(stack) == 0


@pytest.mark.unit
class TestScopeResolver:
    """Test the ScopeResolver component."""

    def test_singleton_resolution(self):
        """Test singleton resolution with thread safety."""
        resolver = ScopeResolver()

        call_count = 0

        def factory():
            nonlocal call_count
            call_count += 1
            return Database()

        # First call creates instance
        instance1 = resolver.resolve_singleton("db", factory)
        assert call_count == 1

        # Second call returns cached instance
        instance2 = resolver.resolve_singleton("db", factory)
        assert call_count == 1
        assert instance1 is instance2

    def test_singleton_thread_safety(self):
        """Test thread-safe singleton creation."""
        resolver = ScopeResolver()
        instances = []
        barrier = threading.Barrier(5)

        def factory():
            barrier.wait()  # Ensure all threads start together
            return Database()

        def resolve_in_thread():
            instance = resolver.resolve_singleton("db", factory)
            instances.append(instance)

        threads = [threading.Thread(target=resolve_in_thread) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All threads should get the same instance
        assert len(set(id(inst) for inst in instances)) == 1

    def test_scoped_resolution(self):
        """Test scoped instance resolution."""
        resolver = ScopeResolver()
        active_scopes = {"request": {}}

        def factory():
            return Database()

        # Resolve in scope
        instance1 = resolver.resolve_scoped("db", "request", factory, active_scopes)
        instance2 = resolver.resolve_scoped("db", "request", factory, active_scopes)

        assert instance1 is instance2

        # Different scope gets different instance
        active_scopes["session"] = {}
        instance3 = resolver.resolve_scoped("db", "session", factory, active_scopes)

        assert instance3 is not instance1

    def test_scoped_resolution_no_active_scope(self):
        """Test scoped resolution when scope is not active."""
        resolver = ScopeResolver()

        def factory():
            return Database()

        with pytest.raises(ScopeError, match="Scope 'request' is not active"):
            resolver.resolve_scoped("db", "request", factory, None)

    def test_clear_scope(self):
        """Test clearing a scope."""
        resolver = ScopeResolver()
        active_scopes = {"request": {}}

        def factory():
            return Database()

        # Create scoped instance
        instance = resolver.resolve_scoped("db", "request", factory, active_scopes)
        assert instance is not None

        # Clear scope
        resolver.clear_scope("request")

        # New resolution creates new instance
        instance2 = resolver.resolve_scoped("db", "request", factory, active_scopes)
        assert instance2 is not instance


@pytest.mark.unit
class TestAsyncResolver:
    """Test the AsyncResolver component."""

    def test_is_async_context(self):
        """Test async context detection."""
        # Not in async context
        assert not AsyncResolver.is_async_context()

        # In async context
        async def check_async():
            return AsyncResolver.is_async_context()

        assert asyncio.run(check_async())

    def test_require_sync_context(self):
        """Test sync context requirement."""
        # Should not raise in sync context
        AsyncResolver.require_sync_context("test", Database)

        # Should raise in async context
        async def check_async():
            AsyncResolver.require_sync_context("test", Database)

        with pytest.raises(RuntimeError, match="Cannot perform synchronous"):
            asyncio.run(check_async())

    def test_check_async_provider(self):
        """Test async provider checking."""
        # Sync provider should not raise
        AsyncResolver.check_async_provider(Database, Database)

        # Async provider should raise
        with pytest.raises(RuntimeError, match="async factory"):
            AsyncResolver.check_async_provider(async_factory, Database)


@pytest.mark.unit
class TestUnifiedResolver:
    """Test the UnifiedResolver integration."""

    def test_basic_resolution(self):
        """Test basic component resolution."""
        registry = ComponentRegistry()
        registry.register(Database, Database)

        resolver = create_resolver(registry)
        instance = resolver._resolve_sync(Database)

        assert isinstance(instance, Database)

    def test_resolution_with_dependencies(self):
        """Test resolution with dependency injection."""
        registry = ComponentRegistry()
        registry.register(Database, Database)
        registry.register(Cache, Cache)
        registry.register(Service, Service)

        resolver = create_resolver(registry)
        instance = resolver._resolve_sync(Service)

        assert isinstance(instance, Service)
        assert isinstance(instance.db, Database)
        assert isinstance(instance.cache, Cache)

    def test_optional_dependency_resolution(self):
        """Test optional dependency resolution."""
        registry = ComponentRegistry()
        registry.register(Database, Database)
        registry.register(Service, Service)
        # Cache not registered

        resolver = create_resolver(registry)
        instance = resolver._resolve_sync(Service)

        assert isinstance(instance, Service)
        assert isinstance(instance.db, Database)
        assert instance.cache is None

    def test_singleton_scope_resolution(self):
        """Test singleton scope resolution."""
        registry = ComponentRegistry()
        registry.register(Database, Database, scope=Scope.SINGLETON)

        resolver = create_resolver(registry)

        instance1 = resolver._resolve_sync(Database)
        instance2 = resolver._resolve_sync(Database)

        assert instance1 is instance2

    def test_circular_dependency_detection(self):
        """Test circular dependency detection."""
        registry = ComponentRegistry()
        registry.register(CircularA, CircularA)
        registry.register(CircularB, CircularB)

        resolver = create_resolver(registry)

        with pytest.raises(CircularDependencyError):
            resolver._resolve_sync(CircularA)

    def test_auto_creation(self):
        """Test auto-creation of unregistered types."""
        registry = ComponentRegistry()
        registry.register(Database, Database)
        # Service not registered, but dependencies are

        resolver = create_resolver(registry)
        instance = resolver._resolve_sync(Service)

        assert isinstance(instance, Service)
        assert isinstance(instance.db, Database)

    def test_resolution_with_overrides(self):
        """Test resolution with dependency overrides."""
        registry = ComponentRegistry()
        registry.register(Service, Service)

        resolver = create_resolver(registry)
        custom_db = Database()

        instance = resolver._resolve_sync(Service, overrides={"db": custom_db})

        assert isinstance(instance, Service)
        assert instance.db is custom_db

    @pytest.mark.asyncio
    async def test_async_resolution(self):
        """Test asynchronous resolution."""
        registry = ComponentRegistry()
        registry.register(Database, async_factory)

        resolver = create_resolver(registry)
        instance = await resolver._resolve_async(Database)

        assert isinstance(instance, Database)

    def test_smart_resolution_sync_context(self):
        """Test smart resolution in sync context."""
        registry = ComponentRegistry()
        registry.register(Database, Database)

        resolver = create_resolver(registry)
        result = resolver.resolve(Database)

        # In sync context, should return instance directly
        assert isinstance(result, Database)

    @pytest.mark.asyncio
    async def test_smart_resolution_async_context(self):
        """Test smart resolution in async context."""
        registry = ComponentRegistry()
        registry.register(Database, Database)

        resolver = create_resolver(registry)
        result = resolver.resolve(Database)

        # In async context, should return coroutine
        assert asyncio.iscoroutine(result)
        instance = await result
        assert isinstance(instance, Database)

    def test_context_preservation(self):
        """Test that resolution context is properly preserved."""
        registry = ComponentRegistry()

        def factory(**kwargs):
            # Factory should receive scope context
            return kwargs.get("scope_context", {})

        registry.register("test", factory)

        resolver = create_resolver(registry)
        context = {"custom": "value"}

        result = resolver._resolve_sync("test", scope_context=context)
        assert result == context


if __name__ == "__main__":
    pytest.main([__file__, "-v"])