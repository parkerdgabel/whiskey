#!/usr/bin/env python3
"""
Whiskey Framework Stress Test

This application attempts to break the Whiskey framework by testing:
1. Circular dependencies
2. Scope violations
3. Concurrent access and thread safety
4. Memory leaks and resource cleanup
5. Edge cases in dependency resolution
6. Error handling and recovery
7. Performance under load
8. Unusual type hints and generics
"""

import asyncio
import gc
import sys
import threading
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Generic, Optional, Protocol, TypeVar, Union

sys.path.insert(0, "src")

from whiskey import (
    Container,
    Whiskey,
    component,
    factory,
    inject,
    scoped,
    singleton,
)
from whiskey.core.errors import CircularDependencyError, ResolutionError, ScopeError
from whiskey.core.registry import Scope

# Test 1: Circular Dependencies
print("\n=== TEST 1: Circular Dependencies ===")


# Test 2: Scope Violations
print("\n=== TEST 2: Scope Violations ===")


@singleton
class SingletonService:
    def __init__(self, scoped: "ScopedService"):  # Should fail - singleton can't depend on scoped
        self.scoped = scoped


@scoped("request")
class ScopedService:
    def __init__(self):
        self.id = id(self)


@scoped("request")
class RequestService:
    def __init__(self, session: "SessionService"):  # Different scope dependency
        self.session = session


@scoped("session")
class SessionService:
    def __init__(self):
        self.id = id(self)


# Test 3: Complex Type Hints
print("\n=== TEST 3: Complex Type Hints ===")

T = TypeVar("T")
U = TypeVar("U", bound="BaseModel")


class BaseModel:
    pass


@dataclass
class UserModel(BaseModel):
    name: str


class Repository(Generic[T], ABC):
    @abstractmethod
    async def find(self, id: int) -> Optional[T]:
        pass


@component
class UserRepository(Repository[UserModel]):
    async def find(self, id: int) -> Optional[UserModel]:
        return UserModel(name=f"User{id}")


class Service(Protocol):
    def process(self) -> str: ...


@component
class ComplexService:
    def __init__(
        self,
        repo: Repository[UserModel],  # Generic type
        optional: Optional["OptionalDep"] = None,  # Optional dependency
        union_type: Union[str, int] = "default",  # Union type
        list_type: Optional[list[str]] = None,  # Collection type
        dict_type: Optional[dict[str, Any]] = None,  # Dict type
        callable_type: Optional[callable] = None,  # Callable type
    ):
        self.repo = repo
        self.optional = optional
        self.union_type = union_type
        self.list_type = list_type or []
        self.dict_type = dict_type or {}
        self.callable_type = callable_type


@component
class OptionalDep:
    def __init__(self):
        self.value = "I exist!"


# Test 4: Memory Leaks and Resource Management
print("\n=== TEST 4: Memory Leaks and Resource Management ===")


class LeakyService:
    instances = []  # Class variable holding references

    def __init__(self):
        self.data = bytearray(1024 * 1024)  # 1MB of data
        LeakyService.instances.append(self)  # Leak!


@component
class CircularRefService:
    def __init__(self):
        self.self_ref = self  # Circular reference
        self.children = []

    def add_child(self, child):
        self.children.append(child)
        child.parent = self  # Circular reference


@singleton
class ResourceHog:
    def __init__(self):
        self.resources = []
        for _i in range(100):
            self.resources.append(bytearray(1024 * 1024))  # 100MB total


# Test 5: Concurrent Access
print("\n=== TEST 5: Concurrent Access ===")


@singleton
class SharedCounter:
    def __init__(self):
        self.count = 0
        self.lock = threading.Lock()

    def increment(self):
        # Unsafe increment (race condition)
        current = self.count
        time.sleep(0.00001)  # Simulate work
        self.count = current + 1

    def safe_increment(self):
        with self.lock:
            self.count += 1


@component
class ThreadUnsafeService:
    def __init__(self):
        self.state = {}

    def update(self, key, value):
        # Not thread-safe
        self.state[key] = value


# Test 6: Factory Abuse
print("\n=== TEST 6: Factory Abuse ===")

call_count = 0


@factory(int)
def create_random_int():
    global call_count
    call_count += 1
    if call_count > 5:
        raise Exception("Factory explosion!")
    return call_count


@factory(list, scope=Scope.SINGLETON)
def create_shared_list():
    return []  # Mutable singleton!


class FactoryState:
    initialized = False


@factory(FactoryState)
def create_stateful_factory(counter: SharedCounter):
    # Factory with side effects
    counter.increment()
    state = FactoryState()
    state.initialized = True
    return state


