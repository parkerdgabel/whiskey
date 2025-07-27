#!/usr/bin/env python3
"""Debug option handling in CLI extension."""

from whiskey import Whiskey
from whiskey_cli import cli_extension
from click.testing import CliRunner

app = Whiskey()
app.use(cli_extension)

print("=== Before decorators ===")
print(f"Pending commands: {list(app.cli_manager.pending_commands.keys())}")

@app.command()
def test_no_options():
    """Test without options."""
    print("No options")

print(f"After @app.command(): {list(app.cli_manager.pending_commands.keys())}")

@app.option("--count", default=1, help="Number of greetings")
def test_no_options_decorated():
    """Test with option but no command."""
    pass

print(f"After @app.option(): {list(app.cli_manager.pending_commands.keys())}")

# Now let's try the proper order
@app.command()
@app.option("--verbose", is_flag=True)
def test_with_option():
    """Test with option."""
    import click
    ctx = click.get_current_context()
    verbose = ctx.params.get('verbose', False)
    print(f"Verbose: {verbose}")

print(f"After command with option: {list(app.cli_manager.pending_commands.keys())}")

# Check what's in the metadata
for name, metadata in app.cli_manager.pending_commands.items():
    print(f"\nCommand {name}:")
    print(f"  Arguments: {metadata.arguments}")
    print(f"  Options: {metadata.options}")

# Test it
runner = CliRunner()
print(f"\n=== Test no options ===")
result = runner.invoke(app.cli, ["test-no-options"])
print(f"Exit code: {result.exit_code}")
print(f"Output: {result.output}")

print(f"\n=== Test with option (no flag) ===")
result = runner.invoke(app.cli, ["test-with-option"])
print(f"Exit code: {result.exit_code}")
print(f"Output: {result.output}")

print(f"\n=== Test with option (with flag) ===")
result = runner.invoke(app.cli, ["test-with-option", "--verbose"])
print(f"Exit code: {result.exit_code}")
print(f"Output: {result.output}")