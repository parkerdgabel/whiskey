#!/usr/bin/env python3
"""
Whiskey Framework Stress Test V2

This application attempts to break the Whiskey framework by testing edge cases.
"""

import asyncio
import gc
import sys
import threading
import time
import weakref
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Generic, Optional, TypeVar, Union

sys.path.insert(0, "src")

from whiskey import Whiskey
from whiskey.core.errors import CircularDependencyError, ResolutionError, ScopeError
from whiskey.core.registry import Scope


async def test_circular_dependencies():
    """Test 1: Circular Dependencies"""
    print("\n[TEST 1] Testing circular dependencies...")
    app = Whiskey(name="test_circular")
    results = []

    # Define circular dependency classes
    @app.component
    class ServiceA:
        def __init__(self, b: "ServiceB"):
            self.b = b

    @app.component
    class ServiceB:
        def __init__(self, a: ServiceA):
            self.a = a

    # Try to resolve - should fail
    try:
        await app.resolve(ServiceA)
        results.append(("FAIL", "Circular dependency A<->B not caught!"))
    except CircularDependencyError as e:
        results.append(("PASS", f"Circular dependency A<->B caught: {e}"))
    except Exception as e:
        results.append(("FAIL", f"Wrong exception type: {type(e).__name__}: {e}"))

    # Test longer cycle
    @app.component
    class ServiceC:
        def __init__(self, d: "ServiceD"):
            self.d = d

    @app.component
    class ServiceD:
        def __init__(self, e: "ServiceE"):
            self.e = e

    @app.component
    class ServiceE:
        def __init__(self, c: ServiceC):
            self.c = c

    try:
        await app.resolve(ServiceC)
        results.append(("FAIL", "Circular dependency C->D->E->C not caught!"))
    except CircularDependencyError as e:
        results.append(("PASS", f"Circular dependency C->D->E->C caught: {e}"))
    except Exception as e:
        results.append(("FAIL", f"Wrong exception type: {type(e).__name__}: {e}"))

    return results


async def test_scope_violations():
    """Test 2: Scope Violations"""
    print("\n[TEST 2] Testing scope violations...")
    app = Whiskey(name="test_scopes")
    results = []

    # Define scoped service first
    @app.scoped("request")
    class ScopedService:
        def __init__(self):
            self.id = id(self)

    # Singleton depending on scoped - should fail
    @app.singleton
    class SingletonService:
        def __init__(self, scoped: ScopedService):
            self.scoped = scoped

    try:
        await app.resolve(SingletonService)
        results.append(("FAIL", "Scope violation: Singleton depending on Scoped not caught!"))
    except (ScopeError, ResolutionError) as e:
        results.append(("PASS", f"Scope violation caught: {e}"))
    except Exception as e:
        results.append(("FAIL", f"Unexpected exception: {type(e).__name__}: {e}"))

    # Test cross-scope dependencies
    @app.scoped("session")
    class SessionService:
        def __init__(self):
            self.id = id(self)

    @app.scoped("request")
    class RequestService:
        def __init__(self, session: SessionService):
            self.session = session

    # This might work if request scope is nested in session scope
    try:
        async with app.container.scope("session") as session_scope:
            async with session_scope.scope("request") as request_scope:
                await request_scope.resolve(RequestService)
                results.append(("PASS", "Cross-scope dependency works when properly nested"))
    except Exception as e:
        results.append(("INFO", f"Cross-scope dependency behavior: {e}"))

    return results


async def test_complex_types():
    """Test 3: Complex Type Hints"""
    print("\n[TEST 3] Testing complex type hints...")
    app = Whiskey(name="test_types")
    results = []

    # Define complex types
    T = TypeVar("T")

    class BaseModel:
        pass

    @dataclass
    class UserModel(BaseModel):
        name: str

    class Repository(Generic[T], ABC):
        @abstractmethod
        async def find(self, id: int) -> Optional[T]:
            pass

    @app.component
    class UserRepository(Repository[UserModel]):
        async def find(self, id: int) -> Optional[UserModel]:
            return UserModel(name=f"User{id}")

    @app.component
    class OptionalDep:
        def __init__(self):
            self.value = "I exist!"

    @app.component
    class ComplexService:
        def __init__(
            self,
            repo: Repository[UserModel],  # Generic type
            optional: Optional[OptionalDep] = None,  # Optional dependency
            union_type: Union[str, int] = "default",  # Union type - should not be injected
            list_type: Optional[list[str]] = None,  # Collection type - should not be injected
            dict_type: Optional[dict[str, Any]] = None,  # Dict type - should not be injected
        ):
            self.repo = repo
            self.optional = optional
            self.union_type = union_type
            self.list_type = list_type or []
            self.dict_type = dict_type or {}

    try:
        service = await app.resolve(ComplexService)
        results.append(("PASS", "Complex type hints resolved"))

        # Check optional was injected
        if service.optional and service.optional.value == "I exist!":
            results.append(("PASS", "Optional dependency injected correctly"))
        else:
            results.append(("FAIL", "Optional dependency not injected"))

        # Check defaults preserved
        if service.union_type == "default":
            results.append(("PASS", "Default values preserved"))
        else:
            results.append(("FAIL", "Default values not preserved"))

    except Exception as e:
        results.append(("FAIL", f"Complex type resolution failed: {e}"))

    return results