# Test 7: Injection Edge Cases
print("\n=== TEST 7: Injection Edge Cases ===")


@inject
async def function_with_args_and_kwargs(*args, service: SharedCounter, **kwargs):
    return args, service, kwargs


@inject
def function_with_defaults(
    required: str,
    service: SharedCounter,
    optional: str = "default",
    nullable: Optional[SharedCounter] = None,
):
    return required, service, optional, nullable


class InjectionTest:
    @inject
    async def method_injection(self, service: SharedCounter):
        return service

    @inject
    @staticmethod
    def static_injection(service: SharedCounter):
        return service

    @inject
    @classmethod
    def class_injection(cls, service: SharedCounter):
        return cls, service


# Test 8: Dynamic Registration
print("\n=== TEST 8: Dynamic Registration ===")


def create_dynamic_classes():
    for i in range(1000):
        # Create classes dynamically
        cls = type(f"DynamicClass{i}", (), {"value": i})
        component(cls)  # Register dynamically


def register_conflicting():
    # Try to register same key multiple times
    container = Container()
    container.add_singleton("key", instance="value1")
    container.add_singleton("key", instance="value2")  # Should this override?


# Main stress test
async def stress_test():
    app = Whiskey(name="stress_test")
    results = {"passed": [], "failed": []}

    print("\n" + "=" * 50)
    print("RUNNING WHISKEY FRAMEWORK STRESS TEST")
    print("=" * 50)

    # Test 1: Circular Dependencies
    print("\n[TEST 1] Testing circular dependencies...")
    try:
        await app.resolve(ServiceA)
        results["failed"].append("Circular dependency A<->B not caught!")
    except CircularDependencyError as e:
        results["passed"].append(f"✓ Circular dependency A<->B caught: {e}")

    try:
        await app.resolve(ServiceC)
        results["failed"].append("Circular dependency C->D->E->C not caught!")
    except CircularDependencyError as e:
        results["passed"].append(f"✓ Circular dependency C->D->E->C caught: {e}")

    # Test 2: Scope Violations
    print("\n[TEST 2] Testing scope violations...")
    try:
        await app.resolve(SingletonService)
        results["failed"].append("Scope violation: Singleton depending on Scoped not caught!")
    except (ScopeError, ResolutionError) as e:
        results["passed"].append(f"✓ Scope violation caught: {e}")

    # Test 3: Complex Type Hints
    print("\n[TEST 3] Testing complex type hints...")
    try:
        complex_service = await app.resolve(ComplexService)
        results["passed"].append("✓ Complex type hints resolved correctly")

        # Verify optional was injected
        if complex_service.optional and complex_service.optional.value == "I exist!":
            results["passed"].append("✓ Optional dependency injected correctly")
        else:
            results["failed"].append("Optional dependency not injected")

    except Exception as e:
        results["failed"].append(f"Complex type resolution failed: {e}")

    # Test 4: Memory Leaks
    print("\n[TEST 4] Testing memory management...")
    len(gc.get_objects())

    # Create many transient instances
    for _i in range(100):
        LeakyService()
        circular = CircularRefService()
        circular.add_child(CircularRefService())

    gc.collect()
    len(gc.get_objects())

    if len(LeakyService.instances) > 100:
        results["failed"].append(
            f"Memory leak detected: {len(LeakyService.instances)} instances retained"
        )
    else:
        results["passed"].append("✓ No significant memory leak detected")

    # Test 5: Concurrent Access
    print("\n[TEST 5] Testing concurrent access...")
    counter = await app.resolve(SharedCounter)

    # Race condition test
    async def increment_task():
        for _ in range(100):
            counter.increment()

    tasks = [increment_task() for _ in range(10)]
    await asyncio.gather(*tasks)

    if counter.count != 1000:
        results["passed"].append(
            f"✓ Race condition detected: count={counter.count} (expected 1000)"
        )
    else:
        results["failed"].append("Race condition not detected in unsafe increment")

    # Thread safety test
    counter.count = 0
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for _ in range(10):
            for _ in range(100):
                futures.append(executor.submit(counter.safe_increment))

        for future in futures:
            future.result()

    if counter.count == 1000:
        results["passed"].append("✓ Thread-safe increment works correctly")
    else:
        results["failed"].append(f"Thread-safe increment failed: count={counter.count}")

    # Test 6: Factory Abuse
    print("\n[TEST 6] Testing factory edge cases...")
    try:
        for i in range(10):
            num = await app.resolve(int)
            if i < 5:
                assert num == i + 1
        results["failed"].append("Factory exception not raised")
    except Exception as e:
        results["passed"].append(f"✓ Factory exception caught: {e}")

    # Mutable singleton test
    list1 = await app.resolve(list)
    list2 = await app.resolve(list)
    list1.append("modified")

    if list2 == ["modified"]:
        results["failed"].append("Mutable singleton allows shared state mutation")
    else:
        results["passed"].append("✓ Mutable singleton handled correctly")

    # Test 7: Injection Edge Cases
    print("\n[TEST 7] Testing injection edge cases...")
    try:
        # Test *args, **kwargs
        args_result = await function_with_args_and_kwargs(1, 2, 3, extra="value")
        if args_result[0] == (1, 2, 3) and args_result[2] == {"extra": "value"}:
            results["passed"].append("✓ *args/**kwargs injection works")
        else:
            results["failed"].append("*args/**kwargs injection failed")

        # Test defaults
        defaults_result = function_with_defaults("required_value")
        if defaults_result[2] == "default":
            results["passed"].append("✓ Default parameters preserved")
        else:
            results["failed"].append("Default parameters not preserved")

    except Exception as e:
        results["failed"].append(f"Injection edge case failed: {e}")

    # Test 8: Container Abuse
    print("\n[TEST 8] Testing container abuse...")
    try:
        # Register many dynamic classes
        create_dynamic_classes()

        # Try to resolve some
        for i in range(0, 1000, 100):
            cls_name = f"DynamicClass{i}"
            cls = globals().get(cls_name)
            if cls:
                await app.resolve(cls)

        results["passed"].append("✓ Dynamic registration handled")

    except Exception as e:
        results["failed"].append(f"Dynamic registration failed: {e}")

    # Test 9: Scope Nesting
    print("\n[TEST 9] Testing scope nesting...")
    try:
        async with app.container.scope("level1") as scope1:
            async with scope1.scope("level2") as scope2:
                async with scope2.scope("level3") as scope3:
                    # Deep nesting
                    await scope3.resolve(ThreadUnsafeService)
                    results["passed"].append("✓ Deep scope nesting works")
    except Exception as e:
        results["failed"].append(f"Scope nesting failed: {e}")

    # Test 10: Error Recovery
    print("\n[TEST 10] Testing error recovery...")

    @component
    class FailingService:
        def __init__(self):
            raise RuntimeError("Initialization failed!")

    try:
        await app.resolve(FailingService)
        results["failed"].append("Failed service initialization not caught")
    except Exception as e:
        results["passed"].append(f"✓ Service initialization error caught: {e}")

        # Can we still use the container?
        try:
            await app.resolve(OptionalDep)
            results["passed"].append("✓ Container still works after error")
        except Exception:
            results["failed"].append("Container broken after error")

    # Print results
    print("\n" + "=" * 50)
    print("STRESS TEST RESULTS")
    print("=" * 50)

    print(f"\nPASSED: {len(results['passed'])}")
    for msg in results["passed"]:
        print(f"  {msg}")

    print(f"\nFAILED: {len(results['failed'])}")
    for msg in results["failed"]:
        print(f"  {msg}")

    print(
        f"\nSUCCESS RATE: {len(results['passed'])}/"
        + f"{len(results['passed']) + len(results['failed'])}"
    )

    # Additional diagnostics
    print("\n" + "=" * 50)
    print("DIAGNOSTICS")
    print("=" * 50)
    print(f"Memory objects: {len(gc.get_objects())}")
    print(f"Container registrations: {len(app.container._registry)}")

    return results


