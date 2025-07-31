"""Component discovery example showing auto-registration and introspection.

This example demonstrates:
- Automatic component discovery in modules/packages
- Filtering components by criteria
- Container introspection and debugging
- Dependency analysis and visualization

Run this example:
    python examples/discovery_example.py
"""

import asyncio
from typing import Annotated, Protocol

from whiskey import (
    ComponentDiscoverer,
    Container,
    Inject,
    Whiskey,
    discover_components,
    scoped,
    singleton,
)

# Step 1: Create a module structure with various components
# =========================================================


# Base interfaces (protocols)
class Repository(Protocol):
    """Base protocol for repositories."""

    async def find(self, id: int) -> dict | None: ...
    async def save(self, entity: dict) -> dict: ...


class Service(Protocol):
    """Base protocol for services."""

    pass


# Concrete implementations
@singleton
class DatabaseConnection:
    """Shared database connection."""

    def __init__(self):
        print("🔌 Creating database connection (singleton)")
        self.connected = True


class UserRepository:
    """Repository for user data access."""

    _service = True  # Custom marker for discovery

    def __init__(self, db: Annotated[DatabaseConnection, Inject()]):
        self.db = db
        print("👤 UserRepository created")

    async def find(self, id: int) -> dict | None:
        if self.db.connected:
            return {"id": id, "name": f"User {id}"}
        return None

    async def save(self, entity: dict) -> dict:
        print(f"💾 Saving user: {entity}")
        return entity


class ProductRepository:
    """Repository for product data access."""

    _service = True

    def __init__(self, db: Annotated[DatabaseConnection, Inject()]):
        self.db = db
        print("📦 ProductRepository created")

    async def find(self, id: int) -> dict | None:
        if self.db.connected:
            return {"id": id, "name": f"Product {id}", "price": id * 10.0}
        return None


@scoped("request")
class OrderService:
    """Service for order processing."""

    _service = True

    def __init__(
        self,
        user_repo: Annotated[UserRepository, Inject()],
        product_repo: Annotated[ProductRepository, Inject()],
    ):
        self.user_repo = user_repo
        self.product_repo = product_repo
        print("🛒 OrderService created")

    async def create_order(self, user_id: int, product_id: int) -> dict:
        user = await self.user_repo.find(user_id)
        product = await self.product_repo.find(product_id)

        if not user or not product:
            raise ValueError("User or product not found")

        return {"id": 12345, "user": user, "product": product, "total": product["price"]}


class EmailService:
    """Service for sending emails."""

    _service = True

    async def send_email(self, to: str, subject: str, body: str):
        print(f"📧 Sending email to {to}: {subject}")


class NotificationService:
    """Service for notifications - demonstrates optional injection."""

    _service = True

    def __init__(
        self, email: Annotated[EmailService, Inject()], sms_gateway: str = "default-gateway"
    ):  # Not injected
        self.email = email
        self.sms_gateway = sms_gateway
        print("🔔 NotificationService created")

    async def notify_order(self, order: dict):
        await self.email.send_email(
            to=order["user"]["name"] + "@example.com",
            subject="Order Confirmation",
            body=f"Your order #{order['id']} has been confirmed!",
        )


# Some non-service classes that shouldn't be discovered
class OrderDTO:
    """Data transfer object - not a service."""

    pass


class ValidationError(Exception):
    """Custom exception - not a service."""

    pass


# Step 2: Demonstrate discovery features
# ======================================


async def discovery_demo():
    """Show various discovery capabilities."""

    print("🔍 Component Discovery Demo")
    print("===========================\n")

    # Create container and discoverer
    container = Container()
    discoverer = ComponentDiscoverer(container)

    # Example 1: Discover by module with predicate
    # ============================================
    print("1️⃣ Discovering Repository classes:")

    # Find all classes ending with "Repository"
    repositories = discoverer.discover_module(
        __name__,  # Current module
        predicate=lambda cls: cls.__name__.endswith("Repository"),
    )

    print(f"Found {len(repositories)} repositories:")
    for repo in repositories:
        print(f"  - {repo.__name__}")

    # Auto-register them
    discoverer.auto_register(repositories, scope="singleton")
    print("✅ Repositories registered\n")

    # Example 2: Discover by decorator/marker
    # =======================================
    print("2️⃣ Discovering classes with _service marker:")

    services = discoverer.discover_module(
        __name__,
        decorator_name="_service",  # Look for _service attribute
    )

    print(f"Found {len(services)} services:")
    for svc in services:
        print(f"  - {svc.__name__}")
    print()

    # Example 3: Using the convenience function
    # =========================================
    print("3️⃣ Using discover_components helper:")

    # Discover and auto-register in one call
    components = discover_components(
        __name__,
        container=container,
        predicate=lambda cls: (
            cls.__name__.endswith("Service")
            and cls.__name__ != "EmailService"  # Exclude EmailService
        ),
        auto_register=True,
    )

    print(f"Auto-registered {len(components)} services\n")


