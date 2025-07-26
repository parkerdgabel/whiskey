"""Debug CLI command registration."""

from whiskey import Whiskey
from whiskey_cli import cli_extension


def main():
    # Create app and add CLI extension
    app = Whiskey()
    app.use(cli_extension)
    
    # Register a simple command
    @app.command()
    def hello():
        """Say hello."""
        print("Hello, World!")
    
    # Check what's registered
    print("CLI Manager:", hasattr(app, 'cli_manager'))
    if hasattr(app, 'cli_manager'):
        print("CLI Group:", app.cli_manager.cli_group)
        print("Commands:", app.cli_manager.cli_group.commands)
        print("Pending commands:", getattr(app, '_pending_commands', {}))
    
    # Try to list commands
    try:
        app.run_cli(["--help"])
    except SystemExit:
        pass
    
    print("\n--- After help ---")
    if hasattr(app, 'cli_manager'):
        print("Commands:", app.cli_manager.cli_group.commands)


if __name__ == "__main__":
    main()