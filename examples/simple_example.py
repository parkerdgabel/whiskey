"""Simple example demonstrating Whiskey's core dependency injection features.

This example shows:
- Basic service registration with @provide and @singleton decorators
- Automatic dependency injection with @inject
- Manual container usage with dict-like API
- Factory functions for complex initialization

Run this example:
    python examples/simple_example.py
"""

import asyncio

from whiskey import Container, inject, provide, singleton

# Step 1: Define your services
# =============================


@singleton  # This decorator ensures only one instance exists
class Database:
    """A mock database service.

    In a real application, this would connect to an actual database.
    The @singleton decorator ensures we reuse the same connection.
    """

    def __init__(self):
        # Expensive initialization happens only once
        self.connection = "Connected to DB"
        print("🗄️  Database initialized (singleton - only once!)")

    async def query(self, sql: str) -> list[dict]:
        """Execute a database query."""
        print(f"📊 Executing: {sql}")
        # Mock data - in reality this would query the database
        return [{"id": 1, "name": "Alice", "email": "alice@example.com"}]


@provide  # This decorator registers the class with the default container
class UserService:
    """Service for user-related operations.

    Whiskey automatically injects any type-hinted parameters
    that aren't built-in types and don't have defaults.
    """

    def __init__(self, db: Database):
        # Whiskey automatically injects the Database instance
        self.db = db
        print("👤 UserService initialized")

    async def get_user(self, user_id: int) -> dict | None:
        """Fetch a user by ID."""
        users = await self.db.query(f"SELECT * FROM users WHERE id = {user_id}")
        return users[0] if users else None

    async def get_all_users(self) -> list[dict]:
        """Fetch all users."""
        return await self.db.query("SELECT * FROM users")


# Step 2: Use dependency injection in functions
# =============================================


@inject
async def process_user(
    user_id: int,  # Built-in type - not injected
    user_service: UserService,  # Custom type - automatically injected!
) -> dict | None:
    """Process a user with automatic dependency injection.

    The @inject decorator analyzes the function signature and automatically
    injects any custom types while leaving built-in types for manual passing.
    """
    user = await user_service.get_user(user_id)
    if user:
        print(f"✅ Processing user: {user['name']} ({user['email']})")
        # Perform some business logic here...
        return user
    else:
        print(f"❌ User {user_id} not found")
        return None


async def main():
    """Demonstrate different ways to use Whiskey's DI."""

    # Example 1: Using decorators with the default container
    # ======================================================
    print("\n🚀 Example 1: Default Container with Decorators")
    print("=" * 50)

    # The @provide and @singleton decorators already registered our services
    # The @inject decorator will automatically resolve dependencies
    result = await process_user(1)
    print(f"Result: {result}")

    # Call again to see singleton behavior
    print("\nCalling again (note: Database NOT re-initialized)...")
    result2 = await process_user(1)

    # Example 2: Using explicit container with dict-like API
    # ======================================================
    print("\n\n🎯 Example 2: Explicit Container with Dict-like API")
    print("=" * 50)

    # Create a fresh container (independent of the default one)
    container = Container()

    # Register services using dict-like syntax - it's just Python!
    container[Database] = Database  # Register the class (will be instantiated)
    container[UserService] = UserService  # Whiskey handles dependency injection

    # Manually resolve and use services
    user_service = await container.resolve(UserService)
    user = await user_service.get_user(1)
    print(f"Found user: {user}")

    # Check if a service is registered
    if Database in container:
        print("✓ Database is registered in the container")

    # Example 3: Using factory functions for complex initialization
    # ============================================================
    print("\n\n🏭 Example 3: Factory Functions")
    print("=" * 50)

    container = Container()

    # Use a factory when you need custom initialization logic
    def create_database() -> Database:
        """Factory function for creating Database instances.

        Useful when you need:
        - Configuration from environment
        - Complex initialization
        - Different implementations based on conditions
        """
        import os

        db = Database()
        # Custom initialization based on environment
        if os.getenv("ENV") == "production":
            db.connection = "Production DB Connection"
        else:
            db.connection = "Development DB Connection"
        return db

    # Register the factory function (not the class!)
    container[Database] = create_database
    container[UserService] = UserService

    # The factory will be called when Database is needed
    service = await container.resolve(UserService)
    print(f"DB connection: {service.db.connection}")

    # Example 4: Demonstrating scope behavior
    # =======================================
    print("\n\n🔄 Example 4: Scope Behavior")
    print("=" * 50)

    # Singleton scope - same instance always
    db1 = await container.resolve(Database)
    db2 = await container.resolve(Database)
    print(f"Singleton instances are same: {db1 is db2}")

    # The UserService is transient (default) - new instance each time
    us1 = await container.resolve(UserService)
    us2 = await container.resolve(UserService)
    print(f"Transient instances are same: {us1 is us2}")


# Step 3: Run the examples
# ========================

if __name__ == "__main__":
    print("🥃 Whiskey Simple Example")
    print("========================\n")
    print("This example demonstrates:")
    print("- Service registration with decorators")
    print("- Automatic dependency injection")
    print("- Container dict-like API")
    print("- Factory functions")
    print("- Singleton vs transient scopes")

    asyncio.run(main())

    print("\n✨ Example completed!")
    print("\nNext steps:")
    print("- Check out 'application_example.py' for lifecycle management")
    print("- See 'discovery_example.py' for auto-discovery features")
    print("- Look at extension examples for web/CLI/AI applications")
