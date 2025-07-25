"""
Scopes and Lifecycle Example

This example demonstrates advanced container concepts:
- Service scopes (singleton, transient, scoped)
- Custom scopes with context variables
- Service lifecycle management
- Resource cleanup and disposal

Run this example:
    python examples/02_scopes_and_lifecycle.py
"""

import asyncio
from typing import Annotated

from whiskey import Container, inject, provide, singleton, factory, scoped, Inject
from whiskey.core.scopes import ContextVarScope
from whiskey.core.types import Initializable, Disposable


# Step 1: Services with Lifecycle Management
# ===========================================

class DatabaseConnection(Initializable, Disposable):
    """Database connection with proper lifecycle."""
    
    def __init__(self, connection_string: str = "postgresql://localhost/myapp"):
        self.connection_string = connection_string
        self.connected = False
        self._queries_executed = 0
        print(f"🗄️ Database connection created for: {connection_string}")
    
    async def initialize(self):
        """Initialize the database connection."""
        print("🔌 Connecting to database...")
        await asyncio.sleep(0.1)  # Simulate connection time
        self.connected = True
        print("✅ Database connected")
    
    async def dispose(self):
        """Clean up the database connection."""
        print("🔌 Disconnecting from database...")
        await asyncio.sleep(0.05)  # Simulate cleanup
        self.connected = False
        print("✅ Database disconnected") 
    
    async def query(self, sql: str) -> list[dict]:
        """Execute a query."""
        if not self.connected:
            raise RuntimeError("Database not connected")
        
        self._queries_executed += 1
        print(f"📊 Query #{self._queries_executed}: {sql}")
        return [{"id": 1, "result": f"data_for_{sql}"}]
    
    @property
    def queries_executed(self) -> int:
        return self._queries_executed


@singleton
class ConfigService:
    """Global configuration service (singleton)."""
    
    def __init__(self):
        print("⚙️ ConfigService initialized (singleton)")
        self.settings = {
            "app_name": "WhiskeyApp",
            "version": "1.0.0",
            "debug": True
        }
    
    def get(self, key: str, default=None):
        """Get a configuration value."""
        return self.settings.get(key, default)


class RequestContext:
    """Request-scoped context information."""
    
    def __init__(self):
        self.request_id = f"req_{id(self)}"
        self.user_id = None
        self.start_time = asyncio.get_event_loop().time()
        print(f"🔍 RequestContext created: {self.request_id}")
    
    def set_user(self, user_id: int):
        """Set the current user for this request."""
        self.user_id = user_id
        print(f"👤 User {user_id} set for request {self.request_id}")
    
    @property
    def duration(self) -> float:
        """Get the request duration so far."""
        return asyncio.get_event_loop().time() - self.start_time


@factory
def create_session_id() -> str:
    """Factory function that creates unique session IDs."""
    import time
    session_id = f"session_{int(time.time() * 1000)}"
    print(f"🆔 Created session ID: {session_id}")
    return session_id


# Step 2: Services Using Different Scopes
# ========================================

@provide
class UserService:
    """User service that uses various scoped dependencies."""
    
    def __init__(self,
                 db: Annotated[DatabaseConnection, Inject()],
                 config: Annotated[ConfigService, Inject()],
                 request_ctx: Annotated[RequestContext, Inject()],
                 session_id: Annotated[str, Inject()]):
        self.db = db
        self.config = config
        self.request_ctx = request_ctx
        self.session_id = session_id
        print(f"👤 UserService initialized for {request_ctx.request_id}")
    
    async def get_user(self, user_id: int) -> dict:
        """Get user information."""
        self.request_ctx.set_user(user_id)
        
        app_name = self.config.get("app_name")
        users = await self.db.query(f"SELECT * FROM users WHERE id = {user_id}")
        
        return {
            "user": users[0] if users else None,
            "app_name": app_name,
            "request_id": self.request_ctx.request_id,
            "session_id": self.session_id,
            "request_duration": self.request_ctx.duration
        }


@provide 
class AuditService:
    """Service that logs user actions."""
    
    def __init__(self,
                 db: Annotated[DatabaseConnection, Inject()],
                 request_ctx: Annotated[RequestContext, Inject()]):
        self.db = db
        self.request_ctx = request_ctx
        print(f"📋 AuditService initialized for {self.request_ctx.request_id}")
    
    async def log_action(self, action: str):
        """Log a user action."""
        user_id = self.request_ctx.user_id or "anonymous"
        await self.db.query(f"INSERT INTO audit_log (user_id, action, request_id) VALUES ({user_id}, '{action}', '{self.request_ctx.request_id}')")
        print(f"📝 Logged action: {action} for user {user_id}")


# Step 3: Custom Scopes
# ======================

