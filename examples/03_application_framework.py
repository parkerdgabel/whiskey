"""
Application Framework Example

This example demonstrates Whiskey's rich Application framework:
- Component registration and metadata
- Lifecycle phases and hooks
- Event system with wildcard patterns
- Background tasks
- Health checking and monitoring
- Error handling and recovery

Run this example:
    python examples/03_application_framework.py
"""

import asyncio

from whiskey import (
    Application,
    ApplicationConfig,
    Disposable,
    Initializable,
)

# Step 1: Services with Rich Metadata
# ====================================


class Database(Initializable, Disposable):
    """Critical database service with health checking."""

    def __init__(self):
        self.connected = False
        self.query_count = 0
        self.connection_string = "postgresql://localhost/app"

    async def initialize(self):
        """Initialize database connection."""
        print("🗄️ Initializing database connection...")
        await asyncio.sleep(0.2)  # Simulate connection time
        self.connected = True
        print("✅ Database connection established")

    async def dispose(self):
        """Clean up database connection."""
        print("🗄️ Closing database connection...")
        await asyncio.sleep(0.1)
        self.connected = False
        print("✅ Database connection closed")

    async def query(self, sql: str) -> list[dict]:
        """Execute a database query."""
        if not self.connected:
            raise RuntimeError("Database not connected")

        self.query_count += 1
        print(f"📊 DB Query #{self.query_count}: {sql}")
        return [{"id": 1, "data": f"result_for_{sql}"}]

    async def health_check(self) -> dict:
        """Check database health."""
        return {
            "status": "healthy" if self.connected else "unhealthy",
            "connected": self.connected,
            "queries_executed": self.query_count,
            "connection_string": self.connection_string,
        }


class CacheService(Initializable):
    """Cache service with warming capabilities."""

    def __init__(self):
        self.cache = {}
        self.hit_count = 0
        self.miss_count = 0
        self.warmed = False

    async def initialize(self):
        """Warm up the cache with initial data."""
        print("🗄️ Warming up cache...")
        await asyncio.sleep(0.1)
        # Pre-populate cache
        self.cache.update(
            {
                "config:app_name": "WhiskeyApp",
                "config:version": "1.0.0",
                "user:admin": {"id": 1, "name": "Admin", "role": "admin"},
            }
        )
        self.warmed = True
        print("✅ Cache warmed with initial data")

    async def get(self, key: str) -> any:
        """Get value from cache."""
        if key in self.cache:
            self.hit_count += 1
            print(f"💨 Cache HIT: {key}")
            return self.cache[key]
        else:
            self.miss_count += 1
            print(f"❌ Cache MISS: {key}")
            return None

    async def set(self, key: str, value: any) -> None:
        """Set value in cache."""
        self.cache[key] = value
        print(f"💾 Cache SET: {key}")

    async def health_check(self) -> dict:
        """Check cache health."""
        return {
            "status": "healthy" if self.warmed else "warming",
            "entries": len(self.cache),
            "hit_count": self.hit_count,
            "miss_count": self.miss_count,
            "hit_ratio": self.hit_count / (self.hit_count + self.miss_count)
            if (self.hit_count + self.miss_count) > 0
            else 0,
        }


class NotificationService:
    """Service for sending notifications."""

    def __init__(self):
        self.sent_count = 0
        print("📧 NotificationService initialized")

    async def send(self, recipient: str, message: str, type: str = "info") -> None:
        """Send a notification."""
        self.sent_count += 1
        emoji = {"info": "ℹ️", "warning": "⚠️", "error": "❌", "success": "✅"}.get(type, "📧")
        print(f"{emoji} Notification to {recipient}: {message}")
        await asyncio.sleep(0.05)  # Simulate sending


class MetricsCollector:
    """Background service for collecting application metrics."""

    def __init__(self):
        self.metrics = {
            "uptime_seconds": 0,
            "requests_processed": 0,
            "errors_occurred": 0,
            "active_connections": 0,
        }
        self.running = False
        print("📊 MetricsCollector initialized")

    async def start_collection(self):
        """Start metrics collection loop."""
        self.running = True
        print("📊 Starting metrics collection...")

        while self.running:
            self.metrics["uptime_seconds"] += 1
            self.metrics["requests_processed"] += 1  # Simulate activity

            # Log metrics every 5 seconds
            if self.metrics["uptime_seconds"] % 5 == 0:
                print(f"📈 Metrics update: {self.metrics}")

            await asyncio.sleep(1)

    def stop_collection(self):
        """Stop metrics collection."""
        self.running = False
        print("📊 Metrics collection stopped")

    def increment(self, metric: str, value: int = 1):
        """Increment a metric counter."""
        if metric in self.metrics:
            self.metrics[metric] += value

    def get_metrics(self) -> dict:
        """Get current metrics."""
        return self.metrics.copy()