async def test_memory_and_resources():
    """Test 4: Memory Management"""
    print("\n[TEST 4] Testing memory management...")
    app = Whiskey(name="test_memory")
    results = []

    # Test transient lifecycle
    @app.component
    class TransientService:
        instances = []

        def __init__(self):
            self.id = id(self)
            TransientService.instances.append(weakref.ref(self))

    # Create many instances
    services = []
    for _i in range(100):
        service = await app.resolve(TransientService)
        services.append(service)

    # Check all are different
    ids = {s.id for s in services}
    if len(ids) == 100:
        results.append(("PASS", "Transient services create new instances"))
    else:
        results.append(("FAIL", f"Transient services reused: {len(ids)} unique out of 100"))

    # Clear references and check cleanup
    services.clear()
    gc.collect()

    alive = sum(1 for ref in TransientService.instances if ref() is not None)
    if alive == 0:
        results.append(("PASS", "Transient services properly garbage collected"))
    else:
        results.append(("WARN", f"{alive} transient services still referenced"))

    # Test singleton lifecycle
    @app.singleton
    class SingletonService:
        count = 0

        def __init__(self):
            SingletonService.count += 1
            self.instance_num = SingletonService.count

    # Get multiple times
    s1 = await app.resolve(SingletonService)
    s2 = await app.resolve(SingletonService)
    s3 = await app.resolve(SingletonService)

    if s1 is s2 is s3 and SingletonService.count == 1:
        results.append(("PASS", "Singleton creates only one instance"))
    else:
        results.append(("FAIL", f"Singleton created {SingletonService.count} instances"))

    return results


async def test_concurrent_access():
    """Test 5: Concurrent Access"""
    print("\n[TEST 5] Testing concurrent access...")
    app = Whiskey(name="test_concurrent")
    results = []

    @app.singleton
    class SharedCounter:
        def __init__(self):
            self.count = 0
            self.lock = threading.Lock()

        def increment_unsafe(self):
            current = self.count
            # Simulate race condition
            time.sleep(0.00001)
            self.count = current + 1

        def increment_safe(self):
            with self.lock:
                self.count += 1

    counter = await app.resolve(SharedCounter)

    # Test race condition
    async def increment_task():
        for _ in range(100):
            counter.increment_unsafe()

    # Run concurrently
    tasks = [increment_task() for _ in range(10)]
    await asyncio.gather(*tasks)

    if counter.count < 1000:
        results.append(("PASS", f"Race condition detected: count={counter.count} (expected 1000)"))
    else:
        results.append(("WARN", "Race condition might not have occurred"))

    # Test thread safety
    counter.count = 0

    def thread_increment():
        for _ in range(100):
            counter.increment_safe()

    threads = []
    for _ in range(10):
        t = threading.Thread(target=thread_increment)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    if counter.count == 1000:
        results.append(("PASS", "Thread-safe increment works correctly"))
    else:
        results.append(("FAIL", f"Thread-safe increment failed: count={counter.count}"))

    return results


async def test_factory_edge_cases():
    """Test 6: Factory Edge Cases"""
    print("\n[TEST 6] Testing factory edge cases...")
    app = Whiskey(name="test_factory")
    results = []

    # Factory with state
    call_count = 0

    @app.factory(int)
    def create_int():
        nonlocal call_count
        call_count += 1
        if call_count > 3:
            raise RuntimeError("Factory exploded!")
        return call_count

    # Call factory multiple times
    try:
        nums = []
        for _i in range(5):
            num = await app.resolve(int)
            nums.append(num)
        results.append(("FAIL", "Factory exception not raised"))
    except RuntimeError as e:
        if "exploded" in str(e):
            results.append(("PASS", f"Factory exception caught after {call_count} calls"))
        else:
            results.append(("FAIL", f"Wrong exception: {e}"))

    # Mutable singleton factory
    @app.factory(list, scope=Scope.SINGLETON)
    def create_list():
        return []  # Dangerous - mutable singleton!

    list1 = await app.resolve(list)
    list2 = await app.resolve(list)

    list1.append("modified")

    if list2 == ["modified"]:
        results.append(("WARN", "Mutable singleton shares state (potential bug source)"))
    else:
        results.append(("PASS", "Mutable singleton handled separately"))

    # Factory with dependencies
    @app.singleton
    class Config:
        def __init__(self):
            self.value = 42

    @app.factory(str)
    def create_string(config: Config):
        return f"Value: {config.value}"

    try:
        string = await app.resolve(str)
        if string == "Value: 42":
            results.append(("PASS", "Factory with dependencies works"))
        else:
            results.append(("FAIL", f"Factory returned unexpected: {string}"))
    except Exception as e:
        results.append(("FAIL", f"Factory with dependencies failed: {e}"))

    return results


