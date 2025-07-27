#!/usr/bin/env python3
"""Debug decorator application order."""

from whiskey import Whiskey
from whiskey_cli import cli_extension
from click.testing import CliRunner

app = Whiskey()
app.use(cli_extension)

# Test exact same pattern as in my failing test
@app.command()
@app.option("--count", default=1, help="Number of greetings")
@app.option("--name", default="World", help="Name to greet")
def greet():
    """Greet with options."""
    import click
    count = click.get_current_context().params['count']
    name = click.get_current_context().params['name']
    for _ in range(count):
        print(f"Hello, {name}!")

# Check the metadata
print("Command metadata:")
print(f"  Arguments: {greet._cli_metadata.arguments}")
print(f"  Options: {greet._cli_metadata.options}")

# Check pending commands
cmd_name = greet._cli_pending_name
if cmd_name in app.cli_manager.pending_commands:
    metadata = app.cli_manager.pending_commands[cmd_name]
    print(f"\nPending metadata:")
    print(f"  Arguments: {metadata.arguments}")
    print(f"  Options: {metadata.options}")

# Test it
runner = CliRunner()
print(f"\n=== Test with defaults ===")
result = runner.invoke(app.cli, ["greet"])
print(f"Exit code: {result.exit_code}")
print(f"Output: {result.output}")

print(f"\n=== Test with options ===")
result = runner.invoke(app.cli, ["greet", "--count", "2", "--name", "Alice"])
print(f"Exit code: {result.exit_code}")
print(f"Output: {result.output}")

# Debug help
print(f"\n=== Help ===")
result = runner.invoke(app.cli, ["greet", "--help"])
print(f"Exit code: {result.exit_code}")
print(f"Output: {result.output}")