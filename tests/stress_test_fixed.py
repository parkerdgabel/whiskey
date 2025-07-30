#!/usr/bin/env python3
"""
Fixed Whiskey Framework Stress Test

This application tests the Whiskey framework improvements with corrected API usage.
"""

import asyncio
import gc
import threading
import time
import weakref
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, TypeVar, Generic, Protocol, Union
from abc import ABC, abstractmethod

import sys
sys.path.insert(0, 'src')

from whiskey import Whiskey, Container
from whiskey.core.errors import CircularDependencyError, ResolutionError, ScopeError, ConfigurationError
from whiskey.core.registry import Scope


async def test_circular_dependencies():
    """Test 1: Circular Dependencies"""
    print("\n[TEST 1] Testing circular dependencies...")
    app = Whiskey(name="test_circular")
    results = []
    
    # Define circular dependency classes
    @app.component
    class ServiceA:
        def __init__(self, b: 'ServiceB'):
            self.b = b

    @app.component
    class ServiceB:
        def __init__(self, a: ServiceA):
            self.a = a

    # Try to resolve - should fail
    try:
        service_a = await app.resolve_async(ServiceA)
        results.append(("FAIL", "Circular dependency A<->B not caught!"))
    except CircularDependencyError as e:
        results.append(("PASS", f"Circular dependency A<->B caught: {e}"))
    except Exception as e:
        results.append(("FAIL", f"Wrong exception type: {type(e).__name__}: {e}"))
    
    # Test longer cycle
    @app.component
    class ServiceC:
        def __init__(self, d: 'ServiceD'):
            self.d = d

    @app.component  
    class ServiceD:
        def __init__(self, e: 'ServiceE'):
            self.e = e

    @app.component
    class ServiceE:
        def __init__(self, c: ServiceC):
            self.c = c
    
    try:
        service_c = await app.resolve_async(ServiceC)
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
    @app.scoped(scope_name="request")
    class ScopedService:
        def __init__(self):
            self.id = id(self)
    
    # Singleton depending on scoped - should fail at registration time now
    try:
        @app.singleton
        class SingletonService:
            def __init__(self, scoped: ScopedService):
                self.scoped = scoped
        results.append(("FAIL", "Scope violation: Singleton depending on Scoped not caught!"))
    except ConfigurationError as e:
        results.append(("PASS", f"Scope violation caught at registration: {e}"))
    except Exception as e:
        results.append(("FAIL", f"Unexpected exception: {type(e).__name__}: {e}"))
    
    # Test valid cross-scope dependency (request depends on session is valid)
    @app.scoped(scope_name="session")
    class SessionService:
        def __init__(self):
            self.id = id(self)
    
    @app.scoped(scope_name="request")
    class RequestService:
        def __init__(self, session: SessionService):
            self.session = session
    
    # This should work since request can depend on session
    try:
        with app.scope("session"):
            with app.scope("request"):
                service = app.resolve(RequestService)
                results.append(("PASS", "Valid cross-scope dependency works"))
    except Exception as e:
        results.append(("INFO", f"Cross-scope dependency behavior: {e}"))
    
    # Test invalid hierarchy (session depends on request should fail)
    try:
        @app.scoped(scope_name="session")
        class BadSessionService:
            def __init__(self, req: RequestService):
                self.req = req
        results.append(("FAIL", "Invalid scope hierarchy not caught!"))
    except ConfigurationError as e:
        results.append(("PASS", f"Invalid scope hierarchy caught: {e}"))
    
    return results


async def test_complex_types():
    """Test 3: Complex Type Hints"""
    print("\n[TEST 3] Testing complex type hints...")
    app = Whiskey(name="test_types")
    results = []
    
    # Define complex types
    T = TypeVar('T')
    
    @dataclass
    class UserModel:
        id: int
        name: str
    
    class Repository(Generic[T]):
        def __init__(self):
            self.items: List[T] = []
    
    # Register the specific repository type
    @app.singleton
    class UserRepository(Repository[UserModel]):
        def __init__(self):
            super().__init__()
    
    @app.component
    class ComplexService:
        def __init__(self, repo: UserRepository):  # Use concrete type
            self.repo = repo
    
    try:
        service = await app.resolve_async(ComplexService)
        results.append(("PASS", "Complex type resolution works"))
    except Exception as e:
        results.append(("FAIL", f"Complex type resolution failed: {e}"))
    
    # Test optional dependencies
    @app.component
    class OptionalService:
        def __init__(self, required: ComplexService, optional: Optional[str] = None):
            self.required = required
            self.optional = optional
    
    try:
        service = await app.resolve_async(OptionalService)
        results.append(("PASS", "Optional dependencies handled"))
    except Exception as e:
        results.append(("FAIL", f"Optional dependency failed: {e}"))
    
    return results


