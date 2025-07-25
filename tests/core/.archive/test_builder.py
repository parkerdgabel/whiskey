"""Tests for the fluent ApplicationBuilder system.

This module tests the ApplicationBuilder and ServiceBuilder classes
that provide the fluent, chainable API for application configuration.
"""

import os
from unittest.mock import patch

import pytest

from whiskey.core.builder import ApplicationBuilder, ServiceBuilder, create_app
from whiskey.core.container import Container
from whiskey.core.registry import Scope, ServiceDescriptor


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


def test_factory():
    """Test factory function."""
    return TestService()


async def async_test_factory():
    """Async test factory function."""
    return TestService()


class TestServiceBuilder:
    """Test the ServiceBuilder class for fluent service configuration."""

    @pytest.fixture
    def app_builder(self):
        """Create an ApplicationBuilder for testing."""
        return ApplicationBuilder()

    @pytest.fixture
    def service_builder(self, app_builder):
        """Create a ServiceBuilder for testing."""
        return ServiceBuilder(app_builder, TestService, TestService)

    def test_service_builder_creation(self, app_builder):
        """Test creating a ServiceBuilder."""
        builder = ServiceBuilder(app_builder, "test_service", TestService)

        assert builder._app_builder is app_builder
        assert builder._key == "test_service"
        assert builder._provider is TestService
        assert builder._scope == Scope.TRANSIENT  # Default
        assert builder._name is None
        assert builder._tags == set()
        assert builder._condition is None
        assert builder._lazy is False
        assert builder._metadata == {}

    def test_as_singleton(self, service_builder):
        """Test configuring service as singleton."""
        result = service_builder.as_singleton()

        assert result is service_builder  # Fluent interface
        assert service_builder._scope == Scope.SINGLETON

    def test_as_scoped(self, service_builder):
        """Test configuring service as scoped."""
        result = service_builder.as_scoped("request")

        assert result is service_builder  # Fluent interface
        assert service_builder._scope == Scope.SCOPED
        assert service_builder._metadata["scope_name"] == "request"

    def test_as_scoped_default(self, service_builder):
        """Test configuring service as scoped with default scope name."""
        result = service_builder.as_scoped()

        assert result is service_builder
        assert service_builder._scope == Scope.SCOPED
        assert service_builder._metadata["scope_name"] == "default"

    def test_as_transient(self, service_builder):
        """Test configuring service as transient."""
        # Set to singleton first
        service_builder.as_singleton()

        result = service_builder.as_transient()

        assert result is service_builder
        assert service_builder._scope == Scope.TRANSIENT

    def test_named(self, service_builder):
        """Test setting service name."""
        result = service_builder.named("primary")

        assert result is service_builder
        assert service_builder._name == "primary"

    def test_tagged(self, service_builder):
        """Test adding tags to service."""
        result = service_builder.tagged("core", "database", "infrastructure")

        assert result is service_builder
        assert service_builder._tags == {"core", "database", "infrastructure"}

    def test_tagged_multiple_calls(self, service_builder):
        """Test that multiple tagged() calls accumulate tags."""
        service_builder.tagged("core", "stable")
        result = service_builder.tagged("database", "important")

        assert result is service_builder
        assert service_builder._tags == {"core", "stable", "database", "important"}

    def test_when_condition_function(self, service_builder):
        """Test setting condition with function."""
        condition = lambda: True
        result = service_builder.when(condition)

        assert result is service_builder
        assert service_builder._condition is condition

    def test_when_condition_boolean(self, service_builder):
        """Test setting condition with boolean value."""
        result = service_builder.when(True)

        assert result is service_builder
        assert service_builder._condition is not None
        assert service_builder._condition() is True

        # Test False case
        service_builder.when(False)
        assert service_builder._condition() is False

    def test_when_env(self, service_builder):
        """Test environment-based condition."""
        # Test with environment variable present
        with patch.dict(os.environ, {"TEST_MODE": "active"}):
            result = service_builder.when_env("TEST_MODE", "active")

            assert result is service_builder
            assert service_builder._condition is not None
            assert service_builder._condition() is True

        # Test with environment variable not matching
        with patch.dict(os.environ, {"TEST_MODE": "inactive"}):
            service_builder.when_env("TEST_MODE", "active")
            assert service_builder._condition() is False

    def test_when_env_existence_only(self, service_builder):
        """Test environment condition checking only existence."""
        # Test with environment variable present
        with patch.dict(os.environ, {"DEBUG": "1"}):
            result = service_builder.when_env("DEBUG")

            assert result is service_builder
            assert service_builder._condition() is True

        # Test without environment variable
        with patch.dict(os.environ, {}, clear=True):
            service_builder.when_env("DEBUG")
            assert service_builder._condition() is False

    def test_when_debug(self, service_builder):
        """Test debug mode condition."""
        # Test with debug mode on
        with patch.dict(os.environ, {"DEBUG": "true"}):
            result = service_builder.when_debug()

            assert result is service_builder
            assert service_builder._condition() is True

        # Test various debug values
        debug_values = ["1", "yes", "TRUE", "Yes"]
        for value in debug_values:
            with patch.dict(os.environ, {"DEBUG": value}):
                service_builder.when_debug()
                assert service_builder._condition() is True

        # Test with debug mode off
        with patch.dict(os.environ, {"DEBUG": "false"}):
            service_builder.when_debug()
            assert service_builder._condition() is False

    def test_lazy(self, service_builder):
        """Test setting lazy resolution."""
        result = service_builder.lazy()

        assert result is service_builder
        assert service_builder._lazy is True

        # Test setting lazy to False
        result = service_builder.lazy(False)
        assert service_builder._lazy is False

    def test_with_metadata(self, service_builder):
        """Test adding arbitrary metadata."""
        result = service_builder.with_metadata(version="1.0", author="test")

        assert result is service_builder
        assert service_builder._metadata["version"] == "1.0"
        assert service_builder._metadata["author"] == "test"

    def test_with_metadata_multiple_calls(self, service_builder):
        """Test that multiple metadata calls accumulate."""
        service_builder.with_metadata(version="1.0")
        result = service_builder.with_metadata(author="test", priority=5)

        assert result is service_builder
        assert service_builder._metadata == {"version": "1.0", "author": "test", "priority": 5}

    def test_build(self, service_builder):
        """Test building the service configuration."""
        descriptor = service_builder.as_singleton().tagged("core").named("primary").build()

        assert isinstance(descriptor, ServiceDescriptor)
        assert descriptor.scope == Scope.SINGLETON
        assert "core" in descriptor.tags
        assert descriptor.name == "primary"
        # Should be registered with the application builder's container
        assert service_builder._app_builder._container.has(TestService, name="primary")

    def test_fluent_chaining(self, service_builder):
        """Test complete fluent chaining."""
        result = (
            service_builder.as_singleton()
            .named("primary")
            .tagged("core", "stable")
            .when_debug()
            .lazy()
            .with_metadata(version="2.0")
        )

        assert result is service_builder  # All methods return self
        assert service_builder._scope == Scope.SINGLETON
        assert service_builder._name == "primary"
        assert service_builder._tags == {"core", "stable"}
        assert service_builder._lazy is True
        assert service_builder._metadata["version"] == "2.0"


