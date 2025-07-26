"""Tests for the ServiceRegistry and ServiceDescriptor classes.

This module tests the service registration and metadata management system.
"""

import os

import pytest

from whiskey.core.errors import RegistrationError
from whiskey.core.registry import Scope, ServiceDescriptor, ServiceRegistry


# Test classes
class TestService:
    def __init__(self):
        self.value = "test"


class DatabaseService:
    def __init__(self, connection_string: str = "default"):
        self.connection_string = connection_string


class CacheService:
    def __init__(self):
        self.data = {}


def test_factory() -> TestService:
    """Test factory function."""
    return TestService()


async def async_test_factory() -> TestService:
    """Async test factory function."""
    return TestService()


class TestServiceDescriptor:
    """Test the ServiceDescriptor class."""

    def test_descriptor_creation(self):
        """Test creating a ServiceDescriptor."""
        descriptor = ServiceDescriptor(
            key="test_service",
            service_type=TestService,
            provider=TestService,
            scope=Scope.SINGLETON,
            name="primary",
            tags={"core", "test"},
            condition=lambda: True,
            lazy=True,
            metadata={"version": "1.0"},
        )

        assert descriptor.key == "test_service"
        assert descriptor.service_type == TestService
        assert descriptor.provider == TestService
        assert descriptor.scope == Scope.SINGLETON
        assert descriptor.name == "primary"
        assert descriptor.tags == {"core", "test"}
        assert descriptor.condition() is True
        assert descriptor.lazy is True
        assert descriptor.metadata == {"version": "1.0"}

    def test_descriptor_defaults(self):
        """Test ServiceDescriptor with default values."""
        descriptor = ServiceDescriptor(
            key="test_service", service_type=TestService, provider=TestService
        )

        assert descriptor.scope == Scope.TRANSIENT
        assert descriptor.name is None
        assert descriptor.tags == set()
        assert descriptor.condition is None
        assert descriptor.lazy is False
        assert descriptor.metadata == {}

    def test_is_factory_detection(self):
        """Test detection of factory vs class providers."""
        # Class provider
        class_descriptor = ServiceDescriptor(
            key="test_service", service_type=TestService, provider=TestService
        )
        assert not class_descriptor.is_factory

        # Function provider
        function_descriptor = ServiceDescriptor(
            key="test_service", service_type=TestService, provider=test_factory
        )
        assert function_descriptor.is_factory

        # Instance provider
        instance_descriptor = ServiceDescriptor(
            key="test_service", service_type=TestService, provider=TestService()
        )
        assert not instance_descriptor.is_factory

    def test_matches_condition_no_condition(self):
        """Test condition matching when no condition is set."""
        descriptor = ServiceDescriptor(
            key="test_service", service_type=TestService, provider=TestService
        )
        assert descriptor.matches_condition() is True

    def test_matches_condition_with_condition(self):
        """Test condition matching with various conditions."""
        # True condition
        true_descriptor = ServiceDescriptor(
            key="test_service",
            service_type=TestService,
            provider=TestService,
            condition=lambda: True,
        )
        assert true_descriptor.matches_condition() is True

        # False condition
        false_descriptor = ServiceDescriptor(
            key="test_service",
            service_type=TestService,
            provider=TestService,
            condition=lambda: False,
        )
        assert false_descriptor.matches_condition() is False

    def test_matches_condition_exception_handling(self):
        """Test condition matching with exception in condition."""

        def failing_condition():
            raise ValueError("Test error")

        descriptor = ServiceDescriptor(
            key="test_service",
            service_type=TestService,
            provider=TestService,
            condition=failing_condition,
        )

        # Should return False if condition throws exception
        assert descriptor.matches_condition() is False

    def test_has_tag(self):
        """Test tag checking functionality."""
        descriptor = ServiceDescriptor(
            key="test_service",
            service_type=TestService,
            provider=TestService,
            tags={"core", "database", "important"},
        )

        assert descriptor.has_tag("core")
        assert descriptor.has_tag("database")
        assert descriptor.has_tag("important")
        assert not descriptor.has_tag("cache")
        assert not descriptor.has_tag("optional")

    def test_has_any_tag(self):
        """Test checking for any of multiple tags."""
        descriptor = ServiceDescriptor(
            key="test_service",
            service_type=TestService,
            provider=TestService,
            tags={"core", "database"},
        )

        assert descriptor.has_any_tag({"core"})
        assert descriptor.has_any_tag({"database"})
        assert descriptor.has_any_tag({"core", "cache"})
        assert descriptor.has_any_tag({"database", "optional"})
        assert not descriptor.has_any_tag({"cache", "optional"})
        assert not descriptor.has_any_tag(set())

    def test_has_all_tags(self):
        """Test checking for all of multiple tags."""
        descriptor = ServiceDescriptor(
            key="test_service",
            service_type=TestService,
            provider=TestService,
            tags={"core", "database", "important"},
        )

        assert descriptor.has_all_tags({"core"})
        assert descriptor.has_all_tags({"core", "database"})
        assert descriptor.has_all_tags({"core", "database", "important"})
        assert not descriptor.has_all_tags({"core", "cache"})
        assert not descriptor.has_all_tags({"database", "optional"})
        assert descriptor.has_all_tags(set())  # Empty set returns True

    def test_string_representation(self):
        """Test string representation of ServiceDescriptor."""
        descriptor = ServiceDescriptor(
            key="test_service",
            service_type=TestService,
            provider=TestService,
            scope=Scope.SINGLETON,
            name="primary",
        )

        str_repr = str(descriptor)
        assert "test_service" in str_repr
        assert "TestService" in str_repr
        assert "SINGLETON" in str_repr

    def test_equality(self):
        """Test ServiceDescriptor equality comparison."""
        descriptor1 = ServiceDescriptor(
            key="test_service",
            service_type=TestService,
            provider=TestService,
            scope=Scope.SINGLETON,
        )

        descriptor2 = ServiceDescriptor(
            key="test_service",
            service_type=TestService,
            provider=TestService,
            scope=Scope.SINGLETON,
        )

        descriptor3 = ServiceDescriptor(
            key="other_service",
            service_type=TestService,
            provider=TestService,
            scope=Scope.SINGLETON,
        )

        assert descriptor1 == descriptor2
        assert descriptor1 != descriptor3


