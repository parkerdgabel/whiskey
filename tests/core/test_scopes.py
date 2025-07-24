"""Tests for scope management."""

import asyncio
import contextvars

import pytest

from whiskey.core.exceptions import ScopeError
from whiskey.core.scopes import (
    AIContextScope,
    BatchScope,
    ContextVarScope,
    ConversationScope,
    RequestScope,
    ScopeManager,
    ScopeType,
    SessionScope,
    SingletonScope,
    StreamScope,
    TransientScope,
)
from whiskey.core.types import Disposable


class DisposableTestService(Disposable):
    """Test service that tracks disposal."""
    
    def __init__(self):
        self.disposed = False
    
    async def dispose(self):
        self.disposed = True


class TestSingletonScope:
    """Test SingletonScope functionality."""
    
    @pytest.mark.unit
    async def test_singleton_stores_instance(self):
        """Test singleton scope stores instances."""
        scope = SingletonScope()
        service = DisposableTestService()
        
        await scope.set("test", service)
        retrieved = await scope.get("test")
        
        assert retrieved is service
    
    @pytest.mark.unit
    async def test_singleton_returns_same_instance(self):
        """Test singleton returns same instance."""
        scope = SingletonScope()
        service = DisposableTestService()
        
        await scope.set("test", service)
        
        # Multiple retrievals return same instance
        instance1 = await scope.get("test")
        instance2 = await scope.get("test")
        
        assert instance1 is instance2 is service
    
    @pytest.mark.unit
    async def test_singleton_remove(self):
        """Test removing from singleton scope."""
        scope = SingletonScope()
        service = DisposableTestService()
        
        await scope.set("test", service)
        await scope.remove("test")
        
        assert await scope.get("test") is None
    
    @pytest.mark.unit
    async def test_singleton_clear(self):
        """Test clearing singleton scope."""
        scope = SingletonScope()
        
        await scope.set("test1", DisposableTestService())
        await scope.set("test2", DisposableTestService())
        
        await scope.clear()
        
        assert await scope.get("test1") is None
        assert await scope.get("test2") is None
    
    @pytest.mark.unit
    async def test_singleton_dispose(self):
        """Test singleton disposes instances."""
        scope = SingletonScope()
        service = DisposableTestService()
        
        await scope.set("test", service)
        await scope.dispose()
        
        assert service.disposed
        assert await scope.get("test") is None


class TestTransientScope:
    """Test TransientScope functionality."""
    
    @pytest.mark.unit
    async def test_transient_always_returns_none(self):
        """Test transient scope doesn't store instances."""
        scope = TransientScope()
        service = DisposableTestService()
        
        await scope.set("test", service)
        retrieved = await scope.get("test")
        
        assert retrieved is None
    
    @pytest.mark.unit
    async def test_transient_operations_noop(self):
        """Test transient scope operations are no-ops."""
        scope = TransientScope()
        
        # These should not raise errors
        await scope.set("test", DisposableTestService())
        await scope.remove("test")
        await scope.clear()
        await scope.dispose()


class TestContextVarScope:
    """Test ContextVarScope functionality."""
    
    @pytest.mark.unit
    async def test_context_var_isolation(self):
        """Test context var scopes are isolated."""
        scope = RequestScope()
        
        async def task1():
            service1 = DisposableTestService()
            await scope.set("test", service1)
            await asyncio.sleep(0.01)
            retrieved = await scope.get("test")
            return retrieved is service1
        
        async def task2():
            await asyncio.sleep(0.005)  # Start after task1
            service2 = DisposableTestService()
            await scope.set("test", service2)
            retrieved = await scope.get("test")
            return retrieved is service2
        
        # Run tasks concurrently
        results = await asyncio.gather(task1(), task2())
        
        # Each task should see its own instance
        assert all(results)
    
    @pytest.mark.unit
    async def test_context_var_inheritance(self):
        """Test context variables are inherited in child tasks."""
        scope = SessionScope()
        service = DisposableTestService()
        
        await scope.set("test", service)
        
        async def child_task():
            # Should inherit parent's context
            retrieved = await scope.get("test")
            return retrieved is service
        
        result = await child_task()
        assert result
    
    @pytest.mark.unit
    async def test_context_var_clear(self):
        """Test clearing context var scope."""
        scope = ConversationScope()
        service = DisposableTestService()
        
        await scope.set("test", service)
        await scope.clear()
        
        assert await scope.get("test") is None
        assert service.disposed
    
    @pytest.mark.unit
    async def test_all_context_var_scopes(self):
        """Test all context var scope types work."""
        scopes = [
            RequestScope(),
            SessionScope(),
            ConversationScope(),
            AIContextScope(),
            BatchScope(),
            StreamScope(),
        ]
        
        for scope in scopes:
            service = DisposableTestService()
            await scope.set("test", service)
            retrieved = await scope.get("test")
            assert retrieved is service


