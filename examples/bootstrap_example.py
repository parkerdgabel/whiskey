"""Example showing different bootstrapping patterns."""

import asyncio

from whiskey import inject, singleton, standalone


# Shared services
@singleton
class DatabaseService:
    """Mock database service."""

    def __init__(self):
        self.data = {"users": [], "products": []}

    async def save(self, collection: str, item: dict) -> None:
        """Save an item to a collection."""
        self.data[collection].append(item)
        print(f"Saved to {collection}: {item}")

    async def find_all(self, collection: str) -> list[dict]:
        """Find all items in a collection."""
        return self.data[collection]


@singleton
class NotificationService:
    """Mock notification service."""

    async def send(self, message: str) -> None:
        """Send a notification."""
        print(f"📧 Notification: {message}")


# Example 1: Standalone Worker Application
async def example_standalone():
    """Example of a standalone worker application."""
    print("\n=== Standalone Worker Example ===")

    # Build a standalone application
    app = (
        standalone()
        .configure(lambda c: setattr(c, "name", "DataProcessor"))
        .service(DatabaseService, implementation=DatabaseService)
        .service(NotificationService, implementation=NotificationService)
        .setup(lambda app: print(f"Setting up {app.config.name}..."))
        .build()
    )

    # Use the application
    @inject
    async def process_data(db: DatabaseService, notify: NotificationService):
        # Process some data
        await db.save("users", {"id": 1, "name": "Alice"})
        await db.save("products", {"id": 1, "name": "Widget"})

        # Send notification
        await notify.send("Data processing complete!")

        # Show results
        users = await db.find_all("users")
        products = await db.find_all("products")
        print(f"Users: {users}")
        print(f"Products: {products}")

    # Run with the app's container as context
    async with app.lifespan():
        await process_data()


# Example 2: Web Application (using ASGI plugin)
async def example_web():
    """Example of a web application."""
    print("\n=== Web Application Example ===")

    try:
        from whiskey_asgi import Request, Response, asgi

        # Build an ASGI application
        # The asgi() builder automatically includes the ASGI extension
        web_app = (
            asgi()
            .configure(lambda c: setattr(c, "name", "WebAPI"))
            .service(DatabaseService, implementation=DatabaseService)
            .service(NotificationService, implementation=NotificationService)
        )

        @web_app.get("/users")
        @inject
        async def list_users(
            request: Request,
            response: Response,
            db: DatabaseService,
        ):
            users = await db.find_all("users")
            await response.json({"users": users})

        @web_app.post("/users")
        @inject
        async def create_user(
            request: Request,
            response: Response,
            db: DatabaseService,
            notify: NotificationService,
        ):
            data = await request.json()
            await db.save("users", data)
            await notify.send(f"New user created: {data.get('name')}")
            await response.json({"status": "created"})

        # Build the ASGI app
        asgi_app = web_app.build()
        print(f"Built ASGI app: {asgi_app}")
        print("Routes registered: /users (GET, POST)")

    except ImportError:
        print("ASGI plugin not available")


# Example 3: CLI Application (using CLI plugin)
async def example_cli():
    """Example of a CLI application."""
    print("\n=== CLI Application Example ===")

    try:
        from whiskey_cli import cli

        # Build a CLI application
        cli_app = (
            cli()
            .configure(lambda c: setattr(c, "name", "DataCLI"))
            .service(DatabaseService, implementation=DatabaseService)
        )

        @cli_app.command()
        @inject
        async def add_user(name: str, db: DatabaseService):
            """Add a new user."""
            await db.save("users", {"name": name})
            print(f"Added user: {name}")

        @cli_app.command()
        @inject
        async def list_users(db: DatabaseService):
            """List all users."""
            users = await db.find_all("users")
            for user in users:
                print(f"- {user['name']}")

        # Build the CLI
        cli_group = cli_app.build()
        print(f"Built CLI with commands: {list(cli_group.commands.keys())}")

    except ImportError:
        print("CLI plugin not available")


# Run all examples
async def main():
    """Run all bootstrap examples."""
    await example_standalone()
    await example_web()
    await example_cli()


if __name__ == "__main__":
    asyncio.run(main())
