"""Comprehensive tests for the Whiskey application class."""

import asyncio
from typing import Optional

import pytest

from whiskey import Container, Scope, Whiskey
from whiskey.core.builder import ComponentBuilder, WhiskeyBuilder
from whiskey.core.errors import ResolutionError
from whiskey.core.types import Disposable, Initializable


# Test components/services
class SimpleService:
    """Simple test service."""

    def __init__(self, value: str = "test"):
        self.value = value


class DatabaseService:
    """Mock database service."""

    def __init__(self, connection_string: str = "sqlite://"):
        self.connection_string = connection_string


class CacheService:
    """Mock cache service."""

    def __init__(self, ttl: int = 300):
        self.ttl = ttl


class ComplexService:
    """Service with dependencies."""

    def __init__(self, db: DatabaseService, cache: CacheService):
        self.db = db
        self.cache = cache


class DependentService:
    """Service with single dependency."""

    def __init__(self, simple: SimpleService):
        self.simple = simple


# Factory functions
def create_simple_service():
    """Factory function for testing."""
    return SimpleService("factory")


async def async_service_factory():
    """Async factory for testing."""
    await asyncio.sleep(0.001)
    return DatabaseService("async://")


class TestWhiskeyBasics:
    """Test basic Whiskey functionality."""

    def test_whiskey_creation(self):
        """Test creating a Whiskey instance."""
        app = Whiskey()
        assert app is not None
        assert isinstance(app.container, Container)
        assert app._is_running is False
        assert app._startup_callbacks == []
        assert app._shutdown_callbacks == []
        assert app._error_handlers == {}
        assert app._middleware == []

    def test_whiskey_with_container(self):
        """Test creating Whiskey with existing container."""
        container = Container()
        container.register("test", "value")

        app = Whiskey(container=container)
        assert app.container is container
        assert app.resolve("test") == "value"

    def test_whiskey_with_name(self):
        """Test creating Whiskey with custom name."""
        app = Whiskey(name="MyApp")
        assert app.name == "MyApp"

    def test_whiskey_default_name(self):
        """Test Whiskey default name."""
        app = Whiskey()
        assert app.name == "Whiskey"


class TestComponentRegistration:
    """Test component registration methods."""

    def test_register_component_direct(self):
        """Test direct component registration."""
        app = Whiskey()
        app.register(SimpleService, SimpleService())

        instance = app.resolve(SimpleService)
        assert isinstance(instance, SimpleService)

    def test_component_decorator(self):
        """Test @app.component decorator."""
        app = Whiskey()

        @app.component
        class MyService:
            def __init__(self):
                self.value = 42

        instance = app.resolve(MyService)
        assert isinstance(instance, MyService)
        assert instance.value == 42

    def test_component_decorator_with_params(self):
        """Test @app.component with parameters."""
        app = Whiskey()

        @app.component(name="custom", scope=Scope.SINGLETON)
        class MyService:
            def __init__(self):
                self.id = id(self)

        # Resolve by custom name
        instance1 = app.resolve("custom")
        instance2 = app.resolve("custom")

        # Should be singleton
        assert instance1 is instance2

    def test_provider_decorator_alias(self):
        """Test @app.provider is alias for @app.component."""
        app = Whiskey()
        assert app.provider == app.component

    def test_managed_decorator(self):
        """Test @app.managed decorator for transient scope."""
        app = Whiskey()

        @app.managed
        class ManagedService:
            def __init__(self):
                self.id = id(self)

        instance1 = app.resolve(ManagedService)
        instance2 = app.resolve(ManagedService)

        # Should be different instances (transient)
        assert instance1 is not instance2

    def test_system_decorator(self):
        """Test @app.system decorator for singleton scope."""
        app = Whiskey()

        @app.system
        class SystemService:
            def __init__(self):
                self.id = id(self)

        instance1 = app.resolve(SystemService)
        instance2 = app.resolve(SystemService)

        # Should be same instance (singleton)
        assert instance1 is instance2

    def test_singleton_method(self):
        """Test app.singleton() method."""
        app = Whiskey()
        app.singleton(DatabaseService, instance=DatabaseService("singleton://"))

        instance = app.resolve(DatabaseService)
        assert instance.connection_string == "singleton://"

    def test_transient_method(self):
        """Test app.transient() method."""
        app = Whiskey()
        app.transient(SimpleService)

        instance1 = app.resolve(SimpleService)
        instance2 = app.resolve(SimpleService)

        assert instance1 is not instance2

    def test_factory_method(self):
        """Test app.factory() method."""
        app = Whiskey()
        app.factory(SimpleService, create_simple_service)

        instance = app.resolve(SimpleService)
        assert instance.value == "factory"

    async def test_async_factory(self):
        """Test async factory registration."""
        app = Whiskey()
        app.factory(DatabaseService, async_service_factory)

        instance = await app.resolve_async(DatabaseService)
        assert instance.connection_string == "async://"


