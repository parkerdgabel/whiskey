"""Tests for the @emits decorator."""

import asyncio
import pytest
from typing import Dict, List

from whiskey import Application, inject


class TestEventEmitter:
    """Test the @emits decorator functionality."""
    
    @pytest.mark.unit
    async def test_emits_decorator_async(self):
        """Test @emits decorator with async function."""
        app = Application()
        events_received = []
        
        @app.on("user.created")
        async def capture_event(data: Dict):
            events_received.append(data)
        
        @app.emits("user.created")
        async def create_user(name: str) -> Dict:
            # Simulate user creation
            return {"id": 1, "name": name}
        
        async with app.lifespan():
            result = await create_user("Alice")
            # Give event time to propagate
            await asyncio.sleep(0.01)
            
        assert result == {"id": 1, "name": "Alice"}
        assert events_received == [{"id": 1, "name": "Alice"}]
    
    @pytest.mark.unit
    async def test_emits_decorator_sync(self):
        """Test @emits decorator with sync function."""
        app = Application()
        events_received = []
        
        @app.on("config.loaded")
        async def capture_event(data: Dict):
            events_received.append(data)
        
        @app.emits("config.loaded")
        def load_config() -> Dict:
            return {"debug": True}
        
        async with app.lifespan():
            result = load_config()
            # Give event time to propagate (sync emits use create_task)
            await asyncio.sleep(0.01)
            
        assert result == {"debug": True}
        assert events_received == [{"debug": True}]
    
    @pytest.mark.unit
    async def test_emits_with_none_return(self):
        """Test @emits doesn't emit when function returns None."""
        app = Application()
        events_received = []
        
        @app.on("void.event")
        async def capture_event(data):
            events_received.append(data)
        
        @app.emits("void.event")
        async def void_function():
            # Returns None implicitly
            pass
        
        async with app.lifespan():
            result = await void_function()
            await asyncio.sleep(0.01)
            
        assert result is None
        assert events_received == []  # No event emitted
    
    @pytest.mark.unit
    async def test_emits_with_dependency_injection(self):
        """Test @emits works with @inject."""
        app = Application()
        events_received = []
        
        class UserService:
            def create(self, name: str) -> Dict:
                return {"id": 42, "name": name}
        
        app.container[UserService] = UserService()
        
        @app.on("user.created")
        async def capture_event(data: Dict):
            events_received.append(data)
        
        @app.emits("user.created")
        @inject
        async def create_user(name: str, service: UserService) -> Dict:
            return service.create(name)
        
        async with app.lifespan():
            result = await create_user("Bob")
            await asyncio.sleep(0.01)
            
        assert result == {"id": 42, "name": "Bob"}
        assert events_received == [{"id": 42, "name": "Bob"}]
    
    @pytest.mark.unit
    async def test_emits_on_component_method(self):
        """Test @emits on a component method."""
        app = Application()
        events_received = []
        
        @app.component
        class OrderService:
            @app.emits("order.placed")
            async def place_order(self, item: str, quantity: int) -> Dict:
                return {
                    "id": "order-123",
                    "item": item,
                    "quantity": quantity,
                    "status": "placed"
                }
        
        @app.on("order.placed")
        async def capture_event(data: Dict):
            events_received.append(data)
        
        async with app.lifespan():
            service = await app.container.resolve(OrderService)
            result = await service.place_order("Widget", 5)
            await asyncio.sleep(0.01)
            
        assert result["item"] == "Widget"
        assert result["quantity"] == 5
        assert events_received == [result]
    
    @pytest.mark.unit
    async def test_multiple_emits_decorators(self):
        """Test multiple @emits decorators on same function."""
        app = Application()
        events = {"created": [], "logged": []}
        
        @app.on("user.created")
        async def on_created(data: Dict):
            events["created"].append(data)
            
        @app.on("audit.logged")
        async def on_logged(data: Dict):
            events["logged"].append(data)
        
        @app.emits("audit.logged")
        @app.emits("user.created")
        async def create_user(name: str) -> Dict:
            return {"id": 1, "name": name, "action": "create"}
        
        async with app.lifespan():
            result = await create_user("Charlie")
            await asyncio.sleep(0.01)
            
        # Both events should be emitted with same data
        assert events["created"] == [result]
        assert events["logged"] == [result]
    
    @pytest.mark.unit
    async def test_emits_error_propagation(self):
        """Test errors in emitted functions are propagated."""
        app = Application()
        
        @app.on("error.event")
        async def handler(data):
            pass  # Should not be called
        
        @app.emits("error.event")
        async def failing_function():
            raise ValueError("Test error")
        
        async with app.lifespan():
            with pytest.raises(ValueError, match="Test error"):
                await failing_function()
    
    @pytest.mark.unit
    async def test_emits_with_wildcard_handlers(self):
        """Test @emits works with wildcard event handlers."""
        app = Application()
        all_events = []
        user_events = []
        
        @app.on("*")  # Catch all
        async def catch_all(data: Dict = None):
            if data is not None:
                all_events.append(data)
            
        @app.on("user.*")
        async def catch_user(data: Dict):
            user_events.append(data)
        
        @app.emits("user.created")
        async def create_user() -> Dict:
            return {"type": "user", "id": 1}
            
        @app.emits("order.created")
        async def create_order() -> Dict:
            return {"type": "order", "id": 1}
        
        async with app.lifespan():
            user = await create_user()
            order = await create_order()
            await asyncio.sleep(0.01)
            
        assert len(all_events) == 2  # Both events
        assert len(user_events) == 1  # Only user event
        assert user_events[0] == user