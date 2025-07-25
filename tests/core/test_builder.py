"""Consolidated tests for builder classes."""

import os
from unittest.mock import patch

import pytest

from whiskey import Container, Scope, Whiskey, create_app
from whiskey.core.builder import WhiskeyBuilder, ComponentBuilder, ConditionBuilder
from whiskey.core.errors import ConfigurationError


class TestComponent:
    """Test component."""

    def __init__(self, value: str = "test"):
        self.value = value


class DatabaseComponent:
    """Database component."""

    def __init__(self, url: str = "sqlite://"):
        self.url = url


class CacheComponent:
    """Cache component."""

    def __init__(self, ttl: int = 300):
        self.ttl = ttl


def create_test_component():
    """Factory function."""
    return TestComponent("factory")


class TestComponentBuilder:
    """Test ComponentBuilder functionality."""

    def test_component_builder_creation(self):
        """Test creating a ComponentBuilder."""
        app_builder = WhiskeyBuilder()
        builder = ComponentBuilder(app_builder, TestComponent, TestComponent)

        assert builder._key is TestComponent
        assert builder._provider is TestComponent
        assert builder._scope == Scope.TRANSIENT
        assert builder._name is None
        assert builder._tags == set()

    def test_as_singleton(self):
        """Test configuring as singleton."""
        app_builder = WhiskeyBuilder()
        builder = ComponentBuilder(app_builder, TestComponent, TestComponent)

        result = builder.as_singleton()
        assert result is builder  # Fluent interface
        assert builder._scope == Scope.SINGLETON

    def test_as_scoped(self):
        """Test configuring as scoped."""
        app_builder = WhiskeyBuilder()
        builder = ComponentBuilder(app_builder, TestComponent, TestComponent)

        result = builder.as_scoped("request")
        assert result is builder
        assert builder._scope == Scope.SCOPED
        assert builder._metadata["scope_name"] == "request"

    def test_as_transient(self):
        """Test configuring as transient."""
        app_builder = WhiskeyBuilder()
        builder = ComponentBuilder(app_builder, TestComponent, TestComponent)

        # Change to singleton first
        builder.as_singleton()

        # Then back to transient
        result = builder.as_transient()
        assert result is builder
        assert builder._scope == Scope.TRANSIENT

    def test_named(self):
        """Test naming a component."""
        app_builder = WhiskeyBuilder()
        builder = ComponentBuilder(app_builder, TestComponent, TestComponent)

        result = builder.named("primary")
        assert result is builder
        assert builder._name == "primary"

    def test_tagged(self):
        """Test adding tags."""
        app_builder = WhiskeyBuilder()
        builder = ComponentBuilder(app_builder, TestComponent, TestComponent)

        result = builder.tagged("core", "infrastructure")
        assert result is builder
        assert builder._tags == {"core", "infrastructure"}

        # Multiple calls accumulate
        builder.tagged("stable")
        assert builder._tags == {"core", "infrastructure", "stable"}

    def test_when_conditions(self):
        """Test various condition methods."""
        app_builder = WhiskeyBuilder()
        builder = ComponentBuilder(app_builder, TestComponent, TestComponent)

        # Boolean condition
        builder.when(True)
        assert builder._condition() is True

        # Callable condition
        condition = lambda: False
        builder.when(condition)
        assert builder._condition is condition

    def test_lazy(self):
        """Test lazy configuration."""
        app_builder = WhiskeyBuilder()
        builder = ComponentBuilder(app_builder, TestComponent, TestComponent)

        result = builder.lazy()
        assert result is builder
        assert builder._lazy is True

        # Turn off lazy
        builder.lazy(False)
        assert builder._lazy is False

    def test_with_metadata(self):
        """Test adding metadata."""
        app_builder = WhiskeyBuilder()
        builder = ComponentBuilder(app_builder, TestComponent, TestComponent)

        result = builder.with_metadata(version="1.0", priority=5)
        assert result is builder
        assert builder._metadata["version"] == "1.0"
        assert builder._metadata["priority"] == 5

    def test_build(self):
        """Test building the component registration."""
        app_builder = WhiskeyBuilder()
        builder = ComponentBuilder(app_builder, TestComponent, TestComponent)

        builder.as_singleton().named("test").tagged("core")

        result = builder.build()
        assert result is app_builder  # Returns to app builder

        # Verify registration was added
        container = app_builder.build()
        assert TestComponent in container