class TestServiceRegistry:
    """Test the ServiceRegistry class."""

    @pytest.fixture
    def registry(self):
        """Create a fresh registry for testing."""
        return ServiceRegistry()

    def test_registry_initialization(self, registry):
        """Test registry initialization."""
        assert len(registry) == 0
        assert registry._services == {}
        assert registry._type_index == {}
        assert registry._tag_index == {}

    def test_register_basic_service(self, registry):
        """Test basic service registration."""
        descriptor = registry.register(key=TestService, provider=TestService, scope=Scope.SINGLETON)

        assert descriptor.key == "TestService"
        assert descriptor.service_type == TestService
        assert descriptor.provider == TestService
        assert descriptor.scope == Scope.SINGLETON
        assert len(registry) == 1

    def test_register_with_string_key(self, registry):
        """Test service registration with string key."""
        descriptor = registry.register(
            key="database", provider=DatabaseService, scope=Scope.SINGLETON
        )

        assert descriptor.key == "database"
        assert descriptor.service_type == DatabaseService
        assert len(registry) == 1

    def test_register_with_name(self, registry):
        """Test service registration with name."""
        descriptor = registry.register(
            key=DatabaseService, provider=DatabaseService, name="primary", scope=Scope.SINGLETON
        )

        assert descriptor.name == "primary"
        # Key should include the name
        assert "primary" in descriptor.key
        assert len(registry) == 1

    def test_register_factory_function(self, registry):
        """Test registering factory functions."""
        descriptor = registry.register(
            key="test_service", provider=test_factory, scope=Scope.TRANSIENT
        )

        assert descriptor.is_factory
        assert descriptor.provider == test_factory
        # Service type should be inferred from return type
        assert descriptor.service_type == TestService

    def test_register_async_factory(self, registry):
        """Test registering async factory functions."""
        descriptor = registry.register(
            key="async_test", provider=async_test_factory, scope=Scope.TRANSIENT
        )

        assert descriptor.is_factory
        assert descriptor.provider == async_test_factory

    def test_register_instance(self, registry):
        """Test registering service instances."""
        instance = TestService()
        descriptor = registry.register(
            key="test_instance", provider=instance, scope=Scope.SINGLETON
        )

        assert descriptor.provider is instance
        assert not descriptor.is_factory
        assert descriptor.service_type == TestService

    def test_register_with_tags(self, registry):
        """Test service registration with tags."""
        descriptor = registry.register(
            key=DatabaseService,
            provider=DatabaseService,
            tags={"database", "core", "infrastructure"},
        )

        assert descriptor.tags == {"database", "core", "infrastructure"}

        # Check tag index
        for tag in descriptor.tags:
            assert tag in registry._tag_index
            assert descriptor.key in registry._tag_index[tag]

    def test_register_with_condition(self, registry):
        """Test service registration with condition."""
        condition = lambda: os.getenv("TESTING") == "true"

        descriptor = registry.register(key=TestService, provider=TestService, condition=condition)

        assert descriptor.condition is condition

    def test_register_duplicate_key_error(self, registry):
        """Test that duplicate registration raises error."""
        registry.register(key="test", provider=TestService)

        with pytest.raises(RegistrationError):
            registry.register(key="test", provider=DatabaseService)

    def test_register_with_metadata(self, registry):
        """Test service registration with metadata."""
        metadata = {"version": "2.0", "author": "test"}

        descriptor = registry.register(key=TestService, provider=TestService, metadata=metadata)

        assert descriptor.metadata == metadata

    def test_get_service(self, registry):
        """Test getting registered services."""
        registry.register(key=TestService, provider=TestService)

        descriptor = registry.get(TestService)
        assert descriptor.service_type == TestService

        # Test with string key
        descriptor2 = registry.get("TestService")
        assert descriptor2 is descriptor

    def test_get_service_with_name(self, registry):
        """Test getting named services."""
        registry.register(key=DatabaseService, provider=DatabaseService, name="primary")

        registry.register(key=DatabaseService, provider=DatabaseService, name="secondary")

        primary = registry.get(DatabaseService, name="primary")
        secondary = registry.get(DatabaseService, name="secondary")

        assert primary.name == "primary"
        assert secondary.name == "secondary"
        assert primary is not secondary

    def test_get_nonexistent_service(self, registry):
        """Test getting non-existent service raises KeyError."""
        with pytest.raises(KeyError):
            registry.get("nonexistent")

        with pytest.raises(KeyError):
            registry.get(TestService)

    def test_has_service(self, registry):
        """Test checking if service exists."""
        assert not registry.has(TestService)
        assert not registry.has("test")

        registry.register(key=TestService, provider=TestService)

        assert registry.has(TestService)
        assert registry.has("TestService")

    def test_has_service_with_name(self, registry):
        """Test checking named service existence."""
        registry.register(key=DatabaseService, provider=DatabaseService, name="primary")

        assert registry.has(DatabaseService, name="primary")
        assert not registry.has(DatabaseService, name="secondary")
        assert not registry.has(DatabaseService)  # Without name

    def test_remove_service(self, registry):
        """Test removing registered services."""
        registry.register(key=TestService, provider=TestService)
        assert registry.has(TestService)

        removed = registry.remove(TestService)
        assert removed is True
        assert not registry.has(TestService)
        assert len(registry) == 0

    def test_remove_nonexistent_service(self, registry):
        """Test removing non-existent service."""
        removed = registry.remove("nonexistent")
        assert removed is False

    def test_remove_service_with_tags(self, registry):
        """Test that removing service also removes from tag index."""
        registry.register(key=TestService, provider=TestService, tags={"test", "core"})

        # Check tag index is populated
        assert "test" in registry._tag_index
        assert "core" in registry._tag_index

        registry.remove(TestService)

        # Check tag index is cleaned up
        assert "TestService" not in registry._tag_index.get("test", set())
        assert "TestService" not in registry._tag_index.get("core", set())

    def test_list_all_services(self, registry):
        """Test listing all registered services."""
        registry.register(key=TestService, provider=TestService)
        registry.register(key=DatabaseService, provider=DatabaseService)
        registry.register(key="cache", provider=CacheService)

        all_services = registry.list_all()
        assert len(all_services) == 3

        keys = {desc.key for desc in all_services}
        assert keys == {"TestService", "DatabaseService", "cache"}

    def test_find_by_type(self, registry):
        """Test finding services by type."""
        registry.register(key="test1", provider=TestService)
        registry.register(key="test2", provider=TestService)
        registry.register(key="db", provider=DatabaseService)

        test_services = registry.find_by_type(TestService)
        assert len(test_services) == 2

        db_services = registry.find_by_type(DatabaseService)
        assert len(db_services) == 1

        cache_services = registry.find_by_type(CacheService)
        assert len(cache_services) == 0

    def test_find_by_tag(self, registry):
        """Test finding services by tag."""
        registry.register(key="test1", provider=TestService, tags={"core", "test"})
        registry.register(key="test2", provider=TestService, tags={"core", "experimental"})
        registry.register(key="db", provider=DatabaseService, tags={"database", "infrastructure"})

        core_services = registry.find_by_tag("core")
        assert len(core_services) == 2

        db_services = registry.find_by_tag("database")
        assert len(db_services) == 1

        missing_services = registry.find_by_tag("nonexistent")
        assert len(missing_services) == 0

    def test_find_multiple_services_by_tag(self, registry):
        """Test finding multiple services that share tags."""
        registry.register(key="test1", provider=TestService, tags={"core", "test", "stable"})
        registry.register(key="test2", provider=TestService, tags={"core", "experimental"})
        registry.register(key="db", provider=DatabaseService, tags={"database", "core", "stable"})

        # Find services with "core" tag
        core_services = registry.find_by_tag("core")
        assert len(core_services) == 3  # All have core tag

        # Find services with "stable" tag
        stable_services = registry.find_by_tag("stable")
        assert len(stable_services) == 2  # test1 and db

        # Find services with unique tag
        db_services = registry.find_by_tag("database")
        assert len(db_services) == 1  # Only db

    def test_clear_registry(self, registry):
        """Test clearing the entire registry."""
        registry.register(key=TestService, provider=TestService)
        registry.register(key=DatabaseService, provider=DatabaseService)

        assert len(registry) == 2

        registry.clear()

        assert len(registry) == 0
        assert registry._services == {}
        assert registry._type_index == {}
        assert registry._tag_index == {}

    def test_iteration(self, registry):
        """Test iterating over registry."""
        registry.register(key="test1", provider=TestService)
        registry.register(key="test2", provider=DatabaseService)

        keys = list(registry)
        assert len(keys) == 2
        assert "test1" in keys
        assert "test2" in keys

    def test_contains_operator(self, registry):
        """Test 'in' operator for registry."""
        registry.register(key=TestService, provider=TestService)

        assert TestService in registry
        assert "TestService" in registry
        assert DatabaseService not in registry
        assert "nonexistent" not in registry

    def test_key_normalization(self, registry):
        """Test that keys are properly normalized."""
        # Type keys should become string keys
        registry.register(key=TestService, provider=TestService)

        # Both should work
        assert registry.has(TestService)
        assert registry.has("TestService")  # Key is normalized to lowercase

        # Check internal storage uses normalized string
        assert "TestService" in registry._services

    def test_key_normalization_with_name(self, registry):
        """Test key normalization with names."""
        registry.register(key=TestService, provider=TestService, name="primary")

        normalized_key = registry._normalize_key(TestService, "primary")
        assert normalized_key in registry._services

        # Should be able to retrieve with both type and name
        descriptor = registry.get(TestService, name="primary")
        assert descriptor.name == "primary"

    def test_conditional_registration_filtering(self, registry):
        """Test that conditional services are filtered correctly."""
        # Always true condition
        registry.register(key="always", provider=TestService, condition=lambda: True)

        # Always false condition
        registry.register(key="never", provider=TestService, condition=lambda: False)

        # Environment-based condition
        registry.register(
            key="env_based",
            provider=TestService,
            condition=lambda: os.getenv("TEST_ENV") == "active",
        )

        # Test has() with conditions
        assert registry.has("always")
        assert not registry.has("never")

        # Set environment and test again
        os.environ["TEST_ENV"] = "active"
        assert registry.has("env_based")

        # Clean up
        os.environ.pop("TEST_ENV", None)
        assert not registry.has("env_based")


