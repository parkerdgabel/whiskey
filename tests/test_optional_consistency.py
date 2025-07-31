"""Test Optional type consistency for Phase 4.2.

This test identifies and fixes inconsistencies in Optional type handling:
- Optional[T] should behave consistently across different contexts
- None values should be properly handled in all injection scenarios
- Optional dependencies should have consistent resolution behavior
- Error messages for Optional types should be clear and helpful
"""

from typing import Optional, Union

import pytest

from whiskey import Whiskey
from whiskey.core.analyzer import InjectDecision, TypeAnalyzer
from whiskey.core.errors import ResolutionError
from whiskey.core.registry import ComponentRegistry


# Test classes for Optional dependency scenarios
class Database:
    def __init__(self):
        self.connected = True


class Cache:
    def __init__(self):
        self.size = 100


class Logger:
    def __init__(self):
        self.level = "INFO"


class ServiceWithOptionalDep:
    """Service with optional dependency."""

    def __init__(self, db: Database, cache: Optional[Cache] = None):
        self.db = db
        self.cache = cache

    def has_cache(self) -> bool:
        return self.cache is not None


class ServiceWithMultipleOptionals:
    """Service with multiple optional dependencies."""

    def __init__(
        self, db: Database, cache: Optional[Cache] = None, logger: Optional[Logger] = None
    ):
        self.db = db
        self.cache = cache
        self.logger = logger


class ServiceWithUnionOptional:
    """Service with Union[T, None] instead of Optional[T]."""

    def __init__(self, db: Database, cache: Union[Cache, None] = None):
        self.db = db
        self.cache = cache


class ServiceWithNestedOptional:
    """Service that depends on another service with optional dependencies."""

    def __init__(self, service: ServiceWithOptionalDep):
        self.service = service


@pytest.mark.unit
class TestOptionalAnalysis:
    """Test Optional type analysis consistency."""

    def test_optional_vs_union_none_consistency(self):
        """Test that Optional[T] and Union[T, None] are handled consistently."""
        registry = ComponentRegistry()
        registry.register(Database, Database)
        analyzer = TypeAnalyzer(registry)

        # Define functions with different Optional syntax
        def func_with_optional(cache: Optional[Cache]):
            pass

        def func_with_union_none(cache: Union[Cache, None]):
            pass

        # Both should have identical analysis results
        results_optional = analyzer.analyze_callable(func_with_optional)
        results_union = analyzer.analyze_callable(func_with_union_none)

        assert "cache" in results_optional
        assert "cache" in results_union

        # Both should be OPTIONAL decisions
        assert results_optional["cache"].decision == InjectDecision.OPTIONAL
        assert results_union["cache"].decision == InjectDecision.OPTIONAL

        # Inner types should be the same
        assert results_optional["cache"].inner_type == Cache
        assert results_union["cache"].inner_type == Cache

        # Reasons should be similar
        assert "optional" in results_optional["cache"].reason.lower()
        assert "optional" in results_union["cache"].reason.lower()

    def test_optional_with_default_none(self):
        """Test Optional parameters with default None values."""
        registry = ComponentRegistry()
        registry.register(Database, Database)
        analyzer = TypeAnalyzer(registry)

        def func_with_default_none(cache: Optional[Cache] = None):
            pass

        results = analyzer.analyze_callable(func_with_default_none)

        # Should be OPTIONAL - Optional[T] = None is a special case that can still be injected
        assert results["cache"].decision == InjectDecision.OPTIONAL
        assert "optional type" in results["cache"].reason.lower()
        assert results["cache"].inner_type == Cache

    def test_optional_with_non_none_default(self):
        """Test Optional parameters with non-None default values."""
        registry = ComponentRegistry()
        registry.register(Cache, Cache)
        analyzer = TypeAnalyzer(registry)

        # Create a default Cache instance
        default_cache = Cache()

        def func_with_non_none_default(cache: Optional[Cache] = default_cache):
            pass

        results = analyzer.analyze_callable(func_with_non_none_default)

        # Should NOT inject because it has a non-None default value
        assert results["cache"].decision == InjectDecision.NO
        assert "default value" in results["cache"].reason.lower()

    def test_optional_without_default(self):
        """Test Optional parameters without default values."""
        registry = ComponentRegistry()
        registry.register(Database, Database)
        analyzer = TypeAnalyzer(registry)

        def func_without_default(cache: Optional[Cache]):
            pass

        results = analyzer.analyze_callable(func_without_default)

        # Should be OPTIONAL (inject if available)
        assert results["cache"].decision == InjectDecision.OPTIONAL
        assert results["cache"].inner_type == Cache

    def test_optional_registered_vs_unregistered(self):
        """Test Optional behavior with registered vs unregistered types."""
        registry = ComponentRegistry()
        registry.register(Database, Database)
        registry.register(Cache, Cache)
        # Logger is not registered

        analyzer = TypeAnalyzer(registry)

        def func_with_optionals(cache: Optional[Cache], logger: Optional[Logger]):
            pass

        results = analyzer.analyze_callable(func_with_optionals)

        # Both should be OPTIONAL regardless of registration status
        assert results["cache"].decision == InjectDecision.OPTIONAL
        assert results["logger"].decision == InjectDecision.OPTIONAL

        # Inner types should be correct
        assert results["cache"].inner_type == Cache
        assert results["logger"].inner_type == Logger