class TestDependencyInjection:
    """Test dependency injection features."""

    def test_inject_decorator(self):
        """Test @app.inject decorator."""
        app = Whiskey()
        app.singleton(SimpleService, instance=SimpleService("injected"))

        @app.inject
        def process(service: SimpleService, value: str) -> str:
            return f"{service.value}: {value}"

        result = process(value="test")
        assert result == "injected: test"

    async def test_inject_async_function(self):
        """Test @app.inject with async function."""
        app = Whiskey()
        app.singleton(DatabaseService)

        @app.inject
        async def async_process(db: DatabaseService) -> str:
            await asyncio.sleep(0.001)
            return db.connection_string

        result = await async_process()
        assert result == "sqlite://"

    def test_inject_with_defaults(self):
        """Test injection with default parameters."""
        app = Whiskey()
        app.singleton(SimpleService)

        @app.inject
        def greet(service: SimpleService, name: str = "World") -> str:
            return f"{service.value}: Hello, {name}!"

        result = greet()
        assert result == "test: Hello, World!"

    def test_call_method(self):
        """Test app.call() method."""
        app = Whiskey()
        app.singleton(SimpleService)

        def calculate(service: SimpleService, x: int) -> str:
            return f"{service.value}: {x * 2}"

        result = app.call(calculate, x=5)
        assert result == "test: 10"

    async def test_call_async(self):
        """Test app.call() with async function."""
        app = Whiskey()
        app.singleton(DatabaseService)

        async def get_info(db: DatabaseService) -> str:
            await asyncio.sleep(0.001)
            return f"Connected to: {db.connection_string}"

        result = await app.call_async(get_info)
        assert result == "Connected to: sqlite://"

    def test_invoke_method(self):
        """Test app.invoke() method."""
        app = Whiskey()
        app.singleton(SimpleService)

        def get_value(service: SimpleService) -> str:
            return service.value

        result = app.invoke(get_value)
        assert result == "test"

    def test_automatic_dependency_resolution(self):
        """Test automatic dependency resolution."""
        app = Whiskey()
        app.transient(DatabaseService)
        app.transient(CacheService)
        app.transient(ComplexService)

        instance = app.resolve(ComplexService)
        assert isinstance(instance, ComplexService)
        assert isinstance(instance.db, DatabaseService)
        assert isinstance(instance.cache, CacheService)


