<<<<<<< HEAD
"""Comprehensive tests for the decorators module."""

import asyncio
import os
from unittest.mock import patch

import pytest

from whiskey.core.application import Whiskey
from whiskey.core.decorators import (
    _get_default_app,
    call,
    call_sync,
    component,
    configure_app,
    factory,
    get_app,
    inject,
    invoke,
    on_error,
    on_shutdown,
    on_startup,
    provide,
    resolve,
    resolve_async,
    scoped,
    singleton,
    when_debug,
    when_env,
    when_production,
    wrap_function,
)
from whiskey.core.errors import ResolutionError
from whiskey.core.registry import Scope


# Test services
class SimpleService:
    """Simple test service."""

    def __init__(self):
        self.value = "simple"


class DependentService:
    """Service with dependencies."""

    def __init__(self, simple: SimpleService):
        self.simple = simple


class TestGlobalAppManagement:
    """Test default app initialization and management."""

    def teardown_method(self):
        """Reset global state between tests."""
        import whiskey.core.decorators

        whiskey.core.decorators._default_app = None

    def test_get_default_app_creates_instance(self):
        """Test that _get_default_app creates a default instance."""
        app = _get_default_app()
        assert isinstance(app, Whiskey)
        assert app is not None

        # Should return same instance on subsequent calls
        app2 = _get_default_app()
        assert app is app2

    def test_get_app_returns_default(self):
        """Test get_app returns the default app."""
        app = get_app()
        assert isinstance(app, Whiskey)
        assert app is _get_default_app()

    def test_configure_app(self):
        """Test configuring the default app."""
        config_called = False
        received_app = None

        def config_func(app):
            nonlocal config_called, received_app
            config_called = True
            received_app = app
            app.container.singleton("test_config", "configured")

        configure_app(config_func)

        assert config_called
        assert isinstance(received_app, Whiskey)
        assert get_app().resolve("test_config") == "configured"


class TestComponentDecorators:
    """Test global component registration decorators."""

    def teardown_method(self):
        """Reset global state between tests."""
        import whiskey.core.decorators

        whiskey.core.decorators._default_app = None

    def test_component_decorator_simple(self):
        """Test simple component decorator usage."""

        @component
        class MyService:
            pass

        # Should be registered in default app
        app = get_app()
        instance = app.resolve(MyService)
        assert isinstance(instance, MyService)

    def test_component_decorator_with_params(self):
        """Test component decorator with parameters."""

        @component(key="custom_service", scope=Scope.SINGLETON)
        class MyService:
            def __init__(self):
                self.id = id(self)

        app = get_app()

        # Should be registered with custom key
        instance1 = app.resolve("custom_service")
        instance2 = app.resolve("custom_service")

        # Should be singleton
        assert instance1 is instance2
        assert isinstance(instance1, MyService)

    def test_singleton_decorator(self):
        """Test singleton decorator."""

        @singleton
        class SingletonService:
            def __init__(self):
                self.id = id(self)

        app = get_app()
        instance1 = app.resolve(SingletonService)
        instance2 = app.resolve(SingletonService)

        assert instance1 is instance2
        assert instance1.id == instance2.id
=======
"""Tests for simplified decorator functionality."""

import asyncio
import pytest

from whiskey import Container, factory, inject, provide, scoped, singleton
from whiskey.core.decorators import get_default_container, set_default_container


class SimpleService:
    """Simple test service."""
    def __init__(self):
        self.value = "simple"


class DependentService:
    """Service with dependencies."""
    def __init__(self, simple: SimpleService):
        self.simple = simple


class TestProvideDecorator:
    """Test @provide decorator."""
    
    @pytest.fixture(autouse=True)
    def reset_default_container(self):
        """Reset default container before each test."""
        set_default_container(Container())
        yield
        set_default_container(None)
    
    @pytest.mark.unit
    def test_provide_decorator(self):
        """Test @provide registers with default container."""
        @provide
        class TestService:
            pass
        
        container = get_default_container()
        assert TestService in container
    
    @pytest.mark.unit
    async def test_provide_with_context_container(self):
        """Test @provide uses context container."""
        container = Container()
        
        with container:
            @provide
            class TestService:
                pass
        
        assert TestService in container
        resolved = await container.resolve(TestService)
        assert isinstance(resolved, TestService)