class TestScopeManager:
    """Test ScopeManager functionality."""
    
    @pytest.mark.unit
    def test_scope_manager_creation(self):
        """Test scope manager initializes with default scopes."""
        manager = ScopeManager()
        
        # Check all default scopes exist
        for scope_type in ScopeType:
            scope = manager.get_scope(scope_type)
            assert scope is not None
    
    @pytest.mark.unit
    def test_get_scope_by_enum(self):
        """Test getting scope by enum."""
        manager = ScopeManager()
        
        scope = manager.get_scope(ScopeType.SINGLETON)
        assert isinstance(scope, SingletonScope)
        
        scope = manager.get_scope(ScopeType.TRANSIENT)
        assert isinstance(scope, TransientScope)
    
    @pytest.mark.unit
    def test_get_scope_by_string(self):
        """Test getting scope by string name."""
        manager = ScopeManager()
        
        # Register custom scope
        custom_scope = SingletonScope()
        custom_scope.name = "custom"
        manager.register_scope("custom", custom_scope)
        
        retrieved = manager.get_scope("custom")
        assert retrieved is custom_scope
    
    @pytest.mark.unit
    def test_register_custom_scope(self):
        """Test registering custom scope."""
        manager = ScopeManager()
        
        class CustomScope(SingletonScope):
            pass
        
        custom = CustomScope()
        custom.name = "my_custom"
        manager.register_scope("my_custom", custom)
        
        retrieved = manager.get_scope("my_custom")
        assert retrieved is custom
    
    @pytest.mark.unit
    def test_register_duplicate_scope_error(self):
        """Test registering duplicate scope raises error."""
        manager = ScopeManager()
        
        scope1 = SingletonScope()
        scope1.name = "custom"
        manager.register_scope("custom", scope1)
        
        scope2 = SingletonScope()
        scope2.name = "custom"
        
        with pytest.raises(ScopeError) as exc_info:
            manager.register_scope("custom", scope2)
        
        assert "already registered" in str(exc_info.value)
    
    @pytest.mark.unit
    def test_get_unknown_scope_error(self):
        """Test getting unknown scope raises error."""
        manager = ScopeManager()
        
        with pytest.raises(ScopeError) as exc_info:
            manager.get_scope("nonexistent")
        
        assert "Unknown scope" in str(exc_info.value)
    
    @pytest.mark.unit
    async def test_dispose_all_scopes(self):
        """Test disposing all scopes."""
        manager = ScopeManager()
        
        # Add services to various scopes
        singleton_scope = manager.get_scope(ScopeType.SINGLETON)
        service1 = DisposableTestService()
        await singleton_scope.set("test", service1)
        
        request_scope = manager.get_scope(ScopeType.REQUEST)
        service2 = DisposableTestService()
        await request_scope.set("test", service2)
        
        # Dispose all
        await manager.dispose_all()
        
        # Check services were disposed
        assert service1.disposed
        assert service2.disposed
    
    @pytest.mark.integration
    async def test_scope_isolation_across_types(self):
        """Test different scope types are isolated."""
        manager = ScopeManager()
        
        singleton = manager.get_scope(ScopeType.SINGLETON)
        request = manager.get_scope(ScopeType.REQUEST)
        
        # Set same key in different scopes
        service1 = DisposableTestService()
        service2 = DisposableTestService()
        
        await singleton.set("test", service1)
        await request.set("test", service2)
        
        # Each scope maintains its own instance
        assert await singleton.get("test") is service1
        assert await request.get("test") is service2
    
    @pytest.mark.integration
    async def test_concurrent_scope_access(self):
        """Test concurrent access to scopes."""
        manager = ScopeManager()
        scope = manager.get_scope(ScopeType.SINGLETON)
        
        async def add_service(key: str):
            service = DisposableTestService()
            await scope.set(key, service)
            return service
        
        # Add multiple services concurrently
        tasks = [add_service(f"test{i}") for i in range(10)]
        services = await asyncio.gather(*tasks)
        
        # Verify all services are stored
        for i, service in enumerate(services):
            retrieved = await scope.get(f"test{i}")
            assert retrieved is service