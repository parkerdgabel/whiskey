"""Tests for simplified scope system."""

import pytest

from whiskey import ContextVarScope, Scope, ScopeType


class TestScope:
    """Test basic Scope functionality."""
    
    @pytest.mark.unit
    def test_scope_creation(self):
        """Test scope creation."""
        scope = Scope("test")
        assert scope.name == "test"
        assert scope._instances == {}
    
    @pytest.mark.unit
    def test_scope_get_set(self):
        """Test getting and setting in scope."""
        scope = Scope("test")
        
        class TestService:
            pass
        
        instance = TestService()
        scope.set(TestService, instance)
        
        retrieved = scope.get(TestService)
        assert retrieved is instance
    
    @pytest.mark.unit
    def test_scope_get_missing(self):
        """Test getting missing service."""
        scope = Scope("test")
        assert scope.get(str) is None
    
    @pytest.mark.unit
    def test_scope_context_manager(self):
        """Test scope as context manager."""
        class TestService:
            def __init__(self):
                self.disposed = False
                
            def dispose(self):
                self.disposed = True
        
        scope = Scope("test")
        instance = TestService()
        scope.set(TestService, instance)
        
        with scope:
            assert not instance.disposed
        
        # Should be disposed after exit
        assert instance.disposed
    
    @pytest.mark.unit
    async def test_scope_async_context_manager(self):
        """Test scope as async context manager."""
        class TestService:
            def __init__(self):
                self.disposed = False
                
            async def dispose(self):
                self.disposed = True
        
        scope = Scope("test")
        instance = TestService()
        scope.set(TestService, instance)
        
        async with scope:
            assert not instance.disposed
        
        # Should be disposed after exit
        assert instance.disposed
    
    @pytest.mark.unit
    def test_scope_clear(self):
        """Test clearing scope."""
        scope = Scope("test")
        
        class TestService:
            pass
        
        scope.set(TestService, TestService())
        assert scope.get(TestService) is not None
        
        scope.clear()
        assert scope.get(TestService) is None


class TestContextVarScope:
    """Test ContextVarScope functionality."""
    
    @pytest.mark.unit
    def test_contextvar_scope_creation(self):
        """Test ContextVarScope creation."""
        scope = ContextVarScope("test")
        assert scope.name == "test"
    
    @pytest.mark.unit
    async def test_contextvar_isolation(self):
        """Test that ContextVarScope provides isolation."""
        import asyncio
        
        scope = ContextVarScope("test")
        
        class TestService:
            def __init__(self, value):
                self.value = value
        
        async def task1():
            instance = TestService("task1")
            scope.set(TestService, instance)
            await asyncio.sleep(0.1)
            retrieved = scope.get(TestService)
            assert retrieved.value == "task1"
        
        async def task2():
            await asyncio.sleep(0.05)  # Start after task1
            instance = TestService("task2")
            scope.set(TestService, instance)
            retrieved = scope.get(TestService)
            assert retrieved.value == "task2"
        
        # Run concurrently
        await asyncio.gather(task1(), task2())
    
    @pytest.mark.unit
    def test_contextvar_clear(self):
        """Test clearing context var scope."""
        scope = ContextVarScope("test")
        
        class TestService:
            pass
        
        scope.set(TestService, TestService())
        assert scope.get(TestService) is not None
        
        scope.clear()
        assert scope.get(TestService) is None


class TestScopeType:
    """Test ScopeType constants."""
    
    @pytest.mark.unit
    def test_scope_types(self):
        """Test built-in scope types."""
        assert ScopeType.SINGLETON == "singleton"
        assert ScopeType.TRANSIENT == "transient"
        assert ScopeType.REQUEST == "request"