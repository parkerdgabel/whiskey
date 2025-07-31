"""
Lazy Resolution Example

This example demonstrates how to use lazy resolution in Whiskey
to defer expensive dependency initialization until first access.
"""

import asyncio
import time
from typing import Annotated

from whiskey import Container, provide
from whiskey.core.decorators import Inject
from whiskey.core.lazy import Lazy, LazyDescriptor


# Expensive services that should be loaded lazily
class DatabaseConnection:
    def __init__(self, connection_string: str = "postgres://localhost"):
        print(f"🔌 Connecting to database: {connection_string}")
        time.sleep(0.5)  # Simulate slow connection
        self.connection_string = connection_string
        self.connected = True
        print("✅ Database connected successfully")

    def query(self, sql: str) -> list[dict]:
        if not self.connected:
            raise RuntimeError("Database not connected")
        print(f"🔍 Executing query: {sql}")
        return [{"id": 1, "name": "John"}, {"id": 2, "name": "Jane"}]

    def close(self):
        print("🔌 Closing database connection")
        self.connected = False


class ExternalAPIClient:
    def __init__(self, api_url: str = "https://api.example.com"):
        print(f"🌐 Initializing API client for: {api_url}")
        time.sleep(0.3)  # Simulate API client setup
        self.api_url = api_url
        self.session_id = f"session_{int(time.time())}"
        print(f"✅ API client ready with session: {self.session_id}")

    def fetch_data(self, endpoint: str) -> dict:
        print(f"📡 Fetching data from: {self.api_url}{endpoint}")
        return {"data": f"Response from {endpoint}", "session": self.session_id}


class HeavyComputationService:
    def __init__(self):
        print("🧮 Starting heavy computation service...")
        time.sleep(0.4)  # Simulate heavy initialization
        self.cache = {}
        self.initialized_at = time.time()
        print("✅ Heavy computation service ready")

    def compute(self, input_data: str) -> str:
        if input_data in self.cache:
            print(f"💨 Cache hit for: {input_data}")
            return self.cache[input_data]

        print(f"🔢 Computing result for: {input_data}")
        time.sleep(0.2)  # Simulate computation
        result = f"computed_{input_data}_{len(input_data)}"
        self.cache[input_data] = result
        return result


# Services that use lazy dependencies
class UserService:
    def __init__(
        self,
        # Lazy database - only connected when first used
        db: Lazy[DatabaseConnection],
        # Regular dependency - initialized immediately
        logger: Annotated["Logger", Inject()],
    ):
        self.db = db
        self.logger = logger
        print("👤 UserService created (database not yet connected)")

    async def get_user(self, user_id: int) -> dict:
        self.logger.log(f"Getting user {user_id}")

        # First access to db.value will trigger database connection
        print("📊 About to access database for the first time...")
        users = self.db.value.query(f"SELECT * FROM users WHERE id = {user_id}")

        if users:
            return users[0]
        return {"error": "User not found"}

    def is_db_connected(self) -> bool:
        return self.db.is_resolved and self.db.value.connected


class AnalyticsService:
    def __init__(
        self,
        # Lazy API client and computation service
        api_client: Lazy[ExternalAPIClient],
        compute_service: Lazy[HeavyComputationService],
    ):
        self.api_client = api_client
        self.compute_service = compute_service
        print("📈 AnalyticsService created (expensive services not yet loaded)")

    async def generate_report(self, report_type: str) -> dict:
        print(f"📋 Generating {report_type} report...")

        # Only initialize API client if we need external data
        if report_type == "external":
            print("🌐 Report needs external data, initializing API client...")
            external_data = self.api_client.value.fetch_data("/analytics")
        else:
            external_data = {"data": "internal data"}
            print("🏠 Using internal data only")

        # Only initialize computation service if we need heavy processing
        if report_type == "complex":
            print("🧮 Report needs heavy computation, initializing service...")
            processed_data = self.compute_service.value.compute(str(external_data))
        else:
            processed_data = "simple processing"
            print("⚡ Using simple processing")

        return {
            "report_type": report_type,
            "external_data": external_data,
            "processed_data": processed_data,
            "api_initialized": self.api_client.is_resolved,
            "compute_initialized": self.compute_service.is_resolved,
        }


