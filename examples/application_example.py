"""Rich application example demonstrating Whiskey's Application framework.

This example shows:
- Full application lifecycle management
- Component initialization and disposal
- Event system with wildcard patterns
- Background tasks
- Health checking
- Error handling
- Component metadata and priority

Run this example:
    python examples/application_example.py
"""

import asyncio

from whiskey import Disposable, Initializable, Whiskey, WhiskeyConfig


# Step 1: Define services with lifecycle hooks
class DatabaseService(Initializable, Disposable):
    """Database service with full lifecycle management."""

    def __init__(self):
        self.connected = False
        self.connection_string = "postgresql://localhost/myapp"

    async def initialize(self):
        """Connect to database on startup."""
        print("🗄️  Connecting to database...")
        await asyncio.sleep(0.5)  # Simulate connection time
        self.connected = True
        print("✅ Database connected")

    async def dispose(self):
        """Clean up database connection."""
        print("🗄️  Closing database connection...")
        await asyncio.sleep(0.2)
        self.connected = False
        print("✅ Database disconnected")

    async def query(self, sql: str) -> str:
        """Execute a query."""
        if not self.connected:
            raise RuntimeError("Database not connected")
        return f"Results for: {sql}"


class CacheService(Initializable):
    """Cache service that only needs initialization."""

    def __init__(self):
        self.cache = {}
        self.initialized = False

    async def initialize(self):
        """Warm up the cache on startup."""
        print("🗄️  Initializing cache...")
        # Pre-load some data
        self.cache["config"] = {"version": "1.0", "features": ["auth", "api"]}
        self.initialized = True
        print("✅ Cache initialized")

    async def get(self, key: str) -> any:
        """Get value from cache."""
        return self.cache.get(key)

    async def set(self, key: str, value: any) -> None:
        """Set value in cache."""
        self.cache[key] = value


# Step 2: Create services that use dependency injection


class UserService:
    """Service that depends on database and cache."""

    def __init__(self, db: DatabaseService, cache: CacheService):
        self.db = db
        self.cache = cache

    async def get_user(self, user_id: int) -> dict:
        """Get user by ID with caching."""
        # Check cache first
        cache_key = f"user:{user_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            print(f"✨ Cache hit for user {user_id}")
            return cached

        # Query database
        result = await self.db.query(f"SELECT * FROM users WHERE id = {user_id}")
        user = {"id": user_id, "name": f"User {user_id}", "data": result}

        # Cache the result
        await self.cache.set(cache_key, user)
        return user


# Step 3: Main application
async def main():
    """Main application entry point."""
    # Create application
    app = Whiskey(
        config=WhiskeyConfig(
            name="MyApp",
            version="1.0.0",
            debug=True,
        )
    )

    # Register services
    app.singleton(DatabaseService)
    app.singleton(CacheService)
    app.component(UserService)

    # Start the application
    async with app:
        # Services are automatically initialized
        user_service = await app.resolve(UserService)

        # Use the service
        user = await user_service.get_user(123)
        print(f"Retrieved user: {user}")

        # Get from cache
        user2 = await user_service.get_user(123)
        print(f"Retrieved user again: {user2}")


if __name__ == "__main__":
    asyncio.run(main())