class TestSingletonDecorator:
    """Test @singleton decorator."""
    
    @pytest.fixture(autouse=True)
    def reset_default_container(self):
        """Reset default container before each test."""
        set_default_container(Container())
        yield
        set_default_container(None)
    
    @pytest.mark.unit
    async def test_singleton_decorator(self):
        """Test @singleton creates singletons."""
        @singleton
        class TestService:
            pass
        
        container = get_default_container()
        resolved1 = await container.resolve(TestService)
        resolved2 = await container.resolve(TestService)
        
        assert resolved1 is resolved2


class TestFactoryDecorator:
    """Test @factory decorator."""
    
    @pytest.fixture(autouse=True)
    def reset_default_container(self):
        """Reset default container before each test."""
        set_default_container(Container())
        yield
        set_default_container(None)
    
    @pytest.mark.unit
    async def test_factory_decorator(self):
        """Test @factory registers factory functions."""
        @factory(SimpleService)
        def create_simple() -> SimpleService:
            service = SimpleService()
            service.value = "factory-created"
            return service
        
        container = get_default_container()
        resolved = await container.resolve(SimpleService)
        assert resolved.value == "factory-created"
    
    @pytest.mark.unit
    async def test_factory_with_dependencies(self):
        """Test factory with dependencies."""
        @provide
        class BaseService:
            pass
        
        @factory(DependentService)
        def create_dependent(simple: SimpleService) -> DependentService:
            return DependentService(simple)
        
        container = get_default_container()
        container[SimpleService] = SimpleService
        
        resolved = await container.resolve(DependentService)
        assert isinstance(resolved, DependentService)
        assert isinstance(resolved.simple, SimpleService)
>>>>>>> origin/main

    def test_factory_decorator(self):
        """Test factory decorator."""
        creation_count = 0

<<<<<<< HEAD
        @factory(SimpleService)
        def create_simple() -> SimpleService:
            nonlocal creation_count
            creation_count += 1
            service = SimpleService()
            service.value = f"factory_{creation_count}"
            return service

        app = get_app()
        instance1 = app.resolve(SimpleService)
        instance2 = app.resolve(SimpleService)

        # Factory should create new instances
        assert instance1 is not instance2
        assert instance1.value == "factory_1"
        assert instance2.value == "factory_2"

    def test_factory_with_dependencies(self):
        """Test factory with injected dependencies."""

        @component
        class Database:
            def __init__(self):
                self.connected = True

        @factory(DependentService)
        def create_dependent(simple: SimpleService) -> DependentService:
            return DependentService(simple)

        app = get_app()
        app.container.register(SimpleService, SimpleService)

        instance = app.resolve(DependentService)
        assert isinstance(instance, DependentService)
        assert isinstance(instance.simple, SimpleService)

    def test_scoped_decorator(self):
        """Test scoped decorator."""

        @scoped("request")
        class RequestScopedService:
            def __init__(self):
                self.id = id(self)

        app = get_app()

        # Should be registered with scope
        # Note: trying to resolve scoped service without active scope should fail
        from whiskey.core.errors import ScopeError
        with pytest.raises(ScopeError):
            app.resolve(RequestScopedService)

    def test_provide_alias(self):
        """Test that provide is an alias for component."""
        assert provide is component


class TestInjectionDecorator:
    """Test the inject decorator."""

    def teardown_method(self):
        """Reset global state between tests."""
        import whiskey.core.decorators

        whiskey.core.decorators._default_app = None

    def test_inject_sync_function(self):
        """Test inject decorator with sync function."""

        @component
        class Service:
            def __init__(self):
                self.value = 42

        @inject
        def calculate(service: Service, x: int) -> int:
            return service.value + x

        result = calculate(x=10)
        assert result == 52

    async def test_inject_async_function(self):
        """Test inject decorator with async function."""

        @component
        class Service:
            def __init__(self):
                self.value = 42

        @inject
        async def calculate(service: Service, x: int) -> int:
            await asyncio.sleep(0)
            return service.value + x

        result = await calculate(x=10)
        assert result == 52

    def test_inject_with_defaults(self):
        """Test inject with default values."""

        @component
        class Service:
            def __init__(self):
                self.value = "test"

        @inject
        def greet(service: Service, name: str = "World") -> str:
            return f"{service.value}: Hello, {name}!"

        # Should use default
        result1 = greet()
        assert result1 == "test: Hello, World!"

        # Should override default
        result2 = greet(name="Python")
        assert result2 == "test: Hello, Python!"

    def test_inject_partial_arguments(self):
        """Test inject with partial arguments."""

        @component
        class Service:
            def __init__(self):
                self.multiplier = 2

        @inject
        def multiply(x: int, service: Service, y: int) -> int:
            return x * service.multiplier * y

        # Provide non-injected arguments
        result = multiply(3, y=4)
        assert result == 24

    def test_inject_missing_service(self):
        """Test inject with missing service."""

        class MissingService:
            pass

        @inject
        def use_missing(service: MissingService) -> str:
            return "should not reach here"

        with pytest.raises(ResolutionError):
            use_missing()

    def test_inject_preserves_function_metadata(self):
        """Test that inject preserves function metadata."""

        @inject
        def documented_function(service: SimpleService) -> str:
            """This is a documented function."""
            return service.value

        assert documented_function.__name__ == "documented_function"
        assert documented_function.__doc__ == "This is a documented function."


