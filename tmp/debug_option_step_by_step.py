#!/usr/bin/env python3
"""Debug option decorator step by step."""

from whiskey import Whiskey
from whiskey_cli import cli_extension

app = Whiskey()
app.use(cli_extension)

# Step 1: Just the command
def greet_func():
    """Greet with options."""
    print("Hello!")

print("=== Step 1: Raw function ===")
print(f"hasattr(_cli_metadata): {hasattr(greet_func, '_cli_metadata')}")

# Step 2: Apply @app.command()
decorated_func = app.command()(greet_func)

print(f"\n=== Step 2: After @app.command() ===")
print(f"hasattr(_cli_metadata): {hasattr(decorated_func, '_cli_metadata')}")
print(f"hasattr(_cli_pending_name): {hasattr(decorated_func, '_cli_pending_name')}")
if hasattr(decorated_func, '_cli_metadata'):
    print(f"Metadata options: {decorated_func._cli_metadata.options}")

# Step 3: Apply @app.option()
option_decorated = app.option("--count", default=1)(decorated_func)

print(f"\n=== Step 3: After @app.option() ===")
print(f"Same function? {option_decorated is decorated_func}")
print(f"hasattr(_cli_metadata): {hasattr(option_decorated, '_cli_metadata')}")
if hasattr(option_decorated, '_cli_metadata'):
    print(f"Metadata options: {option_decorated._cli_metadata.options}")

# Check pending commands
cmd_name = getattr(option_decorated, '_cli_pending_name', 'greet-func')
print(f"\nPending command '{cmd_name}': {cmd_name in app.cli_manager.pending_commands}")
if cmd_name in app.cli_manager.pending_commands:
    metadata = app.cli_manager.pending_commands[cmd_name]
    print(f"Pending metadata options: {metadata.options}")
    
# Now test the multi-decorator syntax
print(f"\n=== Multi-decorator syntax ===")

@app.option("--name", default="World")
@app.command()
def test_multi():
    """Test multi decorator."""
    pass

print(f"test_multi metadata: {getattr(test_multi, '_cli_metadata', None)}")
if hasattr(test_multi, '_cli_metadata'):
    print(f"Options: {test_multi._cli_metadata.options}")