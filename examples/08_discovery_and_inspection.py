"""
Component Discovery and Inspection Example

This example demonstrates Whiskey's component discovery and introspection capabilities:
- Automatic component discovery in modules/packages
- Filtering components by criteria
- Container introspection and debugging
- Dependency analysis and visualization
- Resolution troubleshooting

Run this example:
    python examples/08_discovery_and_inspection.py
"""

import asyncio
from typing import Annotated, Protocol

from whiskey import (
    ComponentDiscoverer,
    Container,
    Inject,
    discover_components,
    scoped,
    singleton,
)

# Step 1: Define Service Architecture
# ===================================


# Protocols for interfaces
class Repository(Protocol):
    """Base repository interface."""

    async def find(self, item_id: int) -> dict | None: ...
    async def save(self, entity: dict) -> dict: ...


class Notifier(Protocol):
    """Base notification interface."""

    async def notify(self, message: str) -> None: ...


# Infrastructure Services
@singleton
class DatabaseConnection:
    """Shared database connection (singleton)."""

    def __init__(self):
        print("🔌 Database connection created (singleton)")
        self.connected = True
        self.queries = 0

    async def execute(self, query: str) -> list[dict]:
        """Execute a database query."""
        self.queries += 1
        print(f"📊 DB Query #{self.queries}: {query}")
        return [{"id": 1, "result": f"data_for_{query}"}]


@singleton
class ConfigService:
    """Application configuration service."""

    def __init__(self):
        print("⚙️ Configuration service initialized")
        self.settings = {"app_name": "DiscoveryDemo", "version": "1.0.0", "debug": True}

    def get(self, key: str, default=None):
        return self.settings.get(key, default)


# Repository Layer (will be discovered)
class UserRepository:
    """Repository for user data access."""

    _discoverable = True  # Marker for discovery
    _layer = "repository"

    def __init__(self, db: Annotated[DatabaseConnection, Inject()]):
        self.db = db
        print("👤 UserRepository created")

    async def find(self, item_id: int) -> dict | None:
        results = await self.db.execute(f"SELECT * FROM users WHERE id = {item_id}")
        return results[0] if results else None

    async def save(self, entity: dict) -> dict:
        await self.db.execute(f"INSERT INTO users VALUES ({entity})")
        print(f"💾 Saved user: {entity}")
        return entity


class ProductRepository:
    """Repository for product data access."""

    _discoverable = True
    _layer = "repository"

    def __init__(self, db: Annotated[DatabaseConnection, Inject()]):
        self.db = db
        print("📦 ProductRepository created")

    async def find(self, item_id: int) -> dict | None:
        results = await self.db.execute(f"SELECT * FROM products WHERE id = {item_id}")
        return results[0] if results else None

    async def save(self, entity: dict) -> dict:
        await self.db.execute(f"INSERT INTO products VALUES ({entity})")
        return entity


class OrderRepository:
    """Repository for order data access."""

    _discoverable = True
    _layer = "repository"

    def __init__(self, db: Annotated[DatabaseConnection, Inject()]):
        self.db = db
        print("🛒 OrderRepository created")

    async def find(self, item_id: int) -> dict | None:
        results = await self.db.execute(f"SELECT * FROM orders WHERE id = {item_id}")
        return results[0] if results else None


# Service Layer (will be discovered)
@scoped("request")
class UserService:
    """Service for user operations."""

    _discoverable = True
    _layer = "service"

    def __init__(
        self,
        user_repo: Annotated[UserRepository, Inject()],
        config: Annotated[ConfigService, Inject()],
    ):
        self.user_repo = user_repo
        self.config = config
        print("👤 UserService created")

    async def get_user(self, user_id: int) -> dict:
        app_name = self.config.get("app_name")
        user = await self.user_repo.find(user_id)
        return {"user": user, "app": app_name}