class TestLifecycleDecorators:
    """Test lifecycle decorators."""

    def teardown_method(self):
        """Reset global state between tests."""
        import whiskey.core.decorators

        whiskey.core.decorators._default_app = None

    async def test_on_startup_decorator(self):
        """Test on_startup decorator."""
        startup_called = False

        @on_startup
        async def initialize():
            nonlocal startup_called
            startup_called = True

        app = get_app()
        await app.start()

        assert startup_called

    async def test_on_shutdown_decorator(self):
        """Test on_shutdown decorator."""
        shutdown_called = False

        @on_shutdown
        async def cleanup():
            nonlocal shutdown_called
            shutdown_called = True

        app = get_app()
        await app.start()
        await app.stop()

        assert shutdown_called

    async def test_on_error_decorator(self):
        """Test on_error decorator."""
        error_handled = False
        caught_exception = None

        @on_error
        async def handle_error(error: Exception):
            nonlocal error_handled, caught_exception
            error_handled = True
            caught_exception = error

        app = get_app()

        # Trigger an error
        test_error = ValueError("Test error")
        await app.emit("error", test_error)

        assert error_handled
        assert caught_exception is test_error

    def test_on_startup_sync_function(self):
        """Test on_startup with sync function."""
        startup_called = False

        @on_startup
        def initialize():
            nonlocal startup_called
            startup_called = True

        app = get_app()
        # Startup hooks are called during app.start()
        assert initialize in app._hooks["before_startup"]


class TestConditionalDecorators:
    """Test conditional registration decorators."""

    def teardown_method(self):
        """Reset global state between tests."""
        import whiskey.core.decorators

        whiskey.core.decorators._default_app = None

    def test_when_env_decorator(self):
        """Test when_env decorator."""

        @when_env("TEST_ENV", "true")
        @component
        class TestService:
            pass

        # Set environment variable
        with patch.dict(os.environ, {"TEST_ENV": "true"}):
            app = get_app()
            instance = app.resolve(TestService)
            assert isinstance(instance, TestService)

    def test_when_env_not_matching(self):
        """Test when_env when condition doesn't match."""

        @when_env("TEST_ENV", "production")
        @component
        class TestService:
            pass

        # Environment variable not set or different value
        with patch.dict(os.environ, {"TEST_ENV": "development"}):
            app = get_app()
            with pytest.raises(ResolutionError):
                app.resolve(TestService)

    def test_when_debug_decorator(self):
        """Test when_debug decorator."""

        @when_debug
        @component
        class DebugService:
            pass

        # Mock debug mode
        with patch.dict(os.environ, {"DEBUG": "true"}):
            app = get_app()
            instance = app.resolve(DebugService)
            assert isinstance(instance, DebugService)

    def test_when_production_decorator(self):
        """Test when_production decorator."""

        @when_production
        @component
        class ProductionService:
            pass

        # Mock production environment
        with patch.dict(os.environ, {"ENV": "production"}):
            app = get_app()
            instance = app.resolve(ProductionService)
            assert isinstance(instance, ProductionService)


