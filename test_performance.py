"""Performance testing for the Whiskey DI system.

This script tests various performance scenarios and generates reports.
"""

import asyncio
import time
from typing import Optional

from src.whiskey.core.container import Container
from src.whiskey.core.performance import PerformanceMonitor
from src.whiskey.core.registry import Scope


# Test services for performance testing
class Database:
    def __init__(self):
        self.connection_id = f"db_{time.time()}"
    
    def query(self, sql: str) -> str:
        return f"Result from {self.connection_id}: {sql}"


class Cache:
    def __init__(self, db: Database):
        self.db = db
        self.cache_id = f"cache_{time.time()}"
    
    def get(self, key: str) -> Optional[str]:
        return f"Cached value for {key} via {self.cache_id}"


class Logger:
    def __init__(self):
        self.logger_id = f"logger_{time.time()}"
    
    def log(self, message: str) -> None:
        print(f"[{self.logger_id}] {message}")


class UserService:
    def __init__(self, db: Database, cache: Cache, logger: Logger):
        self.db = db
        self.cache = cache
        self.logger = logger
    
    def get_user(self, user_id: int) -> str:
        result = self.db.query(f"SELECT * FROM users WHERE id={user_id}")
        cached = self.cache.get(f"user_{user_id}")
        self.logger.log(f"Retrieved user {user_id}")
        return f"{result} | {cached}"


class OrderService:
    def __init__(self, db: Database, user_service: UserService, logger: Logger):
        self.db = db
        self.user_service = user_service
        self.logger = logger
    
    def get_order(self, order_id: int) -> str:
        user_info = self.user_service.get_user(1)  # Always get user 1
        order_data = self.db.query(f"SELECT * FROM orders WHERE id={order_id}")
        self.logger.log(f"Retrieved order {order_id}")
        return f"Order: {order_data}, User: {user_info}"


async def test_transient_performance():
    """Test performance with transient services."""
    print("Testing transient service performance...")
    
    container = Container()
    
    # Register all services as transient
    container.add(Database, Database).build()
    container.add(Cache, Cache).build()
    container.add(Logger, Logger).build()
    container.add(UserService, UserService).build()
    container.add(OrderService, OrderService).build()
    
    with PerformanceMonitor() as metrics:
        # Resolve services multiple times
        for i in range(100):
            order_service = await container.resolve(OrderService)
            result = order_service.get_order(i)
    
    print(f"Transient Performance:")
    print(f"  Resolutions: {metrics.resolution_count}")
    print(f"  Average time: {metrics.average_resolution_time:.4f}s")
    print(f"  Cache hit rate: {metrics.cache_hit_rate:.1f}%")
    print(f"  Average depth: {metrics.average_resolution_depth:.1f}")
    print()


async def test_singleton_performance():
    """Test performance with singleton services."""
    print("Testing singleton service performance...")
    
    container = Container()
    
    # Register all services as singletons
    container.add(Database, Database).as_singleton().build()
    container.add(Cache, Cache).as_singleton().build()
    container.add(Logger, Logger).as_singleton().build()
    container.add(UserService, UserService).as_singleton().build()
    container.add(OrderService, OrderService).as_singleton().build()
    
    with PerformanceMonitor() as metrics:
        # Resolve services multiple times
        for i in range(100):
            order_service = await container.resolve(OrderService)
            result = order_service.get_order(i)
    
    print(f"Singleton Performance:")
    print(f"  Resolutions: {metrics.resolution_count}")
    print(f"  Average time: {metrics.average_resolution_time:.4f}s")
    print(f"  Cache hit rate: {metrics.cache_hit_rate:.1f}%")
    print(f"  Average depth: {metrics.average_resolution_depth:.1f}")
    print()


async def test_mixed_scopes_performance():
    """Test performance with mixed scopes."""
    print("Testing mixed scope performance...")
    
    container = Container()
    
    # Mix of scopes based on usage patterns
    container.add(Database, Database).as_singleton().build()  # Expensive to create
    container.add(Cache, Cache).as_singleton().build()       # Shared state
    container.add(Logger, Logger).as_singleton().build()     # Shared state
    container.add(UserService, UserService).build()          # Business logic, transient
    container.add(OrderService, OrderService).build()        # Business logic, transient
    
    with PerformanceMonitor() as metrics:
        # Resolve services multiple times
        for i in range(100):
            order_service = await container.resolve(OrderService)
            result = order_service.get_order(i)
    
    print(f"Mixed Scopes Performance:")
    print(f"  Resolutions: {metrics.resolution_count}")
    print(f"  Average time: {metrics.average_resolution_time:.4f}s")
    print(f"  Cache hit rate: {metrics.cache_hit_rate:.1f}%")
    print(f"  Average depth: {metrics.average_resolution_depth:.1f}")
    print()


