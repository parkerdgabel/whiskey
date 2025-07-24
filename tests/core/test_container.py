"""Tests for the Container class."""

import pytest

from whiskey.core.container import Container
from whiskey.core.exceptions import InvalidServiceError, ServiceNotFoundError
from whiskey.core.types import ScopeType
from ..conftest import (
    SimpleService,
    DependentService,
    CircularServiceA,
    CircularServiceB,
    simple_factory,
    async_factory,
    factory_with_deps,
)


class TestContainer:
    """Test Container functionality."""
    
    @pytest.mark.unit
    def test_container_creation(self):
        """Test container can be created."""
        container = Container()
        assert container is not None
        assert container.parent is None
        assert not container._is_disposed
    
    @pytest.mark.unit
    def test_container_with_parent(self):
        """Test container with parent."""
        parent = Container()
        child = Container(parent=parent)
        assert child.parent is parent
    
    @pytest.mark.unit
    def test_register_implementation(self, container):
        """Test registering a service with implementation."""
        container.register(SimpleService, implementation=SimpleService)
        
        # Check service is registered
        assert container.has_service(SimpleService)
        descriptor = container.get_descriptor(SimpleService)
        assert descriptor is not None
        assert descriptor.implementation is SimpleService
        assert descriptor.scope == ScopeType.TRANSIENT
    
    @pytest.mark.unit
    def test_register_factory(self, container):
        """Test registering a service with factory."""
        container.register(SimpleService, factory=simple_factory)
        
        descriptor = container.get_descriptor(SimpleService)
        assert descriptor is not None
        assert descriptor.factory is simple_factory
    
    @pytest.mark.unit
    def test_register_instance(self, container):
        """Test registering a service with instance."""
        instance = SimpleService()
        container.register(SimpleService, instance=instance)
        
        descriptor = container.get_descriptor(SimpleService)
        assert descriptor is not None
        assert descriptor.instance is instance
    
    @pytest.mark.unit
    def test_register_with_scope(self, container):
        """Test registering with different scopes."""
        container.register(
            SimpleService,
            implementation=SimpleService,
            scope=ScopeType.SINGLETON
        )
        
        descriptor = container.get_descriptor(SimpleService)
        assert descriptor.scope == ScopeType.SINGLETON
    
    @pytest.mark.unit
    def test_register_with_name(self, container):
        """Test registering with name."""
        container.register(
            SimpleService,
            implementation=SimpleService,
            name="special"
        )
        
        assert container.has_service(SimpleService, name="special")
    
    @pytest.mark.unit
    def test_register_invalid(self, container):
        """Test invalid registration scenarios."""
        # No implementation, factory, or instance
        with pytest.raises(InvalidServiceError):
            container.register(SimpleService)
        
        # Multiple provided
        with pytest.raises(InvalidServiceError):
            container.register(
                SimpleService,
                implementation=SimpleService,
                factory=simple_factory
            )
    
    @pytest.mark.unit
    def test_register_singleton_shortcut(self, container):
        """Test register_singleton shortcut."""
        container.register_singleton(
            SimpleService,
            implementation=SimpleService
        )
        
        descriptor = container.get_descriptor(SimpleService)
        assert descriptor.scope == ScopeType.SINGLETON
    
    @pytest.mark.unit
    def test_register_transient_shortcut(self, container):
        """Test register_transient shortcut."""
        container.register_transient(
            SimpleService,
            implementation=SimpleService
        )
        
        descriptor = container.get_descriptor(SimpleService)
        assert descriptor.scope == ScopeType.TRANSIENT
    
    @pytest.mark.unit
    def test_register_scoped(self, container):
        """Test register_scoped."""
        container.register_scoped(
            ScopeType.REQUEST,
            SimpleService,
            implementation=SimpleService
        )
        
        descriptor = container.get_descriptor(SimpleService)
        assert descriptor.scope == ScopeType.REQUEST
    
    @pytest.mark.unit
    async def test_resolve_simple(self, container):
        """Test resolving a simple service."""
        container.register(SimpleService, implementation=SimpleService)
        
        service = await container.resolve(SimpleService)
        assert isinstance(service, SimpleService)
        assert service.initialized
    
    @pytest.mark.unit
    async def test_resolve_with_dependencies(self, container):
        """Test resolving service with dependencies."""
        container.register(SimpleService, implementation=SimpleService)
        container.register(DependentService, implementation=DependentService)
        
        service = await container.resolve(DependentService)
        assert isinstance(service, DependentService)
        assert isinstance(service.simple, SimpleService)
    
    @pytest.mark.unit
    async def test_resolve_factory(self, container):
        """Test resolving service from factory."""
        container.register(SimpleService, factory=simple_factory)
        
        service = await container.resolve(SimpleService)
        assert isinstance(service, SimpleService)
    
    @pytest.mark.unit
    async def test_resolve_async_factory(self, container):
        """Test resolving service from async factory."""
        container.register(SimpleService, factory=async_factory)
        
        service = await container.resolve(SimpleService)
        assert isinstance(service, SimpleService)
    
    @pytest.mark.unit
    async def test_resolve_factory_with_deps(self, container):
        """Test resolving factory with dependencies."""
        container.register(SimpleService, implementation=SimpleService)
        container.register(DependentService, factory=factory_with_deps)
        
        service = await container.resolve(DependentService)
        assert isinstance(service, DependentService)
        assert isinstance(service.simple, SimpleService)
    
    @pytest.mark.unit
    async def test_resolve_instance(self, container):
        """Test resolving pre-existing instance."""
        instance = SimpleService()
        instance.value = "custom"
        container.register(SimpleService, instance=instance)
        
        resolved = await container.resolve(SimpleService)
        assert resolved is instance
        assert resolved.value == "custom"
    
    @pytest.mark.unit
    async def test_resolve_singleton(self, container):
        """Test singleton returns same instance."""
        container.register_singleton(
            SimpleService,
            implementation=SimpleService
        )
        
        service1 = await container.resolve(SimpleService)
        service2 = await container.resolve(SimpleService)
        assert service1 is service2
    
    @pytest.mark.unit
    async def test_resolve_transient(self, container):
        """Test transient returns new instances."""
        container.register_transient(
            SimpleService,
            implementation=SimpleService
        )
        
        service1 = await container.resolve(SimpleService)
        service2 = await container.resolve(SimpleService)
        assert service1 is not service2
    
    @pytest.mark.unit
    async def test_resolve_not_found(self, container):
        """Test resolving non-existent service."""
        with pytest.raises(ServiceNotFoundError) as exc_info:
            await container.resolve(SimpleService)
        
        assert "SimpleService" in str(exc_info.value)
    
    @pytest.mark.unit
    async def test_resolve_with_name(self, container):
        """Test resolving named service."""
        container.register(
            SimpleService,
            implementation=SimpleService,
            name="special"
        )
        
        service = await container.resolve(SimpleService, name="special")
        assert isinstance(service, SimpleService)
    
    @pytest.mark.unit
    def test_resolve_sync(self, container):
        """Test synchronous resolution."""
        container.register(SimpleService, implementation=SimpleService)
        
        service = container.resolve_sync(SimpleService)
        assert isinstance(service, SimpleService)
    
    @pytest.mark.unit
    async def test_resolve_all(self, container):
        """Test resolving all services of a type."""
        # Register multiple services
        container.register(SimpleService, implementation=SimpleService)
        container.register(SimpleService, implementation=SimpleService, name="v2")
        
        # Resolve all
        services = await container.resolve_all(SimpleService)
        assert len(services) >= 1
        assert all(isinstance(s, SimpleService) for s in services)
    
    @pytest.mark.unit
    def test_has_service(self, container):
        """Test checking if service exists."""
        assert not container.has_service(SimpleService)
        
        container.register(SimpleService, implementation=SimpleService)
        assert container.has_service(SimpleService)
    
    @pytest.mark.unit
    def test_has_service_with_parent(self):
        """Test has_service checks parent."""
        parent = Container()
        child = Container(parent=parent)
        
        parent.register(SimpleService, implementation=SimpleService)
        assert child.has_service(SimpleService)
    
    @pytest.mark.unit
    def test_get_descriptor(self, container):
        """Test getting service descriptor."""
        container.register(
            SimpleService,
            implementation=SimpleService,
            scope=ScopeType.SINGLETON
        )
        
        descriptor = container.get_descriptor(SimpleService)
        assert descriptor is not None
        assert descriptor.service_type is SimpleService
        assert descriptor.scope == ScopeType.SINGLETON
    
    @pytest.mark.unit
    def test_get_all_services(self, container):
        """Test getting all registered services."""
        container.register(SimpleService, implementation=SimpleService)
        container.register(DependentService, implementation=DependentService)
        
        services = container.get_all_services()
        assert len(services) >= 2
        assert SimpleService in services
        assert DependentService in services
    
    @pytest.mark.unit
    def test_create_child(self, container):
        """Test creating child container."""
        child = container.create_child()
        assert child.parent is container
    
    @pytest.mark.unit
    async def test_dispose(self, container):
        """Test container disposal."""
        container.register(SimpleService, implementation=SimpleService)
        
        assert not container._is_disposed
        await container.dispose()
        assert container._is_disposed
        
        # Should not be able to register after disposal
        with pytest.raises(InvalidServiceError):
            container.register(DependentService, implementation=DependentService)
        
        # Should not be able to resolve after disposal
        with pytest.raises(InvalidServiceError):
            await container.resolve(SimpleService)
    
    @pytest.mark.unit
    def test_string_representation(self, container):
        """Test container string representation."""
        container.register(SimpleService, implementation=SimpleService)
        
        repr_str = repr(container)
        assert "Container" in repr_str
        assert "services=1" in repr_str
    
    @pytest.mark.integration
    async def test_parent_child_resolution(self):
        """Test resolution across parent-child containers."""
        parent = Container()
        child = parent.create_child()
        
        # Register in parent
        parent.register(SimpleService, implementation=SimpleService)
        
        # Register in child
        child.register(DependentService, implementation=DependentService)
        
        # Child can resolve from parent
        service = await child.resolve(DependentService)
        assert isinstance(service, DependentService)
        assert isinstance(service.simple, SimpleService)
    
    @pytest.mark.integration
    async def test_child_overrides_parent(self):
        """Test child container can override parent services."""
        parent = Container()
        child = parent.create_child()
        
        # Register in parent
        instance1 = SimpleService()
        instance1.value = "parent"
        parent.register(SimpleService, instance=instance1)
        
        # Override in child
        instance2 = SimpleService()
        instance2.value = "child"
        child.register(SimpleService, instance=instance2)
        
        # Parent resolves its own
        parent_service = await parent.resolve(SimpleService)
        assert parent_service.value == "parent"
        
        # Child resolves its override
        child_service = await child.resolve(SimpleService)
        assert child_service.value == "child"