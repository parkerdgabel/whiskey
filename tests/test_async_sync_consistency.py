"""Test async/sync API consistency issues in Whiskey DI framework.

This test suite identifies and validates fixes for Phase 2.1: Clarify async/sync API consistency.
The main issues are:
1. Confusing mix of resolve() vs resolve_sync() vs resolve_async()
2. Dict-like access always uses sync resolution
3. Complex thread-based workarounds in call_sync() when in async context
4. Inconsistent method names across Container and Application
5. Error-prone nested asyncio.run() calls

The goal is to create a clear, consistent API where:
- resolve() works in both sync and async contexts (smart resolution)
- Explicit async/sync methods when needed
- No confusing thread-based workarounds
- Clear documentation of which methods to use when
"""

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


class AsyncFactory:
    """Test async factory functions."""
    
    async def create_service(self) -> UserService:
        await asyncio.sleep(0.001)  # Simulate async work
        return UserService(Database())


@pytest.mark.unit
class TestCurrentAsyncSyncIssues:
    """Test current issues with async/sync API consistency."""
    
    def test_dict_access_forces_sync_resolution(self):
        """Dict access like container[Service] always uses sync resolution."""
        container = Container()
        container[Database] = Database
        
        # This works - sync resolution
        db = container[Database]
        assert isinstance(db, Database)
        
        # But if we register an async factory, dict access will fail
        async def async_db_factory():
            await asyncio.sleep(0.001)
            return Database()
        
        container["async_db"] = async_db_factory
        
        # This should fail because dict access can't handle async factories
        with pytest.raises(RuntimeError, match="async factory"):
            _ = container["async_db"]
    
    def test_confusing_method_names(self):
        """Multiple resolve methods are confusing."""
        container = Container()
        container[Database] = Database
        
        # We have multiple ways to resolve:
        # 1. resolve() - smart (works in both contexts)
        # 2. resolve_sync() - explicit sync
        # 3. resolve_async() - explicit async  
        # 4. dict access - sync with smart error handling
        
        # The NEW smart system handles this better
        try:
            asyncio.get_running_loop()
            pytest.skip("Already in event loop")
        except RuntimeError:
            # In sync context, resolve() should work directly
            db1 = container.resolve(Database)  # Smart resolution!
            db2 = container.resolve_sync(Database)  
            db3 = container[Database]
            
            assert all(isinstance(db, Database) for db in [db1, db2, db3])
    
    def test_call_sync_complex_workaround(self):
        """call_sync() has complex thread-based workarounds."""
        container = Container()
        container[Database] = Database
        
        def test_func(db: Database) -> str:
            return "worked"
        
        # In sync context - works fine
        result = container.call_sync(test_func)
        assert result == "worked"
        
        # In async context - uses complex thread workaround
        async def async_test():
            # This triggers the complex ThreadPoolExecutor workaround
            return container.call_sync(test_func)
        
        result = asyncio.run(async_test())
        assert result == "worked"
    
    def test_inconsistent_application_methods(self):
        """Application class has inconsistent method names."""
        from whiskey.core.application import Whiskey
        
        app = Whiskey()
        app.container[Database] = Database
        
        # Application has:
        # - resolve() - sync (confusing!)
        # - resolve_async() - async
        # - call_sync() - sync
        # - No async call method
        
        db1 = app.resolve(Database)  # Actually sync!
        db2 = asyncio.run(app.resolve_async(Database))  # Async
        
        assert isinstance(db1, Database)
        assert isinstance(db2, Database)


@pytest.mark.unit  
class TestDesiredAsyncSyncAPI:
    """Test the desired consistent async/sync API."""
    
    def test_smart_resolve_method(self):
        """resolve() should work in both sync and async contexts."""
        container = Container()
        container[Database] = Database
        
        # In sync context - should work without asyncio.run
        try:
            asyncio.get_running_loop()
            pytest.skip("Already in event loop")
        except RuntimeError:
            # No event loop - this should work
            db = container.resolve(Database)
            assert isinstance(db, Database)
        
        # In async context - should work with await
        async def async_test():
            db = await container.resolve(Database)
            assert isinstance(db, Database)
            return db
        
        db = asyncio.run(async_test())
        assert isinstance(db, Database)
    
    def test_explicit_sync_async_when_needed(self):
        """Explicit sync/async methods for when behavior must be guaranteed."""
        container = Container()
        container[Database] = Database
        
        # resolve_sync() - guaranteed synchronous
        db1 = container.resolve_sync(Database)
        assert isinstance(db1, Database)
        
        # resolve_async() - guaranteed asynchronous  
        db2 = asyncio.run(container.resolve_async(Database))
        assert isinstance(db2, Database)
    
    def test_dict_access_smart_resolution(self):
        """Dict access should handle both sync and async factories intelligently."""
        container = Container()
        container[Database] = Database
        
        # Sync factory - should work
        db1 = container[Database]
        assert isinstance(db1, Database)
        
        # For async factories, dict access should either:
        # 1. Raise a clear error with guidance, or
        # 2. Use smart resolution to handle it properly
        
        async def async_factory():
            await asyncio.sleep(0.001)
            return Database()
        
        container["async_db"] = async_factory
        
        # Should either work or give clear error message
        try:
            db2 = container["async_db"]
            assert isinstance(db2, Database)
        except RuntimeError as e:
            assert "async factory" in str(e).lower()
            assert "resolve" in str(e) or "await" in str(e)
    
    def test_consistent_application_api(self):
        """Application should have consistent method names."""
        from whiskey.core.application import Whiskey
        
        app = Whiskey()
        app.container[Database] = Database
        
        # Should have:
        # - resolve() - smart resolution
        # - resolve_sync() - guaranteed sync  
        # - resolve_async() - guaranteed async
        # - call() - smart calling
        # - call_sync() - guaranteed sync calling
        # - call_async() - guaranteed async calling
        
        # This will need implementation
        pass


@pytest.mark.unit
class TestAsyncSyncBestPractices:
    """Test clear best practices for async/sync usage."""
    
    def test_when_to_use_which_method(self):
        """Clear guidance on when to use which resolution method."""
        container = Container()
        container[Database] = Database
        
        # Use resolve() for most cases - it's smart
        # - In sync context: works without asyncio
        # - In async context: works with await
        
        # Use resolve_sync() when you need guaranteed sync behavior
        # - In mixed async/sync code where you must avoid await
        # - In sync-only contexts where async would be wrong
        
        # Use resolve_async() when you need guaranteed async behavior  
        # - In async contexts where you want async factories to work
        # - When building async-first applications
        
        pass
    
    def test_migration_path(self):
        """Test migration path from current API to new consistent API."""
        container = Container()
        container[Database] = Database
        
        # Current code using resolve_sync() should continue to work
        db1 = container.resolve_sync(Database)
        assert isinstance(db1, Database)
        
        # Current code using asyncio.run(container.resolve()) should work  
        # In the new system, resolve() is smart and returns the result directly in sync context
        try:
            asyncio.get_running_loop()
            pytest.skip("Already in event loop")
        except RuntimeError:
            # New code can use smart resolve() - no asyncio.run needed!
            db2 = container.resolve(Database)
            assert isinstance(db2, Database)
            
            # But if they want to use asyncio.run, they need resolve_async() 
            db3 = asyncio.run(container.resolve_async(Database))
            assert isinstance(db3, Database)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])