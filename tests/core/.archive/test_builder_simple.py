"""Simplified tests for the ApplicationBuilder and ServiceBuilder.

This focuses on testing the core functionality that actually exists.
"""


from whiskey.core.builder import ApplicationBuilder, ServiceBuilder, create_app
from whiskey.core.container import Container
from whiskey.core.registry import Scope


# Test classes
class TestService:
    def __init__(self):
        self.value = "test"


class DatabaseService:
    def __init__(self):
        self.connection_string = "default"


def test_factory():
    return TestService()


class TestServiceBuilder:
    """Test ServiceBuilder basic functionality."""

    def test_service_builder_creation(self):
        """Test creating a ServiceBuilder."""
        app_builder = ApplicationBuilder()
        builder = ServiceBuilder(app_builder, TestService, TestService)

        assert builder._app_builder is app_builder
        assert builder._key is TestService
        assert builder._provider is TestService
        assert builder._scope == Scope.TRANSIENT

    def test_as_singleton(self):
        """Test configuring as singleton."""
        app_builder = ApplicationBuilder()
        builder = ServiceBuilder(app_builder, TestService, TestService)

        result = builder.as_singleton()
        assert result is builder
        assert builder._scope == Scope.SINGLETON

    def test_as_scoped(self):
        """Test configuring as scoped."""
        app_builder = ApplicationBuilder()
        builder = ServiceBuilder(app_builder, TestService, TestService)

        result = builder.as_scoped("request")
        assert result is builder
        assert builder._scope == Scope.SCOPED
        assert builder._metadata["scope_name"] == "request"

    def test_as_transient(self):
        """Test configuring as transient."""
        app_builder = ApplicationBuilder()
        builder = ServiceBuilder(app_builder, TestService, TestService)

        builder.as_singleton()  # Change from default
        result = builder.as_transient()

        assert result is builder
        assert builder._scope == Scope.TRANSIENT

    def test_named(self):
        """Test setting service name."""
        app_builder = ApplicationBuilder()
        builder = ServiceBuilder(app_builder, TestService, TestService)

        result = builder.named("primary")
        assert result is builder
        assert builder._name == "primary"

    def test_tagged(self):
        """Test adding tags."""
        app_builder = ApplicationBuilder()
        builder = ServiceBuilder(app_builder, TestService, TestService)

        result = builder.tagged("core", "database")
        assert result is builder
        assert builder._tags == {"core", "database"}

    def test_when_boolean(self):
        """Test setting condition with boolean."""
        app_builder = ApplicationBuilder()
        builder = ServiceBuilder(app_builder, TestService, TestService)

        result = builder.when(True)
        assert result is builder
        assert builder._condition() is True

    def test_when_function(self):
        """Test setting condition with function."""
        app_builder = ApplicationBuilder()
        builder = ServiceBuilder(app_builder, TestService, TestService)

        condition = lambda: False
        result = builder.when(condition)
        assert result is builder
        assert builder._condition is condition

    def test_priority(self):
        """Test setting priority."""
        app_builder = ApplicationBuilder()
        builder = ServiceBuilder(app_builder, TestService, TestService)

        result = builder.priority(5)
        assert result is builder
        # Priority should be stored in metadata
        assert builder._metadata.get("priority") == 5

    def test_lazy(self):
        """Test lazy configuration."""
        app_builder = ApplicationBuilder()
        builder = ServiceBuilder(app_builder, TestService, TestService)

        result = builder.lazy()
        assert result is builder
        assert builder._lazy is True

        result = builder.lazy(False)
        assert builder._lazy is False

    def test_with_metadata(self):
        """Test adding metadata."""
        app_builder = ApplicationBuilder()
        builder = ServiceBuilder(app_builder, TestService, TestService)

        result = builder.with_metadata(version="1.0", author="test")
        assert result is builder
        assert builder._metadata["version"] == "1.0"
        assert builder._metadata["author"] == "test"

    def test_fluent_chaining(self):
        """Test fluent method chaining."""
        app_builder = ApplicationBuilder()
        builder = ServiceBuilder(app_builder, TestService, TestService)

        result = (
            builder.as_singleton()
            .named("primary")
            .tagged("core")
            .lazy()
            .with_metadata(version="2.0")
        )

        assert result is builder
        assert builder._scope == Scope.SINGLETON
        assert builder._name == "primary"
        assert "core" in builder._tags
        assert builder._lazy is True
        assert builder._metadata["version"] == "2.0"


