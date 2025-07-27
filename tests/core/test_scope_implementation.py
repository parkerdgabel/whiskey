"""Test the scope implementation functionality."""

import pytest
from whiskey import Container, scoped, inject
from whiskey.core.scopes import Scope, ContextVarScope


class Counter:
    """Test service that counts instances."""
    instance_count = 0
    
    def __init__(self):
        Counter.instance_count += 1
        self.instance_number = Counter.instance_count
        self.disposed = False
        
    def dispose(self):
        """Mark as disposed."""
        self.disposed = True


@pytest.mark.asyncio
async def test_transient_scope():
    """Test transient scope creates new instances each time."""
    container = Container()
    container.register(Counter, scope="transient")
    
    counter1 = await container.resolve(Counter)
    counter2 = await container.resolve(Counter)
    
    assert counter1.instance_number != counter2.instance_number
    assert Counter.instance_count == 2


@pytest.mark.asyncio
async def test_singleton_scope():
    """Test singleton scope returns same instance."""
    container = Container()
    Counter.instance_count = 0
    container.register(Counter, scope="singleton")
    
    counter1 = await container.resolve(Counter)
    counter2 = await container.resolve(Counter)
    
    assert counter1 is counter2
    assert Counter.instance_count == 1


@pytest.mark.asyncio
async def test_custom_scope():
    """Test custom scope management."""
    container = Container()
    Counter.instance_count = 0
    
    # Register a custom scope
    container.register_scope("request", Scope)
    container.register(Counter, scope="request")
    
    # Outside of scope - should create new instances
    counter1 = await container.resolve(Counter)
    counter2 = await container.resolve(Counter)
    assert counter1.instance_number != counter2.instance_number
    
    # Inside scope - should reuse instance
    async with container.scope("request"):
        counter3 = await container.resolve(Counter)
        counter4 = await container.resolve(Counter)
        assert counter3 is counter4
        assert counter3.instance_number == counter4.instance_number
        
    # After scope - should create new instances again
    counter5 = await container.resolve(Counter)
    assert counter5.instance_number not in (counter3.instance_number, counter4.instance_number)


@pytest.mark.asyncio
async def test_scope_disposal():
    """Test that scoped instances are disposed when scope exits."""
    container = Container()
    container.register_scope("request", Scope)
    container.register(Counter, scope="request")
    
    counter = None
    async with container.scope("request"):
        counter = await container.resolve(Counter)
        assert not counter.disposed
        
    # After scope exit, instance should be disposed
    assert counter.disposed


@pytest.mark.asyncio
async def test_nested_scopes():
    """Test nested scope behavior."""
    container = Container()
    Counter.instance_count = 0
    
    # Register two scopes
    container.register_scope("request", Scope)
    container.register_scope("session", Scope)
    
    # Register services with different scopes
    class RequestService:
        def __init__(self):
            self.id = "request"
            
    class SessionService:
        def __init__(self):
            self.id = "session"
    
    container.register(RequestService, scope="request")
    container.register(SessionService, scope="session")
    
    async with container.scope("session"):
        session1 = await container.resolve(SessionService)
        
        async with container.scope("request"):
            request1 = await container.resolve(RequestService)
            session2 = await container.resolve(SessionService)
            
            # Same instances within scopes
            assert session1 is session2
            
        async with container.scope("request"):
            request2 = await container.resolve(RequestService)
            session3 = await container.resolve(SessionService)
            
            # New request instance, same session instance
            assert request1 is not request2
            assert session1 is session3


@pytest.mark.asyncio
async def test_scoped_decorator():
    """Test @scoped decorator."""
    container = Container()
    container.register_scope("request", Scope)
    
    # Set the container as default so @scoped can use it
    from whiskey.core.decorators import set_default_container
    set_default_container(container)
    
    @scoped("request")
    class RequestScopedService:
        instance_count = 0
        
        def __init__(self):
            RequestScopedService.instance_count += 1
            self.instance_number = RequestScopedService.instance_count
    
    # No need to register again - @scoped already did it
    
    async with container.scope("request"):
        service1 = await container.resolve(RequestScopedService)
        service2 = await container.resolve(RequestScopedService)
        assert service1 is service2


@pytest.mark.asyncio
async def test_context_var_scope():
    """Test ContextVarScope for async safety."""
    container = Container()
    container.register_scope("request", ContextVarScope)
    
    Counter.instance_count = 0
    container.register(Counter, scope="request")
    
    # Each async context should have its own instance
    import asyncio
    
    async def task(task_id: int):
        async with container.scope("request"):
            counter = await container.resolve(Counter)
            # Each task should get its own instance
            return counter.instance_number
    
    # Run tasks concurrently
    results = await asyncio.gather(
        task(1),
        task(2),
        task(3)
    )
    
    # All should have different instances
    assert len(set(results)) == 3


@pytest.mark.asyncio
async def test_scope_with_inject():
    """Test scope works with @inject decorator."""
    container = Container()
    container.register_scope("request", Scope)
    container.register(Counter, scope="request")
    
    # Set the container as default for @inject
    from whiskey.core.decorators import set_default_container
    set_default_container(container)
    
    @inject
    async def get_counter(counter: Counter) -> int:
        return counter.instance_number
    
    async with container.scope("request"):
        # Multiple calls should get same instance
        num1 = await get_counter()
        num2 = await get_counter()
        assert num1 == num2