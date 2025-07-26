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
from typing import Annotated

from whiskey import Application, Disposable, Initializable, Inject, inject

# Step 1: Define services with lifecycle hooks
# ============================================


class Database(Initializable, Disposable):
    """Database service with proper lifecycle management.

    Implements:
    - Initializable: for async setup (connection)
    - Disposable: for cleanup (disconnection)
    """

    def __init__(self):
        self.connected = False
        self.connection_string = "postgresql://localhost/myapp"

    async def initialize(self):
        """Called during application startup."""
        print("📊 Connecting to database...")
        await asyncio.sleep(0.1)  # Simulate connection time
        self.connected = True
        print(f"✅ Database connected to {self.connection_string}")

    async def dispose(self):
        """Called during application shutdown."""
        print("🔌 Disconnecting from database...")
        await asyncio.sleep(0.1)  # Simulate cleanup
        self.connected = False
        print("✅ Database disconnected")

    async def query(self, sql: str) -> str:
        """Execute a database query."""
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
# =====================================================


@inject
class UserService:
    """Service demonstrating dependency injection."""

    def __init__(self, db: Annotated[Database, Inject()], cache: Annotated[CacheService, Inject()]):
        self.db = db
        self.cache = cache
        print("👤 UserService created")

    async def get_user(self, user_id: int) -> dict:
        """Get user with caching."""
        # Check cache first
        cache_key = f"user:{user_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            print(f"✨ Cache hit for user {user_id}")
            return cached

        # Query database
        result = await self.db.query(f"SELECT * FROM users WHERE id = {user_id}")
        user = {"id": user_id, "name": f"User {user_id}", "query": result}

        # Cache the result
        await self.cache.set(cache_key, user)
        return user


class MetricsCollector:
    """Background service that collects metrics."""

    def __init__(self):
        self.metrics = {"requests": 0, "cache_hits": 0, "errors": 0, "uptime_seconds": 0}

    async def collect_metrics(self):
        """Continuously collect metrics."""
        print("📊 Starting metrics collection...")
        while True:
            self.metrics["uptime_seconds"] += 1
            self.metrics["requests"] += 1  # Simulate activity

            if self.metrics["uptime_seconds"] % 3 == 0:
                print(f"📈 Metrics: {self.metrics}")

            await asyncio.sleep(1)

    def record_cache_hit(self):
        """Record a cache hit."""
        self.metrics["cache_hits"] += 1

    def record_error(self):
        """Record an error."""
        self.metrics["errors"] += 1


# Step 3: Create the application with rich features
# ================================================


async def main():
    """Demonstrate Application framework features."""

    # Create application with configuration
    app = Application(config={"name": "MyApp", "version": "1.0.0", "debug": True})

    print("🥃 Whiskey Application Example")
    print("==============================\n")

    # Register components with metadata
    # ==================================

    # Critical component - app fails if this fails
    @app.component
    @app.critical
    @app.priority(100)  # Initialize first
    class ConfigService:
        """Critical configuration service."""

        async def initialize(self):
            print("⚙️  Loading configuration...")
            # Simulate config loading
            await asyncio.sleep(0.1)
            print("✅ Configuration loaded")

    # Register our services
    app.component(Database)
    app.component(CacheService)
    app.component(UserService)
    app.component(MetricsCollector)

    # Set up lifecycle hooks
    # ======================

    @app.on_startup
    async def on_startup():
        """Called when application starts."""
        print(f"\n🚀 Starting {app.config['name']} v{app.config['version']}...")

    @app.on_ready
    async def on_ready():
        """Called when application is fully initialized."""
        print("✅ Application ready to serve requests!\n")

    @app.on_shutdown
    async def on_shutdown():
        """Called when application stops."""
        print("\n👋 Shutting down gracefully...")

    # Event handlers with patterns
    # ============================

    @app.on("user.created")
    async def handle_user_created(data):
        """Handle specific user.created events."""
        print(f"📧 Sending welcome email to user {data['user_id']}")

    @app.on("user.*")  # Wildcard pattern
    async def log_user_events(data):
        """Log all user events."""
        print(f"📝 User event: {data}")

    @app.on("metrics.error")
    async def handle_metric_error(data):
        """Handle metric errors."""
        collector = await app.container.resolve(MetricsCollector)
        collector.record_error()
        print(f"⚠️  Metric error: {data.get('message', 'Unknown error')}")

    # Background tasks
    # ================

    @app.task
    async def metrics_task():
        """Background task for collecting metrics."""
        collector = await app.container.resolve(MetricsCollector)
        try:
            await collector.collect_metrics()
        except asyncio.CancelledError:
            print("📊 Metrics collection stopped")
            raise

    @app.task
    async def periodic_health_check():
        """Periodic health check task."""
        while True:
            await asyncio.sleep(5)
            db = await app.container.resolve(Database)
            if db.connected:
                print("💚 Health check: OK")
            else:
                print("💔 Health check: Database disconnected!")
                await app.emit("health.unhealthy", {"service": "database"})

    # Error handling
    # ==============

    @app.on_error
    async def handle_errors(error_data):
        """Global error handler."""
        error = error_data["error"]
        phase = error_data.get("phase", "unknown")
        print(f"❌ Error in {phase}: {error}")

        # Could send to monitoring service, etc.
        await app.emit(
            "metrics.error", {"phase": phase, "error": str(error), "type": type(error).__name__}
        )

    # Run the application
    # ===================

    async with app.lifespan():
        # Application is now running with all services initialized

        # Demonstrate service usage
        print("--- Demonstrating Services ---\n")

        # Get and use services
        user_service = await app.container.resolve(UserService)

        # First call - will hit database
        user1 = await user_service.get_user(123)
        print(f"Got user: {user1}")

        # Second call - should hit cache
        user2 = await user_service.get_user(123)
        print(f"Got user again: {user2}")

        # Emit some events
        await app.emit("user.created", {"user_id": 456})
        await app.emit("user.updated", {"user_id": 123, "name": "Alice"})

        # Check component metadata
        print("\n--- Component Information ---")
        components = app.list_components()
        for comp in components:
            info = app.inspect_component(comp)
            print(
                f"📦 {comp.__name__}: priority={info.get('priority', 0)}, "
                f"critical={info.get('critical', False)}"
            )

        # Let background tasks run
        print("\n--- Running for 10 seconds ---")
        await asyncio.sleep(10)

    # Application has shut down cleanly
    print("\n✅ Application stopped successfully!")


# Step 4: Run the application
# ===========================

if __name__ == "__main__":
    print("🥃 Whiskey Rich Application Example")
    print("===================================\n")
    print("This example demonstrates:")
    print("- Application lifecycle management")
    print("- Component initialization and disposal")
    print("- Event system with wildcards")
    print("- Background tasks")
    print("- Error handling")
    print("- Component metadata\n")

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")

    print("\n🎉 Example completed!")
    print("\nNext steps:")
    print("- Try 'extension_example.py' to see how to build extensions")
    print("- Check 'event_emitter_example.py' for advanced event patterns")
    print("- Look at 'discovery_example.py' for component auto-discovery")
