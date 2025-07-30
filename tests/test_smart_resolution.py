"""Test the new smart resolution system for Phase 2.1."""

import asyncio
import pytest
from whiskey.core import Container
from whiskey.core.errors import ResolutionError


class Database:
    def __init__(self):
        self.connection = "postgresql://localhost/test"


class UserService:
    def __init__(self, db: Database):
        self.db = db


async def async_database_factory():
    """Async factory for testing."""
    await asyncio.sleep(0.001)  # Simulate async work
    return Database()


@pytest.mark.unit
class TestSmartResolution:
    """Test the new smart resolve() method."""
    
    def test_sync_context_resolve(self):
        """resolve() should work directly in sync context."""
        container = Container()
        container[Database] = Database
        
        # In sync context - should work without asyncio.run
        try:
            asyncio.get_running_loop()
            pytest.skip("Already in event loop")
        except RuntimeError:
            # No event loop - this should work directly
            db = container.resolve(Database)
            assert isinstance(db, Database)
    
    async def test_async_context_resolve(self):
        """resolve() should work with await in async context."""
        container = Container()
        container[Database] = Database
        
        # In async context - should work with await
        db = await container.resolve(Database)
        assert isinstance(db, Database)
    
    async def test_async_factory_resolution(self):
        """resolve() should handle async factories in async context."""
        container = Container()
        container["async_db"] = async_database_factory
        
        # Should work with async factories in async context
        db = await container.resolve("async_db")
        assert isinstance(db, Database)
        
    def test_explicit_sync_resolution(self):
        """resolve_sync() should guarantee synchronous behavior."""
        container = Container()
        container[Database] = Database
        
        # Should work in any context
        db = container.resolve_sync(Database)
        assert isinstance(db, Database)
        
    def test_explicit_sync_with_async_factory_fails(self):
        """resolve_sync() should fail on async factories with clear error."""
        container = Container()
        container["async_db"] = async_database_factory
        
        # Should fail with clear error
        with pytest.raises(RuntimeError, match="async factory"):
            container.resolve_sync("async_db")
            
    async def test_explicit_async_resolution(self):
        """resolve_async() should guarantee asynchronous behavior."""
        container = Container()
        container[Database] = Database
        container["async_db"] = async_database_factory
        
        # Should work with both sync and async providers
        db1 = await container.resolve_async(Database)
        db2 = await container.resolve_async("async_db")
        
        assert isinstance(db1, Database)
        assert isinstance(db2, Database)


@pytest.mark.unit
class TestSmartDictAccess:
    """Test the improved dict-like access."""
    
    def test_dict_access_sync_components(self):
        """Dict access should work with sync components."""
        container = Container()
        container[Database] = Database
        
        db = container[Database]
        assert isinstance(db, Database)
        
    def test_dict_access_async_factory_error(self):
        """Dict access should give clear error for async factories."""
        container = Container()
        container["async_db"] = async_database_factory
        
        with pytest.raises(RuntimeError) as exc_info:
            _ = container["async_db"]
            
        error_msg = str(exc_info.value)
        assert "async factory" in error_msg.lower()
        assert "await container.resolve" in error_msg
        
    def test_dict_access_unregistered_component(self):
        """Dict access should give clear error for unregistered components."""
        container = Container()
        
        with pytest.raises(KeyError, match="not found"):
            _ = container[Database]


@pytest.mark.unit  
class TestSmartCalling:
    """Test the smart function calling system."""
    
    def test_sync_function_sync_context(self):
        """call() should work with sync functions in sync context."""
        container = Container()
        container[Database] = Database
        
        def test_func(db: Database) -> str:
            return f"Connected to {db.connection}"
        
        try:
            asyncio.get_running_loop()
            pytest.skip("Already in event loop")
        except RuntimeError:
            # No event loop - should work directly
            result = container.call(test_func)
            assert "Connected to postgresql" in result
            
    async def test_sync_function_async_context(self):
        """call() should work with sync functions in async context."""
        container = Container()
        container[Database] = Database
        
        def test_func(db: Database) -> str:
            return f"Connected to {db.connection}"
        
        # Should work in async context (no await needed for sync function)
        result = await container.call(test_func)
        assert "Connected to postgresql" in result
        
    async def test_async_function_async_context(self):
        """call() should work with async functions in async context."""
        container = Container()
        container[Database] = Database
        
        async def test_func(db: Database) -> str:
            await asyncio.sleep(0.001)
            return f"Connected to {db.connection}"
        
        # Should work with async functions
        result = await container.call(test_func)
        assert "Connected to postgresql" in result
        
    def test_explicit_sync_calling(self):
        """call_sync() should guarantee synchronous calling."""
        container = Container()
        container[Database] = Database
        
        def test_func(db: Database) -> str:
            return f"Connected to {db.connection}"
        
        result = container.call_sync(test_func)
        assert "Connected to postgresql" in result
        
    def test_sync_calling_async_function_fails(self):
        """call_sync() should fail on async functions with clear error."""
        container = Container()
        container[Database] = Database
        
        async def test_func(db: Database) -> str:
            await asyncio.sleep(0.001)
            return f"Connected to {db.connection}"
        
        with pytest.raises(RuntimeError, match="Cannot call async function"):
            container.call_sync(test_func)
            
    async def test_explicit_async_calling(self):
        """call_async() should guarantee asynchronous calling."""
        container = Container()
        container[Database] = Database
        
        def sync_func(db: Database) -> str:
            return f"Connected to {db.connection}"
            
        async def async_func(db: Database) -> str:
            await asyncio.sleep(0.001)
            return f"Async connected to {db.connection}"
        
        # Should work with both sync and async functions
        result1 = await container.call_async(sync_func)
        result2 = await container.call_async(async_func)
        
        assert "Connected to postgresql" in result1
        assert "Async connected to postgresql" in result2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])