class TestApplicationBuilder:
    """Test the ApplicationBuilder class for fluent application configuration."""

    def test_application_builder_creation(self):
        """Test creating an ApplicationBuilder."""
        builder = ApplicationBuilder()

        assert isinstance(builder._container, Container)
        assert builder._startup_callbacks == []
        assert builder._shutdown_callbacks == []
        assert builder._error_handlers == {}

    def test_application_builder_with_container(self):
        """Test ApplicationBuilder container access."""
        builder = ApplicationBuilder()

        assert isinstance(builder._container, Container)

    def test_service_registration(self):
        """Test basic service registration."""
        builder = ApplicationBuilder()
        service_builder = builder.service(TestService, TestService)

        assert isinstance(service_builder, ServiceBuilder)
        assert service_builder._key is TestService
        assert service_builder._provider is TestService
        assert service_builder._scope == Scope.TRANSIENT  # Default

    def test_service_with_string_key(self):
        """Test service registration with string key."""
        builder = ApplicationBuilder("test-app")
        service_builder = builder.service("test_service", TestService)

        assert service_builder._key == "test_service"
        assert service_builder._provider is TestService

    def test_singleton_registration(self):
        """Test singleton service registration."""
        builder = ApplicationBuilder("test-app")
        service_builder = builder.singleton(TestService, TestService)

        assert isinstance(service_builder, ServiceBuilder)
        assert service_builder._scope == Scope.SINGLETON

    def test_singleton_with_string_key(self):
        """Test singleton registration with string key."""
        builder = ApplicationBuilder("test-app")
        service_builder = builder.singleton("test_service", TestService)

        assert service_builder._key == "test_service"
        assert service_builder._scope == Scope.SINGLETON

    def test_scoped_registration(self):
        """Test scoped service registration."""
        builder = ApplicationBuilder("test-app")
        service_builder = builder.scoped(TestService, TestService, scope_name="request")

        assert service_builder._scope == Scope.SCOPED
        assert service_builder._metadata["scope_name"] == "request"

    def test_factory_registration(self):
        """Test factory function registration."""
        builder = ApplicationBuilder("test-app")
        service_builder = builder.factory("test_service", test_factory)

        assert service_builder._key == "test_service"
        assert service_builder._provider is test_factory

    def test_instance_registration(self):
        """Test instance registration."""
        instance = TestService()
        builder = ApplicationBuilder("test-app")
        service_builder = builder.instance("test_instance", instance)

        assert service_builder._key == "test_instance"
        assert service_builder._provider is instance
        assert service_builder._scope == Scope.SINGLETON  # Instances are singleton

    def test_on_startup(self):
        """Test startup callback registration."""
        builder = ApplicationBuilder("test-app")

        def startup_callback():
            pass

        result = builder.on_startup(startup_callback)

        assert result is builder  # Fluent interface
        assert startup_callback in builder._startup_callbacks

    def test_on_shutdown(self):
        """Test shutdown callback registration."""
        builder = ApplicationBuilder("test-app")

        def shutdown_callback():
            pass

        result = builder.on_shutdown(shutdown_callback)

        assert result is builder
        assert shutdown_callback in builder._shutdown_callbacks

    def test_on_error(self):
        """Test error handler registration."""
        builder = ApplicationBuilder("test-app")

        def error_handler(exc: ValueError):
            pass

        result = builder.on_error(ValueError, error_handler)

        assert result is builder
        assert builder._error_handlers[ValueError] is error_handler

    def test_configure(self):
        """Test configuration function."""
        builder = ApplicationBuilder("test-app")

        def config_func(app_builder):
            app_builder.singleton("configured_service", TestService)

        result = builder.configure(config_func)

        assert result is builder
        # Check that configuration was applied
        assert builder.container.has("configured_service")

    def test_build_app(self):
        """Test building the application."""
        builder = ApplicationBuilder("test-app")
        builder.singleton(TestService, TestService)

        app = builder.build_app()

        from whiskey.core.application import Application

        assert isinstance(app, Application)
        assert app.name == "test-app"

    def test_fluent_application_building(self):
        """Test complete fluent application building."""

        def startup_hook():
            pass

        def shutdown_hook():
            pass

        def error_handler(exc: ValueError):
            pass

        def config_func(builder):
            builder.singleton("configured", TestService)

        builder = (
            ApplicationBuilder("test-app")
            .singleton(DatabaseService, DatabaseService)
            .build()
            .service(CacheService, CacheService)
            .as_singleton()
            .build()
            .factory("test_factory", test_factory)
            .build()
            .on_startup(startup_hook)
            .on_shutdown(shutdown_hook)
            .on_error(ValueError, error_handler)
            .configure(config_func)
        )

        app = builder.build_app()

        # Verify all registrations
        assert builder.container.has(DatabaseService)
        assert builder.container.has(CacheService)
        assert builder.container.has("test_factory")
        assert builder.container.has("configured")

        # Verify callbacks
        assert startup_hook in builder._startup_callbacks
        assert shutdown_hook in builder._shutdown_callbacks
        assert builder._error_handlers[ValueError] is error_handler

    def test_multiple_services_same_type(self):
        """Test registering multiple services of same type with different names."""
        builder = ApplicationBuilder("test-app")

        builder.singleton(DatabaseService, DatabaseService).named("primary").build()
        builder.singleton(DatabaseService, DatabaseService).named("secondary").build()

        assert builder.container.has(DatabaseService, name="primary")
        assert builder.container.has(DatabaseService, name="secondary")

    def test_conditional_registration(self):
        """Test conditional service registration."""
        builder = ApplicationBuilder("test-app")

        # Register service that's only active in debug mode
        with patch.dict(os.environ, {"DEBUG": "true"}):
            builder.service(TestService, TestService).when_debug().build()
            assert builder.container.has(TestService)

        # Register service that's only active when env var is set
        with patch.dict(os.environ, {"FEATURE_ENABLED": "yes"}):
            builder.service("feature_service", CacheService).when_env(
                "FEATURE_ENABLED", "yes"
            ).build()
            assert builder.container.has("feature_service")