@pytest.mark.unit
class TestOptionalResolution:
    """Test Optional type resolution consistency."""

    def test_optional_with_registered_dependency(self):
        """Test resolution when Optional dependency is registered."""
        app = Whiskey()

        # Register required and optional dependencies
        app.singleton(Database)
        app.singleton(Cache)
        app.component(ServiceWithOptionalDep)

        # Should resolve with both dependencies
        service = app.resolve(ServiceWithOptionalDep)
        assert isinstance(service, ServiceWithOptionalDep)
        assert isinstance(service.db, Database)
        assert isinstance(service.cache, Cache)
        assert service.has_cache() is True

    def test_optional_with_unregistered_dependency(self):
        """Test resolution when Optional dependency is not registered."""
        app = Whiskey()

        # Register only required dependency, not optional one
        app.singleton(Database)
        app.component(ServiceWithOptionalDep)

        # Should resolve with None for optional dependency
        service = app.resolve(ServiceWithOptionalDep)
        assert isinstance(service, ServiceWithOptionalDep)
        assert isinstance(service.db, Database)
        assert service.cache is None
        assert service.has_cache() is False

    def test_multiple_optional_dependencies(self):
        """Test resolution with multiple optional dependencies."""
        app = Whiskey()

        # Register required and one optional dependency
        app.singleton(Database)
        app.singleton(Cache)
        # Logger not registered
        app.component(ServiceWithMultipleOptionals)

        service = app.resolve(ServiceWithMultipleOptionals)
        assert isinstance(service, ServiceWithMultipleOptionals)
        assert isinstance(service.db, Database)
        assert isinstance(service.cache, Cache)
        assert service.logger is None

    def test_union_none_resolution_consistency(self):
        """Test that Union[T, None] resolves consistently with Optional[T]."""
        app = Whiskey()

        # Test both services with same registration
        app.singleton(Database)
        app.singleton(Cache)
        app.component(ServiceWithOptionalDep)
        app.component(ServiceWithUnionOptional)

        optional_service = app.resolve(ServiceWithOptionalDep)
        union_service = app.resolve(ServiceWithUnionOptional)

        # Both should have the same behavior
        assert isinstance(optional_service.cache, Cache)
        assert isinstance(union_service.cache, Cache)
        assert type(optional_service.cache) == type(union_service.cache)

    def test_nested_optional_resolution(self):
        """Test resolution of services that depend on other services with optionals."""
        app = Whiskey()

        app.singleton(Database)
        app.singleton(Cache)
        app.component(ServiceWithOptionalDep)
        app.component(ServiceWithNestedOptional)

        nested_service = app.resolve(ServiceWithNestedOptional)
        assert isinstance(nested_service, ServiceWithNestedOptional)
        assert isinstance(nested_service.service, ServiceWithOptionalDep)
        assert isinstance(nested_service.service.cache, Cache)

    def test_optional_factory_consistency(self):
        """Test Optional consistency with factory functions."""
        app = Whiskey()

        app.singleton(Database)

        def create_service_with_optional(
            db: Database, cache: Optional[Cache] = None
        ) -> ServiceWithOptionalDep:
            return ServiceWithOptionalDep(db, cache)

        app.factory(ServiceWithOptionalDep, create_service_with_optional)

        # Should resolve successfully with None for cache
        service = app.resolve(ServiceWithOptionalDep)
        assert isinstance(service, ServiceWithOptionalDep)
        assert isinstance(service.db, Database)
        assert service.cache is None


