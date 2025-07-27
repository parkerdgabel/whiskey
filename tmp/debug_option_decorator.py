#!/usr/bin/env python3
"""Debug option decorator logic."""

from whiskey import Whiskey
from whiskey_cli import cli_extension

app = Whiskey()
app.use(cli_extension)

# Test the flow
@app.command()
def test_func():
    """Test function."""
    print("Test")

print("After @app.command():")
print(f"  hasattr(_cli_metadata): {hasattr(test_func, '_cli_metadata')}")
print(f"  hasattr(_cli_pending_name): {hasattr(test_func, '_cli_pending_name')}")
if hasattr(test_func, '_cli_pending_name'):
    print(f"  _cli_pending_name: {test_func._cli_pending_name}")
if hasattr(test_func, '_cli_metadata'):
    print(f"  _cli_metadata: {test_func._cli_metadata}")

# Check what happens when we apply the option decorator
print(f"\nBefore option: metadata.options = {test_func._cli_metadata.options}")

# Apply option decorator manually to see what happens
option_decorator = app.option("--verbose", is_flag=True)
test_func_decorated = option_decorator(test_func)

print(f"After option: metadata.options = {test_func._cli_metadata.options}")
print(f"Same function? {test_func is test_func_decorated}")

# Check the command in pending
cmd_name = test_func._cli_pending_name
if cmd_name in app.cli_manager.pending_commands:
    metadata = app.cli_manager.pending_commands[cmd_name]
    print(f"Pending command metadata options: {metadata.options}")
else:
    print("Command not found in pending!")