class TestCreateAppFunction:
    """Test the create_app convenience function."""

    def test_create_app_basic(self):
        """Test basic create_app usage."""
        builder = create_app()

        assert isinstance(builder, ApplicationBuilder)
        assert builder.name == "whiskey-app"  # Default name

    def test_create_app_with_name(self):
        """Test create_app with custom name."""
        builder = create_app("my-app")

        assert builder.name == "my-app"

    def test_create_app_fluent_usage(self):
        """Test create_app in fluent chain."""
        app = (
            create_app("test-app")
            .singleton(TestService, TestService)
            .build()
            .service(DatabaseService, DatabaseService)
            .build()
            .build_app()
        )

        from whiskey.core.application import Application

        assert isinstance(app, Application)
        assert app.name == "test-app"


class TestBuilderErrorHandling:
    """Test error handling in builders."""

    def test_service_builder_invalid_condition(self):
        """Test ServiceBuilder with invalid condition."""
        builder = ApplicationBuilder("test")
        service_builder = ServiceBuilder(builder, TestService, TestService)

        # This should work - any callable is valid
        result = service_builder.when(lambda: True)
        assert result is service_builder

    def test_application_builder_invalid_error_type(self):
        """Test ApplicationBuilder with invalid error type."""
        builder = ApplicationBuilder("test")

        def handler(exc):
            pass

        # Should work with any exception type
        result = builder.on_error(RuntimeError, handler)
        assert result is builder
        assert builder._error_handlers[RuntimeError] is handler

    def test_configuration_function_error(self):
        """Test configuration function that raises an error."""
        builder = ApplicationBuilder("test")

        def bad_config(app_builder):
            raise ValueError("Configuration failed")

        # The error should propagate
        with pytest.raises(ValueError, match="Configuration failed"):
            builder.configure(bad_config)

    def test_none_provider_error(self):
        """Test registration with None provider."""
        builder = ApplicationBuilder("test")

        # ServiceBuilder should handle None provider gracefully
        service_builder = builder.service("test", None)
        assert service_builder._provider is None

    def test_empty_name_handling(self):
        """Test handling of empty names."""
        builder = ApplicationBuilder("test")
        service_builder = builder.service(TestService, TestService)

        # Empty name should be handled
        result = service_builder.named("")
        assert result is service_builder
        assert service_builder._name == ""


