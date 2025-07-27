#!/usr/bin/env python3
"""Debug script to trace DI execution flow."""

import asyncio
from whiskey import Whiskey, inject, singleton
from whiskey_cli import cli_extension


# Service
@singleton
class TestService:
    def __init__(self):
        print("TestService.__init__ called")
    
    def greet(self, name: str) -> str:
        return f"Hello, {name}!"


# Create app
app = Whiskey()
app.use(cli_extension)


# Command with injection
@app.command()
@inject
def greet(name: str, service: TestService):
    """Test command with DI."""
    print(f"greet() called with name={name}")
    print(f"service type: {type(service)}")
    message = service.greet(name)
    print(message)


# Let's trace what happens
print("=== Analyzing the decorated function ===")
print(f"greet function: {greet}")
print(f"Has __wrapped__: {hasattr(greet, '__wrapped__')}")
if hasattr(greet, '__wrapped__'):
    print(f"__wrapped__ is: {greet.__wrapped__}")
    print(f"__wrapped__ is coroutine function: {asyncio.iscoroutinefunction(greet.__wrapped__)}")

# Check what inject decorator does
print("\n=== Testing inject decorator behavior ===")

# Test 1: Call the inject-wrapped function directly
print("\nTest 1: Direct call to @inject function")
try:
    result = greet("Bob")
    print(f"Direct call result: {result}")
except Exception as e:
    print(f"Direct call failed: {type(e).__name__}: {e}")

# Test 2: Check container behavior
print("\n=== Container behavior ===")
print(f"Container type: {type(app.container)}")
print(f"Container.call is async: {asyncio.iscoroutinefunction(app.container.call)}")
print(f"Container.call_sync exists: {hasattr(app.container, 'call_sync')}")

# Test 3: Try container.call_sync directly
print("\nTest 3: Direct container.call_sync")
try:
    result = app.container.call_sync(greet.__wrapped__, "Charlie")
    print(f"container.call_sync result: {result}")
except Exception as e:
    print(f"container.call_sync failed: {type(e).__name__}: {e}")

# Test 4: Check event loop status
print("\n=== Event loop status ===")
try:
    loop = asyncio.get_running_loop()
    print(f"Running event loop found: {loop}")
except RuntimeError:
    print("No running event loop")

# Test 5: Manually test the CLI callback wrapper logic
print("\n=== Testing CLI wrapper logic ===")
# This simulates what happens in the CLI extension's wrapped_callback
if hasattr(greet, "__wrapped__"):
    unwrapped = greet.__wrapped__
    print(f"Unwrapped function: {unwrapped}")
    print(f"Is coroutine function: {asyncio.iscoroutinefunction(unwrapped)}")
    
    # This is what the CLI wrapper tries to do
    if asyncio.iscoroutinefunction(unwrapped):
        print("Would call: asyncio.run(container.call(unwrapped, *args, **kwargs))")
    else:
        print("Would call: container.call_sync(unwrapped, *args, **kwargs)")
        # Let's trace what container.call returns
        print("\nChecking what container.call returns for sync function:")
        call_result = app.container.call(unwrapped, "Dave")
        print(f"container.call returned: {call_result}")
        print(f"Is coroutine: {asyncio.iscoroutine(call_result)}")
        
        if asyncio.iscoroutine(call_result):
            print("This is the problem! container.call returns a coroutine even for sync functions")