class OrderService:
    """Service for order processing."""

    _discoverable = True
    _layer = "service"

    def __init__(
        self,
        user_repo: Annotated[UserRepository, Inject()],
        product_repo: Annotated[ProductRepository, Inject()],
        order_repo: Annotated[OrderRepository, Inject()],
    ):
        self.user_repo = user_repo
        self.product_repo = product_repo
        self.order_repo = order_repo
        print("🛒 OrderService created")

    async def create_order(self, user_id: int, product_id: int) -> dict:
        user = await self.user_repo.find(user_id)
        product = await self.product_repo.find(product_id)

        if not user or not product:
            raise ValueError("User or product not found")

        order = {"id": 12345, "user_id": user_id, "product_id": product_id}
        await self.order_repo.save(order)
        return order


# Notification Layer (will be discovered)
class EmailNotifier:
    """Email notification service."""

    _discoverable = True
    _layer = "notification"

    async def notify(self, message: str) -> None:
        print(f"📧 Email: {message}")


class SMSNotifier:
    """SMS notification service."""

    _discoverable = True
    _layer = "notification"

    async def notify(self, message: str) -> None:
        print(f"📱 SMS: {message}")


class NotificationService:
    """Service that aggregates notifications."""

    _discoverable = True
    _layer = "service"

    def __init__(
        self, email: Annotated[EmailNotifier, Inject()], sms: Annotated[SMSNotifier, Inject()]
    ):
        self.email = email
        self.sms = sms
        print("🔔 NotificationService created")

    async def notify_order_created(self, order: dict):
        message = f"Order {order['id']} created!"
        await self.email.notify(message)
        await self.sms.notify(message)


# Non-discoverable classes (should be ignored)
class OrderDTO:
    """Data transfer object - not discoverable."""

    pass


class ValidationError(Exception):
    """Exception class - not discoverable."""

    pass


# Step 2: Discovery Demonstrations
# =================================


async def demonstrate_basic_discovery():
    """Show basic component discovery."""
    print("🔍 Basic Component Discovery")
    print("=" * 40)

    container = Container()
    discoverer = ComponentDiscoverer(container)

    # Example 1: Discover by naming pattern
    print("\n1️⃣ Discover Repository classes:")
    repositories = discoverer.discover_module(
        __name__, predicate=lambda cls: cls.__name__.endswith("Repository")
    )

    print(f"Found {len(repositories)} repositories:")
    for repo in repositories:
        print(f"  - {repo.__name__}")

    # Auto-register them
    discoverer.auto_register(repositories, scope="singleton")
    print("✅ Repositories auto-registered\n")

    # Example 2: Discover by marker attribute
    print("2️⃣ Discover classes with _discoverable marker:")
    discoverable = discoverer.discover_module(__name__, decorator_name="_discoverable")

    print(f"Found {len(discoverable)} discoverable components:")
    for comp in discoverable:
        layer = getattr(comp, "_layer", "unknown")
        print(f"  - {comp.__name__:<20} (layer: {layer})")
    print()

    # Example 3: Discover by layer
    print("3️⃣ Discover by layer attribute:")
    services = discoverer.discover_module(
        __name__, predicate=lambda cls: getattr(cls, "_layer", None) == "service"
    )

    print(f"Found {len(services)} service layer components:")
    for svc in services:
        print(f"  - {svc.__name__}")
    print()

    return container


async def demonstrate_advanced_discovery():
    """Show advanced discovery features."""
    print("\n🔬 Advanced Discovery Features")
    print("=" * 40)

    container = Container()

    # Use the convenience function with complex predicate
    def complex_predicate(cls):
        """Complex predicate for selective registration."""
        # Must be discoverable
        if not getattr(cls, "_discoverable", False):
            return False

        # Skip notification layer for this demo
        if getattr(cls, "_layer", None) == "notification":
            return False

        # Must not be a DTO or exception
        return not (cls.__name__.endswith("DTO") or issubclass(cls, Exception))

    components = discover_components(
        __name__, container=container, predicate=complex_predicate, auto_register=True
    )

    print(f"Auto-registered {len(components)} components with complex predicate:")
    for comp in components:
        layer = getattr(comp, "_layer", "unknown")
        print(f"  - {comp.__name__:<20} (layer: {layer})")

    return container