async def test_deep_dependency_tree():
    """Test performance with deep dependency trees."""
    print("Testing deep dependency performance...")
    
    # Create a chain of dependencies: A -> B -> C -> D -> E
    class ServiceE:
        pass
    
    class ServiceD:
        def __init__(self, e: ServiceE):
            self.e = e
    
    class ServiceC:
        def __init__(self, d: ServiceD):
            self.d = d
    
    class ServiceB:
        def __init__(self, c: ServiceC):
            self.c = c
    
    class ServiceA:
        def __init__(self, b: ServiceB, logger: Logger):  # Also depends on logger
            self.b = b
            self.logger = logger
    
    container = Container()
    
    # Register the chain
    container.add(ServiceE, ServiceE).as_singleton().build()
    container.add(ServiceD, ServiceD).as_singleton().build()
    container.add(ServiceC, ServiceC).as_singleton().build()
    container.add(ServiceB, ServiceB).as_singleton().build()
    container.add(ServiceA, ServiceA).build()  # Transient top-level service
    container.add(Logger, Logger).as_singleton().build()
    
    with PerformanceMonitor() as metrics:
        # Resolve the top-level service multiple times
        for i in range(50):
            service_a = await container.resolve(ServiceA)
    
    print(f"Deep Dependencies Performance:")
    print(f"  Resolutions: {metrics.resolution_count}")
    print(f"  Average time: {metrics.average_resolution_time:.4f}s")
    print(f"  Cache hit rate: {metrics.cache_hit_rate:.1f}%")
    print(f"  Average depth: {metrics.average_resolution_depth:.1f}")
    print()


async def test_concurrent_resolutions():
    """Test performance under concurrent load."""
    print("Testing concurrent resolution performance...")
    
    container = Container()
    
    # Register services
    container.add(Database, Database).as_singleton().build()
    container.add(Cache, Cache).as_singleton().build()
    container.add(Logger, Logger).as_singleton().build()
    container.add(UserService, UserService).build()
    container.add(OrderService, OrderService).build()
    
    async def resolve_worker(worker_id: int, iterations: int):
        """Worker that resolves services concurrently."""
        for i in range(iterations):
            order_service = await container.resolve(OrderService)
            user_service = await container.resolve(UserService)
            logger = await container.resolve(Logger)
    
    with PerformanceMonitor() as metrics:
        # Create concurrent workers
        tasks = []
        for worker_id in range(10):
            task = asyncio.create_task(resolve_worker(worker_id, 20))
            tasks.append(task)
        
        # Wait for all workers to complete
        await asyncio.gather(*tasks)
    
    print(f"Concurrent Performance (10 workers, 20 iterations each):")
    print(f"  Resolutions: {metrics.resolution_count}")
    print(f"  Average time: {metrics.average_resolution_time:.4f}s")
    print(f"  Cache hit rate: {metrics.cache_hit_rate:.1f}%")
    print(f"  Average depth: {metrics.average_resolution_depth:.1f}")
    print()


async def test_comprehensive_performance():
    """Run comprehensive performance tests and generate a report."""
    print("=== Whiskey DI Performance Test Suite ===\n")
    
    await test_transient_performance()
    await test_singleton_performance()
    await test_mixed_scopes_performance()
    await test_deep_dependency_tree()
    await test_concurrent_resolutions()
    
    # Final comprehensive test with detailed reporting
    print("Running comprehensive test with detailed metrics...")
    
    container = Container()
    container.add(Database, Database).as_singleton().build()
    container.add(Cache, Cache).as_singleton().build()
    container.add(Logger, Logger).as_singleton().build()
    container.add(UserService, UserService).build()
    container.add(OrderService, OrderService).build()
    
    with PerformanceMonitor() as metrics:
        # Mix of different resolution patterns
        for i in range(200):
            if i % 3 == 0:
                await container.resolve(OrderService)
            elif i % 3 == 1:
                await container.resolve(UserService)
            else:
                await container.resolve(Logger)
    
    print(metrics.generate_report())


if __name__ == "__main__":
    asyncio.run(test_comprehensive_performance())