# Step 2: Business Services Using Rich DI
# ========================================


class UserService:
    """User service with comprehensive dependencies."""

    def __init__(
        self,
        db: Database,
        cache: CacheService,
        notifications: NotificationService,
        metrics: MetricsCollector,
    ):
        self.db = db
        self.cache = cache
        self.notifications = notifications
        self.metrics = metrics
        print("👤 UserService initialized with all dependencies")

    async def get_user(self, user_id: int) -> dict:
        """Get user with caching and metrics."""
        self.metrics.increment("requests_processed")

        # Check cache first
        cache_key = f"user:{user_id}"
        cached_user = await self.cache.get(cache_key)
        if cached_user:
            return cached_user

        # Query database
        try:
            users = await self.db.query(f"SELECT * FROM users WHERE id = {user_id}")
            if users:
                user = users[0]
                # Cache the result
                await self.cache.set(cache_key, user)
                return user
            else:
                await self.notifications.send("admin", f"User {user_id} not found", "warning")
                return {"error": "User not found"}

        except Exception as e:
            self.metrics.increment("errors_occurred")
            await self.notifications.send("admin", f"Database error: {e}", "error")
            raise

    async def create_user(self, name: str, email: str) -> dict:
        """Create a new user."""
        self.metrics.increment("requests_processed")

        try:
            # Save to database
            await self.db.query(f"INSERT INTO users (name, email) VALUES ('{name}', '{email}')")

            # Create user object
            user = {
                "id": len(await self.db.query("SELECT id FROM users")) + 1,
                "name": name,
                "email": email,
            }

            # Cache the new user
            await self.cache.set(f"user:{user['id']}", user)

            # Send welcome notification
            await self.notifications.send(email, f"Welcome to our app, {name}!", "success")

            return user

        except Exception as e:
            self.metrics.increment("errors_occurred")
            await self.notifications.send("admin", f"Failed to create user {name}: {e}", "error")
            raise


# Step 3: Application with Rich Configuration
# ============================================