# Performance benchmark
async def performance_benchmark():
    print("\n" + "=" * 50)
    print("PERFORMANCE BENCHMARK")
    print("=" * 50)

    app = Whiskey()

    # Register many components
    for i in range(1000):

        @component
        class BenchmarkService:
            def __init__(self):
                self.id = i

    # Benchmark resolution
    start = time.time()
    for _ in range(10000):
        await app.resolve(ThreadUnsafeService)
    resolution_time = time.time() - start

    print(f"10,000 resolutions: {resolution_time:.3f}s")
    print(f"Average: {resolution_time / 10000 * 1000:.3f}ms per resolution")

    # Benchmark injection
    @inject
    async def injected_function(s1: SharedCounter, s2: OptionalDep, s3: ThreadUnsafeService):
        return s1, s2, s3

    start = time.time()
    for _ in range(10000):
        await injected_function()
    injection_time = time.time() - start

    print(f"10,000 injections: {injection_time:.3f}s")
    print(f"Average: {injection_time / 10000 * 1000:.3f}ms per injection")


if __name__ == "__main__":
    print("Starting Whiskey Framework Stress Test...")

    # Run stress test
    asyncio.run(stress_test())

    # Run performance benchmark
    asyncio.run(performance_benchmark())

    print("\nStress test complete!")
