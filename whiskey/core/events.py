"""Event-driven architecture for IoC."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Awaitable, Callable
from uuid import UUID, uuid4

from loguru import logger


@dataclass
class Event:
    """Base class for all events."""
    
    event_id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)


EventHandler = Callable[[Event], Awaitable[None]]
Middleware = Callable[[Event, Callable], Awaitable[Any]]


class EventBus:
    """
    Central event bus for IoC event-driven architecture.
    
    Enables loose coupling between components through events.
    """
    
    def __init__(self):
        self._handlers: dict[type[Event] | str, list[EventHandler]] = {}
        self._middleware: list[Middleware] = []
        self._event_queue: asyncio.Queue[tuple[Event | None, EventHandler | None]] = None
        self._worker_task: asyncio.Task | None = None
        self._running = False
    
    def on(self, event_type: type[Event] | str, handler: EventHandler) -> None:
        """Register an event handler."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.debug(f"Registered handler for {event_type}")
    
    def off(self, event_type: type[Event] | str, handler: EventHandler) -> None:
        """Unregister an event handler."""
        if event_type in self._handlers:
            self._handlers[event_type].remove(handler)
    
    def add_middleware(self, middleware: Middleware) -> None:
        """Add middleware to process all events."""
        self._middleware.append(middleware)
    
    async def emit(self, event: Event) -> None:
        """Emit an event asynchronously."""
        # Initialize queue if needed
        if self._event_queue is None:
            self._event_queue = asyncio.Queue()
        
        # Get handlers for event type
        handlers = self._handlers.get(type(event), [])
        handlers.extend(self._handlers.get(event.__class__.__name__, []))
        
        # Apply middleware chain
        for handler in handlers:
            wrapped_handler = handler
            
            # Wrap handler with middleware
            for middleware in reversed(self._middleware):
                async def make_wrapped(mw, h):
                    async def wrapped(e):
                        return await mw(e, lambda ev: h(ev))
                    return wrapped
                
                wrapped_handler = await make_wrapped(middleware, wrapped_handler)
            
            # Queue for processing
            await self._event_queue.put((event, wrapped_handler))
    
    async def emit_sync(self, event: Event) -> None:
        """Emit an event and wait for all handlers to complete."""
        tasks = []
        
        # Get handlers
        handlers = self._handlers.get(type(event), [])
        handlers.extend(self._handlers.get(event.__class__.__name__, []))
        
        for handler in handlers:
            wrapped_handler = handler
            
            # Apply middleware
            for middleware in reversed(self._middleware):
                async def make_wrapped(mw, h):
                    async def wrapped(e):
                        return await mw(e, lambda ev: h(ev))
                    return wrapped
                
                wrapped_handler = await make_wrapped(middleware, wrapped_handler)
            
            # Create task
            task = asyncio.create_task(wrapped_handler(event))
            tasks.append(task)
        
        # Wait for all handlers
        if tasks:
            await asyncio.gather(*tasks)
    
    async def start(self):
        """Start the event processing worker."""
        if self._event_queue is None:
            self._event_queue = asyncio.Queue()
        self._running = True
        self._worker_task = asyncio.create_task(self._process_events())
        logger.info("Event bus started")
    
    async def stop(self):
        """Stop the event processing worker."""
        self._running = False
        if self._worker_task:
            await self._event_queue.put((None, None))  # Sentinel
            await self._worker_task
        logger.info("Event bus stopped")
    
    async def _process_events(self):
        """Process events from the queue."""
        while self._running:
            try:
                event, handler = await self._event_queue.get()
                
                if event is None:  # Sentinel
                    break
                
                try:
                    await handler(event)
                except Exception as e:
                    logger.error(f"Error handling event {event.event_id}: {e}")
                
            except Exception as e:
                logger.error(f"Event processing error: {e}")


# Common event types

@dataclass
class ApplicationStarted(Event):
    """Emitted when application starts."""
    app_name: str = ""
    version: str = ""


@dataclass
class ApplicationStopping(Event):
    """Emitted when application is shutting down."""
    reason: str = "normal"


@dataclass
class ServiceInitialized(Event):
    """Emitted when a service is initialized."""
    service_name: str = ""
    service_type: type | None = None


@dataclass
class RequestReceived(Event):
    """Emitted when a request is received."""
    request_id: UUID = field(default_factory=uuid4)
    method: str = ""
    path: str = ""
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class RequestCompleted(Event):
    """Emitted when a request is completed."""
    request_id: UUID = field(default_factory=uuid4)
    status_code: int = 0
    duration_ms: float = 0.0


@dataclass 
class ErrorOccurred(Event):
    """Emitted when an error occurs."""
    error_type: str = ""
    error_message: str = ""
    stack_trace: str | None = None
    context: dict[str, Any] = field(default_factory=dict)