class TestLifecycle:
    """Test application lifecycle management."""

    async def test_startup_shutdown(self):
        """Test basic startup and shutdown."""
        app = Whiskey()
        startup_called = False
        shutdown_called = False

        @app.on_startup
        async def startup():
            nonlocal startup_called
            startup_called = True

        @app.on_shutdown
        async def shutdown():
            nonlocal shutdown_called
            shutdown_called = True

        await app.start()
        assert startup_called
        assert app._is_running

        await app.stop()
        assert shutdown_called
        assert not app._is_running

    async def test_sync_lifecycle_callbacks(self):
        """Test sync callbacks in lifecycle."""
        app = Whiskey()
        events = []

        @app.on_startup
        def sync_startup():
            events.append("startup")

        @app.on_shutdown
        def sync_shutdown():
            events.append("shutdown")

        await app.start()
        await app.stop()

        assert events == ["startup", "shutdown"]

    async def test_multiple_startup_callbacks(self):
        """Test multiple startup callbacks execute in order."""
        app = Whiskey()
        events = []

        @app.on_startup
        async def first():
            events.append("first")

        @app.on_startup
        async def second():
            events.append("second")

        await app.start()
        assert events == ["first", "second"]

    async def test_error_handler(self):
        """Test error handler registration."""
        app = Whiskey()
        handled_errors = []

        @app.on_error
        async def handle_value_error(error: ValueError):
            handled_errors.append(error)

        # Emit error event
        error = ValueError("Test error")
        await app.emit("error", error)

        assert len(handled_errors) == 1
        assert handled_errors[0] is error

    async def test_service_initialization(self):
        """Test services implementing Initializable."""
        app = Whiskey()
        initialized = False

        @app.component
        class InitializableService(Initializable):
            async def initialize(self):
                nonlocal initialized
                initialized = True

        # Start app should initialize services
        await app.start()
        assert initialized

    async def test_service_disposal(self):
        """Test services implementing Disposable."""
        app = Whiskey()
        disposed = False

        @app.system  # Singleton so we can track disposal
        class DisposableService(Disposable):
            async def dispose(self):
                nonlocal disposed
                disposed = True

        # Resolve to create instance
        app.resolve(DisposableService)

        # Stop app should dispose services
        await app.start()
        await app.stop()
        assert disposed

    async def test_context_manager(self):
        """Test using Whiskey as context manager."""
        events = []

        async with Whiskey() as app:

            @app.on_startup
            async def on_start():
                events.append("started")

            @app.on_shutdown
            async def on_stop():
                events.append("stopped")

            assert app._is_running
            # Allow startup callbacks to run
            await asyncio.sleep(0)
            events.append("running")

        assert events == ["started", "running", "stopped"]

    def test_sync_context_manager(self):
        """Test using Whiskey as sync context manager."""
        with Whiskey() as app:
            app.singleton(SimpleService)
            instance = app.resolve(SimpleService)
            assert isinstance(instance, SimpleService)


class TestExtensions:
    """Test extension functionality."""

    def test_use_extension(self):
        """Test applying extensions."""
        app = Whiskey()
        applied = []

        def extension1(app: Whiskey, **kwargs):
            applied.append("ext1")
            app.ext1_applied = True

        def extension2(app: Whiskey, **kwargs):
            applied.append("ext2")
            app.ext2_applied = True

        app.use(extension1)
        app.use(extension2)

        assert applied == ["ext1", "ext2"]
        assert hasattr(app, "ext1_applied")
        assert hasattr(app, "ext2_applied")

    def test_extension_adds_functionality(self):
        """Test extension adding new functionality."""
        app = Whiskey()

        def auth_extension(app: Whiskey, **kwargs):
            """Add authentication functionality."""
            # Add new decorator
            def require_auth(func):
                def wrapper(*args, **kwargs):
                    # Check auth here
                    return func(*args, **kwargs)
                return wrapper
            
            app.add_decorator("require_auth", require_auth)
            
            # Add new method
            app.authenticate = lambda user, password: user == "admin" and password == "secret"

        app.use(auth_extension)

        # Test new functionality
        assert hasattr(app, "require_auth")
        assert hasattr(app, "authenticate") 
        assert app.authenticate("admin", "secret")
        assert not app.authenticate("user", "wrong")
    
    def test_extension_with_kwargs(self):
        """Test extension with configuration kwargs."""
        app = Whiskey()
        
        def configurable_extension(app: Whiskey, prefix: str = "default_", 
                                   enable_logging: bool = False, **kwargs):
            """Extension that accepts configuration."""
            app.config = {
                "prefix": prefix,
                "enable_logging": enable_logging,
                "extra": kwargs
            }
            
            # Add method using config
            def get_prefixed(name: str) -> str:
                return f"{prefix}{name}"
            
            app.get_prefixed = get_prefixed
        
        # Use extension with custom config
        app.use(configurable_extension, prefix="custom_", enable_logging=True, 
                custom_option="value")
        
        # Test configuration was applied
        assert app.config["prefix"] == "custom_"
        assert app.config["enable_logging"] is True
        assert app.config["extra"]["custom_option"] == "value"
        assert app.get_prefixed("test") == "custom_test"