class TestResolutionFunctions:
    """Test global resolution functions."""

    def teardown_method(self):
        """Reset global state between tests."""
        import whiskey.core.decorators

        whiskey.core.decorators._default_app = None

    def test_resolve_sync(self):
        """Test synchronous resolution."""

        @component
        class Service:
            def __init__(self):
                self.value = "resolved"

        instance = resolve(Service)
        assert isinstance(instance, Service)
        assert instance.value == "resolved"

    async def test_resolve_async(self):
        """Test asynchronous resolution."""

        @component
        class Service:
            def __init__(self):
                self.value = "async_resolved"

        instance = await resolve_async(Service)
        assert isinstance(instance, Service)
        assert instance.value == "async_resolved"

    def test_resolve_with_name(self):
        """Test resolution by key."""

        @component(key="named_service")
        class Service:
            pass

        instance = resolve("named_service")
        assert isinstance(instance, Service)

    def test_resolve_missing_service(self):
        """Test resolving missing service."""

        class MissingService:
            pass

        with pytest.raises(ResolutionError):
            resolve(MissingService)


class TestCallFunctions:
    """Test global call and invoke functions."""

    def teardown_method(self):
        """Reset global state between tests."""
        import whiskey.core.decorators

        whiskey.core.decorators._default_app = None

    def test_call_sync(self):
        """Test synchronous call."""

        @component
        class Service:
            def __init__(self):
                self.value = 10

        def calculate(service: Service, x: int) -> int:
            return service.value * x

        result = call_sync(calculate, x=5)
        assert result == 50

    async def test_call_async(self):
        """Test asynchronous call."""

        @component
        class Service:
            def __init__(self):
                self.value = 10

        async def calculate(service: Service, x: int) -> int:
            await asyncio.sleep(0)
            return service.value * x

        result = await call(calculate, x=5)
        assert result == 50

    def test_invoke_sync(self):
        """Test synchronous invoke."""

        @component
        class Service:
            def __init__(self):
                self.message = "Hello"

        def get_message(service: Service) -> str:
            return service.message

        result = invoke(get_message)
        assert result == "Hello"

    async def test_invoke_async(self):
        """Test asynchronous invoke with async function."""

        @component
        class Service:
            def __init__(self):
                self.message = "Async Hello"

        async def get_message(service: Service) -> str:
            await asyncio.sleep(0)
            return service.message

        result = await invoke(get_message)
        assert result == "Async Hello"


class TestWrapFunction:
    """Test wrap_function utility."""

    def teardown_method(self):
        """Reset global state between tests."""
        import whiskey.core.decorators

        whiskey.core.decorators._default_app = None

    def test_wrap_function_sync(self):
        """Test wrapping a sync function."""

        @component
        class Service:
            def __init__(self):
                self.prefix = "wrapped"

        def original_func(service: Service, text: str) -> str:
            return f"{service.prefix}: {text}"

        wrapped = wrap_function(original_func)
        result = wrapped(text="test")
        assert result == "wrapped: test"

    async def test_wrap_function_async(self):
        """Test wrapping an async function."""

        @component
        class Service:
            def __init__(self):
                self.prefix = "async_wrapped"

        async def original_func(service: Service, text: str) -> str:
            await asyncio.sleep(0)
            return f"{service.prefix}: {text}"

        wrapped = wrap_function(original_func)
        result = await wrapped(text="test")
        assert result == "async_wrapped: test"

    def test_wrap_function_preserves_metadata(self):
        """Test that wrap_function preserves metadata."""

        def original_func(x: int) -> int:
            """Original docstring."""
            return x * 2

        wrapped = wrap_function(original_func)
        assert wrapped.__name__ == "original_func"
        assert wrapped.__doc__ == "Original docstring."


class TestDecoratorChaining:
    """Test chaining multiple decorators."""

    def teardown_method(self):
        """Reset global state between tests."""
        import whiskey.core.decorators

        whiskey.core.decorators._default_app = None

    def test_conditional_singleton(self):
        """Test combining conditional and singleton decorators."""

        @when_env("ENABLE_CACHE", "true")
        @singleton
        class CacheService:
            def __init__(self):
                self.id = id(self)

        with patch.dict(os.environ, {"ENABLE_CACHE": "true"}):
            app = get_app()
            instance1 = app.resolve(CacheService)
            instance2 = app.resolve(CacheService)

            assert instance1 is instance2
            assert instance1.id == instance2.id

    def test_multiple_conditions(self):
        """Test multiple conditional decorators."""

        @when_env("FEATURE_FLAG", "enabled")
        @when_debug
        @component
        class DebugFeatureService:
            pass

        # Both conditions must be true
        with patch.dict(os.environ, {"FEATURE_FLAG": "enabled", "DEBUG": "true"}):
            app = get_app()
            instance = app.resolve(DebugFeatureService)
            assert isinstance(instance, DebugFeatureService)

        # If either condition is false, should not resolve
        with patch.dict(os.environ, {"FEATURE_FLAG": "disabled", "DEBUG": "true"}):
            app2 = Whiskey()  # New app instance
            import whiskey.core.decorators

            whiskey.core.decorators._default_app = app2

            with pytest.raises(ResolutionError):
                app2.resolve(DebugFeatureService)


