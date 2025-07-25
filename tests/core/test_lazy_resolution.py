"""Tests for lazy resolution feature."""

import pytest
from typing import Annotated

from whiskey import Container, provide, singleton
from whiskey.core.decorators import Inject
from whiskey.core.lazy import Lazy, LazyDescriptor, lazy_inject


class ExpensiveService:
    """Service that's expensive to create."""
    instances_created = 0
    
    def __init__(self):
        ExpensiveService.instances_created += 1
        self.id = ExpensiveService.instances_created
        print(f"ExpensiveService #{self.id} created!")
    
    def get_data(self):
        return f"Data from instance #{self.id}"


class Database:
    """Mock database service."""
    def __init__(self):
        self.connected = True
        
    def query(self, sql: str):
        return f"Result of: {sql}"


class Cache:
    """Mock cache service."""
    def __init__(self):
        self.items = {}
        
    def get(self, key: str):
        return self.items.get(key)
        
    def set(self, key: str, value: str):
        self.items[key] = value


class ServiceWithLazyDeps:
    """Service that uses lazy dependencies."""
    def __init__(self, 
                 lazy_expensive: Lazy[ExpensiveService],
                 lazy_db: Annotated[Lazy[Database], Inject()]):
        self.lazy_expensive = lazy_expensive
        self.lazy_db = lazy_db
        print("ServiceWithLazyDeps created")
        
    def use_expensive(self):
        # This triggers lazy resolution
        return self.lazy_expensive.get_data()
        
    def use_database(self):
        # This triggers lazy resolution
        return self.lazy_db.query("SELECT * FROM users")


class ServiceWithDescriptor:
    """Service using LazyDescriptor."""
    database = LazyDescriptor(Database)
    cache = LazyDescriptor(Cache)
    
    def __init__(self):
        print("ServiceWithDescriptor created")
        
    def use_services(self):
        # First access creates Lazy instances
        db_result = self.database.value.query("SELECT 1")
        self.cache.value.set("key", "value")
        return db_result, self.cache.value.get("key")


class ServiceA:
    """Service A that optionally depends on B."""
    def __init__(self, b_lazy: Lazy | None = None):
        self.b_lazy = b_lazy
        self.name = "A"
        
    def get_b_name(self):
        if self.b_lazy:
            return self.b_lazy.value.name
        return "No B"


class ServiceB:
    """Service B that optionally depends on A."""
    def __init__(self, a_lazy: Lazy | None = None):
        self.a_lazy = a_lazy
        self.name = "B"
        
    def get_a_name(self):
        if self.a_lazy:
            return self.a_lazy.value.name
        return "No A"