class TestBuilderEdgeCases:
    """Test edge cases and unusual scenarios."""

    def test_service_builder_reuse(self):
        """Test that ServiceBuilder can be reconfigured."""
        builder = ApplicationBuilder("test")
        service_builder = ServiceBuilder(builder, TestService, TestService)

        # Configure as singleton first
        service_builder.as_singleton().tagged("core")

        # Reconfigure as transient
        service_builder.as_transient().tagged("optional")

        assert service_builder._scope == Scope.TRANSIENT
        assert service_builder._tags == {"core", "optional"}  # Tags accumulate

    def test_metadata_overwrite(self):
        """Test that metadata can be overwritten."""
        builder = ApplicationBuilder("test")
        service_builder = ServiceBuilder(builder, TestService, TestService)

        service_builder.with_metadata(version="1.0")
        service_builder.with_metadata(version="2.0", author="test")

        assert service_builder._metadata == {"version": "2.0", "author": "test"}

    def test_large_number_of_services(self):
        """Test builder with many services."""
        builder = ApplicationBuilder("test")

        # Register many services
        for i in range(100):
            builder.service(f"service_{i}", TestService).tagged(f"tag_{i % 10}").build()

        # Should handle large number of services
        assert len(builder.container) == 100

        # Check that tags work
        for i in range(10):
            services_with_tag = builder.container.registry.find_by_tag(f"tag_{i}")
            assert len(services_with_tag) == 10  # Every 10th service

    def test_callback_order_preservation(self):
        """Test that callbacks are preserved in order."""
        builder = ApplicationBuilder("test")

        callbacks = []
        for i in range(5):
            callback = lambda i=i: callbacks.append(i)  # Capture i
            builder.on_startup(callback)

        assert len(builder._startup_callbacks) == 5

        # Execute callbacks in order to verify they're preserved correctly
        for i, callback in enumerate(builder._startup_callbacks):
            callback()

        assert callbacks == [0, 1, 2, 3, 4]

    def test_complex_conditions(self):
        """Test complex conditional logic."""
        builder = ApplicationBuilder("test")

        def complex_condition():
            return os.getenv("ENV") == "production" and os.getenv("FEATURE_ENABLED") == "true"

        with patch.dict(os.environ, {"ENV": "production", "FEATURE_ENABLED": "true"}):
            service_builder = builder.service(TestService, TestService).when(complex_condition)
            service_builder.build()

            assert builder.container.has(TestService)

        with patch.dict(os.environ, {"ENV": "development", "FEATURE_ENABLED": "true"}):
            builder2 = ApplicationBuilder("test2")
            service_builder2 = builder2.service(TestService, TestService).when(complex_condition)
            service_builder2.build()

            # Should not be registered due to condition
            assert not builder2.container.has(TestService)
