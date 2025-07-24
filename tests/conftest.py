"""Shared test fixtures and utilities."""

import asyncio
from dataclasses import dataclass
from typing import Any

import pytest

from whiskey.core.container import Container
from whiskey.core.decorators import set_default_container
from whiskey.core.types import Disposable, Initializable


@pytest.fixture
def container():
    """Create a fresh container for testing."""
    container = Container()
    # Set as default for decorators
    set_default_container(container)
    yield container
    # Cleanup
    asyncio.run(container.dispose())


@pytest.fixture
def event_bus():
    """Create a fresh event bus for testing."""
    from whiskey.core.events import EventBus
    
    bus = EventBus()
    yield bus
    # Cleanup if started
    if bus._running:
        asyncio.run(bus.stop())


@pytest.fixture
def app():
    """Create a test application."""
    from whiskey.core.application import Application, ApplicationConfig
    
    config = ApplicationConfig(
        name="TestApp",
        version="0.1.0",
        debug=True,
    )
    app = Application(config)
    yield app
    # Cleanup
    if app._running:
        asyncio.run(app.shutdown())


# Test classes for dependency injection
class SimpleService:
    """Simple service with no dependencies."""
    
    def __init__(self):
        self.initialized = True
        self.value = "simple"


class DependentService:
    """Service that depends on SimpleService."""
    
    def __init__(self, simple: SimpleService):
        self.simple = simple
        self.value = "dependent"


class CircularServiceA:
    """Service A in circular dependency."""
    
    def __init__(self, service_b: "CircularServiceB"):
        self.service_b = service_b


class CircularServiceB:
    """Service B in circular dependency."""
    
    def __init__(self, service_a: CircularServiceA):
        self.service_a = service_a


class OptionalDependencyService:
    """Service with optional dependency."""
    
    def __init__(self, simple: SimpleService | None = None):
        self.simple = simple
        self.has_dependency = simple is not None


class AsyncInitService(Initializable):
    """Service with async initialization."""
    
    def __init__(self):
        self.initialized = False
        self.init_count = 0
    
    async def initialize(self):
        await asyncio.sleep(0.01)
        self.initialized = True
        self.init_count += 1


class DisposableService(Disposable):
    """Service with disposal logic."""
    
    def __init__(self):
        self.disposed = False
        self.dispose_count = 0
    
    async def dispose(self):
        await asyncio.sleep(0.01)
        self.disposed = True
        self.dispose_count += 1


class ComplexService(Initializable, Disposable):
    """Service with both initialization and disposal."""
    
    def __init__(self, simple: SimpleService):
        self.simple = simple
        self.initialized = False
        self.disposed = False
    
    async def initialize(self):
        self.initialized = True
    
    async def dispose(self):
        self.disposed = True


# Factory functions for testing
def simple_factory() -> SimpleService:
    """Factory that creates SimpleService."""
    return SimpleService()


async def async_factory() -> SimpleService:
    """Async factory that creates SimpleService."""
    await asyncio.sleep(0.01)
    return SimpleService()


def factory_with_deps(simple: SimpleService) -> DependentService:
    """Factory with dependencies."""
    return DependentService(simple)


# Test utilities
async def wait_for(condition, timeout=1.0, interval=0.01):
    """Wait for a condition to become true."""
    start = asyncio.get_event_loop().time()
    while not condition():
        if asyncio.get_event_loop().time() - start > timeout:
            raise TimeoutError("Condition not met within timeout")
        await asyncio.sleep(interval)