async def introspection_demo():
    """Show container introspection capabilities."""

    print("\n🔬 Container Introspection Demo")
    print("================================\n")

    # Create and populate container
    container = Container()

    # Register all our components
    container.register(DatabaseConnection, scope="singleton")
    container.register(UserRepository, scope="singleton")
    container.register(ProductRepository, scope="singleton")
    container.register(OrderService, scope="request")
    container.register(EmailService)
    container.register(NotificationService)

    # Get inspector
    inspector = container.inspect()

    # Example 1: List all services
    # ============================
    print("1️⃣ All registered services:")
    services = inspector.list_services()
    for svc in services:
        scope = container._service_scopes.get(svc, "transient")
        print(f"  - {svc.__name__:<25} (scope: {scope})")
    print()

    # Example 2: Filter services
    # ==========================
    print("2️⃣ Singleton services only:")
    singletons = inspector.list_services(scope="singleton")
    for svc in singletons:
        print(f"  - {svc.__name__}")
    print()

    # Example 3: Check resolution capability
    # =====================================
    print("3️⃣ Resolution capability check:")

    # Can we resolve these?
    types_to_check = [OrderService, NotificationService, OrderDTO]

    for type_to_check in types_to_check:
        can_resolve = inspector.can_resolve(type_to_check)
        print(f"  - Can resolve {type_to_check.__name__}? {can_resolve}")
    print()

    # Example 4: Get resolution report
    # ================================
    print("4️⃣ Detailed resolution report for OrderService:")

    report = inspector.resolution_report(OrderService)
    print(f"  - Can resolve: {report['can_resolve']}")
    print(f"  - Scope: {report.get('scope', 'transient')}")
    print("  - Dependencies:")

    for dep_name, dep_info in report["dependencies"].items():
        status = "✅" if dep_info["registered"] else "❌"
        print(f"    {status} {dep_name}: {dep_info['type'].__name__}")
    print()

    # Example 5: Dependency graph
    # ===========================
    print("5️⃣ Dependency graph:")

    graph = inspector.dependency_graph()

    # Show dependencies for each service
    for service, deps in graph.items():
        if deps:
            print(f"\n  {service.__name__} depends on:")
            for dep in deps:
                print(f"    → {dep.__name__}")

    # Find services with no dependencies
    print("\n  Services with no dependencies:")
    for service, deps in graph.items():
        if not deps:
            print(f"    - {service.__name__}")

    # Find most depended upon
    dependency_count = {}
    for deps in graph.values():
        for dep in deps:
            dependency_count[dep] = dependency_count.get(dep, 0) + 1

    if dependency_count:
        print("\n  Most depended upon:")
        for dep, count in sorted(dependency_count.items(), key=lambda x: x[1], reverse=True):
            print(f"    - {dep.__name__}: {count} dependents")


async def usage_demo():
    """Show actual usage of discovered components."""

    print("\n\n🚀 Using Discovered Components")
    print("==============================\n")

    # Create application and discover components
    app = Whiskey()

    # Discover all services in this module
    components = app.discover(__name__, decorator_name="_service", auto_register=True)

    print(f"Discovered and registered {len(components)} components\n")

    # Also register the singleton
    app.component(DatabaseConnection)

    # Use the services
    async with app.lifespan():
        # Create an order (demonstrates dependency chain)
        async with app.container.scope("request"):
            order_service = await app.container.resolve(OrderService)
            order = await order_service.create_order(user_id=100, product_id=42)

            print(f"Created order: {order}\n")

            # Send notification
            notifier = await app.container.resolve(NotificationService)
            await notifier.notify_order(order)

        print("\n✅ Request scope ended, request-scoped services cleaned up")


async def debugging_demo():
    """Show how to debug resolution issues."""

    print("\n\n🐛 Debugging Resolution Issues")
    print("==============================\n")

    container = Container()

    # Register some but not all dependencies
    container.register(UserRepository)
    container.register(ProductRepository)
    # Oops! Forgot to register DatabaseConnection

    inspector = container.inspect()

    # Try to understand why OrderService can't be resolved
    print("❌ Trying to resolve OrderService without all dependencies...")

    report = inspector.resolution_report(OrderService)

    if not report["can_resolve"]:
        print("\nResolution failed! Let's debug:")
        print(f"OrderService registered: {report['registered']}")
        print("\nDependency analysis:")

        for param, info in report["dependencies"].items():
            if info["registered"]:
                print(f"  ✅ {param}: {info['type'].__name__} is registered")
            else:
                print(f"  ❌ {param}: {info['type'].__name__} is NOT registered")

                # Check what this dependency needs
                sub_report = inspector.resolution_report(info["type"])
                if not sub_report["can_resolve"]:
                    print(f"     → {info['type'].__name__} also has missing dependencies:")
                    for sub_param, sub_info in sub_report["dependencies"].items():
                        if not sub_info["registered"]:
                            print(f"        ❌ {sub_param}: {sub_info['type'].__name__}")

    print("\n🔧 Fixing the issue...")
    container.register(DatabaseConnection, scope="singleton")
    container.register(OrderService)

    # Check again
    if inspector.can_resolve(OrderService):
        print("✅ OrderService can now be resolved!")


# Step 3: Run all demonstrations
# ==============================


async def main():
    """Run all discovery demonstrations."""

    print("🥃 Whiskey Discovery & Introspection Example")
    print("============================================\n")
    print("This example demonstrates:")
    print("- Automatic component discovery")
    print("- Filtering by predicate or decorator")
    print("- Container introspection")
    print("- Dependency analysis")
    print("- Resolution troubleshooting\n")

    # Run demos
    await discovery_demo()
    await introspection_demo()
    await usage_demo()
    await debugging_demo()

    print("\n✨ Discovery example completed!")
    print("\nKey takeaways:")
    print("- Use discovery to reduce boilerplate")
    print("- Filter components by name, interface, or marker")
    print("- Inspect container to debug resolution issues")
    print("- Analyze dependencies to understand your app structure")


if __name__ == "__main__":
    asyncio.run(main())