# Using LazyDescriptor for class-level lazy attributes
class ApplicationService:
    # These create Lazy instances on first access
    database = LazyDescriptor(DatabaseConnection)
    api_client = LazyDescriptor(ExternalAPIClient)
    compute_service = LazyDescriptor(HeavyComputationService)

    def __init__(self):
        print("🚀 ApplicationService created (no dependencies loaded yet)")

    async def quick_operation(self) -> str:
        """Operation that doesn't need any expensive services."""
        print("⚡ Performing quick operation...")
        return "Quick result - no expensive services loaded"

    async def database_operation(self) -> dict:
        """Operation that only needs the database."""
        print("🗄️ Performing database operation...")
        # First access to self.database creates and resolves Lazy[DatabaseConnection]
        result = self.database.value.query("SELECT COUNT(*) FROM users")
        return {"operation": "database", "result": result}

    async def api_operation(self) -> dict:
        """Operation that only needs the API client."""
        print("🌐 Performing API operation...")
        # First access to self.api_client creates and resolves Lazy[ExternalAPIClient]
        result = self.api_client.value.fetch_data("/status")
        return {"operation": "api", "result": result}

    async def complex_operation(self) -> dict:
        """Operation that needs all services."""
        print("🎯 Performing complex operation...")

        # All three services will be initialized on first access
        db_result = self.database.value.query("SELECT * FROM analytics")
        api_result = self.api_client.value.fetch_data("/complex")
        compute_result = self.compute_service.value.compute("complex_input")

        return {
            "operation": "complex",
            "database": db_result,
            "api": api_result,
            "computation": compute_result,
        }

    def get_initialization_status(self) -> dict:
        """Check which services have been initialized."""
        return {
            "database_initialized": hasattr(self, "_database_lazy") and self.database.is_resolved,
            "api_initialized": hasattr(self, "_api_client_lazy") and self.api_client.is_resolved,
            "compute_initialized": hasattr(self, "_compute_service_lazy")
            and self.compute_service.is_resolved,
        }


# Simple logger service
@provide
class Logger:
    def __init__(self):
        print("📝 Logger initialized")

    def log(self, message: str):
        print(f"📝 LOG: {message}")


# Service demonstrating lazy named dependencies
class MultiDatabaseService:
    def __init__(
        self,
        primary_db: Annotated[Lazy[DatabaseConnection], Inject(name="primary")],
        backup_db: Annotated[Lazy[DatabaseConnection], Inject(name="backup")],
    ):
        self.primary_db = primary_db
        self.backup_db = backup_db
        print("🏢 MultiDatabaseService created (no databases connected yet)")

    async def read_data(self, table: str) -> list[dict]:
        """Read from primary database, fallback to backup if needed."""
        try:
            print("📊 Attempting to read from primary database...")
            # This will initialize the primary database connection
            return self.primary_db.value.query(f"SELECT * FROM {table}")
        except Exception as e:
            print(f"❌ Primary database failed: {e}")
            print("🔄 Falling back to backup database...")
            # This will initialize the backup database connection
            return self.backup_db.value.query(f"SELECT * FROM {table}")

    def get_connection_status(self) -> dict:
        return {
            "primary_connected": self.primary_db.is_resolved,
            "backup_connected": self.backup_db.is_resolved,
        }


async def demonstrate_basic_lazy_loading():
    """Demonstrate basic lazy loading concepts."""
    print("\n" + "=" * 60)
    print("BASIC LAZY LOADING DEMONSTRATION")
    print("=" * 60)

    container = Container()

    # Register services
    container[DatabaseConnection] = DatabaseConnection
    container[UserService] = UserService
    container[Logger] = Logger

    print("\n1. Creating UserService...")
    start_time = time.time()
    user_service = await container.resolve(UserService)
    creation_time = time.time() - start_time
    print(f"⏱️ UserService created in {creation_time:.3f}s")
    print(f"🔍 Database connected yet? {user_service.is_db_connected()}")

    print("\n2. First database access...")
    start_time = time.time()
    user = await user_service.get_user(1)
    first_access_time = time.time() - start_time
    print(f"⏱️ First database access took {first_access_time:.3f}s")
    print(f"👤 User: {user}")
    print(f"🔍 Database connected now? {user_service.is_db_connected()}")

    print("\n3. Second database access...")
    start_time = time.time()
    user2 = await user_service.get_user(2)
    second_access_time = time.time() - start_time
    print(f"⏱️ Second database access took {second_access_time:.3f}s")
    print(f"👤 User: {user2}")


