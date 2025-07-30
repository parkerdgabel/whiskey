#!/usr/bin/env python3
"""
Test enhanced error messages after fixes
"""

import sys
sys.path.insert(0, 'src')

from whiskey import component, singleton, inject, Whiskey
from whiskey.core.errors import ParameterResolutionError, ResolutionError


def test_builtin_type_error():
    """Test error message for built-in types"""
    print("\n=== Testing Built-in Type Error Message ===")
    
    app = Whiskey(name="test_builtin_error")
    
    @app.component
    class ServiceNeedingString:
        def __init__(self, name: str, count: int):
            self.name = name
            self.count = count
    
    try:
        service = app.resolve(ServiceNeedingString)
        print("✗ FAILED: Should have raised an error")
        return False
    except ParameterResolutionError as e:
        print(f"✓ Got ParameterResolutionError as expected")
        print(f"  Error message:\n{e}")
        
        # Check that the error has helpful information
        error_str = str(e)
        if "name: str" in error_str:
            print("  ✓ Parameter name and type included")
        else:
            print("  ✗ Parameter info missing")
            
        if "Built-in type" in error_str:
            print("  ✓ Reason explained")
        else:
            print("  ✗ Reason missing")
            
        if "Hint:" in error_str:
            print("  ✓ Helpful hint provided")
        else:
            print("  ✗ Hint missing")
            
        return True
    except Exception as e:
        print(f"✗ Wrong error type: {type(e).__name__}: {e}")
        return False


def test_missing_dependency_error():
    """Test error message for missing dependencies"""
    print("\n=== Testing Missing Dependency Error Message ===")
    
    app = Whiskey(name="test_missing_dep")
    
    @app.component
    class ServiceA:
        def __init__(self, b: 'ServiceB'):
            self.b = b
    
    # Note: ServiceB is not registered
    
    try:
        service = app.resolve(ServiceA)
        print("✗ FAILED: Should have raised an error")
        return False
    except (ParameterResolutionError, ResolutionError) as e:
        print(f"✓ Got error as expected: {type(e).__name__}")
        print(f"  Error message:\n{e}")
        
        error_str = str(e)
        if "ServiceB" in error_str:
            print("  ✓ Missing type mentioned")
        else:
            print("  ✗ Missing type not mentioned")
            
        if "not registered" in error_str.lower() or "not found" in error_str.lower():
            print("  ✓ Registration issue explained")
        else:
            print("  ✗ Registration issue not explained")
            
        return True
    except Exception as e:
        print(f"✗ Wrong error type: {type(e).__name__}: {e}")
        return False


def test_multiple_unresolvable_params():
    """Test error message with multiple unresolvable parameters"""
    print("\n=== Testing Multiple Unresolvable Parameters ===")
    
    app = Whiskey(name="test_multiple_errors")
    
    @app.component
    class ComplexService:
        def __init__(self, 
                     name: str,  # Built-in
                     missing: 'MissingService',  # Not registered
                     count: int,  # Built-in
                     db: 'Database'):  # Not registered
            pass
    
    try:
        service = app.resolve(ComplexService)
        print("✗ FAILED: Should have raised an error")
        return False
    except (ParameterResolutionError, ResolutionError) as e:
        print(f"✓ Got error as expected: {type(e).__name__}")
        print(f"  Error message:\n{e}")
        
        error_str = str(e)
        # Should mention at least one of the problematic parameters
        if any(param in error_str for param in ['name', 'missing', 'count', 'db']):
            print("  ✓ Problematic parameters mentioned")
        else:
            print("  ✗ No parameters mentioned")
            
        return True
    except Exception as e:
        print(f"✗ Wrong error type: {type(e).__name__}: {e}")
        return False


def test_constructor_failure_error():
    """Test error message when constructor itself fails"""
    print("\n=== Testing Constructor Failure Error ===")
    
    app = Whiskey(name="test_constructor_fail")
    
    @app.singleton
    class ConfigService:
        def __init__(self):
            self.value = 42
    
    @app.component
    class FailingService:
        def __init__(self, config: ConfigService):
            self.config = config
            # Simulate an error in constructor
            raise ValueError("Configuration value must be 100, not 42")
    
    try:
        service = app.resolve(FailingService)
        print("✗ FAILED: Should have raised an error")
        return False
    except ResolutionError as e:
        print(f"✓ Got ResolutionError as expected")
        print(f"  Error message:\n{e}")
        
        error_str = str(e)
        if "FailingService" in error_str:
            print("  ✓ Service name mentioned")
        else:
            print("  ✗ Service name missing")
            
        if "Configuration value must be 100" in error_str:
            print("  ✓ Original error preserved")
        else:
            print("  ✗ Original error lost")
            
        return True
    except Exception as e:
        print(f"✗ Wrong error type: {type(e).__name__}: {e}")
        return False


def test_optional_type_error_clarity():
    """Test that Optional types have clear error messages"""
    print("\n=== Testing Optional Type Error Clarity ===")
    
    from typing import Optional
    
    app = Whiskey(name="test_optional_clarity")
    
    @app.component
    class ServiceWithOptional:
        def __init__(self, 
                     required_missing: 'MissingService',
                     optional_missing: Optional['MissingService'] = None):
            self.required = required_missing
            self.optional = optional_missing
    
    try:
        service = app.resolve(ServiceWithOptional)
        print("✗ FAILED: Should have raised an error for required_missing")
        return False
    except (ParameterResolutionError, ResolutionError) as e:
        print(f"✓ Got error as expected: {type(e).__name__}")
        print(f"  Error message:\n{e}")
        
        error_str = str(e)
        if "required_missing" in error_str:
            print("  ✓ Correctly identified required parameter")
        else:
            print("  ✗ Did not identify which parameter failed")
            
        # Should not complain about optional parameter
        if "optional_missing" not in error_str:
            print("  ✓ Correctly ignored optional parameter")
        else:
            print("  ✗ Incorrectly mentioned optional parameter")
            
        return True
    except Exception as e:
        print(f"✗ Wrong error type: {type(e).__name__}: {e}")
        return False


if __name__ == "__main__":
    print("ENHANCED ERROR MESSAGE TESTS")
    print("=" * 50)
    
    tests = [
        test_builtin_type_error,
        test_missing_dependency_error,
        test_multiple_unresolvable_params,
        test_constructor_failure_error,
        test_optional_type_error_clarity,
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
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 50)