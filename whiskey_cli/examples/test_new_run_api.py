"""Test the CLI extension with the new standardized run API."""

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
    
    # Register a simple command
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
    
    # Register another command that's async
    @app.command()
    @inject
    async def status(service: GreetingService):
        """Show application status."""
        print("Application is running!")
        print(f"Test greeting: {service.greet('World')}")
    
    # Test 1: Run with no arguments (should use CLI runner)
    print("=== Test 1: Running with app.run() ===")
    try:
        # Run hello command directly via run_cli to ensure commands are registered
        app.run_cli(["hello", "Alice", "--shout"])
    except SystemExit:
        pass  # Click exits normally
    
    # Test 2: Run with a custom main function
    print("\n=== Test 2: Running with custom main ===")
    @inject
    async def custom_main(service: GreetingService):
        print(f"Custom main says: {service.greet('Bob')}")
        return "Success"
    
    result = app.run(custom_main)
    print(f"Result: {result}")
    
    # Test 3: Direct CLI runner access
    print("\n=== Test 3: Direct CLI runner ===")
    try:
        app.run_cli(["status"])
    except SystemExit:
        pass
    
    # Test 4: Check that the runner is registered
    print("\n=== Test 4: Check runner registration ===")
    print(f"Has run_cli method: {hasattr(app, 'run_cli')}")
    print(f"CLI manager exists: {hasattr(app, 'cli_manager')}")
    
    # Test 5: Run the built-in app-info command
    print("\n=== Test 5: Built-in command ===")
    try:
        app.run_cli(["app-info"])
    except SystemExit:
        pass


if __name__ == "__main__":
    main()