"""Example demonstrating the standardized run API for Whiskey applications."""

import asyncio
from typing import Annotated

from whiskey import Whiskey, component, inject, Inject


# Sample services
@component
class Database:
    def __init__(self):
        self.connected = False
    
    async def connect(self):
        print("Connecting to database...")
        await asyncio.sleep(0.1)
        self.connected = True
        print("Database connected!")
    
    async def disconnect(self):
        print("Disconnecting from database...")
        self.connected = False


@component
class UserService:
    def __init__(self, db: Database):
        self.db = db
    
    async def get_user(self, user_id: int):
        # Ensure database is connected
        if not self.db.connected:
            await self.db.connect()
        return {"id": user_id, "name": f"User {user_id}"}


# Example 1: Simple synchronous function
def example_sync():
    app = Whiskey()
    
    def main():
        print("Hello from sync main!")
        return 42
    
    result = app.run(main)
    print(f"Result: {result}")


# Example 2: Async function with dependency injection
def example_async_with_di():
    app = Whiskey()
    
    @inject
    async def main(db: Database, user_service: UserService):
        await db.connect()
        user = await user_service.get_user(123)
        print(f"Retrieved user: {user}")
        await db.disconnect()
        return user
    
    result = app.run(main)
    print(f"Final result: {result}")


# Example 3: Extension-style runner
def example_extension_runner():
    """Demonstrate how extensions register custom runners."""
    
    app = Whiskey()
    
    # Simulate what an extension would do
    def cli_runner(**kwargs):
        """Custom CLI runner."""
        print("Running CLI application...")
        print(f"CLI args: {kwargs}")
        # CLI logic here
        return 0
    
    # Register the runner
    app.register_runner("cli", cli_runner)
    
    # Now app.run() without args will use the CLI runner
    exit_code = app.run(verbose=True, command="hello")
    print(f"CLI exit code: {exit_code}")


# Example 4: Long-running application
def example_long_running():
    """Example of a long-running application with background tasks."""
    
    app = Whiskey()
    
    @app.on_startup
    async def startup():
        print("Application starting up...")
    
    @app.on_shutdown
    async def shutdown():
        print("Application shutting down...")
    
    @app.task(interval=2.0)
    async def background_task():
        print("Background task running...")
    
    # Run without main - just lifecycle
    print("Running application (press Ctrl+C to stop)...")
    try:
        app.run()  # Will run until interrupted
    except KeyboardInterrupt:
        print("\nShutdown requested")


# Example 5: Using lifespan context manager
def example_lifespan():
    """Example using the lifespan context manager."""
    
    app = Whiskey()
    
    @app.on_startup
    async def setup():
        print("Setting up resources...")
    
    @app.on_shutdown
    async def cleanup():
        print("Cleaning up resources...")
    
    # Async context
    async def async_work():
        async with app.lifespan:
            db = await app.resolve_async(Database)
            await db.connect()
            print("Doing async work...")
            await db.disconnect()
    
    # Run the async work
    asyncio.run(async_work())
    
    # Sync context (when no event loop is running)
    with app.lifespan:
        print("Doing sync work...")
        # Sync operations here


# Example 6: How extensions should implement runners
class MockCLIExtension:
    """Example of how CLI extension would use the standardized API."""
    
    @staticmethod
    def cli_extension(app: Whiskey):
        """Configure CLI functionality."""
        
        # Add CLI-specific functionality
        def run_cli(**kwargs):
            """Run the CLI application."""
            import sys
            
            print(f"CLI starting with args: {sys.argv[1:]}")
            
            # In real implementation, would parse args and dispatch to commands
            # For now, just simulate
            async def cli_main():
                async with app.lifespan:
                    # Execute CLI commands with DI
                    print("Executing CLI command...")
                    return 0
            
            return asyncio.run(cli_main())
        
        # Register the runner
        app.register_runner("cli", run_cli)
        
        # Also make it available as a method
        app.run_cli = run_cli


class MockASGIExtension:
    """Example of how ASGI extension would use the standardized API."""
    
    @staticmethod  
    def asgi_extension(app: Whiskey):
        """Configure ASGI functionality."""
        
        # Create ASGI handler
        async def asgi_handler(scope, receive, send):
            # ASGI implementation
            pass
        
        app.asgi = asgi_handler
        
        # Add runner
        def run_asgi(host="127.0.0.1", port=8000, **kwargs):
            """Run the ASGI server."""
            print(f"Starting ASGI server on {host}:{port}")
            
            # In real implementation, would use uvicorn
            # For now, just simulate
            async def server_main():
                async with app.lifespan:
                    print("ASGI server running...")
                    # Simulate server running
                    await asyncio.sleep(2)
                    print("ASGI server stopped")
            
            return asyncio.run(server_main())
        
        # Register the runner
        app.register_runner("asgi", run_asgi)
        
        # Also make it available as a method
        app.run_asgi = run_asgi


# Example 7: Using multiple extensions
def example_multiple_extensions():
    """Example with multiple extensions that provide runners."""
    
    app = Whiskey()
    
    # Apply extensions
    MockCLIExtension.cli_extension(app)
    MockASGIExtension.asgi_extension(app)
    
    # Now app.run() will use the first registered runner (CLI)
    print("Running with auto-detected runner:")
    app.run()
    
    # Or explicitly run a specific runner
    print("\nRunning ASGI server:")
    app.run_asgi(port=3000)


if __name__ == "__main__":
    print("=== Example 1: Sync Function ===")
    example_sync()
    
    print("\n=== Example 2: Async with DI ===")
    example_async_with_di()
    
    print("\n=== Example 3: Extension Runner ===")
    example_extension_runner()
    
    print("\n=== Example 5: Lifespan Context ===")
    example_lifespan()
    
    print("\n=== Example 7: Multiple Extensions ===")
    example_multiple_extensions()
    
    # Uncomment to run long-running example
    # print("\n=== Example 4: Long Running App ===")
    # example_long_running()