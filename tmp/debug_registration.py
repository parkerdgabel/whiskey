#!/usr/bin/env python3
"""Debug service registration."""

from whiskey import Whiskey, inject, singleton

app = Whiskey()

# Check registration before and after
print("=== Before registration ===")
services = list(app.container.registry.list_all())
print(f"Registered services: {len(services)}")
for service in services:
    print(f"  - {service}")

@singleton  
class TestService:
    def greet(self, name: str) -> str:
        return f"Hello, {name}!"

print("\n=== After @singleton ===")
services = list(app.container.registry.list_all())
print(f"Registered services: {len(services)}")
for service in services:
    print(f"  - {service}")

# Manual registration
print("\n=== Manual registration ===")
app.container[TestService] = TestService()

services = list(app.container.registry.list_all())
print(f"Registered services: {len(services)}")
for service in services:
    print(f"  - {service}")

# Test inject
@inject
def test_inject(name: str, service: TestService):
    return service.greet(name)

print("\n=== Testing inject ===")
try:
    result = test_inject("Test")
    print(f"Inject result: {result}")
except Exception as e:
    print(f"Inject failed: {e}")