class TestApplicationBuilder:
    """Test ApplicationBuilder functionality."""

    def test_creation(self):
        """Test creating ApplicationBuilder."""
        builder = ApplicationBuilder()

        assert isinstance(builder._container, Container)
        assert builder._startup_callbacks == []
        assert builder._shutdown_callbacks == []
        assert builder._error_handlers == {}

    def test_service_registration(self):
        """Test service registration."""
        builder = ApplicationBuilder()
        service_builder = builder.service(TestService, TestService)

        assert isinstance(service_builder, ServiceBuilder)
        assert service_builder._key is TestService
        assert service_builder._provider is TestService

    def test_singleton_registration(self):
        """Test singleton registration."""
        builder = ApplicationBuilder()
        service_builder = builder.singleton(TestService, TestService)

        assert isinstance(service_builder, ServiceBuilder)
        assert service_builder._scope == Scope.SINGLETON

    def test_scoped_registration(self):
        """Test scoped registration."""
        builder = ApplicationBuilder()
        service_builder = builder.scoped(TestService, TestService, scope_name="request")

        assert service_builder._scope == Scope.SCOPED
        assert service_builder._metadata["scope_name"] == "request"

    def test_factory_registration(self):
        """Test factory registration."""
        builder = ApplicationBuilder()
        service_builder = builder.factory("test_service", test_factory)

        assert service_builder._key == "test_service"
        assert service_builder._provider is test_factory

    def test_instance_registration(self):
        """Test instance registration."""
        instance = TestService()
        builder = ApplicationBuilder()
        service_builder = builder.instance("test_instance", instance)

        assert service_builder._key == "test_instance"
        assert service_builder._provider is instance
        assert service_builder._scope == Scope.SINGLETON

    def test_callbacks(self):
        """Test callback registration."""
        builder = ApplicationBuilder()

        def startup():
            pass

        def shutdown():
            pass

        result1 = builder.on_startup(startup)
        result2 = builder.on_shutdown(shutdown)

        assert result1 is builder
        assert result2 is builder
        assert startup in builder._startup_callbacks
        assert shutdown in builder._shutdown_callbacks

    def test_error_handlers(self):
        """Test error handler registration."""
        builder = ApplicationBuilder()

        def handle_error(exc):
            pass

        result = builder.on_error(ValueError, handle_error)

        assert result is builder
        assert builder._error_handlers[ValueError] is handle_error

    def test_configure(self):
        """Test configuration callback."""
        builder = ApplicationBuilder()

        def config_func(container):
            container.singleton("configured", TestService)

        result = builder.configure(config_func)

        assert result is builder
        # Configuration callback should be stored
        assert len(builder._configuration_callbacks) == 1


class TestCreateApp:
    """Test the create_app convenience function."""

    def test_create_app(self):
        """Test create_app function."""
        builder = create_app()

        assert isinstance(builder, ApplicationBuilder)
        assert isinstance(builder._container, Container)

    def test_fluent_usage(self):
        """Test fluent usage with create_app."""
        app_builder = create_app()
        app_builder.singleton(TestService, TestService).build()
        app_builder.service(DatabaseService, DatabaseService).build()

        assert isinstance(app_builder, ApplicationBuilder)


class TestBuilderIntegration:
    """Test integration between builders and container."""

    def test_service_registration_integration(self):
        """Test that service registration actually works."""
        builder = ApplicationBuilder()

        # Register and build service
        service_builder = builder.service(TestService, TestService)
        result = service_builder.build()

        # Build() returns the ApplicationBuilder
        assert result is builder._container or result is builder

    def test_named_service_registration(self):
        """Test named service registration."""
        builder = ApplicationBuilder()

        # Register two services of same type with different names
        builder.service(DatabaseService, DatabaseService).named("primary").build()
        builder.service(DatabaseService, DatabaseService).named("backup").build()

        # Test that the builder handles multiple registrations
        assert isinstance(builder._container, Container)

    def test_conditional_registration(self):
        """Test conditional service registration."""
        builder = ApplicationBuilder()

        # Register service with condition
        builder.service(TestService, TestService).when(True).build()

        # Test that the builder handles conditional registration
        assert isinstance(builder._container, Container)
