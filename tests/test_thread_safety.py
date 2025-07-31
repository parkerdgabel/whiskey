"""Test thread safety for Phase 5.1.

This test identifies and fixes thread-safety issues in singleton creation:
- Race conditions in singleton resolution
- Multiple instances created concurrently
- Cache inconsistencies under concurrent access
- Both sync and async thread safety
"""

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from whiskey import Whiskey
from whiskey.core.container import Container


# Test classes for thread safety scenarios
class ExpensiveService:
    """Service that takes time to initialize to expose race conditions."""

    def __init__(self):
        # Simulate expensive initialization
        time.sleep(0.1)  # 100ms delay
        self.created_at = time.time()
        self.thread_id = threading.get_ident()

    def get_id(self) -> str:
        return f"{self.thread_id}_{self.created_at}"


class DatabaseConnection:
    """Simulates database connection that should be singleton."""

    _instance_count = 0

    def __init__(self):
        # Increment counter atomically
        DatabaseConnection._instance_count += 1
        self.instance_number = DatabaseConnection._instance_count
        time.sleep(0.05)  # Simulate connection setup
        self.connection_id = f"conn_{self.instance_number}_{threading.get_ident()}"

    @classmethod
    def reset_counter(cls):
        cls._instance_count = 0


class ServiceWithDatabaseDep:
    """Service that depends on database connection."""

    def __init__(self, db: DatabaseConnection):
        self.db = db
        self.created_at = time.time()


@pytest.mark.unit
class TestSingletonThreadSafety:
    """Test thread safety of singleton creation."""

    def test_concurrent_singleton_creation_sync(self):
        """Test that concurrent sync singleton creation is thread-safe."""
        DatabaseConnection.reset_counter()
        container = Container()
        container.singleton(DatabaseConnection)

        num_threads = 10
        results = []

        def resolve_service():
            return container.resolve(DatabaseConnection)

        # Resolve singleton concurrently from multiple threads
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(resolve_service) for _ in range(num_threads)]
            results = [future.result() for future in as_completed(futures)]

        # All results should be the same instance
        first_instance = results[0]
        for instance in results[1:]:
            assert instance is first_instance, (
                f"Expected same instance, got different: {instance.connection_id} vs {first_instance.connection_id}"
            )

        # Only one instance should have been created
        assert DatabaseConnection._instance_count == 1, (
            f"Expected 1 instance, created {DatabaseConnection._instance_count}"
        )

    def test_concurrent_singleton_with_dependencies_sync(self):
        """Test thread safety when singleton has dependencies."""
        DatabaseConnection.reset_counter()
        container = Container()
        container.singleton(DatabaseConnection)
        container.register(ServiceWithDatabaseDep, ServiceWithDatabaseDep)

        num_threads = 8
        results = []

        def resolve_service():
            return container.resolve(ServiceWithDatabaseDep)

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(resolve_service) for _ in range(num_threads)]
            results = [future.result() for future in as_completed(futures)]

        # All services should have the same database instance
        first_db = results[0].db
        for service in results[1:]:
            assert service.db is first_db, "Expected same DB instance, got different"

        # Only one database instance should exist
        assert DatabaseConnection._instance_count == 1, (
            f"Expected 1 DB instance, created {DatabaseConnection._instance_count}"
        )

    @pytest.mark.asyncio
    async def test_concurrent_singleton_creation_async(self):
        """Test that concurrent async singleton creation is thread-safe."""
        DatabaseConnection.reset_counter()
        container = Container()
        container.singleton(DatabaseConnection)

        num_tasks = 10

        async def resolve_service():
            return await container.resolve_async(DatabaseConnection)

        # Resolve singleton concurrently from multiple async tasks
        tasks = [resolve_service() for _ in range(num_tasks)]
        results = await asyncio.gather(*tasks)

        # All results should be the same instance
        first_instance = results[0]
        for instance in results[1:]:
            assert instance is first_instance, (
                f"Expected same instance, got different: {instance.connection_id} vs {first_instance.connection_id}"
            )

        # Only one instance should have been created
        assert DatabaseConnection._instance_count == 1, (
            f"Expected 1 instance, created {DatabaseConnection._instance_count}"
        )

    @pytest.mark.asyncio
    async def test_mixed_sync_async_singleton_access(self):
        """Test thread safety when mixing sync and async access to singletons."""
        DatabaseConnection.reset_counter()
        container = Container()
        container.singleton(DatabaseConnection)

        sync_results = []
        async_results = []

        def sync_resolve():
            return container.resolve(DatabaseConnection)

        async def async_resolve():
            return await container.resolve_async(DatabaseConnection)

        # First run async resolutions
        async_tasks = [async_resolve() for _ in range(5)]
        async_results = await asyncio.gather(*async_tasks)

        # Then run sync resolutions in separate threads
        with ThreadPoolExecutor(max_workers=5) as executor:
            sync_futures = [executor.submit(sync_resolve) for _ in range(5)]
            sync_results = [future.result() for future in as_completed(sync_futures)]

        # All instances should be the same
        all_instances = sync_results + async_results
        first_instance = all_instances[0]

        for instance in all_instances[1:]:
            assert instance is first_instance, (
                "Mixed sync/async should return same singleton instance"
            )

        # Only one instance should exist
        assert DatabaseConnection._instance_count == 1, (
            f"Expected 1 instance, created {DatabaseConnection._instance_count}"
        )

    def test_singleton_stress_test(self):
        """Stress test singleton creation under high concurrency."""
        DatabaseConnection.reset_counter()
        container = Container()
        container.singleton(DatabaseConnection)

        num_threads = 50
        resolutions_per_thread = 10
        all_instances = []

        def resolve_multiple():
            thread_instances = []
            for _ in range(resolutions_per_thread):
                instance = container.resolve(DatabaseConnection)
                thread_instances.append(instance)
                # Small delay to increase chance of race conditions
                time.sleep(0.001)
            return thread_instances

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(resolve_multiple) for _ in range(num_threads)]

            for future in as_completed(futures):
                thread_instances = future.result()
                all_instances.extend(thread_instances)

        # All instances should be identical
        first_instance = all_instances[0]
        for instance in all_instances:
            assert instance is first_instance, "All singleton instances must be identical"

        # Only one instance should have been created
        assert DatabaseConnection._instance_count <= 1, (
            f"Expected at most 1 instance, created {DatabaseConnection._instance_count}"
        )


