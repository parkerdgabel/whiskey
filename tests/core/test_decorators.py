"""Tests for decorator functionality."""

import asyncio

import pytest

from whiskey.core.container import Container
from whiskey.core.decorators import (
    factory,
    get_default_container,
    inject,
    named,
    provide,
    scoped,
    set_default_container,
    singleton,
)
from whiskey.core.types import ScopeType
from ..conftest import SimpleService, DependentService


class TestProvideDecorator:
    """Test @provide decorator."""
    
    @pytest.mark.unit
    def test_provide_without_params(self, container):
        """Test @provide without parameters."""
        @provide
        class TestService:
            pass
        
        assert container.has_service(TestService)
        descriptor = container.get_descriptor(TestService)
        assert descriptor.scope == ScopeType.TRANSIENT
    
    @pytest.mark.unit
    def test_provide_with_scope(self, container):
        """Test @provide with scope parameter."""
        @provide(scope=ScopeType.SINGLETON)
        class TestService:
            pass
        
        descriptor = container.get_descriptor(TestService)
        assert descriptor.scope == ScopeType.SINGLETON
    
    @pytest.mark.unit
    def test_provide_with_name(self, container):
        """Test @provide with name parameter."""
        @provide(name="special")
        class TestService:
            pass
        
        assert container.has_service(TestService, name="special")
    
    @pytest.mark.unit
    def test_provide_with_metadata(self, container):
        """Test @provide with metadata."""
        @provide(version="1.0", author="test")
        class TestService:
            pass
        
        descriptor = container.get_descriptor(TestService)
        assert descriptor.metadata["version"] == "1.0"
        assert descriptor.metadata["author"] == "test"
    
    @pytest.mark.unit
    def test_provide_marks_injectable(self, container):
        """Test @provide marks class as injectable."""
        @provide
        class TestService:
            pass
        
        assert hasattr(TestService, "__whiskey_injectable__")
        assert TestService.__whiskey_injectable__ is True


class TestSingletonDecorator:
    """Test @singleton decorator."""
    
    @pytest.mark.unit
    def test_singleton_decorator(self, container):
        """Test @singleton registers as singleton."""
        @singleton
        class TestService:
            pass
        
        descriptor = container.get_descriptor(TestService)
        assert descriptor.scope == ScopeType.SINGLETON
    
    @pytest.mark.unit
    async def test_singleton_returns_same_instance(self, container):
        """Test @singleton creates single instance."""
        @singleton
        class TestService:
            def __init__(self):
                self.id = id(self)
        
        instance1 = await container.resolve(TestService)
        instance2 = await container.resolve(TestService)
        
        assert instance1 is instance2
        assert instance1.id == instance2.id


class TestInjectDecorator:
    """Test @inject decorator."""
    
    @pytest.mark.unit
    async def test_inject_function(self, container):
        """Test @inject on regular function."""
        container.register(SimpleService, implementation=SimpleService)
        
        @inject
        async def test_func(service: SimpleService) -> str:
            return service.value
        
        result = await test_func()
        assert result == "simple"
    
    @pytest.mark.unit
    def test_inject_sync_function(self, container):
        """Test @inject on sync function."""
        container.register(SimpleService, implementation=SimpleService)
        
        @inject
        def test_func(service: SimpleService) -> str:
            return service.value
        
        result = test_func()
        assert result == "simple"
    
    @pytest.mark.unit
    async def test_inject_partial_args(self, container):
        """Test @inject with partial arguments."""
        container.register(SimpleService, implementation=SimpleService)
        
        @inject
        async def test_func(name: str, service: SimpleService) -> str:
            return f"{name}: {service.value}"
        
        result = await test_func("test")
        assert result == "test: simple"
    
    @pytest.mark.unit
    async def test_inject_with_defaults(self, container):
        """Test @inject respects default values."""
        container.register(SimpleService, implementation=SimpleService)
        
        @inject
        async def test_func(
            service: SimpleService,
            name: str = "default"
        ) -> str:
            return f"{name}: {service.value}"
        
        result = await test_func()
        assert result == "default: simple"
    
    @pytest.mark.unit
    async def test_inject_with_overrides(self, container):
        """Test @inject with override parameters."""
        mock_service = SimpleService()
        mock_service.value = "mocked"
        
        @inject(service=mock_service)
        async def test_func(service: SimpleService) -> str:
            return service.value
        
        result = await test_func()
        assert result == "mocked"
    
    @pytest.mark.unit
    async def test_inject_optional_dependency(self, container):
        """Test @inject with optional dependency."""
        # Don't register SimpleService
        
        @inject
        async def test_func(service: SimpleService | None = None) -> str:
            return "missing" if service is None else service.value
        
        result = await test_func()
        assert result == "missing"
    
    @pytest.mark.unit
    async def test_inject_multiple_dependencies(self, container):
        """Test @inject with multiple dependencies."""
        container.register(SimpleService, implementation=SimpleService)
        container.register(DependentService, implementation=DependentService)
        
        @inject
        async def test_func(
            simple: SimpleService,
            dependent: DependentService
        ) -> str:
            return f"{simple.value}, {dependent.value}"
        
        result = await test_func()
        assert result == "simple, dependent"
    
    @pytest.mark.unit
    async def test_inject_preserves_function_metadata(self, container):
        """Test @inject preserves function metadata."""
        @inject
        async def test_func():
            """Test function docstring."""
            pass
        
        assert test_func.__name__ == "test_func"
        assert test_func.__doc__ == "Test function docstring."


