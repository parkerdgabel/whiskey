"""Example using the Application class for lifecycle management."""

import asyncio
from whiskey import Application, Disposable, Initializable


# Services with lifecycle
class Database(Initializable, Disposable):
    def __init__(self):
        self.connected = False
        
    async def initialize(self):
        print("📊 Connecting to database...")
        await asyncio.sleep(0.1)  # Simulate connection
        self.connected = True
        print("✅ Database connected")
        
    async def dispose(self):
        print("🔌 Disconnecting from database...")
        self.connected = False
        print("✅ Database disconnected")
        
    async def query(self, sql: str):
        if not self.connected:
            raise RuntimeError("Database not connected")
        return f"Results for: {sql}"


# Background service
class MetricsCollector:
    def __init__(self):
        self.metrics = {"requests": 0, "errors": 0}
        
    async def collect(self):
        """Collect metrics every second."""
        while True:
            self.metrics["requests"] += 1
            print(f"📈 Metrics: {self.metrics}")
            await asyncio.sleep(1)


# Monitoring service (defined at module level)
class MonitoringService:
    def __init__(self, db: Database, metrics: MetricsCollector):
        self.db = db
        self.metrics = metrics
        
    async def health_check(self):
        try:
            # Test database connection
            await self.db.query("SELECT 1")
            return {"status": "healthy", "metrics": self.metrics.metrics}
        except:
            return {"status": "unhealthy"}


# Extension function
def monitoring_extension(app: Application) -> None:
    """Add monitoring capabilities."""
    
    # Register services
    app.service(MonitoringService)
    app.container.register_singleton(MetricsCollector)
    
    # Register background task
    @app.task
    async def metrics_task():
        collector = await app.container.resolve(MetricsCollector)
        await collector.collect()


async def main():
    # Create application
    app = Application()
    
    # Register services
    app.service(Database)
    
    # Add monitoring extension
    app.extend(monitoring_extension)
    
    # Startup hooks
    @app.on_startup
    async def startup():
        print("🚀 Application starting...")
    
    @app.on_shutdown
    async def shutdown():
        print("👋 Application shutting down...")
    
    # Run application
    async with app.lifespan():
        print("\n✨ Application is running!\n")
        
        # Use services
        monitoring = await app.container.resolve(MonitoringService)
        health = await monitoring.health_check()
        print(f"Health: {health}")
        
        # Let it run for a bit
        await asyncio.sleep(3)
    
    print("\n✅ Application stopped cleanly")


if __name__ == "__main__":
    asyncio.run(main())