@pytest.mark.unit
class TestOptionalErrorHandling:
    """Test error handling consistency for Optional types."""

    def test_optional_circular_dependency_error(self):
        """Test error handling for circular dependencies involving Optional types."""
        app = Whiskey()

        # Create circular dependency with Optional
        class ServiceA:
            def __init__(self, b: Optional["ServiceB"] = None):
                self.b = b

        class ServiceB:
            def __init__(self, a: ServiceA):
                self.a = a

        app.component(ServiceA)
        app.component(ServiceB)

        # Should handle gracefully - Optional breaks the required cycle
        service_a = app.resolve(ServiceA)
        assert isinstance(service_a, ServiceA)
        # ServiceB would fail on its own due to circular dependency to ServiceA
        # But ServiceA should resolve with b=None since it's optional

    def test_optional_resolution_error_messages(self):
        """Test that error messages for Optional types are clear."""
        app = Whiskey()

        # Service with required dependency that can't be resolved
        class ServiceWithBadDep:
            def __init__(self, missing: Database, optional: Optional[Cache] = None):
                self.missing = missing
                self.optional = optional

        app.component(ServiceWithBadDep)

        # Should get clear error about missing required dependency
        with pytest.raises(ResolutionError) as exc_info:
            app.resolve(ServiceWithBadDep)

        error_msg = str(exc_info.value)
        # Error should mention the required dependency, not the optional one
        assert "Database" in error_msg
        # Should not complain about Cache since it's optional
        assert "Cache" not in error_msg or "optional" in error_msg.lower()


@pytest.mark.unit
class TestOptionalAsyncConsistency:
    """Test Optional type consistency in async contexts."""

    @pytest.mark.asyncio
    async def test_async_optional_resolution(self):
        """Test Optional resolution in async context."""
        app = Whiskey()

        app.singleton(Database)
        app.component(ServiceWithOptionalDep)

        # Should work the same in async context
        service = await app.resolve_async(ServiceWithOptionalDep)
        assert isinstance(service, ServiceWithOptionalDep)
        assert isinstance(service.db, Database)
        assert service.cache is None

    @pytest.mark.asyncio
    async def test_async_optional_with_registered_dependency(self):
        """Test async Optional resolution when dependency is registered."""
        app = Whiskey()

        app.singleton(Database)
        app.singleton(Cache)
        app.component(ServiceWithOptionalDep)

        service = await app.resolve_async(ServiceWithOptionalDep)
        assert isinstance(service, ServiceWithOptionalDep)
        assert isinstance(service.cache, Cache)


@pytest.mark.unit
class TestOptionalEdgeCases:
    """Test edge cases in Optional type handling."""

    def test_optional_generic_types(self):
        """Test Optional with generic types."""

        registry = ComponentRegistry()
        analyzer = TypeAnalyzer(registry)

        def func_with_optional_generics(
            items: Optional[list[str]] = None, mapping: Optional[dict[str, int]] = None
        ):
            pass

        results = analyzer.analyze_callable(func_with_optional_generics)

        # Should not inject generic types even when Optional
        assert results["items"].decision == InjectDecision.NO
        assert results["mapping"].decision == InjectDecision.NO
        assert "non-injectable inner type" in results["items"].reason.lower()
        assert "generic" in results["items"].reason.lower()

    def test_optional_protocol_types(self):
        """Test Optional with Protocol types."""
        from typing import Protocol

        class Readable(Protocol):
            def read(self) -> str: ...

        registry = ComponentRegistry()
        analyzer = TypeAnalyzer(registry)

        def func_with_optional_protocol(reader: Optional[Readable]):
            pass

        results = analyzer.analyze_callable(func_with_optional_protocol)

        # Should be OPTIONAL
        assert results["reader"].decision == InjectDecision.OPTIONAL
        assert results["reader"].inner_type == Readable

    def test_deeply_nested_optional(self):
        """Test deeply nested Optional types."""

        registry = ComponentRegistry()
        analyzer = TypeAnalyzer(registry)

        # This is probably not a real use case, but let's test it
        def func_with_nested_optional(data: Optional[Optional[Cache]]):
            pass

        results = analyzer.analyze_callable(func_with_nested_optional)

        # Should handle gracefully - treat as Optional[Optional[Cache]]
        # The analyzer should unwrap to the innermost non-None type
        assert results["data"].decision == InjectDecision.OPTIONAL


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
