"""Shared test fixtures and utilities."""

import asyncio

import pytest

from whiskey.core.builder import create_app
from whiskey.core.container import Container
from whiskey.core.testing import TestContainer, add_test_compatibility_methods


@pytest.fixture
def container():
    """Create a fresh container for testing."""
    container = Container()
    # Add test compatibility methods for tests that need them
    add_test_compatibility_methods(container)
    # Verify methods were added
    assert hasattr(container, 'enter_scope'), "enter_scope method not added"
    yield container
    # Cleanup caches
    container.clear_caches()


@pytest.fixture
def clean_container():
    """Create a fresh container without test compatibility methods."""
    container = Container()
    yield container
    # Cleanup caches
    container.clear_caches()


@pytest.fixture
def event_bus():
    """Create a fresh event bus for testing."""
    # Event bus is now part of Application
    app = create_app().build_app()
    yield app._event_emitter
    # Cleanup handled by application


@pytest.fixture
def app():
    """Create a test application."""
    app = create_app().build_app()
    yield app
    # Cleanup handled by context manager


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


class AsyncInitService:
    """Service with async initialization."""

    def __init__(self):
        self.initialized = False
        self.init_count = 0

    async def initialize(self):
        await asyncio.sleep(0.01)
        self.initialized = True
        self.init_count += 1


class DisposableService:
    """Service with disposal logic."""

    def __init__(self):
        self.disposed = False
        self.dispose_count = 0

    async def dispose(self):
        await asyncio.sleep(0.01)
        self.disposed = True
        self.dispose_count += 1


class ComplexService:
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
