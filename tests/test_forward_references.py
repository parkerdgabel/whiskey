#!/usr/bin/env python3
"""
Test forward reference resolution after fixes
"""

import sys
sys.path.insert(0, 'src')

from whiskey import component, singleton, inject, Whiskey


def test_simple_forward_reference():
    """Test basic forward reference resolution"""
    print("\n=== Testing Simple Forward Reference ===")
    
    app = Whiskey(name="test_forward_ref")
    
    @app.component
    class ServiceA:
        def __init__(self, b: 'ServiceB'):
            self.b = b
            print(f"ServiceA created with ServiceB: {self.b}")
    
    @app.component
    class ServiceB:
        def __init__(self):
            self.name = "I am ServiceB"
            print("ServiceB created")
    
    try:
        # This should now work!
        service_a = app.resolve(ServiceA)
        print(f"✓ SUCCESS: Forward reference resolved!")
        print(f"  ServiceA.b.name = {service_a.b.name}")
        return True
    except Exception as e:
        print(f"✗ FAILED: {type(e).__name__}: {e}")
        return False


def test_mutual_forward_references():
    """Test mutual forward references (should still fail with circular dependency)"""
    print("\n=== Testing Mutual Forward References ===")
    
    app = Whiskey(name="test_mutual")
    
    @app.component
    class ServiceX:
        def __init__(self, y: 'ServiceY'):
            self.y = y
    
    @app.component
    class ServiceY:
        def __init__(self, x: ServiceX):  # Note: not a forward ref
            self.x = x
    
    try:
        service_x = app.resolve(ServiceX)
        print(f"✗ UNEXPECTED: Circular dependency not caught!")
        return False
    except Exception as e:
        print(f"✓ Expected failure: {type(e).__name__}: {e}")
        return True


def test_forward_ref_with_namespace():
    """Test forward references in different namespace contexts"""
    print("\n=== Testing Forward Reference with Namespace ===")
    
    app = Whiskey(name="test_namespace")
    
    # Define in local scope
    @app.component
    class LocalService:
        def __init__(self):
            self.value = "local"
    
    @app.component
    class Consumer:
        def __init__(self, service: 'LocalService'):
            self.service = service
    
    try:
        consumer = app.resolve(Consumer)
        print(f"✓ SUCCESS: Local forward reference resolved!")
        print(f"  Consumer.service.value = {consumer.service.value}")
        return True
    except Exception as e:
        print(f"✗ FAILED: {type(e).__name__}: {e}")
        return False


def test_optional_forward_reference():
    """Test Optional with forward reference"""
    print("\n=== Testing Optional Forward Reference ===")
    
    from typing import Optional
    
    app = Whiskey(name="test_optional_forward")
    
    @app.component
    class OptionalService:
        def __init__(self):
            self.name = "optional"
    
    @app.component
    class ConsumerWithOptional:
        def __init__(self, 
                     required: 'OptionalService',
                     optional: Optional['OptionalService'] = None):
            self.required = required
            self.optional = optional
    
    try:
        consumer = app.resolve(ConsumerWithOptional)
        print(f"✓ SUCCESS: Optional forward reference resolved!")
        print(f"  Required: {consumer.required.name}")
        print(f"  Optional: {consumer.optional.name if consumer.optional else 'None'}")
        return True
    except Exception as e:
        print(f"✗ FAILED: {type(e).__name__}: {e}")
        return False


def test_forward_ref_not_registered():
    """Test forward reference to non-existent type"""
    print("\n=== Testing Forward Reference Not Registered ===")
    
    app = Whiskey(name="test_not_registered")
    
    @app.component
    class ServiceNeedingMissing:
        def __init__(self, missing: 'NonExistentService'):
            self.missing = missing
    
    try:
        service = app.resolve(ServiceNeedingMissing)
        print(f"✗ UNEXPECTED: Should have failed for missing service")
        return False
    except Exception as e:
        print(f"✓ Expected failure: {type(e).__name__}: {e}")
        return True


def test_complex_forward_ref_chain():
    """Test chain of forward references"""
    print("\n=== Testing Complex Forward Reference Chain ===")
    
    app = Whiskey(name="test_chain")
    
    @app.component
    class ServiceA:
        def __init__(self, b: 'ServiceB'):
            self.b = b
    
    @app.component
    class ServiceB:
        def __init__(self, c: 'ServiceC'):
            self.c = c
    
    @app.component
    class ServiceC:
        def __init__(self):
            self.name = "ServiceC"
    
    try:
        service_a = app.resolve(ServiceA)
        print(f"✓ SUCCESS: Forward reference chain resolved!")
        print(f"  A -> B -> C: {service_a.b.c.name}")
        return True
    except Exception as e:
        print(f"✗ FAILED: {type(e).__name__}: {e}")
        return False


if __name__ == "__main__":
    print("FORWARD REFERENCE RESOLUTION TESTS")
    print("=" * 50)
    
    tests = [
        test_simple_forward_reference,
        test_mutual_forward_references,
        test_forward_ref_with_namespace,
        test_optional_forward_reference,
        test_forward_ref_not_registered,
        test_complex_forward_ref_chain,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n✗ Test {test.__name__} crashed: {e}")
            failed += 1
    
    print("\n" + "=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 50)