class TestFactoryDecorator:
    """Test @factory decorator."""
    
    @pytest.mark.unit
    async def test_factory_registration(self, container):
        """Test @factory registers factory function."""
        @factory(SimpleService)
        def create_simple() -> SimpleService:
            service = SimpleService()
            service.value = "factory-created"
            return service
        
        instance = await container.resolve(SimpleService)
        assert instance.value == "factory-created"
    
    @pytest.mark.unit
    async def test_factory_with_dependencies(self, container):
        """Test @factory with dependencies."""
        container.register(SimpleService, implementation=SimpleService)
        
        @factory(DependentService)
        def create_dependent(simple: SimpleService) -> DependentService:
            return DependentService(simple)
        
        instance = await container.resolve(DependentService)
        assert isinstance(instance, DependentService)
        assert isinstance(instance.simple, SimpleService)
    
    @pytest.mark.unit
    async def test_async_factory(self, container):
        """Test @factory with async function."""
        @factory(SimpleService, scope=ScopeType.SINGLETON)
        async def create_simple() -> SimpleService:
            await asyncio.sleep(0.01)
            service = SimpleService()
            service.value = "async-factory"
            return service
        
        instance = await container.resolve(SimpleService)
        assert instance.value == "async-factory"


class TestHelperDecorators:
    """Test helper decorators like @named and @scoped."""
    
    @pytest.mark.unit
    def test_named_decorator(self):
        """Test @named decorator."""
        @named("primary")
        class TestService:
            pass
        
        assert hasattr(TestService, "__whiskey_name__")
        assert TestService.__whiskey_name__ == "primary"
    
    @pytest.mark.unit
    def test_scoped_decorator(self):
        """Test @scoped decorator."""
        @scoped(ScopeType.REQUEST)
        class TestService:
            pass
        
        assert hasattr(TestService, "__whiskey_scope__")
        assert TestService.__whiskey_scope__ == ScopeType.REQUEST
    
    @pytest.mark.unit
    def test_decorator_composition(self, container):
        """Test combining multiple decorators."""
        @provide
        @singleton
        @named("main")
        class TestService:
            pass
        
        # Check all decorators applied
        assert container.has_service(TestService)
        assert hasattr(TestService, "__whiskey_name__")
        
        descriptor = container.get_descriptor(TestService)
        assert descriptor.scope == ScopeType.SINGLETON


class TestDefaultContainer:
    """Test default container management."""
    
    @pytest.mark.unit
    def test_get_default_container_creates(self):
        """Test get_default_container creates if needed."""
        # Clear any existing
        set_default_container(None)
        
        container = get_default_container()
        assert isinstance(container, Container)
        
        # Same instance returned
        container2 = get_default_container()
        assert container is container2
    
    @pytest.mark.unit
    def test_set_default_container(self):
        """Test setting default container."""
        custom = Container()
        set_default_container(custom)
        
        retrieved = get_default_container()
        assert retrieved is custom
    
    @pytest.mark.unit
    async def test_decorators_use_default_container(self):
        """Test decorators use default container."""
        # Create and set custom container
        custom = Container()
        set_default_container(custom)
        
        # Register with decorator
        @provide
        class TestService:
            pass
        
        # Should be in custom container
        assert custom.has_service(TestService)
        
        # Can resolve from custom container
        instance = await custom.resolve(TestService)
        assert isinstance(instance, TestService)