class TestWhiskeyBuilder:
    """Test WhiskeyBuilder functionality."""

    def test_application_builder_creation(self):
        """Test creating an WhiskeyBuilder."""
        builder = WhiskeyBuilder()
        assert builder is not None
        assert isinstance(builder._container, Container)

    def test_component_registration(self):
        """Test registering components."""
        builder = WhiskeyBuilder()

        result = builder.component(TestComponent)
        assert isinstance(result, ComponentBuilder)
        assert result._key is TestComponent
        assert result._provider is TestComponent

    def test_singleton_helper(self):
        """Test singleton registration helper."""
        builder = WhiskeyBuilder()

        result = builder.singleton(DatabaseComponent)
        assert isinstance(result, ComponentBuilder)
        assert result._scope == Scope.SINGLETON

    def test_factory_registration(self):
        """Test factory registration."""
        builder = WhiskeyBuilder()

        result = builder.factory("test_factory", create_test_component)
        assert isinstance(result, ComponentBuilder)
        assert result._key == "test_factory"
        assert result._provider is create_test_component

    def test_instance_registration(self):
        """Test instance registration."""
        builder = WhiskeyBuilder()
        instance = TestComponent("instance")

        result = builder.instance(TestComponent, instance)
        assert isinstance(result, ComponentBuilder)
        assert result._provider is instance
        assert result._scope == Scope.SINGLETON

    def test_batch_components(self):
        """Test registering multiple components at once."""
        builder = WhiskeyBuilder()

        result = builder.components(database=DatabaseComponent, cache=CacheComponent)

        assert result is builder  # Fluent interface

        container = builder.build()
        assert "database" in container
        assert "cache" in container

    def test_configuration_callbacks(self):
        """Test configuration callbacks."""
        builder = WhiskeyBuilder()
        configured = False

        def configure(container):
            nonlocal configured
            configured = True
            container["test"] = TestComponent

        builder.configure(configure)
        container = builder.build()

        assert configured
        assert "test" in container

    def test_lifecycle_callbacks(self):
        """Test lifecycle callbacks."""
        builder = WhiskeyBuilder()
        events = []

        builder.on_startup(lambda: events.append("startup"))
        builder.on_shutdown(lambda: events.append("shutdown"))

        container = builder.build()

        # Callbacks should be stored
        assert len(container._startup_callbacks) == 1
        assert len(container._shutdown_callbacks) == 1

    def test_build_container(self):
        """Test building a container."""
        builder = WhiskeyBuilder()
        builder.component(TestComponent).as_singleton().build()

        container = builder.build()
        assert isinstance(container, Container)
        assert TestComponent in container

    def test_build_app(self):
        """Test building a Whiskey application."""
        builder = WhiskeyBuilder()
        builder.component(TestComponent).build()

        app = builder.build_app()
        assert isinstance(app, Whiskey)
        assert TestComponent in app.container


class TestConditionBuilder:
    """Test ConditionBuilder functionality."""

    def test_condition_builder_creation(self):
        """Test creating a ConditionBuilder."""
        app_builder = WhiskeyBuilder()
        condition = lambda: True

        builder = ConditionBuilder(app_builder, condition)
        assert builder._app_builder is app_builder
        assert builder._condition is condition

    def test_conditional_component_registration(self):
        """Test registering component with condition."""
        app_builder = WhiskeyBuilder()
        condition = lambda: True

        cond_builder = ConditionBuilder(app_builder, condition)
        comp_builder = cond_builder.register(TestComponent, TestComponent)

        assert isinstance(comp_builder, ComponentBuilder)
        assert comp_builder._condition is condition

    def test_conditional_singleton(self):
        """Test conditional singleton registration."""
        app_builder = WhiskeyBuilder()
        condition = lambda: False

        cond_builder = ConditionBuilder(app_builder, condition)
        comp_builder = cond_builder.singleton(DatabaseComponent)

        assert comp_builder._scope == Scope.SINGLETON
        assert comp_builder._condition is condition

    def test_conditional_factory(self):
        """Test conditional factory registration."""
        app_builder = WhiskeyBuilder()
        condition = lambda: True

        cond_builder = ConditionBuilder(app_builder, condition)
        comp_builder = cond_builder.factory("test", create_test_component)

        assert comp_builder._provider is create_test_component
        assert comp_builder._condition is condition