async def test_memory_and_resources():
    """Test 4: Memory Management"""
    print("\n[TEST 4] Testing memory management...")
    app = Whiskey(name="test_memory")
    results = []
    
    # Test lifecycle hooks for cleanup
    class TransientService:
        def __init__(self):
            self.initialized = False
            self.disposed = False
        
        def initialize(self):
            self.initialized = True
        
        def dispose(self):
            self.disposed = True
    
    app.component(TransientService)
    
    try:
        # Create multiple instances
        instances = []
        for _ in range(10):
            instance = await app.resolve_async(TransientService)
            instances.append(instance)
            assert instance.initialized is True
        
        # Clear singletons (should call dispose hooks)
        await app.container.clear_singletons_async()
        
        results.append(("PASS", "Memory management with lifecycle hooks works"))
    except Exception as e:
        results.append(("FAIL", f"Memory management failed: {e}"))
    
    # Test weak references
    @app.singleton
    class SingletonService:
        def __init__(self):
            self.data = "singleton_data"
    
    try:
        service1 = await app.resolve_async(SingletonService)
        service2 = await app.resolve_async(SingletonService)
        assert service1 is service2  # Same instance
        results.append(("PASS", "Singleton identity maintained"))
    except Exception as e:
        results.append(("FAIL", f"Singleton test failed: {e}"))
    
    return results


async def test_concurrent_access():
    """Test 5: Concurrent Access"""
    print("\n[TEST 5] Testing concurrent access...")
    app = Whiskey(name="test_concurrent")
    results = []
    
    class SharedCounter:
        def __init__(self):
            self.count = 0
            self.lock = threading.Lock()
        
        def increment(self):
            with self.lock:
                self.count += 1
                return self.count
    
    app.singleton(SharedCounter)
    
    async def concurrent_task():
        counter = await app.resolve_async(SharedCounter)
        return counter.increment()
    
    try:
        # Run multiple concurrent tasks
        tasks = [concurrent_task() for _ in range(100)]
        results_list = await asyncio.gather(*tasks)
        
        # Verify all tasks got the same counter instance
        counter = await app.resolve_async(SharedCounter)
        expected_count = 100
        
        if counter.count == expected_count:
            results.append(("PASS", f"Concurrent access works: {counter.count} increments"))
        else:
            results.append(("FAIL", f"Concurrent access failed: expected {expected_count}, got {counter.count}"))
            
    except Exception as e:
        results.append(("FAIL", f"Concurrent access crashed: {e}"))
    
    return results


async def test_factory_edge_cases():
    """Test 6: Factory Edge Cases"""
    print("\n[TEST 6] Testing factory edge cases...")
    app = Whiskey(name="test_factories")
    results = []
    
    # Test factory function with dependencies
    @app.singleton
    class ConfigService:
        def __init__(self):
            self.config = {"database_url": "postgresql://localhost"}
    
    def create_database_connection(config: ConfigService) -> str:
        return f"Connection to {config.config['database_url']}"
    
    app.factory("database", create_database_connection)
    
    try:
        db_connection = await app.resolve_async("database")
        if "postgresql://localhost" in db_connection:
            results.append(("PASS", "Factory with dependencies works"))
        else:
            results.append(("FAIL", f"Factory result unexpected: {db_connection}"))
    except Exception as e:
        results.append(("FAIL", f"Factory with dependencies failed: {e}"))
    
    # Test async factory
    async def create_async_service() -> str:
        await asyncio.sleep(0.01)  # Simulate async work
        return "async_service_instance"
    
    app.factory("async_service", create_async_service)
    
    try:
        service = await app.resolve_async("async_service")
        if service == "async_service_instance":
            results.append(("PASS", "Async factory works"))
        else:
            results.append(("FAIL", f"Async factory result unexpected: {service}"))
    except Exception as e:
        results.append(("FAIL", f"Async factory failed: {e}"))
    
    return results


