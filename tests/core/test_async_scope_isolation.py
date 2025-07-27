"""Test async scope isolation with ContextVarScope."""

import asyncio
import pytest
from whiskey import Application, inject
from whiskey_asgi import asgi_extension


class RequestService:
    """Service that should be unique per request."""
    instance_count = 0
    
    def __init__(self):
        RequestService.instance_count += 1
        self.request_id = RequestService.instance_count


@pytest.mark.asyncio
async def test_request_scope_isolation():
    """Test that request scope properly isolates between async contexts."""
    app = Application()
    app.use(asgi_extension)
    
    # Register a request-scoped service
    app.container.register(RequestService, scope="request")
    
    results = []
    
    async def simulate_request(request_num: int):
        """Simulate a request handling."""
        async with app.container.scope("request"):
            # Get the service multiple times within same request
            service1 = await app.container.resolve(RequestService)
            await asyncio.sleep(0.01)  # Simulate some async work
            service2 = await app.container.resolve(RequestService)
            
            # Should be same instance within request
            assert service1 is service2
            results.append(service1.request_id)
            return service1.request_id
    
    # Run multiple "requests" concurrently
    request_ids = await asyncio.gather(
        simulate_request(1),
        simulate_request(2),
        simulate_request(3),
        simulate_request(4),
        simulate_request(5)
    )
    
    # Each request should have gotten a different instance
    assert len(set(request_ids)) == 5
    assert sorted(results) == [1, 2, 3, 4, 5]


@pytest.mark.asyncio
async def test_sequential_requests_in_session():
    """Test that sequential requests in a session share session scope."""
    app = Application()
    app.use(asgi_extension)
    
    # Register services with different scopes
    class SessionData:
        def __init__(self):
            self.id = id(self)
    
    class RequestData:
        def __init__(self):
            self.id = id(self)
    
    app.container.register(SessionData, scope="session")
    app.container.register(RequestData, scope="request")
    
    session_ids = []
    request_ids = []
    
    # Simulate session with sequential requests (how it would work in reality)
    async with app.container.scope("session"):
        # Request 1
        async with app.container.scope("request"):
            session = await app.container.resolve(SessionData)
            request = await app.container.resolve(RequestData)
            session_ids.append(session.id)
            request_ids.append(request.id)
        
        # Request 2
        async with app.container.scope("request"):
            session = await app.container.resolve(SessionData)
            request = await app.container.resolve(RequestData)
            session_ids.append(session.id)
            request_ids.append(request.id)
        
        # Request 3
        async with app.container.scope("request"):
            session = await app.container.resolve(SessionData)
            request = await app.container.resolve(RequestData)
            session_ids.append(session.id)
            request_ids.append(request.id)
    
    # All requests should share same session but have different request data
    assert len(set(session_ids)) == 1  # Same session
    assert len(set(request_ids)) == 3  # Different requests


@pytest.mark.asyncio
async def test_scope_with_inject_decorator():
    """Test that @inject works properly with async scopes."""
    app = Application()
    app.use(asgi_extension)
    
    from whiskey.core.decorators import set_default_container
    set_default_container(app.container)
    
    app.container.register(RequestService, scope="request")
    
    @inject
    async def get_request_id(service: RequestService) -> int:
        return service.request_id
    
    async def handle_request():
        async with app.container.scope("request"):
            id1 = await get_request_id()
            id2 = await get_request_id()
            # Same request context should return same ID
            assert id1 == id2
            return id1
    
    # Run multiple requests concurrently
    ids = await asyncio.gather(
        handle_request(),
        handle_request(),
        handle_request()
    )
    
    # Each request should have different ID
    assert len(set(ids)) == 3