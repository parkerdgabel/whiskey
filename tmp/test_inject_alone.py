#!/usr/bin/env python3
"""Test inject decorator behavior in isolation."""

import asyncio
from whiskey import Whiskey, inject, singleton

@singleton
class TestService:
    def greet(self, name: str) -> str:
        return f"Hello, {name}!"

app = Whiskey()

# Original function
def greet_original(name: str, service: TestService):
    print(f"Original called: {name}, {service}")
    return service.greet(name)

# After @inject decorator
@inject
def greet_injected(name: str, service: TestService):
    print(f"Injected called: {name}, {service}")
    return service.greet(name)

print("=== Testing @inject behavior ===")
print(f"Original function: {greet_original}")
print(f"Injected function: {greet_injected}")
print(f"Injected has __wrapped__: {hasattr(greet_injected, '__wrapped__')}")

# Test in event loop context
async def test_in_loop():
    print("\n=== Inside event loop ===")
    try:
        loop = asyncio.get_running_loop()
        print(f"Event loop active: {loop}")
    except RuntimeError:
        print("No event loop")
    
    # Call inject-decorated function
    print("\nCalling @inject function:")
    try:
        result = greet_injected("Alice")
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

# Run test
print("\n=== Running test ===")
asyncio.run(test_in_loop())