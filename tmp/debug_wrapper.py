#!/usr/bin/env python3
"""Debug what function is being called."""

from whiskey import Whiskey, inject, singleton
from whiskey_cli import cli_extension

@singleton
class TestService:
    def greet(self, name: str) -> str:
        return f"Hello, {name}!"

app = Whiskey()
app.use(cli_extension)

@app.command()
@inject
def greet_service(name: str, service: TestService):
    """Test command with DI."""
    message = service.greet(name)
    print(message)

# Analyze the registered command
print("=== Analyzing registered command ===")
# After using the CLI extension, commands are stored in pending
print(f"Pending commands: {app.cli_manager.pending_commands}")

# Finalize to see what gets registered
app.cli_manager.finalize_pending()

# Check the actual command callback
for cmd_name, cmd in app.cli.commands.items():
    print(f"\nCommand: {cmd_name}")
    print(f"Callback: {cmd.callback}")
    print(f"Callback is wrapper: {cmd.callback.__name__ == 'wrapped_callback'}")
    
    # The wrapped_callback should have reference to original
    if hasattr(cmd.callback, '__closure__'):
        print("Checking closure...")
        # Look for original_callback in closure
        
# Actually, let's trace what the inject decorator produces
print("\n=== What @inject produces ===")
original_greet = greet_service.__wrapped__  # Get the original function
print(f"Original function: {original_greet}")
print(f"Injected function: {greet_service}")
print(f"Injected is sync_wrapper: {'sync_wrapper' in str(greet_service)}")

# When the CLI wrapper checks hasattr(original_callback, "__wrapped__")
# original_callback is the @inject decorated function
# So original_callback.__wrapped__ gives us the ORIGINAL function without injection!