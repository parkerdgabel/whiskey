"""Tests for the DependencyResolver class."""

import asyncio

import pytest

from whiskey.core.container import Container
from whiskey.core.exceptions import CircularDependencyError, InjectionError
from whiskey.core.resolver import DependencyResolver
from whiskey.core.types import InjectionPoint, ResolverContext
from ..conftest import (
    SimpleService,
    DependentService,
    CircularServiceA,
    CircularServiceB,
    OptionalDependencyService,
    AsyncInitService,
    DisposableService,
    ComplexService,
)


class TestDependencyResolver:
    """Test DependencyResolver functionality."""
    
    @pytest.mark.unit
    def test_resolver_creation(self, container):
        """Test resolver can be created."""
        resolver = DependencyResolver(container)
        assert resolver is not None
        assert resolver._container is container
    
    @pytest.mark.unit
    async def test_resolve_simple(self, container):
        """Test resolving simple service."""
        container.register(SimpleService, implementation=SimpleService)
        resolver = DependencyResolver(container)
        
        service = await resolver.resolve(SimpleService)
        assert isinstance(service, SimpleService)
    
    @pytest.mark.unit
    async def test_circular_dependency_detection(self, container):
        """Test circular dependency detection."""
        container.register(CircularServiceA, implementation=CircularServiceA)
        container.register(CircularServiceB, implementation=CircularServiceB)
        resolver = DependencyResolver(container)
        
        with pytest.raises(CircularDependencyError) as exc_info:
            await resolver.resolve(CircularServiceA)
        
        # Check error contains the circular path
        error = exc_info.value
        assert CircularServiceA in error.dependency_chain
        assert CircularServiceB in error.dependency_chain
    
    @pytest.mark.unit
    async def test_optional_dependency_present(self, container):
        """Test optional dependency when present."""
        container.register(SimpleService, implementation=SimpleService)
        container.register(
            OptionalDependencyService,
            implementation=OptionalDependencyService
        )
        resolver = DependencyResolver(container)
        
        service = await resolver.resolve(OptionalDependencyService)
        assert service.has_dependency
        assert isinstance(service.simple, SimpleService)
    
    @pytest.mark.unit
    async def test_optional_dependency_missing(self, container):
        """Test optional dependency when missing."""
        container.register(
            OptionalDependencyService,
            implementation=OptionalDependencyService
        )
        resolver = DependencyResolver(container)
        
        service = await resolver.resolve(OptionalDependencyService)
        assert not service.has_dependency
        assert service.simple is None
    
    @pytest.mark.unit
    async def test_initialization_called(self, container):
        """Test Initializable services are initialized."""
        container.register(AsyncInitService, implementation=AsyncInitService)
        resolver = DependencyResolver(container)
        
        service = await resolver.resolve(AsyncInitService)
        assert service.initialized
        assert service.init_count == 1
    
    @pytest.mark.unit
    async def test_complex_dependency_graph(self, container):
        """Test resolving complex dependency graph."""
        container.register(SimpleService, implementation=SimpleService)
        container.register(DependentService, implementation=DependentService)
        container.register(ComplexService, implementation=ComplexService)
        resolver = DependencyResolver(container)
        
        # Resolve top-level service
        service = await resolver.resolve(ComplexService)
        assert isinstance(service, ComplexService)
        assert isinstance(service.simple, SimpleService)
        assert service.initialized
    
    @pytest.mark.unit
    def test_get_injection_points(self, container):
        """Test extracting injection points from a class."""
        resolver = DependencyResolver(container)
        
        # Test simple class
        points = resolver._get_injection_points(SimpleService.__init__)
        assert len(points) == 0  # No dependencies
        
        # Test class with dependencies
        points = resolver._get_injection_points(DependentService.__init__)
        assert len(points) == 1
        assert points[0].parameter_name == "simple"
        assert points[0].service_key == SimpleService
        assert not points[0].is_optional
    
    @pytest.mark.unit
    def test_get_injection_points_optional(self, container):
        """Test extracting optional injection points."""
        resolver = DependencyResolver(container)
        
        points = resolver._get_injection_points(OptionalDependencyService.__init__)
        assert len(points) == 1
        assert points[0].parameter_name == "simple"
        assert points[0].service_key == SimpleService
        assert points[0].is_optional
    
    @pytest.mark.unit
    async def test_injection_error_handling(self, container):
        """Test injection error provides context."""
        # Register dependent but not dependency
        container.register(DependentService, implementation=DependentService)
        resolver = DependencyResolver(container)
        
        with pytest.raises(InjectionError) as exc_info:
            await resolver.resolve(DependentService)
        
        error = exc_info.value
        assert error.parameter == "simple"
        assert "DependentService" in str(error.target)
    
    @pytest.mark.unit
    def test_resolver_context_creation(self, container):
        """Test ResolverContext functionality."""
        scope = container.scope_manager.get_scope("singleton")
        context = ResolverContext(
            container=container,
            scope=scope
        )
        
        assert context.container is container
        assert context.scope is scope
        assert len(context.stack) == 0
        assert len(context.resolved) == 0
    
    @pytest.mark.unit
    def test_resolver_context_child(self, container):
        """Test creating child context."""
        scope = container.scope_manager.get_scope("singleton")
        parent_context = ResolverContext(
            container=container,
            scope=scope
        )
        
        # Add some state
        parent_context.stack.append(SimpleService)
        parent_context.resolved.add(SimpleService)
        
        # Create child
        child_context = parent_context.create_child()
        
        # Child has copy of state
        assert SimpleService in child_context.stack
        assert SimpleService in child_context.resolved
        assert child_context.parent is parent_context
        
        # Modifying child doesn't affect parent
        child_context.stack.append(DependentService)
        assert DependentService not in parent_context.stack
    
    @pytest.mark.unit
    async def test_nested_resolution(self, container):
        """Test nested dependency resolution."""
        # Create a chain: A -> B -> C
        class ServiceA:
            def __init__(self, b: "ServiceB"):
                self.b = b
        
        class ServiceB:
            def __init__(self, c: "ServiceC"):
                self.c = c
        
        class ServiceC:
            def __init__(self):
                self.value = "C"
        
        container.register(ServiceA, implementation=ServiceA)
        container.register(ServiceB, implementation=ServiceB)
        container.register(ServiceC, implementation=ServiceC)
        
        resolver = DependencyResolver(container)
        service_a = await resolver.resolve(ServiceA)
        
        assert isinstance(service_a, ServiceA)
        assert isinstance(service_a.b, ServiceB)
        assert isinstance(service_a.b.c, ServiceC)
        assert service_a.b.c.value == "C"
    
    @pytest.mark.unit
    async def test_factory_resolution(self, container):
        """Test resolver handles factories correctly."""
        def factory(simple: SimpleService) -> DependentService:
            return DependentService(simple)
        
        container.register(SimpleService, implementation=SimpleService)
        container.register(DependentService, factory=factory)
        
        resolver = DependencyResolver(container)
        service = await resolver.resolve(DependentService)
        
        assert isinstance(service, DependentService)
        assert isinstance(service.simple, SimpleService)
    
    @pytest.mark.unit
    async def test_async_factory_resolution(self, container):
        """Test resolver handles async factories."""
        async def async_factory(simple: SimpleService) -> DependentService:
            await asyncio.sleep(0.01)
            return DependentService(simple)
        
        container.register(SimpleService, implementation=SimpleService)
        container.register(DependentService, factory=async_factory)
        
        resolver = DependencyResolver(container)
        service = await resolver.resolve(DependentService)
        
        assert isinstance(service, DependentService)
    
    @pytest.mark.integration
    async def test_resolve_from_parent_container(self):
        """Test resolver can resolve from parent containers."""
        parent = Container()
        child = parent.create_child()
        
        # Register in parent only
        parent.register(SimpleService, implementation=SimpleService)
        
        # Resolve from child's resolver
        resolver = DependencyResolver(child)
        service = await resolver.resolve(SimpleService)
        
        assert isinstance(service, SimpleService)
    
    @pytest.mark.integration
    async def test_singleton_initialization_once(self, container):
        """Test singleton services are initialized only once."""
        container.register_singleton(
            AsyncInitService,
            implementation=AsyncInitService
        )
        
        resolver = DependencyResolver(container)
        
        # Resolve multiple times
        service1 = await resolver.resolve(AsyncInitService)
        service2 = await resolver.resolve(AsyncInitService)
        service3 = await resolver.resolve(AsyncInitService)
        
        # Same instance
        assert service1 is service2 is service3
        
        # Initialized only once
        assert service1.init_count == 1