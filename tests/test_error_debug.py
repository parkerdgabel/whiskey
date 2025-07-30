#!/usr/bin/env python3
"""
Debug error handling
"""

import sys
sys.path.insert(0, 'src')

from whiskey import Whiskey


def test_simple_builtin_error():
    """Test simple builtin type error"""
    print("\n=== Debug Built-in Type Error ===")
    
    app = Whiskey(name="debug_test")
    
    @app.component
    class SimpleService:
        def __init__(self, name: str):
            self.name = name
    
    # First check what the analyzer says
    from whiskey.core.analyzer import TypeAnalyzer
    analyzer = TypeAnalyzer(app.container.registry)
    results = analyzer.analyze_callable(SimpleService.__init__)
    print("Analyzer results for SimpleService:")
    for param_name, result in results.items():
        print(f"  {param_name}: decision={result.decision.value}, reason={result.reason}")
    
    try:
        service = app.resolve(SimpleService)
        print("✗ Should have failed")
    except Exception as e:
        print(f"\nException type: {type(e).__name__}")
        print(f"Exception message: {e}")
        print(f"Exception args: {e.args}")
        
        # Check the cause chain
        if hasattr(e, '__cause__'):
            print(f"Caused by: {type(e.__cause__).__name__}: {e.__cause__}")


def test_component_creation_flow():
    """Test component creation flow"""
    print("\n=== Debug Component Creation Flow ===")
    
    from whiskey.core.container import Container
    from whiskey.core.analyzer import TypeAnalyzer
    
    container = Container()
    
    class TestService:
        def __init__(self, name: str):
            self.name = name
    
    # Register it
    container.register(TestService, TestService)
    
    # Get analyzer results
    analyzer = container.analyzer
    results = analyzer.analyze_callable(TestService.__init__)
    
    print("Analyzer results:")
    for param_name, result in results.items():
        print(f"  {param_name}: decision={result.decision.value}, reason={result.reason}")
    
    # Now try to resolve
    try:
        service = container.resolve_sync(TestService)
        print("✗ Should have failed")
    except Exception as e:
        print(f"\nException: {type(e).__name__}: {e}")


if __name__ == "__main__":
    test_simple_builtin_error()
    test_component_creation_flow()