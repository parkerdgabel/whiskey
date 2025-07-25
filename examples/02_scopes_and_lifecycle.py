"""
Service Scopes and Lifecycle Example

This example demonstrates Whiskey's service lifecycle management:
- Singleton services (shared across application)
- Transient services (new instance per resolution)
- Scoped services (shared within a scope)
- Lifecycle hooks and cleanup

Run this example:
    python examples/02_scopes_and_lifecycle.py
"""

import asyncio
from contextlib import asynccontextmanager

from whiskey import Container, singleton, service, create_app, Scope


# Step 1: Define Services with Different Scopes
# ==============================================

@singleton
class DatabaseConnection:
    """Expensive resource - should be singleton."""
    
    def __init__(self):
        self.connection_id = f"conn_{id(self)}"
        print(f"🔌 Database connection created: {self.connection_id}")
    
    def execute(self, query: str) -> str:
        return f"[{self.connection_id}] Query: {query}"
    
    def dispose(self):
        """Called during cleanup."""
        print(f"🔌 Database connection closed: {self.connection_id}")


class RequestContext:
    """Per-request context information."""
    
    def __init__(self):
        self.request_id = f"req_{id(self)}"
        self.data = {}
        print(f"📨 Request context created: {self.request_id}")
    
    def set_data(self, key: str, value: str):
        self.data[key] = value
    
    def get_data(self, key: str) -> str:
        return self.data.get(key, "")


@service
class UserRepository:
    """Data access layer - transient by default."""
    
    def __init__(self, db: DatabaseConnection):
        self.db = db
        self.instance_id = f"repo_{id(self)}"
        print(f"📚 UserRepository created: {self.instance_id}")
    
    async def get_user(self, user_id: int) -> dict:
        result = self.db.execute(f"SELECT * FROM users WHERE id = {user_id}")
        return {"id": user_id, "name": f"User{user_id}", "query": result}


@service
class UserService:
    """Business logic - uses repository."""
    
    def __init__(self, repo: UserRepository, context: RequestContext):
        self.repo = repo
        self.context = context
        self.instance_id = f"service_{id(self)}"
        print(f"👤 UserService created: {self.instance_id}")
    
    async def process_user(self, user_id: int) -> dict:
        user = await self.repo.get_user(user_id)
        self.context.set_data("last_user", str(user_id))
        return user


async def demonstrate_singleton_vs_transient():
    """Show the difference between singleton and transient services."""
    print("\n🔄 Singleton vs Transient Demonstration")
    print("=" * 45)
    
    container = Container()
    
    # Register with explicit scopes
    container.add_singleton(DatabaseConnection, DatabaseConnection).build()
    container.add(UserRepository, UserRepository).build()  # Transient by default
    
    print("\nResolving services multiple times...")
    
    # Resolve multiple times
    db1 = await container.resolve(DatabaseConnection)
    db2 = await container.resolve(DatabaseConnection)
    repo1 = await container.resolve(UserRepository)
    repo2 = await container.resolve(UserRepository)
    
    print(f"\nSingleton DatabaseConnection:")
    print(f"  Instance 1: {db1.connection_id}")
    print(f"  Instance 2: {db2.connection_id}")
    print(f"  Same object: {db1 is db2}")  # True
    
    print(f"\nTransient UserRepository:")
    print(f"  Instance 1: {repo1.instance_id}")
    print(f"  Instance 2: {repo2.instance_id}")
    print(f"  Same object: {repo1 is repo2}")  # False


async def demonstrate_scoped_services():
    """Show scoped service behavior."""
    print("\n🎯 Scoped Services Demonstration")
    print("=" * 35)
    
    container = Container()
    
    # Register services with different scopes
    container.add_singleton(DatabaseConnection, DatabaseConnection).build()
    container.add_scoped(RequestContext, RequestContext, 'request').build()
    container.add(UserService, UserService).build()
    
    @asynccontextmanager
    async def request_scope():
        """Simulate a request scope."""
        print("\n📨 Starting request scope...")
        # In a real application, this would be handled by the framework
        yield
        print("📨 Ending request scope...")
    
    # Simulate two separate requests
    async with request_scope():
        print("\n--- Request 1 ---")
        service1a = await container.resolve(UserService)
        service1b = await container.resolve(UserService)
        
        user1 = await service1a.process_user(1)
        user2 = await service1b.process_user(2)
        
        print(f"Service 1a context: {service1a.context.request_id}")
        print(f"Service 1b context: {service1b.context.request_id}")
        print(f"Same context: {service1a.context is service1b.context}")
        print(f"Last user in context: {service1a.context.get_data('last_user')}")
    
    async with request_scope():
        print("\n--- Request 2 ---")
        service2a = await container.resolve(UserService)
        service2b = await container.resolve(UserService)
        
        user3 = await service2a.process_user(3)
        
        print(f"Service 2a context: {service2a.context.request_id}")
        print(f"Service 2b context: {service2b.context.request_id}")
        print(f"Same context: {service2a.context is service2b.context}")
        print(f"Last user in context: {service2a.context.get_data('last_user')}")


async def demonstrate_application_lifecycle():
    """Show application lifecycle management."""
    print("\n🚀 Application Lifecycle Demonstration")
    print("=" * 40)
    
    # Track startup and shutdown
    startup_called = False
    shutdown_called = False
    
    async def on_startup():
        nonlocal startup_called
        startup_called = True
        print("🚀 Application starting up...")
    
    async def on_shutdown():
        nonlocal shutdown_called
        shutdown_called = True
        print("🛑 Application shutting down...")
    
    # Create application with lifecycle hooks
    app = create_app() \
        .singleton(DatabaseConnection, DatabaseConnection).build() \
        .service(UserRepository, UserRepository).build() \
        .on_startup(on_startup) \
        .on_shutdown(on_shutdown) \
        .build_app()
    
    print("\nUsing application with lifecycle management:")
    
    # Use application as context manager
    async with app:
        print(f"Startup called: {startup_called}")
        
        # Use services
        repo = await app.resolve_async(UserRepository)
        user = await repo.get_user(42)
        print(f"Retrieved user: {user['name']}")
    
    print(f"Shutdown called: {shutdown_called}")


async def demonstrate_performance_monitoring():
    """Show performance monitoring capabilities."""
    print("\n📊 Performance Monitoring Demonstration")
    print("=" * 42)
    
    from whiskey.core.performance import PerformanceMonitor
    
    container = Container()
    container.add_singleton(DatabaseConnection, DatabaseConnection).build()
    container.add(UserRepository, UserRepository).build()
    container.add(UserService, UserService).build()
    container.add(RequestContext, RequestContext).build()
    
    # Monitor performance
    with PerformanceMonitor() as metrics:
        # Perform various operations
        for i in range(5):
            service = await container.resolve(UserService)
            user = await service.process_user(i + 1)
    
    # Print performance report
    print(metrics.generate_report())


async def main():
    """Run all scope and lifecycle demonstrations."""
    print("🥃 Whiskey Scopes and Lifecycle Example")
    print("=" * 45)
    
    await demonstrate_singleton_vs_transient()
    await demonstrate_scoped_services()
    await demonstrate_application_lifecycle()
    await demonstrate_performance_monitoring()
    
    print("\n✅ All demonstrations completed!")


if __name__ == "__main__":
    asyncio.run(main())