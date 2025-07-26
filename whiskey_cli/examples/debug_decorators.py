"""Debug decorator ordering."""

from whiskey import Whiskey, inject
from whiskey_cli import cli_extension


def main():
    # Create app and add CLI extension
    app = Whiskey()
    app.use(cli_extension)
    
    # Test decorator ordering
    print("=== Registering command ===")
    
    @app.command()
    @app.argument("name")
    @app.option("--shout", is_flag=True, help="Shout the greeting")
    def hello(name: str, shout: bool):
        """Greet someone by name."""
        message = f"Hello, {name}!"
        if shout:
            message = message.upper()
        print(message)
    
    print(f"Command registered: {hello}")
    print(f"Has _cli_metadata: {hasattr(hello, '_cli_metadata')}")
    if hasattr(hello, '_cli_metadata'):
        metadata = hello._cli_metadata
        print(f"  Name: {metadata.name}")
        print(f"  Arguments: {metadata.arguments}")
        print(f"  Options: {metadata.options}")
    
    # Check what's in pending
    print(f"\nPending commands: {app.cli_manager.pending_commands}")
    
    # Try to run it
    print("\n=== Running command ===")
    try:
        app.run_cli(["hello", "World", "--shout"])
    except SystemExit as e:
        print(f"Exit code: {e.code}")


if __name__ == "__main__":
    main()