"""Example demonstrating rich IoC features."""

import asyncio

from whiskey import Disposable, Initializable, Whiskey


# Components with metadata and lifecycle
class Database(Initializable, Disposable):
    """Critical database component."""

    def __init__(self):
        self.connected = False
        self.queries_count = 0

    async def initialize(self):
        print("🔌 Connecting to database...")
        await asyncio.sleep(0.1)
        self.connected = True

    async def dispose(self):
        print("🔌 Disconnecting from database...")
        self.connected = False

    async def query(self, sql: str):
        self.queries_count += 1
        return f"Result for: {sql}"

    async def health_check(self):
        """Check database health."""
        return {"connected": self.connected, "queries": self.queries_count}


class CacheService:
    """Cache service that depends on database."""

    def __init__(self, db: Database):
        self.db = db
        self.cache = {}

    async def get(self, key: str):
        if key in self.cache:
            print(f"✅ Cache hit: {key}")
            return self.cache[key]

        # Cache miss, query database
        print(f"❌ Cache miss: {key}")
        value = await self.db.query(f"SELECT * FROM cache WHERE key='{key}'")
        self.cache[key] = value
        return value


class EmailService:
    """Email service for notifications."""

    async def send(self, to: str, subject: str, body: str):
        print(f"📧 Email to {to}: {subject}")
        await asyncio.sleep(0.05)  # Simulate sending


# Extension that adds monitoring
def monitoring_extension(app: Whiskey) -> None:
    """Add monitoring capabilities to the application."""

    # Add custom lifecycle phase
    app.add_lifecycle_phase("metrics_init", after="startup")

    # Add metrics decorator
    def tracked(cls):
        """Track component metrics."""
        original_init = cls.__init__

        def new_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            self._call_count = 0

        cls.__init__ = new_init

        # Wrap all methods to count calls
        for name, method in cls.__dict__.items():
            if callable(method) and not name.startswith("_"):

                def make_wrapper(m):
                    async def wrapper(self, *args, **kwargs):
                        self._call_count += 1
                        return (
                            await m(self, *args, **kwargs)
                            if asyncio.iscoroutinefunction(m)
                            else m(self, *args, **kwargs)
                        )

                    return wrapper

                setattr(cls, name, make_wrapper(method))

        return cls

    app.add_decorator("tracked", tracked)

    # Listen for lifecycle events
    @app.on("application.ready")
    async def on_ready():
        print("📊 Monitoring: Application is ready!")

    @app.on("application.error")
    async def on_error(data):
        print(f"🚨 Monitoring: Error in {data['phase']} - {data['message']}")


async def main():
    # Create application with extension
    app = Whiskey()
    app.extend(monitoring_extension)

    # Register components with metadata
    @app.priority(10)  # Start first
    @app.provides("database", "storage")
    @app.critical
    @app.component
    class DatabaseComponent(Database):
        @app.health_check
        async def check_health(self):
            return await self.health_check()

    @app.priority(20)
    @app.requires(Database)
    @app.tracked  # Use custom decorator from extension
    @app.component
    class CacheComponent(CacheService):
        pass

    @app.provides("notifications")
    @app.component
    class EmailComponent(EmailService):
        pass

    # Rich lifecycle hooks
    @app.before_startup
    async def before_startup():
        print("\n🚀 Preparing to start application...")

    @app.after_startup
    async def after_startup():
        print("✨ All components started successfully!")

    @app.on_ready
    async def ready():
        print("🎉 Application is fully ready!\n")

    # Event handlers
    @app.on("user.login")
    async def on_user_login(user):
        print(f"👤 User logged in: {user['name']}")
        await app.emit("notification.send", {"to": user["email"], "type": "login"})

    @app.on("notification.*")  # Wildcard handler
    async def on_any_notification(data):
        email = await app.container.resolve(EmailService)
        if data.get("type") == "login":
            await email.send(data["to"], "Login Notification", "You just logged in!")

    # Error handling
    @app.on_error
    async def handle_error(error_data):
        print(f"❌ Error handler: {error_data['message']}")

    # Background task
    @app.task
    async def metrics_collector():
        """Collect metrics every 2 seconds."""
        while True:
            await asyncio.sleep(2)

            # Get all components providing "database"
            db_components = app.get_components_providing("database")
            for comp_type in db_components:
                db = await app.container.resolve(comp_type)
                health = await db.health_check()
                print(f"📊 Database health: {health}")

    # Run the application
    async with app.lifespan():
        # Use components
        cache = await app.container.resolve(CacheService)

        # Test cache
        await cache.get("user:123")
        await cache.get("user:123")  # Should hit cache

        # Emit events
        await app.emit("user.login", {"name": "Alice", "email": "alice@example.com"})

        # Wait a bit to see background task
        await asyncio.sleep(5)

        # Show component metadata
        print("\n📋 Component Metadata:")
        for comp_type, metadata in app._component_metadata.items():
            print(f"  {comp_type.__name__}:")
            print(f"    Priority: {metadata.priority}")
            print(f"    Provides: {metadata.provides}")
            print(f"    Critical: {metadata.critical}")


if __name__ == "__main__":
    asyncio.run(main())