class TestScope:
    """Test the Scope enum."""

    def test_scope_values(self):
        """Test that all expected scope values exist."""
        assert Scope.SINGLETON
        assert Scope.TRANSIENT
        assert Scope.SCOPED

    def test_scope_string_representation(self):
        """Test string representation of scopes."""
        assert str(Scope.SINGLETON) == "Scope.SINGLETON"
        assert str(Scope.TRANSIENT) == "Scope.TRANSIENT"
        assert str(Scope.SCOPED) == "Scope.SCOPED"

    def test_scope_equality(self):
        """Test scope equality comparison."""
        assert Scope.SINGLETON == Scope.SINGLETON
        assert Scope.TRANSIENT == Scope.TRANSIENT
        assert Scope.SINGLETON != Scope.TRANSIENT


class TestErrorHandling:
    """Test error scenarios and edge cases."""

    def test_registration_error_inheritance(self):
        """Test that RegistrationError inherits from correct base."""
        # Test that RegistrationError from errors module is properly defined
        assert issubclass(RegistrationError, Exception)

    def test_invalid_key_types(self):
        """Test registration with invalid key types."""
        registry = ServiceRegistry()

        # Should handle various key types gracefully
        valid_keys = [
            "string_key",
            TestService,
            123,  # Numbers should be converted to strings
        ]

        for key in valid_keys:
            descriptor = registry.register(key=key, provider=TestService)
            assert descriptor is not None

    def test_none_provider_allowed(self):
        """Test registration with None provider is allowed."""
        registry = ServiceRegistry()

        # None provider should be allowed for optional dependencies
        descriptor = registry.register(key="test", provider=None)
        assert descriptor.provider is None

    def test_empty_tags_handling(self):
        """Test registration with empty tags."""
        registry = ServiceRegistry()

        # Should handle empty tags gracefully
        descriptor = registry.register(key="test", provider=TestService, tags=set())
        assert descriptor.tags == set()

        # Should handle None tags
        descriptor2 = registry.register(key="test2", provider=TestService, tags=None)
        assert descriptor2.tags == set()

    def test_large_registry_performance(self):
        """Test registry performance with many services."""
        registry = ServiceRegistry()

        # Register many services
        num_services = 100
        for i in range(num_services):
            registry.register(
                key=f"service_{i}", provider=TestService, tags={f"tag_{i % 10}", "common"}
            )

        assert len(registry) == num_services

        # Test lookups are still fast
        assert registry.has("service_50")
        assert len(registry.find_by_tag("common")) == num_services
        assert len(registry.find_by_tag("tag_5")) == 10  # Every 10th service