class TestBuilderIntegration:
    """Test WhiskeyBuilder integration."""

    def test_configure_with_builder(self):
        """Test configuring app with builder."""
        app = Whiskey()

        def configure(builder: WhiskeyBuilder):
            builder.add_singleton(SimpleService, instance=SimpleService("configured"))
            builder.add_transient(DatabaseService)

        app.configure(configure)

        # Verify registrations
        simple = app.resolve(SimpleService)
        assert simple.value == "configured"

        db = app.resolve(DatabaseService)
        assert isinstance(db, DatabaseService)

    def test_builder_property(self):
        """Test accessing container builder."""
        app = Whiskey()

        # Should create and return builder
        builder = app.builder
        assert isinstance(builder, ComponentBuilder)

        # Builder should add to the app's container
        builder._app_builder = app

    def test_build_method(self):
        """Test build() method."""
        app = Whiskey()

        # Configure using builder
        app.container.add_singleton(SimpleService).build()

        instance = app.resolve(SimpleService)
        assert isinstance(instance, SimpleService)


class TestEventEmitter:
    """Test event emitter functionality."""

    async def test_emit_event(self):
        """Test emitting custom events."""
        app = Whiskey()
        received_events = []

        @app.on("custom_event")
        async def handle_custom(data):
            received_events.append(data)

        await app.emit("custom_event", {"value": 42})
        assert len(received_events) == 1
        assert received_events[0] == {"value": 42}

    async def test_wildcard_event_handler(self):
        """Test wildcard event handlers."""
        app = Whiskey()
        all_events = []

        @app.on("*")
        async def handle_all(event_name, data):
            all_events.append((event_name, data))

        await app.emit("event1", "data1")
        await app.emit("event2", "data2")

        assert len(all_events) == 2
        assert all_events[0] == ("event1", "data1")
        assert all_events[1] == ("event2", "data2")

    def test_hook_decorator(self):
        """Test @app.hook decorator."""
        app = Whiskey()
        hooks_called = []

        @app.hook("before_resolve")
        def before_resolve_hook(key):
            hooks_called.append(("before_resolve", key))

        # Hooks would be called during resolution
        # This tests the registration
        assert "before_resolve" in app._hooks
        assert len(app._hooks["before_resolve"]) == 1


class TestTaskManagement:
    """Test background task functionality."""

    async def test_task_decorator(self):
        """Test @app.task decorator."""
        app = Whiskey()
        task_runs = []

        @app.task(interval=0.1)
        async def background_task():
            task_runs.append(1)

        # Start app to begin tasks
        await app.start()

        # Wait for task to run
        await asyncio.sleep(0.15)

        # Stop app to cancel tasks
        await app.stop()

        assert len(task_runs) > 0

    async def test_task_with_dependencies(self):
        """Test task with injected dependencies."""
        app = Whiskey()
        app.singleton(SimpleService, instance=SimpleService("task"))
        results = []

        @app.task(interval=0.1)
        @app.inject
        async def service_task(service: SimpleService):
            results.append(service.value)

        await app.start()
        await asyncio.sleep(0.15)
        await app.stop()

        assert len(results) > 0
        assert all(r == "task" for r in results)


class TestExtensionSystem:
    """Test extension system functionality."""

    def test_extend_method(self):
        """Test extending app with custom methods."""
        app = Whiskey()

        def my_extension(app_instance):
            # Add custom method
            app_instance.custom_method = lambda: "extended"

        app.extend(my_extension)

        assert hasattr(app, "custom_method")
        assert app.custom_method() == "extended"

    def test_add_decorator_method(self):
        """Test adding custom decorators."""
        app = Whiskey()
        decorated_items = []

        def custom_decorator(name):
            def decorator(cls):
                decorated_items.append((name, cls))
                return cls

            return decorator

        app.add_decorator("custom", custom_decorator)

        @app.custom("test")
        class TestClass:
            pass

        assert len(decorated_items) == 1
        assert decorated_items[0] == ("test", TestClass)


