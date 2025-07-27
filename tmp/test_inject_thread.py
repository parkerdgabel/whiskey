#!/usr/bin/env python3
"""Test @inject in different thread contexts."""

from whiskey import Whiskey, inject

app = Whiskey()

class TestService:
    def greet(self, name: str) -> str:
        return f"Hello from service, {name}!"

# Register service
app.container[TestService] = TestService()

@inject
def test_func(name: str, service: TestService):
    return service.greet(name)

print("=== Direct call ===")
try:
    result = test_func("Alice")
    print(f"Success: {result}")
except Exception as e:
    print(f"Failed: {e}")

print("\n=== Call via container.call_sync ===")
try:
    result = app.container.call_sync(test_func, "Bob")
    print(f"Success: {result}")
except Exception as e:
    print(f"Failed: {e}")
    import traceback
    traceback.print_exc()