async def demonstrate_selective_initialization():
    """Demonstrate how lazy loading allows selective initialization."""
    print("\n" + "=" * 60)
    print("SELECTIVE INITIALIZATION DEMONSTRATION")
    print("=" * 60)

    container = Container()

    # Register all services
    container[ExternalAPIClient] = ExternalAPIClient
    container[HeavyComputationService] = HeavyComputationService
    container[AnalyticsService] = AnalyticsService

    print("\n1. Creating AnalyticsService...")
    analytics = await container.resolve(AnalyticsService)

    print("\n2. Generating simple report (no external dependencies)...")
    simple_report = await analytics.generate_report("simple")
    print(f"📋 Simple report: {simple_report}")

    print("\n3. Generating external report (needs API client)...")
    external_report = await analytics.generate_report("external")
    print(f"📋 External report: {external_report}")

    print("\n4. Generating complex report (needs computation service)...")
    complex_report = await analytics.generate_report("complex")
    print(f"📋 Complex report: {complex_report}")


async def demonstrate_lazy_descriptors():
    """Demonstrate LazyDescriptor usage."""
    print("\n" + "=" * 60)
    print("LAZY DESCRIPTORS DEMONSTRATION")
    print("=" * 60)

    container = Container()

    # Register services
    container[DatabaseConnection] = DatabaseConnection
    container[ExternalAPIClient] = ExternalAPIClient
    container[HeavyComputationService] = HeavyComputationService
    container[ApplicationService] = ApplicationService

    # Set container context for LazyDescriptor
    with container:
        print("\n1. Creating ApplicationService...")
        app = await container.resolve(ApplicationService)

        print(f"\n2. Initial status: {app.get_initialization_status()}")

        print("\n3. Performing quick operation...")
        quick_result = await app.quick_operation()
        print(f"⚡ Result: {quick_result}")
        print(f"📊 Status after quick op: {app.get_initialization_status()}")

        print("\n4. Performing database operation...")
        db_result = await app.database_operation()
        print(f"🗄️ Result: {db_result}")
        print(f"📊 Status after db op: {app.get_initialization_status()}")

        print("\n5. Performing API operation...")
        api_result = await app.api_operation()
        print(f"🌐 Result: {api_result}")
        print(f"📊 Status after API op: {app.get_initialization_status()}")

        print("\n6. Performing complex operation...")
        complex_result = await app.complex_operation()
        print(f"🎯 Result: {complex_result}")
        print(f"📊 Final status: {app.get_initialization_status()}")


async def demonstrate_lazy_named_dependencies():
    """Demonstrate lazy resolution with named dependencies."""
    print("\n" + "=" * 60)
    print("LAZY NAMED DEPENDENCIES DEMONSTRATION")
    print("=" * 60)

    container = Container()

    # Register named database connections
    container[DatabaseConnection, "primary"] = lambda: DatabaseConnection("postgres://primary-db")
    container[DatabaseConnection, "backup"] = lambda: DatabaseConnection("postgres://backup-db")
    container[MultiDatabaseService] = MultiDatabaseService

    print("\n1. Creating MultiDatabaseService...")
    multi_db = await container.resolve(MultiDatabaseService)
    print(f"🔍 Connection status: {multi_db.get_connection_status()}")

    print("\n2. Reading data (will connect to primary)...")
    data = await multi_db.read_data("users")
    print(f"📊 Data: {data}")
    print(f"🔍 Connection status: {multi_db.get_connection_status()}")


async def main():
    """Run all lazy resolution demonstrations."""
    print("=== Lazy Resolution Example ===")

    await demonstrate_basic_lazy_loading()
    await asyncio.sleep(0.5)

    await demonstrate_selective_initialization()
    await asyncio.sleep(0.5)

    await demonstrate_lazy_descriptors()
    await asyncio.sleep(0.5)

    await demonstrate_lazy_named_dependencies()

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print("Lazy resolution benefits:")
    print("✅ Faster application startup")
    print("✅ Reduced memory usage")
    print("✅ Pay-per-use initialization")
    print("✅ Better resource management")
    print("✅ Conditional service loading")
    print("✅ Works with named dependencies")
    print("✅ Transparent proxy access")


if __name__ == "__main__":
    asyncio.run(main())
