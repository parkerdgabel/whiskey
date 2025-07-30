#!/usr/bin/env python3
"""
Focused tests demonstrating specific Whiskey framework issues.
Each test is minimal and demonstrates one specific problem.
"""

import sys
sys.path.insert(0, 'src')

from whiskey import component, singleton, inject, Container
from whiskey.core.application import Whiskey


def test_forward_reference_issue():
    """Issue: Forward references in type hints fail"""
    print("\n=== Forward Reference Issue ===")
    
    container = Container()
    
    # This pattern is common in Python but fails in Whiskey
    @component
    class ServiceA:
        def __init__(self, b: 'ServiceB'):  # Forward reference
            self.b = b
    
    @component
    class ServiceB:
        def __init__(self):
            self.value = "B"
    
    try:
        # This should work but doesn't
        container.add_transient(ServiceB)
        container.add_transient(ServiceA)
        
        service_a = container.resolve_sync(ServiceA)
        print(f"✗ FAIL: Expected forward reference to fail, but got: {service_a}")
    except TypeError as e:
        print(f"✓ Confirmed Issue: {e}")
        print("  Fix needed: Use get_type_hints() with proper namespace")


def test_sync_resolve_confusion():
    """Issue: Sync/async API is confusing"""
    print("\n=== Sync/Async API Confusion ===")
    
    app = Whiskey()
    
    @app.singleton
    class MyService:
        def __init__(self):
            self.value = 42
    
    # What's the right way to resolve synchronously?
    try:
        # This is the actual sync API but it's not intuitive
        service = app.container.resolve_sync(MyService)
        print(f"✓ Sync resolution works with: container.resolve_sync()")
        
        # This looks like it should work but doesn't
        service2 = app.resolve(MyService)  # Returns sync, not async!
        print(f"✓ app.resolve() is actually synchronous")
        
    except Exception as e:
        print(f"✗ Issue: {e}")
    
    print("  Confusion: When to use async vs sync is unclear")


def test_optional_injection():
    """Issue: Optional type handling is inconsistent"""
    print("\n=== Optional Type Handling ===")
    
    from typing import Optional
    
    container = Container()
    
    @component
    class OptionalService:
        def __init__(self):
            self.name = "I exist"
    
    @component
    class ConsumerService:
        def __init__(self, 
                     required: OptionalService,
                     optional: Optional[OptionalService] = None,
                     missing: Optional['NonExistentService'] = None):
            self.required = required
            self.optional = optional
            self.missing = missing
    
    container.add_transient(OptionalService)
    container.add_transient(ConsumerService)
    
    try:
        service = container.resolve_sync(ConsumerService)
        
        print(f"✓ Required service injected: {service.required.name}")
        print(f"? Optional existing service: {service.optional}")
        print(f"? Optional missing service: {service.missing}")
        
        if service.optional is not None:
            print("✓ Optional[ExistingService] was injected")
        else:
            print("✗ Optional[ExistingService] was not injected (inconsistent)")
            
    except Exception as e:
        print(f"✗ Failed: {e}")


def test_factory_decorator_syntax():
    """Issue: Factory decorator syntax is confusing"""
    print("\n=== Factory Decorator Syntax ===")
    
    app = Whiskey()
    
    # This is the expected syntax but it's not intuitive
    @app.factory(int, lambda: 42)
    class Dummy: pass  # Need a dummy class/function
    
    # What users expect to write:
    # @app.factory(int)
    # def create_int():
    #     return 42
    
    try:
        value = app.resolve(int)
        print(f"✓ Factory works but syntax is weird: {value}")
    except Exception as e:
        print(f"✗ Factory failed: {e}")
    
    print("  Issue: Factory decorator API is not Pythonic")


def test_error_message_quality():
    """Issue: Error messages lack context"""
    print("\n=== Error Message Quality ===")
    
    container = Container()
    
    @component
    class ServiceA:
        def __init__(self, b: 'ServiceB', c: 'ServiceC', name: str):
            pass
    
    container.add_transient(ServiceA)
    
    try:
        service = container.resolve_sync(ServiceA)
        print("✗ Should have failed")
    except Exception as e:
        print(f"Current error: {e}")
        print("Issues with this error:")
        print("  - Doesn't say which parameters failed")
        print("  - Doesn't mention 'ServiceB' or 'ServiceC' are missing")
        print("  - Doesn't explain 'name: str' can't be auto-injected")


