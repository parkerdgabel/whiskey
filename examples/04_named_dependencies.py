"""
Named Dependencies Example

This example demonstrates how to use named dependencies in Whiskey
to register multiple implementations of the same interface.
"""

import asyncio
from typing import Annotated, Protocol

from whiskey import Container, factory, provide
from whiskey.core.decorators import Inject


# Database interface
class Database(Protocol):
    async def query(self, sql: str) -> list[dict]: ...

    async def execute(self, sql: str) -> bool: ...


# Different database implementations
class PostgresDB:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        print(f"PostgresDB connected to: {connection_string}")

    async def query(self, sql: str) -> list[dict]:
        print(f"PostgresDB executing query: {sql}")
        return [{"id": 1, "name": "John"}]

    async def execute(self, sql: str) -> bool:
        print(f"PostgresDB executing: {sql}")
        return True


class MySQLDB:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        print(f"MySQLDB connected to: {connection_string}")

    async def query(self, sql: str) -> list[dict]:
        print(f"MySQLDB executing query: {sql}")
        return [{"id": 2, "name": "Jane"}]

    async def execute(self, sql: str) -> bool:
        print(f"MySQLDB executing: {sql}")
        return True


# Cache implementations
@provide(name="redis")
class RedisCache:
    def __init__(self):
        print("RedisCache initialized")
        self.data = {}

    def get(self, key: str) -> str | None:
        return self.data.get(key)

    def set(self, key: str, value: str) -> None:
        self.data[key] = value
        print(f"RedisCache: Set {key} = {value}")


@provide(name="memory")
class MemoryCache:
    def __init__(self):
        print("MemoryCache initialized")
        self.data = {}

    def get(self, key: str) -> str | None:
        return self.data.get(key)

    def set(self, key: str, value: str) -> None:
        self.data[key] = value
        print(f"MemoryCache: Set {key} = {value}")


# Services using named dependencies
class UserRepository:
    def __init__(
        self,
        primary_db: Annotated[Database, Inject(name="primary")],
        readonly_db: Annotated[Database, Inject(name="readonly")],
    ):
        self.primary_db = primary_db
        self.readonly_db = readonly_db
        print("UserRepository initialized with named databases")

    async def find_user(self, user_id: int) -> dict:
        # Use readonly database for queries
        users = await self.readonly_db.query(f"SELECT * FROM users WHERE id = {user_id}")
        return users[0] if users else {}

    async def create_user(self, name: str) -> bool:
        # Use primary database for writes
        return await self.primary_db.execute(f"INSERT INTO users (name) VALUES ('{name}')")


class CacheService:
    def __init__(
        self,
        redis_cache: Annotated[RedisCache, Inject(name="redis")],
        memory_cache: Annotated[MemoryCache, Inject(name="memory")],
    ):
        self.redis_cache = redis_cache
        self.memory_cache = memory_cache
        print("CacheService initialized with named caches")

    def cache_user(self, user_id: int, user_data: dict):
        # Cache in both Redis and memory
        user_json = str(user_data)  # Simplified serialization
        self.redis_cache.set(f"user:{user_id}", user_json)
        self.memory_cache.set(f"user:{user_id}", user_json)


# Factory functions with names
@factory(Database, name="test")
def create_test_database() -> Database:
    """Create a test database."""
    print("Creating test database")
    return PostgresDB("postgres://test-db")


@factory(Database, name="analytics")
def create_analytics_database() -> Database:
    """Create analytics database."""
    print("Creating analytics database")
    return MySQLDB("mysql://analytics-db")


# Service that uses multiple named dependencies
class ApplicationService:
    def __init__(
        self,
        user_repo: Annotated[UserRepository, Inject()],
        cache_service: Annotated[CacheService, Inject()],
        test_db: Annotated[Database, Inject(name="test")],
        analytics_db: Annotated[Database, Inject(name="analytics")],
    ):
        self.user_repo = user_repo
        self.cache_service = cache_service
        self.test_db = test_db
        self.analytics_db = analytics_db
        print("ApplicationService initialized")

    async def process_user(self, user_id: int):
        # Find user using repository (which uses named databases)
        user = await self.user_repo.find_user(user_id)
        print(f"Found user: {user}")

        # Cache the user
        self.cache_service.cache_user(user_id, user)

        # Run analytics query
        await self.analytics_db.query(f"INSERT INTO user_views (user_id) VALUES ({user_id})")

        # Test database operations
        await self.test_db.execute(
            "CREATE TABLE IF NOT EXISTS test_users (id INT, name VARCHAR(50))"
        )

        return user


async def main():
    """Demonstrate named dependencies."""
    print("=== Named Dependencies Example ===\n")

    container = Container()

    # Register named database instances
    print("1. Registering named databases...")
    container[Database, "primary"] = PostgresDB("postgres://primary-db")
    container[Database, "readonly"] = PostgresDB("postgres://readonly-replica")

    # Register services and factories
    print("\n2. Registering services...")
    container[UserRepository] = UserRepository
    container[CacheService] = CacheService
    container[ApplicationService] = ApplicationService

    print("\n3. Resolving application service...")
    app_service = await container.resolve(ApplicationService)

    print("\n4. Processing user...")
    user = await app_service.process_user(123)

    print(f"\n5. Final result: {user}")

    print("\n6. Testing named resolution directly...")
    # Resolve named services directly
    primary_db = await container.resolve(Database, name="primary")
    test_db = await container.resolve(Database, name="test")
    redis_cache = await container.resolve(RedisCache, name="redis")

    print(f"Primary DB: {primary_db.connection_string}")
    print(f"Test DB: {test_db.connection_string}")
    print(f"Redis cache: {type(redis_cache).__name__}")

    print("\n7. Checking what's registered...")
    # Show all registered services
    print("Registered services:")
    for key in container.keys_full():
        service_type, name = key
        name_str = f"[{name}]" if name else ""
        print(f"  - {service_type.__name__}{name_str}")


if __name__ == "__main__":
    asyncio.run(main())
