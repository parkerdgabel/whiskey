#!/usr/bin/env python3
"""Test container state across threads."""

import asyncio
import concurrent.futures
from whiskey import Whiskey, inject, singleton

@singleton
class TestService:
    def greet(self, name: str) -> str:
        return f"Hello, {name}!"

app = Whiskey()

# Register service
print("Registering service...")
print(f"Container: {app.container}")
print(f"Container registry: {app.container.registry}")

# Test without threads
print("\n=== Direct call ===")
try:
    service = app.container[TestService]
    print(f"Direct resolution worked: {service}")
except Exception as e:
    print(f"Direct resolution failed: {e}")

# Test with thread
print("\n=== Thread call ===")
def test_in_thread():
    print(f"In thread - Container: {app.container}")
    try:
        service = app.container[TestService]
        print(f"Thread resolution worked: {service}")
        return service
    except Exception as e:
        print(f"Thread resolution failed: {e}")
        import traceback
        traceback.print_exc()
        return None

with concurrent.futures.ThreadPoolExecutor() as executor:
    future = executor.submit(test_in_thread)
    result = future.result()
    print(f"Thread result: {result}")

# Test inject in different contexts
@inject
def test_inject(name: str, service: TestService):
    return service.greet(name)

print("\n=== Direct inject call ===")
try:
    result = test_inject("Alice")
    print(f"Direct inject worked: {result}")
except Exception as e:
    print(f"Direct inject failed: {e}")
    import traceback
    traceback.print_exc()

print("\n=== Async context inject call ===")
async def test_async():
    try:
        result = test_inject("Bob") 
        print(f"Async inject worked: {result}")
    except Exception as e:
        print(f"Async inject failed: {e}")
        import traceback
        traceback.print_exc()

asyncio.run(test_async())