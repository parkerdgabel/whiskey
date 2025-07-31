"""Example demonstrating the lifecycle extension features."""

import asyncio
import random

from whiskey import Disposable, Initializable, Whiskey
from whiskey.extensions import lifecycle_extension


# Simulated components with dependencies
class DatabasePool(Initializable, Disposable):
    """Database connection pool."""

    def __init__(self):
        self.connections = []
        self.max_connections = 10

    async def initialize(self):
        print("🔌 Initializing database pool...")
        await asyncio.sleep(0.5)  # Simulate slow startup

        # Simulate occasional startup failure
        if random.random() < 0.3:  # 30% chance of failure
            raise ConnectionError("Failed to connect to database")

        self.connections = list(range(self.max_connections))
        print(f"✅ Database pool ready with {len(self.connections)} connections")

    async def dispose(self):
        print("🔌 Closing database connections...")
        await asyncio.sleep(0.2)
        self.connections = []

    async def health_check(self):
        """Check database health."""
        if not self.connections:
            return {"status": "unhealthy", "message": "No connections available"}
        elif len(self.connections) < 5:
            return {
                "status": "degraded",
                "message": f"Only {len(self.connections)} connections available",
            }
        else:
            return {"status": "healthy", "message": f"{len(self.connections)} connections active"}


class CacheService(Initializable):
    """Redis cache service."""

    def __init__(self, db: DatabasePool):
        self.db = db
        self.connected = False

    async def initialize(self):
        print("🔸 Initializing cache service...")
        await asyncio.sleep(0.2)
        self.connected = True
        print("✅ Cache service ready")

    async def health_check(self):
        return self.connected


class MessageQueue(Initializable):
    """Message queue service."""

    def __init__(self):
        self.queue = asyncio.Queue()
        self.connected = False

    async def initialize(self):
        print("📬 Connecting to message queue...")
        await asyncio.sleep(0.3)

        # Simulate occasional failure
        if random.random() < 0.2:  # 20% chance
            raise ConnectionError("Message queue unavailable")

        self.connected = True
        print("✅ Message queue connected")

    async def is_healthy(self):
        """Alternative health check method name."""
        return {"healthy": self.connected, "queue_size": self.queue.qsize()}


class APIService:
    """API service that depends on multiple components."""

    def __init__(self, db: DatabasePool, cache: CacheService, queue: MessageQueue):
        self.db = db
        self.cache = cache
        self.queue = queue
        self.request_count = 0

    async def handle_request(self):
        self.request_count += 1
        return {"processed": self.request_count}

    async def health_check(self):
        return {
            "status": "healthy",
            "message": f"Processed {self.request_count} requests",
            "dependencies": {
                "database": bool(self.db.connections),
                "cache": self.cache.connected,
                "queue": self.queue.connected,
            },
        }


class MetricsCollector:
    """Non-critical metrics service."""

    def __init__(self):
        self.metrics = {}

    async def initialize(self):
        print("📊 Starting metrics collector...")
        # This might fail but shouldn't stop the app
        if random.random() < 0.5:  # 50% chance
            raise Exception("Metrics service unavailable")
        print("✅ Metrics collector started")


async def main():
    # Create app with lifecycle extension
    app = Whiskey()
    app.use(lifecycle_extension)

    # Register components with metadata and retry policies

    @app.component
    @app.priority(10)  # Start first
    @app.provides("database", "storage")
    @app.critical  # Must start or app fails
    @app.retry(max_retries=5, delay=2.0)  # Retry up to 5 times
    class Database(DatabasePool):
        pass

    @app.component
    @app.priority(20)
    @app.requires(Database)  # Use the registered name
    @app.provides("cache")
    @app.retry(max_retries=3)
    class Cache(CacheService):
        pass

    @app.component
    @app.priority(20)  # Same priority as cache - can start in parallel
    @app.provides("messaging")
    @app.retry(max_retries=3, delay=1.0)
    class Queue(MessageQueue):
        pass

    @app.component
    @app.priority(30)
    @app.requires(Database, Cache, Queue)  # Use the registered names
    @app.provides("api")
    @app.critical
    class API(APIService):
        pass

    @app.component
    @app.priority(40)
    class Metrics(MetricsCollector):
        pass  # Non-critical, allowed to fail

    # Event handlers to track lifecycle
    @app.on("lifecycle.dependency_graph")
    async def show_graph(data):
        print("\n" + data["graph"])

    @app.on("component.retry")
    async def on_retry(data):
        print(
            f"⚠️  Retrying {data['type'].__name__}: attempt {data['attempt']}/{data['max_retries']}"
        )

    @app.on("component.started")
    async def on_started(data):
        print(
            f"✅ {data['type'].__name__} started in {data['time']:.2f}s (attempt {data['attempt']})"
        )

    @app.on("component.failed")
    async def on_failed(data):
        if data["critical"]:
            print(f"❌ CRITICAL: {data['type'].__name__} failed to start!")
        else:
            print(f"⚠️  {data['type'].__name__} failed to start (non-critical)")

    @app.on("lifecycle.level_starting")
    async def on_level(data):
        print(f"\n🔄 Starting level {data['level']}: {', '.join(data['components'])}")

    # Readiness checks
    @app.on_ready
    async def setup_readiness():
        """Add custom readiness checks."""

        async def check_external_api():
            # Simulate external API check
            await asyncio.sleep(0.1)
            return random.random() > 0.2  # 80% success rate

        app.add_readiness_check("external_api", check_external_api)

        def check_disk_space():
            # Simulate disk space check
            return {"ready": True, "free_space": "10GB"}

        app.add_readiness_check("disk_space", check_disk_space)

    # Run the application
    try:
        async with app.lifespan():
            print("\n🎉 Application started successfully!\n")

            # Simulate some work
            api = await app.container.resolve(APIService)
            for i in range(5):
                result = await api.handle_request()
                print(f"📝 Request {i + 1}: {result}")
                await asyncio.sleep(1)

            # Check health
            print("\n🏥 Health Check:")
            health = await app.health_handler()
            print(f"Overall status: {health['status']}")
            for name, status in health["components"].items():
                icon = (
                    "✅"
                    if status["status"] == "healthy"
                    else "⚠️"
                    if status["status"] == "degraded"
                    else "❌"
                )
                print(f"  {icon} {name}: {status['status']} - {status.get('message', 'OK')}")

            # Check readiness
            print("\n🚦 Readiness Check:")
            readiness = await app.readiness_handler()
            print(f"Ready: {'Yes' if readiness['ready'] else 'No'}")
            for check, result in readiness["checks"].items():
                icon = "✅" if result["ready"] else "❌"
                print(f"  {icon} {check}: {result.get('message', result.get('error', 'OK'))}")

            # Show final dependency graph with performance metrics
            print("\n" + app.lifecycle_manager.visualize_dependencies())

    except RuntimeError as e:
        print(f"\n💥 Application failed to start: {e}")


if __name__ == "__main__":
    asyncio.run(main())
