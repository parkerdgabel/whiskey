"""Example showing the new extension pattern for Whiskey."""

import asyncio
from whiskey import Application, inject, singleton


# Extension functions - the new way to extend Whiskey
# =====================================================

def redis_extension(app: Application) -> None:
    """Add Redis support to the application."""
    
    @singleton
    class RedisConfig:
        def __init__(self, host: str = "localhost", port: int = 6379):
            self.host = host
            self.port = port
    
    @app.service
    class RedisClient:
        def __init__(self, config: RedisConfig):
            self.config = config
        
        async def initialize(self):
            print(f"Connecting to Redis at {self.config.host}:{self.config.port}")
        
        async def dispose(self):
            print("Disconnecting from Redis")
        
        async def get(self, key: str) -> str | None:
            # Mock implementation
            return f"value_for_{key}"
        
        async def set(self, key: str, value: str) -> None:
            # Mock implementation
            print(f"SET {key} = {value}")


def cache_extension(app: Application) -> None:
    """Add caching support using Redis."""
    
    @app.service
    class CacheService:
        def __init__(self, redis: RedisClient):
            self.redis = redis
            self._local_cache = {}
        
        async def get(self, key: str) -> str | None:
            # Check local cache first
            if key in self._local_cache:
                return self._local_cache[key]
            
            # Fall back to Redis
            value = await self.redis.get(key)
            if value:
                self._local_cache[key] = value
            return value
        
        async def set(self, key: str, value: str) -> None:
            self._local_cache[key] = value
            await self.redis.set(key, value)


def metrics_extension(app: Application) -> None:
    """Add metrics collection."""
    
    @singleton
    class MetricsCollector:
        def __init__(self):
            self.counters = {}
            self.gauges = {}
        
        def increment(self, name: str, value: int = 1) -> None:
            self.counters[name] = self.counters.get(name, 0) + value
        
        def gauge(self, name: str, value: float) -> None:
            self.gauges[name] = value
        
        def get_metrics(self) -> dict:
            return {
                "counters": self.counters,
                "gauges": self.gauges,
            }
    
    app.container.register_singleton(MetricsCollector, MetricsCollector)


# Using Extensions
# ================

async def main():
    # Method 1: Using extend()
    app1 = Application()
    app1.extend(redis_extension)
    app1.extend(cache_extension)
    app1.extend(metrics_extension)
    
    # Method 2: Using use() for multiple extensions
    app2 = Application().use(
        redis_extension,
        cache_extension,
        metrics_extension,
    )
    
    # Method 3: Inline extensions with lambdas
    app3 = (
        Application()
        .use(redis_extension, cache_extension)
        .extend(lambda app: app.container.register_singleton(
            str, instance="Hello World", name="greeting"
        ))
    )
    
    # Method 4: Using configuration
    from whiskey import ApplicationConfig
    
    app4 = Application(ApplicationConfig(
        name="MyApp",
        extensions=[redis_extension, cache_extension, metrics_extension]
    ))
    
    # Example: Using the extended application
    print("\n=== Using Extended Application ===")
    
    async with app2.lifespan():
        # Services are available via DI
        @inject
        async def demo(cache: CacheService, metrics: MetricsCollector):
            # Use cache
            await cache.set("user:123", "John Doe")
            user = await cache.get("user:123")
            print(f"Cached user: {user}")
            
            # Track metrics
            metrics.increment("cache_hits")
            metrics.gauge("cache_size", 1.0)
            
            print(f"Metrics: {metrics.get_metrics()}")
        
        await demo()


# First-party extensions
# ======================

async def example_with_first_party():
    """Example using first-party extensions."""
    from whiskey_ai import ai_extension
    from whiskey_asgi import asgi_extension
    
    # Create app with AI and web capabilities
    app = (
        Application()
        .use(ai_extension, asgi_extension)
        .use(redis_extension, cache_extension)
    )
    
    print("\n=== First-Party Extensions ===")
    print(f"Available scopes: {list(app.container.scope_manager._custom_scopes.keys())}")
    
    # The app now has:
    # - AI scopes (session, conversation, ai_context, batch, stream)
    # - ASGI capabilities (ASGIApp service)
    # - Redis and cache services


# Creating reusable extension packages
# ====================================

def create_database_extension(connection_string: str):
    """Factory function that creates a configured extension."""
    def database_extension(app: Application) -> None:
        @singleton
        class Database:
            def __init__(self):
                self.connection_string = connection_string
            
            async def initialize(self):
                print(f"Connecting to database: {connection_string}")
            
            async def query(self, sql: str) -> list:
                return [{"id": 1, "name": "test"}]
        
        app.service(Database)
    
    return database_extension


# Using the factory
db_extension = create_database_extension("postgresql://localhost/mydb")
app_with_db = Application().extend(db_extension)


if __name__ == "__main__":
    asyncio.run(main())
    asyncio.run(example_with_first_party())