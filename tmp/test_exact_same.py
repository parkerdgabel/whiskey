#!/usr/bin/env python3
"""Test the exact same scenario as the failing test."""

from whiskey import Whiskey, inject
from whiskey_cli import cli_extension
from click.testing import CliRunner

# Exact same setup as test
app = Whiskey()
app.use(cli_extension)

class GreetingService:
    def greet(self, name: str) -> str:
        return f"Greetings, {name}!"

app.container[GreetingService] = GreetingService()

@app.command()
@inject
def greet(name: str, service: GreetingService):
    """Greet with service."""
    message = service.greet(name)
    print(message)

# Debug what we have
print("=== Debug command setup ===")
print(f"Function: {greet}")
print(f"Has __wrapped__: {hasattr(greet, '__wrapped__')}")

# Check pending commands
app.cli_manager.finalize_pending()
print(f"Commands in CLI: {list(app.cli.commands.keys())}")

# Let's manually test the wrapped callback
if 'greet' in app.cli.commands:
    cmd = app.cli.commands['greet']
    print(f"Command callback: {cmd.callback}")
    
    # Try calling the callback directly
    print("\n=== Manual callback test ===")
    try:
        result = cmd.callback("TestUser")
        print(f"Manual callback success: {result}")
    except Exception as e:
        print(f"Manual callback failed: {e}")
        import traceback
        traceback.print_exc()

# Now test via runner
print(f"\n=== CliRunner test ===")
runner = CliRunner()
result = runner.invoke(app.cli, ["greet", "Bob"])
print(f"Exit code: {result.exit_code}")
print(f"Output: {result.output}")
if result.exception:
    print(f"Exception: {result.exception}")
    import traceback
    traceback.print_exception(type(result.exception), result.exception, result.exception.__traceback__)