@pytest.mark.unit
class TestApplicationThreadSafety:
    """Test thread safety using Whiskey application."""

    def test_app_singleton_thread_safety(self):
        """Test thread safety using Whiskey application decorators."""
        DatabaseConnection.reset_counter()
        app = Whiskey()
        app.singleton(DatabaseConnection)

        num_threads = 15
        results = []

        def resolve_from_app():
            return app.resolve(DatabaseConnection)

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(resolve_from_app) for _ in range(num_threads)]
            results = [future.result() for future in as_completed(futures)]

        # All should be same instance
        first_instance = results[0]
        for instance in results[1:]:
            assert instance is first_instance, "App singleton resolution should be thread-safe"

        assert DatabaseConnection._instance_count == 1, (
            f"Expected 1 instance, created {DatabaseConnection._instance_count}"
        )


@pytest.mark.unit
class TestRaceConditionScenarios:
    """Test specific race condition scenarios."""

    def test_initialization_race_condition(self):
        """Test the specific race condition in singleton initialization."""
        # This test is designed to fail with the current implementation
        # and pass after the thread-safety fix

        container = Container()
        container.singleton(ExpensiveService)

        results = []

        def resolve_expensive():
            return container.resolve(ExpensiveService)

        # Use small number of threads to make race condition more likely
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(resolve_expensive) for _ in range(3)]
            results = [future.result() for future in as_completed(futures)]

        # Check that all instances are identical
        first_instance = results[0]
        instance_ids = {instance.get_id() for instance in results}

        assert len(instance_ids) == 1, (
            f"Race condition detected: created {len(instance_ids)} different instances: {instance_ids}"
        )

        for instance in results:
            assert instance is first_instance, "All instances must be the exact same object"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
