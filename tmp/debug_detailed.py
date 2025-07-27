#!/usr/bin/env python3
"""Detailed debug of singleton registration."""

from whiskey import Whiskey, singleton
from whiskey.core.decorators import _get_default_app

# First check: what app does the singleton decorator use?
print("=== App creation check ===")
app = Whiskey()
print(f"Created app: {app}")
print(f"Default app: {_get_default_app()}")
print(f"Are they the same? {app is _get_default_app()}")

print("\n=== Before decoration ===")
print(f"App container services: {len(list(app.container.registry.list_all()))}")
print(f"Default app container services: {len(list(_get_default_app().container.registry.list_all()))}")

# Test with explicit app parameter
@singleton(app=app)
class TestService1:
    def greet(self, name: str) -> str:
        return f"Hello from Service1, {name}!"

print(f"\n=== After @singleton(app=app) ===")
print(f"App container services: {len(list(app.container.registry.list_all()))}")
print(f"Default app container services: {len(list(_get_default_app().container.registry.list_all()))}")

# Test with no app parameter (uses default)
@singleton
class TestService2:
    def greet(self, name: str) -> str:
        return f"Hello from Service2, {name}!"

print(f"\n=== After @singleton (no app param) ===")
print(f"App container services: {len(list(app.container.registry.list_all()))}")
print(f"Default app container services: {len(list(_get_default_app().container.registry.list_all()))}")

# List all services in both containers
print(f"\n=== App container services ===")
for service in app.container.registry.list_all():
    print(f"  - {service}")

print(f"\n=== Default app container services ===")
for service in _get_default_app().container.registry.list_all():
    print(f"  - {service}")

# Test resolution from both
print(f"\n=== Resolution tests ===")
try:
    service1 = app.container[TestService1]
    print(f"app.container[TestService1]: {service1}")
except Exception as e:
    print(f"app.container[TestService1] failed: {e}")

try:
    service2 = app.container[TestService2]
    print(f"app.container[TestService2]: {service2}")
except Exception as e:
    print(f"app.container[TestService2] failed: {e}")

try:
    service1_default = _get_default_app().container[TestService1]
    print(f"default_app.container[TestService1]: {service1_default}")
except Exception as e:
    print(f"default_app.container[TestService1] failed: {e}")

try:
    service2_default = _get_default_app().container[TestService2]
    print(f"default_app.container[TestService2]: {service2_default}")
except Exception as e:
    print(f"default_app.container[TestService2] failed: {e}")