class TestLazyResolution:
    """Test lazy resolution functionality."""
    
    @pytest.fixture
    def container(self):
        """Create a test container."""
        return Container()
    
    @pytest.fixture(autouse=True)
    def reset_counters(self):
        """Reset instance counters before each test."""
        ExpensiveService.instances_created = 0
        yield
    
    def test_lazy_basic_usage(self, container):
        """Test basic lazy wrapper functionality."""
        container[ExpensiveService] = ExpensiveService
        
        # Create lazy wrapper
        lazy = Lazy(ExpensiveService, container=container)
        
        # Should not be resolved yet
        assert not lazy.is_resolved
        assert ExpensiveService.instances_created == 0
        
        # Access value triggers resolution
        value = lazy.value
        assert lazy.is_resolved
        assert ExpensiveService.instances_created == 1
        assert value.id == 1
        
        # Subsequent access returns same instance
        value2 = lazy.value
        assert value2 is value
        assert ExpensiveService.instances_created == 1
    
    def test_lazy_injection(self, container):
        """Test lazy dependencies are injected correctly."""
        container[ExpensiveService] = ExpensiveService
        container[Database] = Database
        container[ServiceWithLazyDeps] = ServiceWithLazyDeps
        
        # Create service - dependencies should not be resolved yet
        service = container.resolve_sync(ServiceWithLazyDeps)
        assert ExpensiveService.instances_created == 0
        
        # Using expensive service triggers resolution
        result1 = service.use_expensive()
        assert ExpensiveService.instances_created == 1
        assert result1 == "Data from instance #1"
        
        # Using database triggers its resolution
        result2 = service.use_database()
        assert "SELECT * FROM users" in result2
        
        # Both should now be resolved
        assert service.lazy_expensive.is_resolved
        assert service.lazy_db.is_resolved
    
    def test_lazy_with_names(self, container):
        """Test lazy resolution with named dependencies."""
        # Register named services
        container[Database, "primary"] = lambda: Database()
        container[Database, "cache"] = lambda: Database()
        
        # Create lazy wrappers for named services
        lazy_primary = Lazy(Database, name="primary", container=container)
        lazy_cache = Lazy(Database, name="cache", container=container)
        
        # Resolve and verify they're different instances
        primary = lazy_primary.value
        cache = lazy_cache.value
        
        assert primary is not cache
        assert isinstance(primary, Database)
        assert isinstance(cache, Database)
    
    def test_lazy_descriptor(self, container):
        """Test LazyDescriptor functionality."""
        container[Database] = Database
        container[Cache] = Cache
        container[ServiceWithDescriptor] = ServiceWithDescriptor
        
        # Create service within container context
        with container:
            service = container.resolve_sync(ServiceWithDescriptor)
            
            # Descriptors should create Lazy instances on first access
            assert hasattr(service, '_database_lazy') is False
            assert hasattr(service, '_cache_lazy') is False
            
            # Use services
            db_result, cache_result = service.use_services()
            
            # Now lazy instances should exist
            assert hasattr(service, '_database_lazy')
            assert hasattr(service, '_cache_lazy')
            assert service.database.is_resolved
            assert service.cache.is_resolved
            
            # Verify results
            assert "SELECT 1" in db_result
            assert cache_result == "value"
    
    def test_lazy_circular_dependencies(self, container):
        """Test that lazy can help with circular dependencies."""
        # Register services
        container[ServiceA] = ServiceA
        container[ServiceB] = ServiceB
        
        # Manually create circular dependency with lazy
        lazy_b = Lazy(ServiceB, container=container)
        service_a = ServiceA(b_lazy=lazy_b)
        
        lazy_a = Lazy(ServiceA, container=container)
        service_b = ServiceB(a_lazy=lazy_a)
        
        # Register the instances
        container.register_singleton(ServiceA, instance=service_a)
        container.register_singleton(ServiceB, instance=service_b)
        
        # Now they can access each other through lazy
        assert service_a.get_b_name() == "B"
        assert service_b.get_a_name() == "A"
    
    def test_lazy_singleton_behavior(self, container):
        """Test lazy resolution with singleton services."""
        # Register as singleton
        container.register_singleton(ExpensiveService)
        
        # Create multiple lazy wrappers
        lazy1 = Lazy(ExpensiveService, container=container)
        lazy2 = Lazy(ExpensiveService, container=container)
        
        # Resolve from first lazy
        instance1 = lazy1.value
        assert ExpensiveService.instances_created == 1
        
        # Resolve from second lazy should return same instance
        instance2 = lazy2.value
        assert instance1 is instance2
        assert ExpensiveService.instances_created == 1
    
    def test_lazy_proxy_attributes(self, container):
        """Test that lazy wrapper proxies attributes correctly."""
        container[Database] = Database
        
        lazy = Lazy(Database, container=container)
        
        # Access attribute through proxy
        assert lazy.connected is True
        
        # Now it should be resolved
        assert lazy.is_resolved
        
        # Method calls also work
        result = lazy.query("SELECT 1")
        assert "SELECT 1" in result
    
    def test_lazy_repr(self, container):
        """Test string representation of lazy wrapper."""
        container[ExpensiveService] = ExpensiveService
        
        # Unresolved lazy
        lazy = Lazy(ExpensiveService, container=container)
        assert "unresolved" in repr(lazy)
        assert "ExpensiveService" in repr(lazy)
        
        # Resolved lazy
        instance = lazy.value
        assert "resolved" in repr(lazy)
        assert "ExpensiveService" in repr(lazy)
        
        # Named lazy
        lazy_named = Lazy(ExpensiveService, name="special", container=container)
        assert "name='special'" in repr(lazy_named)
    
    def test_lazy_inject_helper(self, container):
        """Test lazy_inject helper function."""
        container[Database] = Database
        
        # Use as default value
        class ServiceWithDefault:
            def __init__(self, db: Database = lazy_inject(Database)):
                self.db = db
        
        # When no container context, it creates a Lazy instance
        service = ServiceWithDefault()
        assert isinstance(service.db, Lazy)
        assert not service.db.is_resolved
    
    def test_lazy_error_handling(self, container):
        """Test error handling in lazy resolution."""
        # Create lazy for abstract/interface type that can't be instantiated
        from abc import ABC, abstractmethod
        
        class AbstractService(ABC):
            @abstractmethod
            def do_something(self):
                pass
        
        lazy = Lazy(AbstractService, container=container)
        
        # Should raise when trying to resolve
        with pytest.raises(KeyError):
            _ = lazy.value
            
        # Test no container available error
        lazy_no_container = Lazy(Database)
        with pytest.raises(RuntimeError, match="No container available"):
            _ = lazy_no_container.value
    
    def test_lazy_in_sync_context(self, container):
        """Test that lazy resolution works in sync context."""
        container[ExpensiveService] = ExpensiveService
        
        # Create service with lazy dependency
        class SyncService:
            def __init__(self, lazy_exp: Lazy[ExpensiveService]):
                self.lazy_exp = lazy_exp
        
        container[SyncService] = SyncService
        
        # Resolve synchronously
        service = container.resolve_sync(SyncService)
        
        # Lazy should work in sync context
        assert not service.lazy_exp.is_resolved
        
        # Access in sync context should work
        result = service.lazy_exp.get_data()
        assert service.lazy_exp.is_resolved
        assert "Data from instance #1" in result