class TestErrorHandling:
    """Test error handling scenarios."""

    def test_resolve_missing_service(self):
        """Test resolving unregistered service."""
        app = Whiskey()

        with pytest.raises(ResolutionError):
            app.resolve("missing_service")

    def test_circular_dependency(self):
        """Test circular dependency detection."""
        app = Whiskey()

        class ServiceA:
            def __init__(self, b: "ServiceB"):
                self.b = b

        class ServiceB:
            def __init__(self, a: ServiceA):
                self.a = a

        app.transient(ServiceA)
        app.transient(ServiceB)

        with pytest.raises(Exception):  # Would be CircularDependencyError
            app.resolve(ServiceA)

    async def test_startup_error_handling(self):
        """Test error during startup."""
        app = Whiskey()

        @app.on_startup
        async def failing_startup():
            raise RuntimeError("Startup failed")

        with pytest.raises(RuntimeError):
            await app.start()

        # App should not be running after failed startup
        assert not app._is_running

    def test_invalid_configuration(self):
        """Test invalid configuration scenarios."""
        app = Whiskey()

        # Test registering None as provider
        with pytest.raises(ValueError):
            app.register("service", None)


class TestMetadataAndPriority:
    """Test component metadata and priority features."""

    def test_component_with_metadata(self):
        """Test registering component with metadata."""
        app = Whiskey()

        @app.component(metadata={"version": "1.0", "author": "test"}, tags={"core", "stable"})
        class MetadataService:
            pass

        # Metadata would be accessible through registry
        # This tests the registration accepts metadata

    def test_component_priority(self):
        """Test component registration priority."""
        app = Whiskey()
        registration_order = []

        @app.component(priority=10)
        class HighPriorityService:
            def __init__(self):
                registration_order.append("high")

        @app.component(priority=1)
        class LowPriorityService:
            def __init__(self):
                registration_order.append("low")

        # Priority would affect initialization order
        # This tests priority parameter is accepted


class TestEdgeCases:
    """Test edge cases and special scenarios."""

    def test_empty_app_resolution(self):
        """Test resolution in empty app."""
        app = Whiskey()

        # Should auto-create simple classes
        instance = app.resolve(SimpleService)
        assert isinstance(instance, SimpleService)

    def test_resolve_with_name_override(self):
        """Test resolving with name parameter."""
        app = Whiskey()
        app.singleton(SimpleService, instance=SimpleService("primary"), name="primary")
        app.singleton(SimpleService, instance=SimpleService("secondary"), name="secondary")

        primary = app.resolve(SimpleService, name="primary")
        secondary = app.resolve(SimpleService, name="secondary")

        assert primary.value == "primary"
        assert secondary.value == "secondary"

    def test_optional_dependency_resolution(self):
        """Test resolution with optional dependencies."""
        app = Whiskey()

        class OptionalDepService:
            def __init__(self, db: Optional[DatabaseService] = None):
                self.db = db

        app.transient(OptionalDepService)
        # Don't register DatabaseService

        instance = app.resolve(OptionalDepService)
        assert instance.db is None

    async def test_async_with_sync_resolve(self):
        """Test mixing async and sync resolution."""
        app = Whiskey()
        app.factory(SimpleService, create_simple_service)

        # Sync resolve of sync factory
        instance = app.resolve(SimpleService)
        assert instance.value == "factory"

        # Async resolve of sync factory
        instance2 = await app.resolve_async(SimpleService)
        assert instance2.value == "factory"

    def test_whiskey_singleton_behavior(self):
        """Test that Whiskey itself is not a singleton."""
        app1 = Whiskey()
        app2 = Whiskey()

        assert app1 is not app2
        assert app1.container is not app2.container