async def demonstrate_basic_scopes():
    """Demonstrate singleton, transient, and factory scopes."""
    print("\n" + "=" * 50)
    print("BASIC SCOPES DEMONSTRATION")
    print("=" * 50)
    
    container = Container()
    
    # Register services with different scopes
    container.singleton(ConfigService, ConfigService)  # One instance globally
    container[DatabaseConnection] = DatabaseConnection  # New instance each time (transient)
    container.factory(str, create_session_id)  # Factory function called each time
    
    print("\n1. Singleton behavior (ConfigService):")
    config1 = await container.resolve(ConfigService)
    config2 = await container.resolve(ConfigService)
    print(f"   Same ConfigService instance: {config1 is config2}")
    
    print("\n2. Transient behavior (DatabaseConnection):")
    db1 = await container.resolve(DatabaseConnection) 
    db2 = await container.resolve(DatabaseConnection)
    print(f"   Same DatabaseConnection instance: {db1 is db2}")
    
    print("\n3. Factory behavior (session ID):")
    session1 = await container.resolve(str)
    session2 = await container.resolve(str)
    print(f"   Same session ID: {session1 == session2}")
    
    # Cleanup
    await db1.dispose() if hasattr(db1, 'dispose') else None
    await db2.dispose() if hasattr(db2, 'dispose') else None


async def demonstrate_custom_scopes():
    """Demonstrate custom scopes using ContextVarScope."""
    print("\n" + "=" * 50)
    print("CUSTOM SCOPES DEMONSTRATION")
    print("=" * 50)
    
    container = Container()
    
    # Create a custom scope for request-level services
    request_scope = ContextVarScope("request")
    
    # Register services with different scopes
    container.singleton(ConfigService, ConfigService)  # Global singleton
    container[DatabaseConnection] = DatabaseConnection  # Transient
    container.factory(str, create_session_id)  # Factory
    container.scoped(RequestContext, RequestContext, scope=request_scope)  # Request-scoped
    container[UserService] = UserService
    container[AuditService] = AuditService
    
    async def simulate_request(request_num: int):
        """Simulate processing a request with request-scoped services."""
        print(f"\n--- Request {request_num} ---")
        
        # Enter request scope
        async with request_scope:
            # All services resolved within this scope will share the same RequestContext
            user_service1 = await container.resolve(UserService)
            user_service2 = await container.resolve(UserService)
            audit_service = await container.resolve(AuditService)
            
            print(f"Same RequestContext: {user_service1.request_ctx is user_service2.request_ctx}")
            print(f"Same RequestContext (audit): {user_service1.request_ctx is audit_service.request_ctx}")
            
            # Use the services
            user_data = await user_service1.get_user(request_num * 100)
            await audit_service.log_action("get_user")
            
            print(f"User data: {user_data}")
            
            # Let the request run for a bit
            await asyncio.sleep(0.1)
            
            # Final audit
            await audit_service.log_action("request_complete")
            print(f"Request {request_num} duration: {user_service1.request_ctx.duration:.3f}s")
        
        print(f"Request {request_num} scope exited")
    
    # Simulate multiple concurrent requests
    await asyncio.gather(
        simulate_request(1),
        simulate_request(2),
        simulate_request(3)
    )


async def demonstrate_lifecycle_management():
    """Demonstrate proper service lifecycle management."""
    print("\n" + "=" * 50)
    print("LIFECYCLE MANAGEMENT DEMONSTRATION")
    print("=" * 50)
    
    container = Container()
    
    # Register services
    container[DatabaseConnection] = DatabaseConnection
    container.singleton(ConfigService, ConfigService)
    
    print("\n1. Manual lifecycle management:")
    
    # Resolve and initialize services
    db = await container.resolve(DatabaseConnection)
    config = await container.resolve(ConfigService)
    
    # Initialize services that need it
    if isinstance(db, Initializable):
        await db.initialize()
    
    # Use the services
    await db.query("SELECT 1")
    app_name = config.get("app_name")
    print(f"App name: {app_name}")
    
    # Dispose services that need cleanup
    if isinstance(db, Disposable):
        await db.dispose()
    
    print("\n2. Using container context manager for automatic lifecycle:")
    
    # Using context manager for automatic lifecycle management
    async with container:
        db = await container.resolve(DatabaseConnection)
        
        # Container automatically calls initialize() if service implements Initializable
        await db.query("SELECT 2")
        print(f"Queries executed: {db.queries_executed}")
        
        # Container automatically calls dispose() on exit if service implements Disposable


async def main():
    """Run all scope and lifecycle demonstrations."""
    print("🥃 Whiskey Scopes and Lifecycle Example")
    print("=" * 45)
    
    await demonstrate_basic_scopes()
    await demonstrate_custom_scopes()
    await demonstrate_lifecycle_management()
    
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print("Scopes demonstrated:")
    print("✅ Singleton - One instance globally")
    print("✅ Transient - New instance each resolution")
    print("✅ Factory - Function called each resolution")
    print("✅ Scoped - Instance per scope context")
    print("\nLifecycle demonstrated:")
    print("✅ Initializable - Services that need setup")
    print("✅ Disposable - Services that need cleanup")
    print("✅ Manual lifecycle management")
    print("✅ Automatic lifecycle with context manager")


if __name__ == "__main__":
    asyncio.run(main())