async def main():
    """Demonstrate the rich Application framework."""

    print("🥃 Whiskey Application Framework Example")
    print("=" * 50)

    # Create application with rich configuration
    config = ApplicationConfig(
        name="WhiskeyDemo",
        version="1.0.0",
        debug=True,
        description="Demonstration of Whiskey's Application framework",
    )

    app = Application(config=config)

    # Step 3a: Register Components with Metadata
    # ===========================================

    @app.component
    @app.critical  # App fails to start if this fails
    @app.priority(100)  # Initialize first
    @app.provides("database", "storage")
    @app.health_check
    class DatabaseComponent(Database):
        """Critical database component."""

        async def check_health(self):
            return await self.health_check()

    @app.component
    @app.priority(90)  # Initialize after database
    @app.requires(Database)
    @app.health_check
    class CacheComponent(CacheService):
        """Cache component that depends on database."""

        async def check_health(self):
            return await self.health_check()

    @app.component
    @app.provides("notifications")
    class NotificationComponent(NotificationService):
        """Notification service component."""

        pass

    @app.component
    @app.provides("metrics", "monitoring")
    class MetricsComponent(MetricsCollector):
        """Metrics collection component."""

        pass

    @app.component
    @app.requires(Database, CacheService, NotificationService, MetricsCollector)
    class UserComponent(UserService):
        """User service with all dependencies."""

        pass

    # Step 3b: Lifecycle Hooks
    # ========================

    @app.before_startup
    async def before_startup():
        """Called before any components are initialized."""
        print(f"\n🚀 Preparing to start {app.config.name} v{app.config.version}...")
        print(f"📝 Description: {app.config.description}")

    @app.on_startup
    async def on_startup():
        """Called during component initialization."""
        print("⚙️ Initializing components...")

    @app.after_startup
    async def after_startup():
        """Called after all components are initialized."""
        print("✨ All components initialized successfully!")

    @app.on_ready
    async def on_ready():
        """Called when application is fully ready."""
        print("🎉 Application is ready to process requests!\n")

    @app.before_shutdown
    async def before_shutdown():
        """Called before shutdown begins."""
        print("\n👋 Beginning graceful shutdown...")

    @app.on_shutdown
    async def on_shutdown():
        """Called during shutdown."""
        print("🛑 Shutting down components...")

    @app.after_shutdown
    async def after_shutdown():
        """Called after shutdown is complete."""
        print("✅ Shutdown complete")

    # Step 3c: Event System
    # =====================

    @app.on("user.created")
    async def on_user_created(data):
        """Handle user creation events."""
        print(f"🎊 Event: User {data['name']} was created!")
        metrics = await app.container.resolve(MetricsCollector)
        metrics.increment("users_created", 1)

    @app.on("user.*")  # Wildcard pattern
    async def log_all_user_events(data):
        """Log all user-related events."""
        print(f"📝 User event logged: {data}")

    @app.on("system.health_check")
    async def on_health_check(data):
        """Handle health check events."""
        print(f"🏥 Health check requested: {data}")

    @app.on("system.error")
    async def on_system_error(data):
        """Handle system errors."""
        print(f"🚨 System error: {data['message']}")
        notifications = await app.container.resolve(NotificationService)
        await notifications.send("admin", f"System error: {data['message']}", "error")

    # Step 3d: Background Tasks
    # =========================

    @app.task
    async def metrics_collection_task():
        """Background task for metrics collection."""
        metrics = await app.container.resolve(MetricsCollector)
        try:
            await metrics.start_collection()
        except asyncio.CancelledError:
            metrics.stop_collection()
            print("📊 Metrics collection task cancelled")
            raise

    @app.task
    async def health_monitor_task():
        """Background task for health monitoring."""
        while True:
            await asyncio.sleep(10)  # Check every 10 seconds

            # Emit health check event
            await app.emit("system.health_check", {"timestamp": asyncio.get_event_loop().time()})

            # Check component health
            try:
                db = await app.container.resolve(Database)
                cache = await app.container.resolve(CacheService)

                db_health = await db.health_check()
                cache_health = await cache.health_check()

                if db_health["status"] != "healthy" or cache_health["status"] != "healthy":
                    await app.emit(
                        "system.error",
                        {
                            "message": "Component health check failed",
                            "db_health": db_health,
                            "cache_health": cache_health,
                        },
                    )
            except Exception as e:
                await app.emit("system.error", {"message": f"Health check error: {e}"})

    # Step 3e: Error Handling
    # =======================

    @app.on_error
    async def global_error_handler(error_data):
        """Global error handler for the application."""
        error = error_data["error"]
        phase = error_data.get("phase", "runtime")
        component = error_data.get("component", "unknown")

        print(f"❌ Global error handler: {phase} error in {component}: {error}")

        # Emit system error event
        await app.emit(
            "system.error",
            {
                "phase": phase,
                "component": component,
                "message": str(error),
                "type": type(error).__name__,
            },
        )

        # Could integrate with external monitoring here

    # Step 4: Run the Application
    # ===========================

    try:
        async with app.lifespan():
            # Application is now fully initialized and running
            print("--- APPLICATION RUNNING ---")

            # Demonstrate service usage
            user_service = await app.container.resolve(UserService)

            # Create some users
            alice = await user_service.create_user("Alice", "alice@example.com")
            await app.emit("user.created", alice)

            bob = await user_service.create_user("Bob", "bob@example.com")
            await app.emit("user.created", bob)

            # Get users (should hit cache on second call)
            user1 = await user_service.get_user(1)
            user1_again = await user_service.get_user(1)  # Cache hit

            print(f"Retrieved user: {user1}")

            # Show component metadata
            print("\n--- COMPONENT METADATA ---")
            components = app.list_components()
            for comp in components:
                metadata = app.inspect_component(comp)
                print(f"📦 {comp.__name__}:")
                print(f"   Priority: {metadata.get('priority', 0)}")
                print(f"   Critical: {metadata.get('critical', False)}")
                print(f"   Provides: {metadata.get('provides', [])}")
                print(f"   Requires: {metadata.get('requires', [])}")

            # Show health status
            print("\n--- HEALTH STATUS ---")
            db = await app.container.resolve(Database)
            cache = await app.container.resolve(CacheService)
            metrics = await app.container.resolve(MetricsCollector)

            print(f"Database: {await db.health_check()}")
            print(f"Cache: {await cache.health_check()}")
            print(f"Metrics: {metrics.get_metrics()}")

            # Let background tasks run for a bit
            print("\n--- RUNNING FOR 15 SECONDS ---")
            print("(Background tasks are collecting metrics and monitoring health)")
            await asyncio.sleep(15)

    except KeyboardInterrupt:
        print("\n⚠️ Interrupted by user")
    except Exception as e:
        print(f"\n💥 Application error: {e}")
        raise


if __name__ == "__main__":
    print("🥃 Whiskey Application Framework")
    print("=" * 40)
    print("Features demonstrated:")
    print("✅ Component registration with metadata")
    print("✅ Rich lifecycle management")
    print("✅ Event system with wildcards")
    print("✅ Background tasks")
    print("✅ Health checking")
    print("✅ Error handling")
    print("✅ Graceful shutdown")
    print()

    asyncio.run(main())
