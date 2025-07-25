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