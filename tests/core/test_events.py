"""Tests for the event bus system."""

import asyncio
from dataclasses import dataclass
from typing import Any

import pytest

from whiskey.core.events import Event, EventBus
from ..conftest import SimpleService


@dataclass
class TestEvent(Event):
    """Test event for testing."""
    value: str = "test"
    count: int = 0


@dataclass
class AnotherTestEvent(Event):
    """Another test event."""
    message: str = "hello"


class TestEventClass:
    """Test Event base class."""
    
    @pytest.mark.unit
    def test_event_creation(self):
        """Test creating events."""
        event = TestEvent(value="custom", count=5)
        
        assert event.value == "custom"
        assert event.count == 5
    
    @pytest.mark.unit
    def test_event_defaults(self):
        """Test event default values."""
        event = TestEvent()
        
        assert event.value == "test"
        assert event.count == 0


class TestEventBus:
    """Test EventBus functionality."""
    
    @pytest.mark.unit
    def test_event_bus_creation(self):
        """Test creating event bus."""
        bus = EventBus()
        
        assert not bus._running
        assert len(bus._handlers) == 0
        assert len(bus._middleware) == 0
        assert bus._queue is None
    
    @pytest.mark.unit
    async def test_start_stop(self):
        """Test starting and stopping event bus."""
        bus = EventBus()
        
        await bus.start()
        assert bus._running
        assert bus._queue is not None
        assert bus._worker_task is not None
        
        await bus.stop()
        assert not bus._running
        assert bus._queue is None
        assert bus._worker_task is None
    
    @pytest.mark.unit
    async def test_emit_when_not_running(self):
        """Test emitting events when bus is not running."""
        bus = EventBus()
        
        # Should not raise error, just log warning
        await bus.emit("test_event", {"data": "test"})
    
    @pytest.mark.unit
    async def test_on_string_event(self):
        """Test registering handler for string event."""
        bus = EventBus()
        
        handler_called = False
        received_event = None
        
        @bus.on("test_event")
        async def handler(event):
            nonlocal handler_called, received_event
            handler_called = True
            received_event = event
        
        await bus.start()
        
        # Emit event
        await bus.emit("test_event", {"data": "test"})
        await asyncio.sleep(0.01)  # Let worker process
        
        assert handler_called
        assert received_event == {"data": "test"}
        
        await bus.stop()
    
    @pytest.mark.unit
    async def test_on_typed_event(self):
        """Test registering handler for typed event."""
        bus = EventBus()
        
        handler_called = False
        received_event = None
        
        @bus.on(TestEvent)
        async def handler(event: TestEvent):
            nonlocal handler_called, received_event
            handler_called = True
            received_event = event
        
        await bus.start()
        
        # Emit typed event
        event = TestEvent(value="typed", count=42)
        await bus.emit(event)
        await asyncio.sleep(0.01)
        
        assert handler_called
        assert received_event is event
        assert received_event.value == "typed"
        assert received_event.count == 42
        
        await bus.stop()
    
    @pytest.mark.unit
    async def test_multiple_handlers(self):
        """Test multiple handlers for same event."""
        bus = EventBus()
        
        call_count = 0
        
        @bus.on("multi_event")
        async def handler1(event):
            nonlocal call_count
            call_count += 1
        
        @bus.on("multi_event")
        async def handler2(event):
            nonlocal call_count
            call_count += 1
        
        await bus.start()
        
        await bus.emit("multi_event", {})
        await asyncio.sleep(0.01)
        
        assert call_count == 2
        
        await bus.stop()
    
    @pytest.mark.unit
    async def test_handler_error_handling(self):
        """Test handler errors don't stop other handlers."""
        bus = EventBus()
        
        handler2_called = False
        
        @bus.on("error_event")
        async def failing_handler(event):
            raise ValueError("Handler failed")
        
        @bus.on("error_event")
        async def working_handler(event):
            nonlocal handler2_called
            handler2_called = True
        
        await bus.start()
        
        await bus.emit("error_event", {})
        await asyncio.sleep(0.01)
        
        # Second handler should still be called
        assert handler2_called
        
        await bus.stop()
    
    @pytest.mark.unit
    async def test_once_handler(self):
        """Test one-time event handler."""
        bus = EventBus()
        
        call_count = 0
        
        @bus.once("once_event")
        async def handler(event):
            nonlocal call_count
            call_count += 1
        
        await bus.start()
        
        # First emit
        await bus.emit("once_event", {})
        await asyncio.sleep(0.01)
        assert call_count == 1
        
        # Second emit - handler should not be called
        await bus.emit("once_event", {})
        await asyncio.sleep(0.01)
        assert call_count == 1
        
        await bus.stop()
    
    @pytest.mark.unit
    async def test_off_remove_handler(self):
        """Test removing event handler."""
        bus = EventBus()
        
        call_count = 0
        
        async def handler(event):
            nonlocal call_count
            call_count += 1
        
        bus.on("remove_event", handler)
        
        await bus.start()
        
        # Handler should be called
        await bus.emit("remove_event", {})
        await asyncio.sleep(0.01)
        assert call_count == 1
        
        # Remove handler
        bus.off("remove_event", handler)
        
        # Handler should not be called
        await bus.emit("remove_event", {})
        await asyncio.sleep(0.01)
        assert call_count == 1
        
        await bus.stop()
    
    @pytest.mark.unit
    def test_off_nonexistent_handler(self):
        """Test removing nonexistent handler doesn't error."""
        bus = EventBus()
        
        async def handler(event):
            pass
        
        # Should not raise error
        bus.off("nonexistent", handler)
        bus.off("test_event", handler)
    
    @pytest.mark.unit
    async def test_middleware_execution(self):
        """Test middleware execution order."""
        bus = EventBus()
        
        execution_order = []
        
        class Middleware1:
            async def process(self, event, next_handler):
                execution_order.append("middleware1_before")
                result = await next_handler(event)
                execution_order.append("middleware1_after")
                return result
        
        class Middleware2:
            async def process(self, event, next_handler):
                execution_order.append("middleware2_before")
                result = await next_handler(event)
                execution_order.append("middleware2_after")
                return result
        
        bus.add_middleware(Middleware1())
        bus.add_middleware(Middleware2())
        
        @bus.on("middleware_event")
        async def handler(event):
            execution_order.append("handler")
            return "result"
        
        await bus.start()
        
        await bus.emit("middleware_event", {})
        await asyncio.sleep(0.01)
        
        # Middleware should wrap handler in order
        expected = [
            "middleware1_before",
            "middleware2_before",
            "handler",
            "middleware2_after",
            "middleware1_after"
        ]
        assert execution_order == expected
        
        await bus.stop()
    
    @pytest.mark.unit
    async def test_middleware_can_modify_event(self):
        """Test middleware can modify events."""
        bus = EventBus()
        
        received_event = None
        
        class ModifyingMiddleware:
            async def process(self, event, next_handler):
                # Modify event
                if isinstance(event, dict):
                    event["modified"] = True
                return await next_handler(event)
        
        bus.add_middleware(ModifyingMiddleware())
        
        @bus.on("modify_event")
        async def handler(event):
            nonlocal received_event
            received_event = event
        
        await bus.start()
        
        await bus.emit("modify_event", {"original": True})
        await asyncio.sleep(0.01)
        
        assert received_event == {"original": True, "modified": True}
        
        await bus.stop()
    
    @pytest.mark.unit
    async def test_middleware_can_short_circuit(self):
        """Test middleware can prevent handler execution."""
        bus = EventBus()
        
        handler_called = False
        
        class ShortCircuitMiddleware:
            async def process(self, event, next_handler):
                # Don't call next_handler
                return "short_circuited"
        
        bus.add_middleware(ShortCircuitMiddleware())
        
        @bus.on("short_circuit_event")
        async def handler(event):
            nonlocal handler_called
            handler_called = True
        
        await bus.start()
        
        await bus.emit("short_circuit_event", {})
        await asyncio.sleep(0.01)
        
        assert not handler_called
        
        await bus.stop()
    
    @pytest.mark.unit
    async def test_concurrent_event_processing(self):
        """Test events are processed concurrently."""
        bus = EventBus()
        
        processing_times = []
        
        @bus.on("concurrent_event")
        async def slow_handler(event):
            start = asyncio.get_event_loop().time()
            await asyncio.sleep(0.05)
            end = asyncio.get_event_loop().time()
            processing_times.append((start, end))
        
        await bus.start()
        
        # Emit multiple events
        for _ in range(3):
            await bus.emit("concurrent_event", {})
        
        # Wait for processing
        await asyncio.sleep(0.1)
        
        # Check events were processed concurrently (overlapping times)
        assert len(processing_times) == 3
        
        # If processed sequentially, total time would be ~0.15s
        # If concurrent, should be ~0.05s
        total_start = min(t[0] for t in processing_times)
        total_end = max(t[1] for t in processing_times)
        total_time = total_end - total_start
        
        assert total_time < 0.1  # Should be much less than sequential time
        
        await bus.stop()
    
    @pytest.mark.unit
    async def test_typed_event_string_conversion(self):
        """Test typed events can be handled by string name."""
        bus = EventBus()
        
        handler_called = False
        
        @bus.on("TestEvent")  # String name of class
        async def handler(event):
            nonlocal handler_called
            handler_called = True
        
        await bus.start()
        
        # Emit typed event
        await bus.emit(TestEvent())
        await asyncio.sleep(0.01)
        
        assert handler_called
        
        await bus.stop()
    
    @pytest.mark.unit
    async def test_emit_wait(self):
        """Test emit_wait waits for handlers."""
        bus = EventBus()
        
        handler_completed = False
        
        @bus.on("wait_event")
        async def slow_handler(event):
            await asyncio.sleep(0.05)
            nonlocal handler_completed
            handler_completed = True
            return "completed"
        
        await bus.start()
        
        # emit_wait should wait for handler
        results = await bus.emit_wait("wait_event", {})
        
        assert handler_completed
        assert results == ["completed"]
        
        await bus.stop()
    
    @pytest.mark.unit
    async def test_emit_wait_multiple_handlers(self):
        """Test emit_wait with multiple handlers."""
        bus = EventBus()
        
        @bus.on("multi_wait_event")
        async def handler1(event):
            await asyncio.sleep(0.01)
            return "result1"
        
        @bus.on("multi_wait_event")
        async def handler2(event):
            await asyncio.sleep(0.02)
            return "result2"
        
        await bus.start()
        
        results = await bus.emit_wait("multi_wait_event", {})
        
        assert len(results) == 2
        assert "result1" in results
        assert "result2" in results
        
        await bus.stop()
    
    @pytest.mark.unit
    async def test_worker_task_cancellation(self):
        """Test worker task is properly cancelled on stop."""
        bus = EventBus()
        
        await bus.start()
        worker_task = bus._worker_task
        
        assert worker_task is not None
        assert not worker_task.cancelled()
        
        await bus.stop()
        
        assert worker_task.cancelled()
    
    @pytest.mark.unit
    async def test_queue_cleanup_on_stop(self):
        """Test queue is cleaned up on stop."""
        bus = EventBus()
        
        await bus.start()
        
        # Add events to queue
        await bus.emit("test1", {})
        await bus.emit("test2", {})
        
        # Stop immediately (before processing)
        await bus.stop()
        
        # Queue should be None
        assert bus._queue is None