"""Tests for type definitions and protocols."""

import asyncio

import pytest

from whiskey.core.types import Disposable, Initializable


class TestInitializableProtocol:
    """Test the Initializable protocol."""

    async def test_initializable_implementation(self):
        """Test implementing the Initializable protocol."""

        class MyService:
            def __init__(self):
                self.initialized = False

            async def initialize(self) -> None:
                await asyncio.sleep(0.01)  # Simulate async work
                self.initialized = True

        service = MyService()
        assert not service.initialized

        await service.initialize()
        assert service.initialized

    def test_runtime_checkable(self):
        """Test that Initializable is runtime checkable."""

        class WithInitialize:
            async def initialize(self) -> None:
                pass

        class WithoutInitialize:
            pass

        assert isinstance(WithInitialize(), Initializable)
        assert not isinstance(WithoutInitialize(), Initializable)

    async def test_initializable_with_error(self):
        """Test Initializable that raises error."""

        class FailingService:
            async def initialize(self) -> None:
                raise RuntimeError("Initialization failed")

        service = FailingService()

        with pytest.raises(RuntimeError, match="Initialization failed"):
            await service.initialize()


class TestDisposableProtocol:
    """Test the Disposable protocol."""

    async def test_disposable_implementation(self):
        """Test implementing the Disposable protocol."""

        class MyResource:
            def __init__(self):
                self.disposed = False

            async def dispose(self) -> None:
                await asyncio.sleep(0.01)  # Simulate cleanup
                self.disposed = True

        resource = MyResource()
        assert not resource.disposed

        await resource.dispose()
        assert resource.disposed

    def test_runtime_checkable(self):
        """Test that Disposable is runtime checkable."""

        class WithDispose:
            async def dispose(self) -> None:
                pass

        class WithoutDispose:
            pass

        assert isinstance(WithDispose(), Disposable)
        assert not isinstance(WithoutDispose(), Disposable)

    async def test_disposable_idempotent(self):
        """Test that dispose can be called multiple times."""

        class IdempotentResource:
            def __init__(self):
                self.dispose_count = 0

            async def dispose(self) -> None:
                self.dispose_count += 1

        resource = IdempotentResource()

        # Should handle multiple calls
        await resource.dispose()
        await resource.dispose()
        await resource.dispose()

        assert resource.dispose_count == 3


class TestCombinedProtocols:
    """Test services implementing multiple protocols."""

    async def test_initializable_and_disposable(self):
        """Test service implementing both protocols."""

        class FullLifecycleService:
            def __init__(self):
                self.initialized = False
                self.disposed = False

            async def initialize(self) -> None:
                self.initialized = True

            async def dispose(self) -> None:
                self.disposed = True

        service = FullLifecycleService()

        # Check both protocols
        assert isinstance(service, Initializable)
        assert isinstance(service, Disposable)

        # Test lifecycle
        assert not service.initialized
        assert not service.disposed

        await service.initialize()
        assert service.initialized
        assert not service.disposed

        await service.dispose()
        assert service.initialized
        assert service.disposed
