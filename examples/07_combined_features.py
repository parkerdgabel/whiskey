"""
Combined Features Example

This example demonstrates how to use all three new Whiskey features together:
- Named Dependencies
- Conditional Registration  
- Lazy Resolution

This creates a realistic microservice application that showcases how these
features work together to create flexible, efficient dependency injection.
"""

import asyncio
import os
import time
from datetime import datetime
from typing import Annotated, Protocol

from whiskey import Container, provide, singleton, factory, inject
from whiskey.core.decorators import Inject, set_default_container
from whiskey.core.conditions import env_equals, env_exists, env_truthy, all_conditions
from whiskey.core.lazy import Lazy, LazyDescriptor


# === INTERFACES ===

class Database(Protocol):
    async def query(self, sql: str) -> list[dict]: ...
    async def execute(self, sql: str) -> bool: ...


class Cache(Protocol):
    def get(self, key: str) -> str | None: ...
    def set(self, key: str, value: str, ttl: int = 300) -> None: ...


class Logger(Protocol):
    def log(self, level: str, message: str) -> None: ...


class MetricsCollector(Protocol):
    def increment(self, metric: str, value: int = 1) -> None: ...
    def gauge(self, metric: str, value: float) -> None: ...


# === DATABASE IMPLEMENTATIONS ===

class PostgresDatabase:
    def __init__(self, connection_string: str):
        print(f"🐘 Connecting to PostgreSQL: {connection_string}")
        time.sleep(0.3)  # Simulate connection time
        self.connection_string = connection_string
        print("✅ PostgreSQL connected")
    
    async def query(self, sql: str) -> list[dict]:
        print(f"🐘 PostgreSQL query: {sql}")
        return [{"id": 1, "name": "John", "db": "postgres"}]
    
    async def execute(self, sql: str) -> bool:
        print(f"🐘 PostgreSQL execute: {sql}")
        return True


class MySQLDatabase:
    def __init__(self, connection_string: str):
        print(f"🗃️ Connecting to MySQL: {connection_string}")
        time.sleep(0.2)
        self.connection_string = connection_string
        print("✅ MySQL connected")
    
    async def query(self, sql: str) -> list[dict]:
        print(f"🗃️ MySQL query: {sql}")
        return [{"id": 2, "name": "Jane", "db": "mysql"}]
    
    async def execute(self, sql: str) -> bool:
        print(f"🗃️ MySQL execute: {sql}")
        return True


class SQLiteDatabase:
    def __init__(self):
        print("💾 Initializing SQLite database")
        time.sleep(0.1)
        print("✅ SQLite ready")
    
    async def query(self, sql: str) -> list[dict]:
        print(f"💾 SQLite query: {sql}")
        return [{"id": 3, "name": "Bob", "db": "sqlite"}]
    
    async def execute(self, sql: str) -> bool:
        print(f"💾 SQLite execute: {sql}")
        return True


# === CACHE IMPLEMENTATIONS ===

@provide(name="redis", condition=env_exists("REDIS_URL"))
class RedisCache:
    def __init__(self):
        redis_url = os.getenv("REDIS_URL", "redis://localhost")
        print(f"🔴 Connecting to Redis: {redis_url}")
        time.sleep(0.2)
        self.url = redis_url
        self.data = {}
        print("✅ Redis cache ready")
    
    def get(self, key: str) -> str | None:
        return self.data.get(key)
    
    def set(self, key: str, value: str, ttl: int = 300) -> None:
        self.data[key] = value
        print(f"🔴 Redis set: {key} = {value} (TTL: {ttl}s)")


@provide(name="memory", condition=lambda: not env_exists("REDIS_URL")())
class MemoryCache:
    def __init__(self):
        print("🧠 Initializing memory cache")
        self.data = {}
        print("✅ Memory cache ready")
    
    def get(self, key: str) -> str | None:
        return self.data.get(key)
    
    def set(self, key: str, value: str, ttl: int = 300) -> None:
        self.data[key] = value
        print(f"🧠 Memory set: {key} = {value}")


# === LOGGING IMPLEMENTATIONS ===

