"""Tests for the simplified Container class."""

import pytest

from whiskey import Container


class SimpleService:
    """Simple test service."""
    def __init__(self):
        self.value = "simple"


class DependentService:
    """Service with dependencies."""
    def __init__(self, simple: SimpleService):
        self.simple = simple


class CircularServiceA:
    """First service in circular dependency."""
    def __init__(self, b: 'CircularServiceB'):
        self.b = b


class CircularServiceB:
    """Second service in circular dependency."""
    def __init__(self, a: CircularServiceA):
        self.a = a


def simple_factory() -> SimpleService:
    """Factory that creates SimpleService."""
    return SimpleService()


async def async_factory() -> SimpleService:
    """Async factory."""
    return SimpleService()


def factory_with_deps(simple: SimpleService) -> DependentService:
    """Factory with dependencies."""
    return DependentService(simple)


class TestContainer:
    """Test Container functionality."""
    
    @pytest.fixture
    def container(self):
        """Create a test container."""
        return Container()
    
    @pytest.mark.unit
    def test_container_creation(self):
        """Test container can be created."""
        container = Container()
        assert container is not None
    
    @pytest.mark.unit
    def test_dict_like_interface(self, container):
        """Test dict-like interface."""
        # Set item
        container[SimpleService] = SimpleService()
        
        # Check contains
        assert SimpleService in container
        assert DependentService not in container
        
        # Delete item
        del container[SimpleService]
        assert SimpleService not in container
    
    @pytest.mark.unit
    async def test_register_instance(self, container):
        """Test registering an instance."""
        instance = SimpleService()
        container[SimpleService] = instance
        
        resolved = await container.resolve(SimpleService)
        assert resolved is instance
    
    @pytest.mark.unit
    async def test_register_class(self, container):
        """Test registering a class."""
        container[SimpleService] = SimpleService
        
        resolved1 = await container.resolve(SimpleService)
        resolved2 = await container.resolve(SimpleService)
        
        # Should create new instances
        assert isinstance(resolved1, SimpleService)
        assert isinstance(resolved2, SimpleService)
        assert resolved1 is not resolved2
    
    @pytest.mark.unit
    async def test_register_factory(self, container):
        """Test registering a factory."""
        container[SimpleService] = simple_factory
        
        resolved = await container.resolve(SimpleService)
        assert isinstance(resolved, SimpleService)
    
    @pytest.mark.unit
    async def test_async_factory(self, container):
        """Test async factory."""
        container[SimpleService] = async_factory
        
        resolved = await container.resolve(SimpleService)
        assert isinstance(resolved, SimpleService)
    
    @pytest.mark.unit
    async def test_singleton(self, container):
        """Test singleton registration."""
        container.register_singleton(SimpleService)
        
        resolved1 = await container.resolve(SimpleService)
        resolved2 = await container.resolve(SimpleService)
        
        assert resolved1 is resolved2
    
    @pytest.mark.unit
    async def test_singleton_instance(self, container):
        """Test singleton with instance."""
        instance = SimpleService()
        container.register_singleton(SimpleService, instance=instance)
        
        resolved = await container.resolve(SimpleService)
        assert resolved is instance
    
    @pytest.mark.unit
    async def test_dependency_injection(self, container):
        """Test automatic dependency injection."""
        container[SimpleService] = SimpleService
        container[DependentService] = DependentService
        
        resolved = await container.resolve(DependentService)
        assert isinstance(resolved, DependentService)
        assert isinstance(resolved.simple, SimpleService)
    
    @pytest.mark.unit
    async def test_factory_with_dependencies(self, container):
        """Test factory with dependencies."""
        container[SimpleService] = SimpleService
        container.register_factory(DependentService, factory_with_deps)
        
        resolved = await container.resolve(DependentService)
        assert isinstance(resolved, DependentService)
        assert isinstance(resolved.simple, SimpleService)
    
    @pytest.mark.unit
    async def test_unregistered_concrete_class(self, container):
        """Test resolving unregistered concrete class."""
        # Should be able to create simple classes without registration
        resolved = await container.resolve(SimpleService)
        assert isinstance(resolved, SimpleService)
    
    @pytest.mark.unit
    async def test_missing_service(self, container):
        """Test resolving missing abstract service."""
        from abc import ABC, abstractmethod
        
        class AbstractService(ABC):
            @abstractmethod
            def do_something(self): pass
        
        with pytest.raises(KeyError, match="AbstractService not registered"):
            await container.resolve(AbstractService)
    
    @pytest.mark.unit
    async def test_circular_dependency(self, container):
        """Test circular dependency detection."""
        container[CircularServiceA] = CircularServiceA
        container[CircularServiceB] = CircularServiceB
        
        # Should raise TypeError for forward reference
        with pytest.raises(TypeError, match="Cannot resolve forward reference"):
            await container.resolve(CircularServiceA)
    
    @pytest.mark.unit
    def test_resolve_sync(self, container):
        """Test synchronous resolution."""
        container[SimpleService] = SimpleService()
        
        # Should work outside async context
        resolved = container.resolve_sync(SimpleService)
        assert isinstance(resolved, SimpleService)
    
    @pytest.mark.unit
    async def test_context_manager(self):
        """Test container as context manager."""
        with Container() as container:
            container[SimpleService] = SimpleService
            resolved = await container.resolve(SimpleService)
            assert isinstance(resolved, SimpleService)
    
    @pytest.mark.unit
    async def test_async_context_manager(self):
        """Test container as async context manager."""
        async with Container() as container:
            container[SimpleService] = SimpleService
            resolved = await container.resolve(SimpleService)
            assert isinstance(resolved, SimpleService)
    
    @pytest.mark.unit
    def test_dict_methods(self, container):
        """Test dict-like methods."""
        container[SimpleService] = SimpleService
        container[DependentService] = DependentService
        
        # keys()
        keys = container.keys()
        assert SimpleService in keys
        assert DependentService in keys
        
        # items()
        items = list(container.items())
        assert len(items) == 2
        
        # clear()
        container.clear()
        assert len(list(container.keys())) == 0