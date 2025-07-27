#!/usr/bin/env python3
"""Debug CLI callback handling."""

from whiskey import Whiskey, inject
from whiskey_cli import cli_extension

app = Whiskey()
app.use(cli_extension)

class GreetingService:
    def greet(self, name: str) -> str:
        return f"Greetings, {name}!"

app.container[GreetingService] = GreetingService()

# First, let's see what the original function looks like
def original_greet(name: str, service: GreetingService):
    """Original function."""
    message = service.greet(name)
    print(f"Original: {message}")

print("=== Original function ===")
print(f"Function: {original_greet}")
print(f"Has __wrapped__: {hasattr(original_greet, '__wrapped__')}")

# Now let's apply @inject
@inject
def inject_greet(name: str, service: GreetingService):
    """Inject decorated function."""
    message = service.greet(name)
    print(f"Inject: {message}")

print(f"\n=== @inject decorated function ===")
print(f"Function: {inject_greet}")
print(f"Has __wrapped__: {hasattr(inject_greet, '__wrapped__')}")
if hasattr(inject_greet, '__wrapped__'):
    print(f"__wrapped__: {inject_greet.__wrapped__}")

# Now let's apply both
@app.command()
@inject
def command_greet(name: str, service: GreetingService):
    """Command + inject decorated function."""
    message = service.greet(name)
    print(f"Command: {message}")

print(f"\n=== @app.command() + @inject decorated function ===")
print(f"Function: {command_greet}")
print(f"Has __wrapped__: {hasattr(command_greet, '__wrapped__')}")
if hasattr(command_greet, '__wrapped__'):
    print(f"__wrapped__: {command_greet.__wrapped__}")

# Check what's in the CLI manager
print(f"\n=== CLI manager pending commands ===")
for name, metadata in app.cli_manager.pending_commands.items():
    print(f"Command {name}:")
    print(f"  func: {metadata.func}")
    print(f"  Has __wrapped__: {hasattr(metadata.func, '__wrapped__')}")
    if hasattr(metadata.func, '__wrapped__'):
        print(f"  __wrapped__: {metadata.func.__wrapped__}")

# Test direct calls
print(f"\n=== Test direct calls ===")
try:
    # This should fail - inject_greet needs container
    inject_greet("Alice")
except Exception as e:
    print(f"inject_greet('Alice') failed: {e}")

try:
    # This should work - container handles injection
    result = app.container.call_sync(inject_greet, "Bob")
    print(f"app.container.call_sync(inject_greet, 'Bob') succeeded")
except Exception as e:
    print(f"app.container.call_sync(inject_greet, 'Bob') failed: {e}")

# What if we call the wrapped function?
if hasattr(inject_greet, '__wrapped__'):
    try:
        result = app.container.call_sync(inject_greet.__wrapped__, "Carol")
        print(f"app.container.call_sync(inject_greet.__wrapped__, 'Carol') succeeded")
    except Exception as e:
        print(f"app.container.call_sync(inject_greet.__wrapped__, 'Carol') failed: {e}")