@provide(condition=env_equals("ENV", "development"))
class DevLogger:
    def __init__(self):
        print("📝 Development logger initialized")
    
    def log(self, level: str, message: str) -> None:
        emoji = {"info": "ℹ️", "warn": "⚠️", "error": "❌"}.get(level, "📝")
        print(f"{emoji} DEV [{level.upper()}]: {message}")


@provide(condition=env_equals("ENV", "production"))
class ProdLogger:
    def __init__(self):
        print("🏭 Production logger initialized")
    
    def log(self, level: str, message: str) -> None:
        timestamp = datetime.now().isoformat()
        print(f"[{timestamp}] PROD [{level.upper()}]: {message}")


# === METRICS IMPLEMENTATIONS ===

@singleton(condition=env_truthy("ENABLE_METRICS"))
class PrometheusMetrics:
    def __init__(self):
        print("📊 Prometheus metrics collector initialized")
        time.sleep(0.1)
        self.metrics = {}
        print("✅ Metrics ready")
    
    def increment(self, metric: str, value: int = 1) -> None:
        current = self.metrics.get(metric, 0)
        self.metrics[metric] = current + value
        print(f"📊 Metric {metric} += {value} (total: {self.metrics[metric]})")
    
    def gauge(self, metric: str, value: float) -> None:
        self.metrics[metric] = value
        print(f"📊 Gauge {metric} = {value}")


@singleton(condition=lambda: not env_truthy("ENABLE_METRICS")())
class NoOpMetrics:
    def __init__(self):
        print("🚫 No-op metrics collector (metrics disabled)")
    
    def increment(self, metric: str, value: int = 1) -> None:
        pass  # No-op
    
    def gauge(self, metric: str, value: float) -> None:
        pass  # No-op


# === DATABASE FACTORIES WITH CONDITIONS ===

@factory(Database, name="primary", condition=all_conditions(
    env_equals("DB_TYPE", "postgres"),
    env_exists("PRIMARY_DB_URL")
))
def create_primary_postgres() -> Database:
    url = os.getenv("PRIMARY_DB_URL")
    return PostgresDatabase(url)


@factory(Database, name="primary", condition=all_conditions(
    env_equals("DB_TYPE", "mysql"),
    env_exists("PRIMARY_DB_URL")
))
def create_primary_mysql() -> Database:
    url = os.getenv("PRIMARY_DB_URL")
    return MySQLDatabase(url)


@factory(Database, name="primary", condition=lambda: not env_exists("PRIMARY_DB_URL")())
def create_primary_sqlite() -> Database:
    return SQLiteDatabase()


@factory(Database, name="replica", condition=env_exists("REPLICA_DB_URL"))
def create_replica_db() -> Database:
    url = os.getenv("REPLICA_DB_URL")
    if "mysql" in url:
        return MySQLDatabase(url)
    else:
        return PostgresDatabase(url)


# === SERVICES USING ALL FEATURES ===

