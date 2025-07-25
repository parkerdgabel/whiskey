"""
Basic Dependency Injection Example

This example demonstrates Whiskey's fundamental dependency injection concepts:
- Service registration with decorators
- Automatic dependency resolution
- Container as a service registry
- Dict-like container interface

Run this example:
    python examples/01_basic_di.py
"""

import asyncio

from whiskey import Container, inject, service, singleton, create_app


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


@service  # Register with default container
class UserService:
    """Service for user operations."""
    
    def __init__(self, db: Database, logger: Logger):
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
async def process_users(user_service: UserService, logger: Logger) -> None:
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
    
    # Example 1: Using Global Decorators
    # ==================================
    print("\n1. Using Global Decorators")
    print("-" * 30)
    
    # Services are already registered via @service and @singleton decorators
    # The @inject decorator automatically resolves dependencies
    
    await process_users()
    
    # Example 2: Manual Container Usage
    # =================================
    print("\n\n2. Manual Container Usage")
    print("-" * 30)
    
    # Create a new container
    container = Container()
    
    # Register services using dict-like syntax
    container['database'] = Database("mysql://localhost/testdb")  # Instance
    container[Logger] = Logger  # Class (will be instantiated)
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
    for service_key in container:
        print(f"  - {service_key}")
    
    # Example 4: Fluent Registration API
    # ==================================
    print("\n\n4. Fluent Registration API")
    print("-" * 30)
    
    container = Container()
    
    # Fluent registration with method chaining
    container.add(Database, Database).build()
    container.add_singleton(Logger, Logger).build()
    container.add(UserService, UserService).tagged('business').build()
    
    # Factory functions
    def create_configured_database() -> Database:
        """Factory function for custom Database creation."""
        import os
        env = os.getenv("ENV", "development")
        
        if env == "production":
            return Database("postgresql://prod-server/app")
        else:
            return Database("sqlite:///dev.db")
    
    # Register the factory
    container.add_factory('database', create_configured_database).build()
    
    # Each resolution calls the factory for transient services
    user_service1 = await container.resolve(UserService)
    user_service2 = await container.resolve(UserService)
    
    # Different UserService instances (transient)
    print(f"Same UserService instance: {user_service1 is user_service2}")
    
    # Same Logger instance (singleton)
    print(f"Same Logger instance: {user_service1.logger is user_service2.logger}")
    
    # Example 5: Application Builder
    # ===============================
    print("\n\n5. Application Builder")
    print("-" * 25)
    
    # Fluent application configuration
    app = create_app() \
        .singleton(Database, Database).build() \
        .singleton(Logger, Logger).build() \
        .service(UserService, UserService).build() \
        .build_app()
    
    # Use the application
    async with app:
        user_service = await app.resolve_async(UserService)
        logger = await app.resolve_async(Logger)
        
        logger.log("Application builder example")
        users = await user_service.get_users()
        print(f"Retrieved {len(users)} users via application")
    
    # Example 6: Function Injection and Calling
    # ==========================================
    print("\n\n6. Function Injection and Calling")
    print("-" * 40)
    
    container = Container()
    container.add_singleton(Database, Database).build()
    container.add_singleton(Logger, Logger).build()
    
    # Define a function that needs dependencies
    def business_logic(db: Database, logger: Logger, user_id: int = 1) -> str:
        """Business logic function with DI."""
        logger.log(f"Processing user {user_id}")
        return f"Processed user {user_id} using {db.connection_string}"
    
    # Call with automatic dependency injection
    result = await container.call(business_logic, user_id=42)
    print(f"Function result: {result}")
    
    # Wrap function for repeated calls
    injected_func = container.wrap_with_injection(business_logic)
    result2_task = injected_func(user_id=99)
    result2 = await result2_task  # Await the task returned by sync wrapper
    print(f"Wrapped function result: {result2}")


if __name__ == "__main__":
    asyncio.run(main())