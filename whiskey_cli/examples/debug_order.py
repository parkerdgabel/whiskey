"""Debug decorator application order."""

from whiskey import Whiskey
from whiskey_cli import cli_extension


def main():
    # Create app and add CLI extension
    app = Whiskey()
    app.use(cli_extension)
    
    print("=== Testing decorator order ===")
    
    # Step by step decoration
    def hello(name: str, shout: bool):
        """Greet someone by name."""
        message = f"Hello, {name}!"
        if shout:
            message = message.upper()
        print(message)
    
    print(f"1. Original function: {hello}")
    
    # Apply @command first
    hello = app.command()(hello)
    print(f"2. After @command: {hello}")
    print(f"   Has _cli_metadata: {hasattr(hello, '_cli_metadata')}")
    print(f"   Has _cli_pending_name: {hasattr(hello, '_cli_pending_name')}")
    if hasattr(hello, '_cli_pending_name'):
        print(f"   Pending name: {hello._cli_pending_name}")
        print(f"   In pending: {'hello' in app.cli_manager.pending_commands}")
        if 'hello' in app.cli_manager.pending_commands:
            metadata = app.cli_manager.pending_commands['hello']
            print(f"   Metadata args: {metadata.arguments}")
            print(f"   Metadata opts: {metadata.options}")
    
    # Apply @argument
    hello = app.argument("name")(hello)
    print(f"\n3. After @argument: {hello}")
    if 'hello' in app.cli_manager.pending_commands:
        metadata = app.cli_manager.pending_commands['hello']
        print(f"   Metadata args: {metadata.arguments}")
        print(f"   Metadata opts: {metadata.options}")
    
    # Apply @option
    hello = app.option("--shout", is_flag=True)(hello)
    print(f"\n4. After @option: {hello}")
    if 'hello' in app.cli_manager.pending_commands:
        metadata = app.cli_manager.pending_commands['hello']
        print(f"   Metadata args: {metadata.arguments}")
        print(f"   Metadata opts: {metadata.options}")


if __name__ == "__main__":
    main()