async def demonstrate_container_introspection():
    """Show container introspection capabilities."""
    print("\n\n🔬 Container Introspection")
    print("=" * 40)

    # Create fully populated container
    container = Container()

    # Register core services manually
    container.singleton(DatabaseConnection, DatabaseConnection)
    container.singleton(ConfigService, ConfigService)

    # Discover and register other components
    discover_components(
        __name__, container=container, decorator_name="_discoverable", auto_register=True
    )

    # Get inspector
    inspector = container.inspect()

    # Example 1: List all services
    print("\n1️⃣ All registered services:")
    services = inspector.list_services()
    for svc in services:
        # Get scope info
        if hasattr(container, "_service_scopes"):
            scope = container._service_scopes.get(svc, "transient")
        else:
            scope = "transient"
        print(f"  - {svc.__name__:<25} (scope: {scope})")
    print()

    # Example 2: Check resolution capability
    print("2️⃣ Resolution capability check:")
    test_types = [OrderService, NotificationService, OrderDTO, ValidationError]

    for test_type in test_types:
        can_resolve = inspector.can_resolve(test_type)
        status = "✅" if can_resolve else "❌"
        print(f"  {status} Can resolve {test_type.__name__}? {can_resolve}")
    print()

    # Example 3: Detailed resolution report
    print("3️⃣ Detailed resolution report for OrderService:")
    report = inspector.resolution_report(OrderService)

    print(f"  - Can resolve: {report['can_resolve']}")
    print(f"  - Registered: {report['registered']}")
    print("  - Dependencies:")

    for param_name, dep_info in report["dependencies"].items():
        status = "✅" if dep_info["registered"] else "❌"
        print(f"    {status} {param_name}: {dep_info['type'].__name__}")
    print()

    # Example 4: Dependency graph analysis
    print("4️⃣ Dependency graph analysis:")
    graph = inspector.dependency_graph()

    # Show direct dependencies
    print("\nDirect dependencies:")
    for service, deps in graph.items():
        if deps:
            print(f"\n  {service.__name__} depends on:")
            for dep in deps:
                print(f"    → {dep.__name__}")

    # Find root services (no dependencies)
    print("\nRoot services (no dependencies):")
    roots = [svc for svc, deps in graph.items() if not deps]
    for root in roots:
        print(f"  - {root.__name__}")

    # Find most depended upon
    dependency_count = {}
    for deps in graph.values():
        for dep in deps:
            dependency_count[dep] = dependency_count.get(dep, 0) + 1

    if dependency_count:
        print("\nMost depended upon services:")
        sorted_deps = sorted(dependency_count.items(), key=lambda x: x[1], reverse=True)
        for dep, count in sorted_deps[:3]:  # Top 3
            print(f"  - {dep.__name__}: {count} dependents")

    return container