class UserRepository:
    def __init__(self,
                 # Named lazy database dependencies
                 primary_db: Annotated[Lazy[Database], Inject(name="primary")],
                 replica_db: Annotated[Lazy[Database], Inject(name="replica")],
                 # Named cache dependency
                 cache: Annotated[Cache, Inject(name="redis" if env_exists("REDIS_URL")() else "memory")],
                 # Regular dependencies
                 logger: Annotated[Logger, Inject()],
                 metrics: Annotated[MetricsCollector, Inject()]):
        
        self.primary_db = primary_db
        self.replica_db = replica_db
        self.cache = cache
        self.logger = logger
        self.metrics = metrics
        
        print("👥 UserRepository initialized")
        self.logger.log("info", "UserRepository ready")
    
    async def get_user(self, user_id: int) -> dict:
        cache_key = f"user:{user_id}"
        
        # Try cache first
        cached = self.cache.get(cache_key)
        if cached:
            self.logger.log("info", f"Cache hit for user {user_id}")
            self.metrics.increment("cache.hits")
            return {"cached": True, "data": cached}
        
        self.metrics.increment("cache.misses")
        
        # Use replica database for reads (lazy initialization)
        self.logger.log("info", f"Fetching user {user_id} from replica database")
        try:
            if hasattr(self, 'replica_db') and not self.replica_db.is_resolved:
                self.logger.log("info", "Initializing replica database connection...")
            
            users = await self.replica_db.value.query(f"SELECT * FROM users WHERE id = {user_id}")
            user_data = users[0] if users else {"error": "User not found"}
            
            # Cache the result
            self.cache.set(cache_key, str(user_data))
            self.metrics.increment("db.replica.queries")
            
            return user_data
            
        except Exception as e:
            self.logger.log("warn", f"Replica database failed, using primary: {e}")
            
            # Fallback to primary database
            if not self.primary_db.is_resolved:
                self.logger.log("info", "Initializing primary database connection...")
            
            users = await self.primary_db.value.query(f"SELECT * FROM users WHERE id = {user_id}")
            user_data = users[0] if users else {"error": "User not found"}
            self.metrics.increment("db.primary.queries")
            
            return user_data
    
    async def create_user(self, name: str) -> dict:
        # Always use primary database for writes
        self.logger.log("info", f"Creating user: {name}")
        
        if not self.primary_db.is_resolved:
            self.logger.log("info", "Initializing primary database connection for write...")
        
        success = await self.primary_db.value.execute(f"INSERT INTO users (name) VALUES ('{name}')")
        
        if success:
            self.metrics.increment("users.created")
            self.cache.set(f"user_created:{name}", "true")
            return {"status": "created", "name": name}
        else:
            self.logger.log("error", f"Failed to create user: {name}")
            return {"status": "error", "name": name}
    
    def get_connection_status(self) -> dict:
        return {
            "primary_connected": self.primary_db.is_resolved,
            "replica_connected": hasattr(self, 'replica_db') and self.replica_db.is_resolved
        }


# Service using LazyDescriptor with conditional dependencies
class ApplicationService:
    # Lazy descriptors for expensive services
    user_repo = LazyDescriptor(UserRepository)
    
    def __init__(self,
                 logger: Annotated[Logger, Inject()],
                 metrics: Annotated[MetricsCollector, Inject()]):
        self.logger = logger
        self.metrics = metrics
        print("🚀 ApplicationService initialized")
        self.logger.log("info", "Application service ready")
    
    async def health_check(self) -> dict:
        """Quick health check that doesn't initialize expensive services."""
        self.logger.log("info", "Performing health check")
        self.metrics.increment("health_checks")
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "services_initialized": {
                "user_repo": hasattr(self, '_user_repo_lazy') and self.user_repo.is_resolved
            }
        }
    
    async def process_user_request(self, action: str, user_id: int = None, name: str = None) -> dict:
        """Process user requests, initializing services as needed."""
        start_time = time.time()
        
        self.logger.log("info", f"Processing {action} request")
        self.metrics.increment(f"requests.{action}")
        
        try:
            if action == "get" and user_id:
                # This will initialize UserRepository on first access
                user = await self.user_repo.value.get_user(user_id)
                result = {"action": action, "user": user}
            
            elif action == "create" and name:
                user = await self.user_repo.value.create_user(name)
                result = {"action": action, "user": user}
            
            else:
                result = {"action": action, "error": "Invalid parameters"}
            
            # Add connection status
            if hasattr(self, '_user_repo_lazy'):
                result["connections"] = self.user_repo.value.get_connection_status()
            
            processing_time = time.time() - start_time
            self.metrics.gauge(f"request_duration.{action}", processing_time)
            
            return result
            
        except Exception as e:
            self.logger.log("error", f"Request processing failed: {e}")
            self.metrics.increment("requests.errors")
            return {"action": action, "error": str(e)}