class TestEnvironmentConditions:
    """Test environment-based conditions."""

    def test_when_env_with_value(self):
        """Test when_env with specific value."""
        builder = WhiskeyBuilder()

        with patch.dict(os.environ, {"TEST_MODE": "active"}):
            cond_builder = builder.when_env("TEST_MODE", "active")
            assert cond_builder._condition() is True

        with patch.dict(os.environ, {"TEST_MODE": "inactive"}):
            assert cond_builder._condition() is False

    def test_when_env_existence(self):
        """Test when_env checking existence only."""
        builder = WhiskeyBuilder()

        with patch.dict(os.environ, {"DEBUG": "anything"}):
            cond_builder = builder.when_env("DEBUG")
            assert cond_builder._condition() is True

        with patch.dict(os.environ, {}, clear=True):
            assert cond_builder._condition() is False

    def test_when_debug(self):
        """Test when_debug condition."""
        builder = WhiskeyBuilder()

        # Test various truthy values
        for value in ["true", "1", "yes", "TRUE"]:
            with patch.dict(os.environ, {"DEBUG": value}):
                cond_builder = builder.when_debug()
                assert cond_builder._condition() is True

        with patch.dict(os.environ, {"DEBUG": "false"}):
            cond_builder = builder.when_debug()
            assert cond_builder._condition() is False

    def test_when_production(self):
        """Test when_production condition."""
        builder = WhiskeyBuilder()

        for value in ["prod", "production"]:
            with patch.dict(os.environ, {"ENV": value}):
                cond_builder = builder.when_production()
                assert cond_builder._condition() is True

        with patch.dict(os.environ, {"ENV": "development"}):
            cond_builder = builder.when_production()
            assert cond_builder._condition() is False


class TestCreateAppFunction:
    """Test create_app convenience function."""

    def test_create_app_basic(self):
        """Test basic create_app usage."""
        builder = create_app()
        assert isinstance(builder, WhiskeyBuilder)

    def test_create_app_fluent_usage(self):
        """Test fluent usage with create_app."""
        app = (
            create_app()
            .component(TestComponent)
            .as_singleton()
            .build()
            .component(DatabaseComponent)
            .named("primary")
            .build()
            .build_app()
        )

        assert isinstance(app, Whiskey)
        assert TestComponent in app.container
        assert DatabaseComponent in app.container


class TestBuilderEdgeCases:
    """Test edge cases and error scenarios."""

    def test_component_without_provider(self):
        """Test component registration without provider."""
        builder = WhiskeyBuilder()

        # Should use key as provider when key is a type
        comp_builder = builder.component(TestComponent)
        assert comp_builder._provider is TestComponent

        # Should raise error when key is string without provider
        with pytest.raises(ConfigurationError):
            builder.component("test_key")

    def test_empty_builder(self):
        """Test building empty application."""
        builder = WhiskeyBuilder()

        container = builder.build()
        assert len(container) == 0

        app = builder.build_app()
        assert isinstance(app, Whiskey)
        assert len(app.container) == 0

    def test_fluent_chaining_complex(self):
        """Test complex fluent chaining."""
        app = (
            WhiskeyBuilder()
            .component(TestComponent)
            .as_singleton()
            .named("primary")
            .tagged("core", "stable")
            .with_metadata(version="1.0")
            .build()
            .singleton(DatabaseComponent)
            .when_env("DB_TYPE", "postgres")
            .build()
            .factory("cache", lambda: CacheComponent(600))
            .when_production()
            .build()
            .on_startup(lambda: print("Starting..."))
            .on_shutdown(lambda: print("Stopping..."))
            .build_app()
        )

        assert isinstance(app, Whiskey)
        assert TestComponent in app.container
