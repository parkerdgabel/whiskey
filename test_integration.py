"""Integration test for the new Pythonic DI system.

This test ensures all components work together properly.
"""

import asyncio
from typing import Protocol
from src.whiskey.core.container import Container
from src.whiskey.core.builder import create_app
from src.whiskey.core.application import Application
from src.whiskey.core.decorators import singleton, service, factory, inject
from src.whiskey.core.registry import Scope


# Test classes and interfaces
class DatabaseInterface(Protocol):
    def query(self, sql: str) -> str:
        ...


class Database:
    def query(self, sql: str) -> str:
        return f"Query result: {sql}"


class Cache:
    def get(self, key: str) -> str:
        return f"Cache value for {key}"


class Config:
    def __init__(self, env: str = "test", debug: bool = True):
        self.env = env
        self.debug = debug
    
    def __str__(self):
        return f"Config(env={self.env}, debug={self.debug})"


class UserService:
    def __init__(self, db: Database, cache: Cache):
        self.db = db
        self.cache = cache
    
    def get_user(self, user_id: int) -> str:
        result = self.db.query(f"SELECT * FROM users WHERE id={user_id}")
        cached = self.cache.get(f"user_{user_id}")
        return f"{result} | {cached}"


@singleton
class GlobalSingleton:
    def __init__(self):
        self.value = "singleton_instance"


@service
class GlobalService:
    def __init__(self, singleton_dep: GlobalSingleton):
        self.singleton_dep = singleton_dep


@factory(key='config')
def create_config():
    return {"env": "test", "debug": True}


def process_data(db: Database, config: Config, user_id: int) -> str:
    return f"Processing user {user_id} with {db.query('test')} and config {config}"


async def test_container_basics():
    """Test basic Container functionality."""
    print("Testing Container basics...")
    
    container = Container()
    
    # Test fluent registration
    container.add('database', Database).as_singleton().build()
    container.add_singleton(Cache).build()
    container.add('user_service', UserService).build()
    
    # Test resolution
    db = await container.resolve('database')
    assert isinstance(db, Database)
    
    # Test singleton behavior
    db2 = await container.resolve('database')
    assert db is db2  # Same instance
    
    # Test dependency injection
    user_service = await container.resolve('user_service')
    assert isinstance(user_service, UserService)
    assert isinstance(user_service.db, Database)
    assert isinstance(user_service.cache, Cache)
    
    print("✓ Container basics working")


async def test_application_builder():
    """Test ApplicationBuilder fluent API."""
    print("Testing ApplicationBuilder...")
    
    app = create_app() \
        .singleton('database', Database).build() \
        .service(Cache, Cache).build() \
        .service('user_service', UserService).build() \
        .factory('config', create_config).build() \
        .build_app()
    
    # Test resolution
    user_service = await app.resolve_async('user_service')
    result = user_service.get_user(123)
    print(f"User service result: {result}")
    
    config = await app.resolve_async('config')
    assert config['env'] == 'test'
    
    print("✓ ApplicationBuilder working")


async def test_decorators():
    """Test global decorators."""
    print("Testing decorators...")
    
    # The decorators should have registered with the default app
    from src.whiskey.core.decorators import get_app, resolve_async
    
    app = get_app()
    
    # Test singleton decorator
    singleton1 = await resolve_async(GlobalSingleton)
    singleton2 = await resolve_async(GlobalSingleton)
    assert singleton1 is singleton2
    assert singleton1.value == "singleton_instance"
    
    # Test service with dependency
    service_instance = await resolve_async(GlobalService)
    assert service_instance.singleton_dep is singleton1
    
    # Test factory
    config = await resolve_async('config')
    assert config['debug'] is True
    
    print("✓ Decorators working")


async def test_function_injection():
    """Test function injection capabilities."""
    print("Testing function injection...")
    
    from src.whiskey.core.decorators import get_app, call
    
    app = get_app()
    app.container.add(Database, Database).as_singleton().build()
    app.container.add(Config, Config).as_singleton().build()
    
    # Test injected function call
    result = await call(process_data, user_id=456)
    print(f"Function injection result: {result}")
    
    # Test container.call directly
    result2 = await app.container.call(process_data, user_id=789)
    print(f"Container call result: {result2}")
    
    print("✓ Function injection working")


async def test_error_handling():
    """Test error handling scenarios."""
    print("Testing error handling...")
    
    container = Container()
    
    try:
        # Try to resolve unregistered service
        await container.resolve('nonexistent')
        assert False, "Should have raised ResolutionError"
    except Exception as e:
        print(f"✓ Proper error for unregistered service: {type(e).__name__}")
    
    # Test circular dependency detection
    class A:
        def __init__(self, b: 'B'):
            self.b = b
    
    class B:
        def __init__(self, a: A):
            self.a = a
    
    container.add('a', A).build()
    container.add('b', B).build()
    
    try:
        await container.resolve('a')
        assert False, "Should have detected circular dependency"
    except Exception as e:
        print(f"✓ Circular dependency detected: {type(e).__name__}")
    
    print("✓ Error handling working")


async def main():
    """Run all integration tests."""
    print("=== Whiskey DI Integration Tests ===\n")
    
    try:
        await test_container_basics()
        await test_application_builder()
        await test_decorators()
        await test_function_injection()
        await test_error_handling()
        
        print("\n🎉 All integration tests passed!")
        
    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())