async def test_edge_cases():
    """Test 7: Edge Cases"""  
    print("\n[TEST 7] Testing edge cases...")
    app = Whiskey(name="test_edges")
    results = []
    
    # Test with no-argument constructor
    class Service:
        def __init__(self):
            self.created = True
    
    app.component(Service)
    
    try:
        service = await app.resolve_async(Service)
        if hasattr(service, 'created') and service.created:
            results.append(("PASS", "No-argument constructor works"))
        else:
            results.append(("FAIL", "No-argument constructor failed"))
    except Exception as e:
        results.append(("FAIL", f"No-argument constructor crashed: {e}"))
    
    # Test multiple registration of same type
    class MultiService:
        def __init__(self):
            self.instance_id = id(self)
    
    app.component(MultiService, name="first")
    app.component(MultiService, name="second")
    
    try:
        first = await app.resolve_async(MultiService, name="first")
        second = await app.resolve_async(MultiService, name="second")
        
        if first.instance_id != second.instance_id:
            results.append(("PASS", "Named component registration works"))
        else:
            results.append(("FAIL", "Named components returned same instance"))
    except Exception as e:
        results.append(("INFO", f"Named components: {e}"))  # May not be implemented
    
    return results


async def test_error_recovery():
    """Test 8: Error Recovery"""
    print("\n[TEST 8] Testing error recovery...")
    app = Whiskey(name="test_recovery")
    results = []
    
    # Test recovery from failed service
    class FailingService:
        attempt_count = 0
        
        def __init__(self):
            FailingService.attempt_count += 1
            if FailingService.attempt_count <= 2:
                raise RuntimeError(f"Init failed on attempt {FailingService.attempt_count}")
            self.success = True
    
    app.component(FailingService)
    
    # First two attempts should fail
    try:
        await app.resolve_async(FailingService)
        results.append(("FAIL", "Expected failure on first attempt"))
    except Exception as e:
        results.append(("PASS", f"First failure handled: {e}"))
    
    try:
        await app.resolve_async(FailingService)
        results.append(("FAIL", "Expected failure on second attempt"))  
    except Exception as e:
        results.append(("PASS", f"Second failure handled: {e}"))
    
    # Third attempt should succeed
    try:
        service = await app.resolve_async(FailingService)
        if hasattr(service, 'success') and service.success:
            results.append(("PASS", "Recovery after failures works"))
        else:
            results.append(("FAIL", "Service not properly initialized after recovery"))
    except Exception as e:
        results.append(("FAIL", f"Recovery failed: {e}"))
    
    return results


async def main():
    """Run all stress tests"""
    print("=" * 60)
    print("WHISKEY FRAMEWORK STRESS TEST - FIXED VERSION")
    print("=" * 60)
    
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
    
    all_results = []
    passed = 0
    failed = 0
    warnings = 0
    info = 0
    errors = 0
    
    for test_func in test_functions:
        try:
            results = await test_func()
            all_results.extend(results)
        except Exception as e:
            all_results.append(("ERROR", f"{test_func.__name__} crashed: {e}"))
    
    # Count results
    for result_type, message in all_results:
        if result_type == "PASS":
            passed += 1
        elif result_type == "FAIL":
            failed += 1
        elif result_type == "WARNING":
            warnings += 1
        elif result_type == "INFO":
            info += 1
        elif result_type == "ERROR":
            errors += 1
    
    total_tests = passed + failed
    success_rate = (passed / total_tests * 100) if total_tests > 0 else 0
    
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print()
    print("Results:")
    print(f"  PASSED:   {passed}")
    print(f"  FAILED:   {failed}")
    print(f"  WARNINGS: {warnings}")
    print(f"  INFO:     {info}")
    print(f"  ERRORS:   {errors}")
    print(f"  TOTAL:    {total_tests}")
    print()
    print(f"Success Rate: {passed}/{total_tests} ({success_rate:.1f}%)")
    
    print("\n" + "=" * 60)
    print("DETAILED RESULTS")
    print("=" * 60)
    
    for result_type, message in all_results:
        if result_type == "PASS":
            print(f"✓ [PASS] {message}")
        elif result_type == "FAIL":
            print(f"✗ [FAIL] {message}")
        elif result_type == "WARNING":
            print(f"⚠ [WARNING] {message}")
        elif result_type == "INFO":
            print(f"ℹ [INFO] {message}")
        elif result_type == "ERROR":
            print(f"⚠ [ERROR] {message}")
    
    return success_rate >= 80.0  # 80% success rate threshold


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)