async def demonstrate_resolution_debugging():
    """Show how to debug resolution issues."""
    print("\n\n🐛 Resolution Debugging")
    print("=" * 35)

    # Create container with missing dependencies
    container = Container()

    # Register some services but not all their dependencies
    container[UserRepository] = UserRepository
    container[OrderService] = OrderService
    # Missing: DatabaseConnection, ProductRepository, OrderRepository

    inspector = container.inspect()

    print("\n❌ Attempting to resolve OrderService with missing dependencies...")

    report = inspector.resolution_report(OrderService)

    if not report["can_resolve"]:
        print("\n🔍 Resolution Analysis:")
        print(f"OrderService registered: {report['registered']}")
        print("\nDependency chain analysis:")

        def analyze_dependency_chain(service_type, level=0):
            """Recursively analyze dependency chain."""
            indent = "  " * level
            sub_report = inspector.resolution_report(service_type)

            print(f"{indent}{service_type.__name__}:")
            print(f"{indent}  Registered: {sub_report['registered']}")
            print(f"{indent}  Can resolve: {sub_report['can_resolve']}")

            if sub_report["dependencies"]:
                print(f"{indent}  Dependencies:")
                for param, info in sub_report["dependencies"].items():
                    status = "✅" if info["registered"] else "❌"
                    print(f"{indent}    {status} {param}: {info['type'].__name__}")

                    # Recurse for unregistered dependencies
                    if not info["registered"] and level < 2:  # Prevent infinite recursion
                        analyze_dependency_chain(info["type"], level + 1)

        analyze_dependency_chain(OrderService)

        print("\n🔧 To fix these issues, register the missing services:")
        missing_services = []

        def find_missing_services(service_type, visited=None):
            if visited is None:
                visited = set()

            if service_type in visited:
                return
            visited.add(service_type)

            sub_report = inspector.resolution_report(service_type)
            if not sub_report["registered"]:
                missing_services.append(service_type)

            for _param, info in sub_report["dependencies"].items():
                if not info["registered"]:
                    find_missing_services(info["type"], visited)

        find_missing_services(OrderService)

        for missing in set(missing_services):
            print(f"  - container[{missing.__name__}] = {missing.__name__}")

    print("\n🔧 Fixing the issues...")
    container.singleton(DatabaseConnection, DatabaseConnection)
    container[ProductRepository] = ProductRepository
    container[OrderRepository] = OrderRepository

    if inspector.can_resolve(OrderService):
        print("✅ OrderService can now be resolved!")


async def demonstrate_practical_usage():
    """Demonstrate practical usage of discovered components."""
    print("\n\n🚀 Practical Usage Example")
    print("=" * 35)

    # Create and populate container
    container = Container()

    # Register core services
    container.singleton(DatabaseConnection, DatabaseConnection)
    container.singleton(ConfigService, ConfigService)

    # Discover and register all discoverable components
    components = discover_components(
        __name__, container=container, decorator_name="_discoverable", auto_register=True
    )

    print(f"\nAuto-discovered and registered {len(components)} components")

    # Use the services with proper scoping
    async with container:
        # Create request scope for request-scoped services
        async with container.scope("request"):
            print("\n--- Processing Order Request ---")

            # Resolve and use services
            order_service = await container.resolve(OrderService)
            user_service = await container.resolve(UserService)

            # Simulate business operations
            user = await user_service.get_user(123)
            print(f"Retrieved user: {user}")

            try:
                order = await order_service.create_order(123, 456)
                print(f"Created order: {order}")

                # Notify about the order (if notification services were registered)
                try:
                    notifier = await container.resolve(NotificationService)
                    await notifier.notify_order_created(order)
                except KeyError:
                    print("📝 Note: Notification services not registered in this demo")

            except ValueError as e:
                print(f"❌ Order creation failed: {e}")

        print("\n✅ Request scope ended - request-scoped services cleaned up")


async def main():
    """Run all discovery and introspection demonstrations."""
    print("🥃 Whiskey Component Discovery & Introspection")
    print("=" * 50)
    print("This example demonstrates:")
    print("- Automatic component discovery")
    print("- Filtering by predicates and markers")
    print("- Container introspection")
    print("- Dependency analysis")
    print("- Resolution debugging")
    print("- Practical usage patterns")

    await demonstrate_basic_discovery()
    await demonstrate_advanced_discovery()
    await demonstrate_container_introspection()
    await demonstrate_resolution_debugging()
    await demonstrate_practical_usage()

    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print("Discovery features demonstrated:")
    print("✅ Component discovery by naming patterns")
    print("✅ Discovery by marker attributes")
    print("✅ Complex predicate filtering")
    print("✅ Automatic registration")
    print("\nIntrospection features demonstrated:")
    print("✅ Service listing and scope detection")
    print("✅ Resolution capability checking")
    print("✅ Detailed dependency analysis")
    print("✅ Dependency graph visualization")
    print("✅ Resolution issue debugging")
    print("\nPractical benefits:")
    print("✅ Reduced boilerplate code")
    print("✅ Automated dependency management")
    print("✅ Better understanding of service architecture")
    print("✅ Easier troubleshooting")


if __name__ == "__main__":
    asyncio.run(main())
