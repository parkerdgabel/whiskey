"""
Basic Dependency Injection Example

This example demonstrates Whiskey's fundamental dependency injection concepts:
- Service registration with decorators
- Automatic dependency resolution
- Container as a service registry
- Manual vs automatic injection

Run this example:
    python examples/01_basic_di.py
"""

import asyncio
from typing import Annotated

from whiskey import Container, inject, provide, singleton, Inject


# Step 1: Define Your Services
# ============================

class Database:
    """A simple database service."""
    
    def __init__(self, connection_string: str = "postgresql://localhost/myapp"):
        self.connection_string = connection_string
        print(f"🗄️ Database connected to: {connection_string}")
    
    async def query(self, sql: str) -> list[dict]:
        """Execute a database query."""
        print(f"📊 Query: {sql}")
        # Mock results
        return [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]


@singleton  # Only one instance across the entire application
class Logger:
    """A logging service (singleton)."""
    
    def __init__(self):
        print("📝 Logger initialized (singleton)")
        self.logs = []
    
    def log(self, message: str) -> None:
        """Log a message."""
        self.logs.append(message)
        print(f"📝 LOG: {message}")


@provide  # Register with default container
class UserService:
    """Service for user operations."""
    
    def __init__(self, 
                 db: Annotated[Database, Inject()],
                 logger: Annotated[Logger, Inject()]):
        self.db = db
        self.logger = logger
        print("👤 UserService initialized")
    
    async def get_users(self) -> list[dict]:
        """Get all users."""
        self.logger.log("Fetching all users")
        return await self.db.query("SELECT * FROM users")
    
    async def get_user(self, user_id: int) -> dict | None:
        """Get a specific user."""
        self.logger.log(f"Fetching user {user_id}")
        users = await self.db.query(f"SELECT * FROM users WHERE id = {user_id}")
        return users[0] if users else None


# Step 2: Using Dependency Injection
# ===================================

@inject
async def process_users(
    user_service: Annotated[UserService, Inject()],
    logger: Annotated[Logger, Inject()]
) -> None:
    """Function that uses dependency injection."""
    logger.log("Starting user processing")
    
    # Get all users
    users = await user_service.get_users()
    logger.log(f"Found {len(users)} users")
    
    # Process each user
    for user in users:
        user_detail = await user_service.get_user(user["id"])
        logger.log(f"Processed user: {user_detail}")


async def main():
    """Demonstrate basic dependency injection patterns."""
    
    print("🥃 Whiskey Basic DI Example")
    print("=" * 40)
    
    # Example 1: Using Default Container with Decorators
    # ==================================================
    print("\n1. Using Default Container with Decorators")
    print("-" * 45)
    
    # Services are already registered via @provide and @singleton decorators
    # The @inject decorator automatically resolves dependencies
    
    await process_users()
    
    # Example 2: Manual Container Usage
    # =================================
    print("\n\n2. Manual Container Usage")
    print("-" * 30)
    
    # Create a new container
    container = Container()
    
    # Register services manually
    container[Database] = Database("mysql://localhost/testdb")  # Instance
    container[Logger] = Logger  # Class (will be instantiated as singleton)
    container[UserService] = UserService  # Class with auto-resolved dependencies
    
    # Resolve services manually
    user_service = await container.resolve(UserService)
    logger = await container.resolve(Logger)
    
    # Use the services
    logger.log("Manual container example")
    users = await user_service.get_users()
    print(f"Retrieved {len(users)} users via manual container")
    
    # Example 3: Container as Dictionary
    # ==================================
    print("\n\n3. Container as Dictionary")
    print("-" * 30)
    
    container = Container()
    
    # Dict-like operations
    container[Database] = Database
    container[Logger] = Logger
    
    # Check registration
    print(f"Database registered: {Database in container}")
    print(f"String registered: {str in container}")
    
    # Get service info
    print(f"Container size: {len(container)}")
    print("Registered services:")
    for service_type in container:
        print(f"  - {service_type.__name__}")
    
    # Example 4: Factory Functions
    # ============================
    print("\n\n4. Factory Functions")
    print("-" * 25)
    
    container = Container()
    
    # Register a factory function
    def create_configured_database() -> Database:
        """Factory function for custom Database creation."""
        import os
        env = os.getenv("ENV", "development")
        
        if env == "production":
            return Database("postgresql://prod-server/app")
        else:
            return Database("sqlite:///dev.db")
    
    # Register the factory
    container[Database] = create_configured_database
    container[Logger] = Logger
    container[UserService] = UserService
    
    # Each resolution calls the factory
    user_service1 = await container.resolve(UserService)
    user_service2 = await container.resolve(UserService)
    
    # Different UserService instances (transient)
    print(f"Same UserService instance: {user_service1 is user_service2}")
    
    # Same Logger instance (singleton)
    print(f"Same Logger instance: {user_service1.logger is user_service2.logger}")
    
    # Example 5: Scope Demonstration
    # ===============================
    print("\n\n5. Scope Demonstration")
    print("-" * 25)
    
    container = Container()
    
    # Different scopes
    container[Database] = Database  # Transient (default)
    container.singleton(Logger, Logger)  # Explicit singleton
    
    # Register factory that creates new instances
    container.factory(str, lambda: f"request-{id(object())}")
    
    # Resolve multiple times
    db1 = await container.resolve(Database)
    db2 = await container.resolve(Database)
    logger1 = await container.resolve(Logger)
    logger2 = await container.resolve(Logger)
    id1 = await container.resolve(str)
    id2 = await container.resolve(str)
    
    print(f"Database instances same: {db1 is db2}")  # False (transient)
    print(f"Logger instances same: {logger1 is logger2}")  # True (singleton)
    print(f"String ID 1: {id1}")
    print(f"String ID 2: {id2}")


if __name__ == "__main__":
    asyncio.run(main())