async def test_edge_cases():
    """Test 7: Edge Cases"""
    print("\n[TEST 7] Testing edge cases...")
    app = Whiskey(name="test_edges")
    results = []

    # Empty container resolution
    try:
        await app.resolve("NonExistentService")
        results.append(("FAIL", "Non-existent service resolved"))
    except ResolutionError:
        results.append(("PASS", "Non-existent service raises ResolutionError"))

    # Multiple registrations
    @app.component(name="impl1")
    class Service:
        def __init__(self):
            self.name = "impl1"

    @app.component(name="impl2")
    class Service:
        def __init__(self):
            self.name = "impl2"

    # Resolve by name
    impl1 = await app.resolve(Service, name="impl1")
    impl2 = await app.resolve(Service, name="impl2")

    if impl1.name == "impl1" and impl2.name == "impl2":
        results.append(("PASS", "Named resolution works"))
    else:
        results.append(("FAIL", "Named resolution failed"))

    # Resolve without name - what happens?
    try:
        default = await app.resolve(Service)
        results.append(("INFO", f"Default resolution returned: {default.name}"))
    except Exception as e:
        results.append(("INFO", f"Default resolution behavior: {e}"))

    # Self-dependency
    @app.component
    class SelfDependent:
        def __init__(self, self_ref: "SelfDependent" = None):
            self.self_ref = self_ref

    try:
        self_dep = await app.resolve(SelfDependent)
        if self_dep.self_ref is None:
            results.append(("PASS", "Self-dependency handled gracefully"))
        else:
            results.append(("WARN", "Self-dependency resolved somehow"))
    except Exception as e:
        results.append(("INFO", f"Self-dependency behavior: {e}"))

    return results


async def test_error_recovery():
    """Test 8: Error Recovery"""
    print("\n[TEST 8] Testing error recovery...")
    app = Whiskey(name="test_errors")
    results = []

    # Component that fails on init
    init_count = 0

    @app.component
    class FailingService:
        def __init__(self):
            nonlocal init_count
            init_count += 1
            raise RuntimeError(f"Init failed on attempt {init_count}")

    # Try multiple times
    for i in range(3):
        try:
            await app.resolve(FailingService)
            results.append(("FAIL", "Failing service succeeded"))
        except RuntimeError as e:
            if f"attempt {i + 1}" in str(e):
                results.append(("PASS", f"Failure {i + 1} caught correctly"))

    # Container should still work
    @app.singleton
    class WorkingService:
        def __init__(self):
            self.working = True

    try:
        working = await app.resolve(WorkingService)
        if working.working:
            results.append(("PASS", "Container works after failures"))
    except Exception as e:
        results.append(("FAIL", f"Container broken after failures: {e}"))

    # Partial initialization failure
    @app.component
    class PartiallyFailingService:
        instances = []

        def __init__(self):
            self.resource = "allocated"
            PartiallyFailingService.instances.append(self)
            raise RuntimeError("Failed after partial init")

    try:
        await app.resolve(PartiallyFailingService)
        results.append(("FAIL", "Partially failing service succeeded"))
    except RuntimeError:
        results.append(("PASS", "Partial failure caught"))
        # Check for resource leak
        if len(PartiallyFailingService.instances) > 0:
            results.append(
                (
                    "WARN",
                    f"Resource leak: {len(PartiallyFailingService.instances)} partial instances",
                )
            )

    return results


async def run_all_tests():
    """Run all stress tests"""
    all_results = []

    print("\n" + "=" * 60)
    print("WHISKEY FRAMEWORK STRESS TEST V2")
    print("=" * 60)

    # Run each test
    test_functions = [
        test_circular_dependencies,
        test_scope_violations,
        test_complex_types,
        test_memory_and_resources,
        test_concurrent_access,
        test_factory_edge_cases,
        test_edge_cases,
        test_error_recovery,
    ]

    for test_func in test_functions:
        try:
            results = await test_func()
            all_results.extend(results)
        except Exception as e:
            all_results.append(("ERROR", f"{test_func.__name__} crashed: {e}"))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for status, _ in all_results if status == "PASS")
    failed = sum(1 for status, _ in all_results if status == "FAIL")
    warnings = sum(1 for status, _ in all_results if status == "WARN")
    info = sum(1 for status, _ in all_results if status == "INFO")
    errors = sum(1 for status, _ in all_results if status == "ERROR")

    print("\nResults:")
    print(f"  PASSED:   {passed}")
    print(f"  FAILED:   {failed}")
    print(f"  WARNINGS: {warnings}")
    print(f"  INFO:     {info}")
    print(f"  ERRORS:   {errors}")
    print(f"  TOTAL:    {len(all_results)}")

    print(f"\nSuccess Rate: {passed}/{passed + failed} ({passed / (passed + failed) * 100:.1f}%)")

    # Detailed results
    print("\n" + "=" * 60)
    print("DETAILED RESULTS")
    print("=" * 60)

    for status, message in all_results:
        symbol = {"PASS": "✓", "FAIL": "✗", "WARN": "⚠", "INFO": "📋", "ERROR": "⚠"}.get(status, "?")
        print(f"{symbol} [{status}] {message}")

    return all_results


if __name__ == "__main__":
    asyncio.run(run_all_tests())