def setup_environment(scenario: str):
    """Set up environment for different deployment scenarios."""
    # Clear environment
    vars_to_clear = [
        "ENV", "DB_TYPE", "PRIMARY_DB_URL", "REPLICA_DB_URL", 
        "REDIS_URL", "ENABLE_METRICS"
    ]
    for var in vars_to_clear:
        if var in os.environ:
            del os.environ[var]
    
    if scenario == "production":
        os.environ["ENV"] = "production"
        os.environ["DB_TYPE"] = "postgres"
        os.environ["PRIMARY_DB_URL"] = "postgres://prod-primary"
        os.environ["REPLICA_DB_URL"] = "postgres://prod-replica"
        os.environ["REDIS_URL"] = "redis://prod-cache"
        os.environ["ENABLE_METRICS"] = "true"
    
    elif scenario == "development":
        os.environ["ENV"] = "development"
        os.environ["DB_TYPE"] = "mysql"
        os.environ["PRIMARY_DB_URL"] = "mysql://dev-db"
        os.environ["ENABLE_METRICS"] = "true"
        # No replica or Redis in dev
    
    elif scenario == "testing":
        os.environ["ENV"] = "production"  # Use prod logger but simple setup
        # No external databases or cache - will use SQLite and memory
        os.environ["ENABLE_METRICS"] = "false"
    
    elif scenario == "local":
        os.environ["ENV"] = "development"
        os.environ["DB_TYPE"] = "postgres"
        os.environ["PRIMARY_DB_URL"] = "postgres://localhost"
        os.environ["REDIS_URL"] = "redis://localhost"
        os.environ["ENABLE_METRICS"] = "true"


async def run_scenario(scenario: str):
    """Run a complete scenario demonstrating all features."""
    print(f"\n{'='*60}")
    print(f"SCENARIO: {scenario.upper()}")
    print('='*60)
    
    setup_environment(scenario)
    
    # Show environment
    print("\n📋 Environment Configuration:")
    env_vars = ["ENV", "DB_TYPE", "PRIMARY_DB_URL", "REPLICA_DB_URL", "REDIS_URL", "ENABLE_METRICS"]
    for var in env_vars:
        value = os.getenv(var, "NOT SET")
        print(f"  {var}: {value}")
    
    # Create container and set as default
    container = Container()
    set_default_container(container)
    
    # Register the application service
    container[ApplicationService] = ApplicationService
    
    print(f"\n🔍 Registered Services:")
    for key in sorted(container.keys_full()):
        service_type, name = key
        name_str = f"[{name}]" if name else ""
        print(f"  - {service_type.__name__}{name_str}")
    
    try:
        print(f"\n🚀 Initializing ApplicationService...")
        start_time = time.time()
        app = await container.resolve(ApplicationService)
        init_time = time.time() - start_time
        print(f"⏱️ Initialization took {init_time:.3f}s")
        
        print(f"\n🏥 Health Check...")
        health = await app.health_check()
        print(f"Health: {health}")
        
        print(f"\n👤 Processing user requests...")
        
        # Get user (will initialize user repo and databases)
        get_result = await app.process_user_request("get", user_id=123)
        print(f"Get result: {get_result}")
        
        # Create user (uses already initialized services)
        create_result = await app.process_user_request("create", name="Alice")
        print(f"Create result: {create_result}")
        
        # Final health check to show initialized services
        final_health = await app.health_check()
        print(f"Final health: {final_health}")
        
    except Exception as e:
        print(f"❌ Scenario failed: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Run all scenarios to demonstrate combined features."""
    print("=== Combined Features Example ===")
    print("Demonstrating Named Dependencies + Conditional Registration + Lazy Resolution")
    
    scenarios = ["production", "development", "testing", "local"]
    
    for scenario in scenarios:
        await run_scenario(scenario)
        await asyncio.sleep(0.5)
    
    print(f"\n{'='*60}")
    print("SUMMARY - COMBINED FEATURES BENEFITS")
    print('='*60)
    print("🏷️  Named Dependencies:")
    print("   • Multiple implementations of same interface")
    print("   • Clear service identification")
    print("   • Flexible architecture")
    print("")
    print("🎯 Conditional Registration:")
    print("   • Environment-specific services")
    print("   • Feature flag support")
    print("   • Automatic fallbacks")
    print("")
    print("⚡ Lazy Resolution:")
    print("   • Faster startup times")
    print("   • Memory efficiency")
    print("   • On-demand initialization")
    print("")
    print("🎉 Combined Power:")
    print("   • Adaptive microservice architecture")
    print("   • Efficient resource utilization")
    print("   • Environment-aware deployments")
    print("   • Graceful degradation")


if __name__ == "__main__":
    asyncio.run(main())