def test_scope_validation_timing():
    """Issue: Scope violations detected too late"""
    print("\n=== Scope Validation Timing ===")
    
    app = Whiskey()
    
    # First register scoped service
    @app.scoped("request")
    class RequestService:
        def __init__(self):
            self.id = "request-scoped"
    
    # Then register singleton that depends on it
    # This should fail at registration, not resolution
    @app.singleton
    class SingletonService:
        def __init__(self, request: RequestService):
            self.request = request
    
    print("✗ Registration succeeded (should have failed)")
    print("  Singleton depending on scoped should fail immediately")
    
    try:
        # Only fails when we try to resolve
        service = app.resolve(SingletonService)
        print("✗ Resolution succeeded (very bad!)")
    except Exception as e:
        print(f"✓ Resolution failed: {e}")
        print("  But this should have been caught at registration time")


def test_circular_dependency_detection():
    """Issue: Circular dependencies need better detection"""
    print("\n=== Circular Dependency Detection ===")
    
    # Current behavior - need to check
    container = Container()
    
    # Direct circular dependency
    class A:
        def __init__(self, b: 'B'):
            self.b = b
    
    class B:
        def __init__(self, a: A):
            self.a = a
    
    container.add_transient(A)
    container.add_transient(B)
    
    try:
        a = container.resolve_sync(A)
        print("✗ Circular dependency not detected!")
    except Exception as e:
        print(f"✓ Circular dependency caught: {type(e).__name__}")
        print(f"  Message: {e}")
        
        # Check if it's the right exception type
        from whiskey.core.errors import CircularDependencyError
        if isinstance(e, CircularDependencyError):
            print("✓ Correct exception type")
        else:
            print(f"✗ Wrong exception type: {type(e)}")


def test_generic_type_support():
    """Issue: Generic types are not properly supported"""
    print("\n=== Generic Type Support ===")
    
    from typing import Generic, TypeVar
    
    T = TypeVar('T')
    
    class Repository(Generic[T]):
        def find(self, id: int) -> T:
            pass
    
    @component
    class UserRepository(Repository[str]):  # Repository of strings for demo
        def find(self, id: int) -> str:
            return f"User{id}"
    
    @component  
    class Service:
        def __init__(self, repo: Repository[str]):
            self.repo = repo
    
    container = Container()
    container.add_transient(UserRepository)
    container.add_transient(Service)
    
    try:
        service = container.resolve_sync(Service)
        print("✗ Generic resolution worked (unexpected!)")
    except Exception as e:
        print(f"✓ Generic resolution failed as expected: {e}")
        print("  Framework doesn't understand Repository[str] -> UserRepository")


def test_initialization_lifecycle():
    """Issue: No post-construct lifecycle hooks"""
    print("\n=== Initialization Lifecycle ===")
    
    # What users want:
    @component
    class DatabaseService:
        def __init__(self, config: str = "default"):
            self.config = config
            self.connected = False
        
        async def initialize(self):
            """This should be called automatically after construction"""
            self.connected = True
            print("Connected to database")
        
        async def dispose(self):
            """This should be called on cleanup"""
            self.connected = False
            print("Disconnected from database")
    
    container = Container()
    container.add_transient(DatabaseService)
    
    service = container.resolve_sync(DatabaseService)
    print(f"Service created, connected: {service.connected}")
    print("✗ No automatic initialization - must call manually")
    print("  Framework needs lifecycle hooks")


def test_thread_safety():
    """Issue: Thread safety is not documented/guaranteed"""
    print("\n=== Thread Safety ===")
    
    import threading
    import time
    
    container = Container()
    
    creation_count = 0
    
    @singleton
    class SharedService:
        def __init__(self):
            nonlocal creation_count
            # Simulate slow initialization
            current = creation_count
            time.sleep(0.01)  # Force thread switching
            creation_count = current + 1
            self.instance_id = creation_count
    
    container.add_singleton(SharedService)
    
    instances = []
    
    def resolve_service():
        instance = container.resolve_sync(SharedService)
        instances.append(instance)
    
    # Try to create singleton from multiple threads
    threads = [threading.Thread(target=resolve_service) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    unique_instances = set(id(inst) for inst in instances)
    print(f"Created {len(unique_instances)} unique instances")
    print(f"Creation count: {creation_count}")
    
    if len(unique_instances) == 1 and creation_count == 1:
        print("✓ Singleton is thread-safe")
    else:
        print("✗ Singleton is NOT thread-safe!")
        print("  Multiple instances or multiple constructions detected")


if __name__ == "__main__":
    print("WHISKEY FRAMEWORK - FOCUSED ISSUE TESTS")
    print("=" * 50)
    
    tests = [
        test_forward_reference_issue,
        test_sync_resolve_confusion,
        test_optional_injection,
        test_factory_decorator_syntax,
        test_error_message_quality,
        test_scope_validation_timing,
        test_circular_dependency_detection,
        test_generic_type_support,
        test_initialization_lifecycle,
        test_thread_safety,
    ]
    
    for test in tests:
        try:
            test()
        except Exception as e:
            print(f"\n✗ Test {test.__name__} crashed: {e}")
    
    print("\n" + "=" * 50)
    print("Tests complete. See issues above.")