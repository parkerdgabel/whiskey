"""Working example of CLI extension with new run API."""

from whiskey import Whiskey, component, inject
from whiskey_cli import cli_extension


# Create a test service
@component
class GreetingService:
    def greet(self, name: str) -> str:
        return f"Hello, {name}!"


def main():
    # Create app and add CLI extension
    app = Whiskey()
    app.use(cli_extension)
    
    # Register commands
    @app.command()
    @app.argument("name")
    @app.option("--shout", is_flag=True, help="Shout the greeting")
    @inject
    def hello(name: str, shout: bool, service: GreetingService):
        """Greet someone by name."""
        message = service.greet(name)
        if shout:
            message = message.upper()
        print(message)
    
    @app.command()
    @inject
    async def status(service: GreetingService):
        """Show application status."""
        print("Application is running!")
        print(f"Test greeting: {service.greet('World')}")
    
    @app.command(name="app-info")
    def info():
        """Show application information."""
        print("Whiskey CLI Example")
        print("Version: 1.0.0")
    
    # Example 1: Use app.run() which will use the CLI runner
    print("=== Example 1: app.run() with sys.argv ===")
    import sys
    if len(sys.argv) > 1:
        # If run with arguments, let app.run() handle it
        app.run()
    else:
        # Otherwise show usage
        print("Usage: python working_cli_example.py [command] [args]")
        print("\nAvailable commands:")
        print("  hello NAME [--shout]  - Greet someone")
        print("  status               - Show status")
        print("  app-info            - Show app info")
        
        # Example 2: Direct CLI execution
        print("\n=== Example 2: Direct CLI execution ===")
        
        print("\n--- Running: hello Alice --shout ---")
        try:
            app.run_cli(["hello", "Alice", "--shout"])
        except SystemExit:
            pass
        
        print("\n--- Running: status ---")
        try:
            app.run_cli(["status"])
        except SystemExit:
            pass
        
        print("\n--- Running: app-info ---")
        try:
            app.run_cli(["app-info"])
        except SystemExit:
            pass
        
        # Example 3: Custom main with DI
        print("\n=== Example 3: Custom main function ===")
        
        @inject
        async def custom_main(service: GreetingService):
            print(f"Custom main says: {service.greet('Bob')}")
            return "Success"
        
        result = app.run(custom_main)
        print(f"Result: {result}")


if __name__ == "__main__":
    main()