class TestEdgeCases:
    """Test edge cases and error handling."""

    def teardown_method(self):
        """Reset global state between tests."""
        import whiskey.core.decorators

        whiskey.core.decorators._default_app = None

    def test_inject_no_type_hints(self):
        """Test inject with function lacking type hints."""

        @inject
        def no_hints(x, y):
            return x + y

        # Should work with explicit arguments
        result = no_hints(1, 2)
        assert result == 3

    def test_factory_without_return_type(self):
        """Test factory without return type annotation."""

        @factory(SimpleService)
        def create_service():
            return SimpleService()

        app = get_app()
        instance = app.resolve(SimpleService)
        assert isinstance(instance, SimpleService)

    def test_component_on_non_class(self):
        """Test component decorator on non-class."""

        with pytest.raises(TypeError):

            @component
            def not_a_class():
                pass

    def test_resolve_with_none_key(self):
        """Test resolve with None key."""

        with pytest.raises(ValueError):
            resolve(None)

    def test_multiple_factory_registrations(self):
        """Test multiple factories for same type."""

        @factory(SimpleService)
        def factory1():
            service = SimpleService()
            service.value = "factory1"
            return service

        @factory(SimpleService)
        def factory2():
            service = SimpleService()
            service.value = "factory2"
            return service

        # Last registration wins
        app = get_app()
        instance = app.resolve(SimpleService)
        assert instance.value == "factory2"
=======
class TestInjectDecorator:
    """Test @inject decorator."""
    
    @pytest.fixture(autouse=True)
    def reset_default_container(self):
        """Reset default container before each test."""
        set_default_container(Container())
        yield
        set_default_container(None)
    
    @pytest.mark.unit
    async def test_inject_async_function(self):
        """Test @inject with async function."""
        container = get_default_container()
        container[SimpleService] = SimpleService
        
        @inject
        async def test_func(service: SimpleService) -> str:
            return service.value
        
        result = await test_func()
        assert result == "simple"
    
    @pytest.mark.unit
    def test_inject_sync_function(self):
        """Test @inject with sync function."""
        container = get_default_container()
        container[SimpleService] = SimpleService()
        
        @inject
        def test_func(service: SimpleService) -> str:
            return service.value
        
        result = test_func()
        assert result == "simple"
    
    @pytest.mark.unit
    async def test_inject_partial_args(self):
        """Test @inject with partial arguments."""
        container = get_default_container()
        container[SimpleService] = SimpleService
        
        @inject
        async def test_func(name: str, service: SimpleService) -> str:
            return f"{name}: {service.value}"
        
        result = await test_func("test")
        assert result == "test: simple"
    
    @pytest.mark.unit
    async def test_inject_with_defaults(self):
        """Test @inject with default values."""
        @inject
        async def test_func(service: SimpleService, name: str = "default") -> str:
            return f"{name}: {service.value}"
        
        container = get_default_container()
        container[SimpleService] = SimpleService
        
        result = await test_func()
        assert result == "default: simple"
    
    @pytest.mark.unit
    async def test_inject_missing_service(self):
        """Test @inject with missing service."""
        from abc import ABC, abstractmethod
        
        class AbstractService(ABC):
            @abstractmethod
            def get_value(self) -> str:
                pass
        
        @inject
        async def test_func(service: AbstractService) -> str:
            return service.get_value()
        
        with pytest.raises(KeyError):
            await test_func()


class TestScopedDecorator:
    """Test @scoped decorator."""
    
    @pytest.fixture(autouse=True)
    def reset_default_container(self):
        """Reset default container before each test."""
        set_default_container(Container())
        yield
        set_default_container(None)
    
    @pytest.mark.unit
    def test_scoped_decorator(self):
        """Test @scoped registers with custom scope."""
        @scoped("custom")
        class TestService:
            pass
        
        # For now, scoped just registers with the scope name
        # The actual scope behavior would be implemented in extensions
        container = get_default_container()
        assert TestService in container
>>>>>>> origin/main
