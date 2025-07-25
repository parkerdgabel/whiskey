"""Example showcasing Whiskey's Pythonic discovery mechanisms.

This example demonstrates:
1. Component discovery and auto-registration
2. Container introspection and debugging
3. Explicit injection with Annotated
4. Pythonic API design
"""

import asyncio
from typing import Annotated, Protocol

from whiskey import (
    Application,
    Container,
    Inject,
    discover_components,
    inject,
    singleton,
)


# Example domain: A modular notification system

class NotificationHandler(Protocol):
    """Protocol for notification handlers."""
    async def send(self, message: str, recipient: str) -> bool:
        ...


@singleton
class EmailHandler:
    """Handles email notifications."""
    def __init__(self):
        self.sent_count = 0
        print("📧 EmailHandler initialized")
    
    async def send(self, message: str, recipient: str) -> bool:
        print(f"📧 Sending email to {recipient}: {message}")
        self.sent_count += 1
        return True


class SmsHandler:
    """Handles SMS notifications."""
    def __init__(self):
        print("📱 SmsHandler initialized")
    
    async def send(self, message: str, recipient: str) -> bool:
        print(f"📱 Sending SMS to {recipient}: {message}")
        return True


class PushHandler:
    """Handles push notifications."""
    _notification_handler = True  # Custom marker for discovery
    
    def __init__(self):
        print("🔔 PushHandler initialized")
    
    async def send(self, message: str, recipient: str) -> bool:
        print(f"🔔 Sending push to {recipient}: {message}")
        return True


class NotificationService:
    """Main notification service using discovered handlers."""
    
    def __init__(self,
                 email: Annotated[EmailHandler, Inject()],
                 sms: Annotated[SmsHandler, Inject()] | None = None,
                 push: PushHandler | None = None):  # Optional, not injected
        self.handlers = []
        self.handlers.append(email)
        if sms:
            self.handlers.append(sms)
        if push:
            self.handlers.append(push)
        print(f"📬 NotificationService initialized with {len(self.handlers)} handlers")
    
    async def notify_all(self, message: str, recipient: str):
        """Send notification through all available handlers."""
        results = []
        for handler in self.handlers:
            result = await handler.send(message, recipient)
            results.append(result)
        return all(results)


async def demo_discovery():
    """Demonstrate discovery capabilities."""
    print("=== Component Discovery Demo ===\n")
    
    # Create container
    container = Container()
    
    # Discover components in this module
    print("🔍 Discovering components...")
    components = container.discover(__name__)
    print(f"Found {len(components)} components: {[c.__name__ for c in components]}")
    
    # Auto-register only handlers
    print("\n🔍 Auto-registering handlers with custom predicate...")
    handlers = container.discover(
        __name__,
        auto_register=True,
        predicate=lambda cls: cls.__name__.endswith('Handler')
    )
    print(f"Registered {len(handlers)} handlers")
    
    # Introspect the container
    print("\n🔬 Container introspection:")
    inspector = container.inspect()
    
    # List all services
    services = inspector.list_services()
    print(f"All registered services: {[s.__name__ for s in services]}")
    
    # List only singletons
    singletons = inspector.list_services(scope="singleton")
    print(f"Singleton services: {[s.__name__ for s in singletons]}")
    
    # Check resolution capability
    print(f"\n🔬 Can resolve NotificationService? {inspector.can_resolve(NotificationService)}")
    
    # Get detailed resolution report
    report = inspector.resolution_report(NotificationService)
    print("\n📊 NotificationService resolution report:")
    print(f"  Registered: {report['registered']}")
    print(f"  Dependencies:")
    for param, info in report['dependencies'].items():
        print(f"    - {param}: {info['actual_type'].__name__ if hasattr(info.get('actual_type'), '__name__') else info['actual_type']} (registered: {info['registered']})")
    
    # Resolve and use
    print("\n🚀 Resolving NotificationService...")
    service = await container.resolve(NotificationService)
    await service.notify_all("Hello from Whiskey!", "user@example.com")
    
    # Show singleton behavior
    print(f"\n📊 EmailHandler sent count: {service.handlers[0].sent_count}")
    service2 = await container.resolve(NotificationService)
    print(f"Same EmailHandler instance? {service.handlers[0] is service2.handlers[0]}")


async def demo_application_discovery():
    """Demonstrate Application-level discovery."""
    print("\n\n=== Application Discovery Demo ===\n")
    
    app = Application()
    
    # Discover with custom marker
    print("🔍 Discovering components with custom marker...")
    marked_components = app.discover(
        __name__,
        decorator_name="_notification_handler"
    )
    print(f"Found {len(marked_components)} marked components: {[c.__name__ for c in marked_components]}")
    
    # Auto-register and configure
    app.discover(__name__, auto_register=True)
    
    # List components with different filters
    print("\n📋 Component listing:")
    all_components = app.list_components()
    print(f"All components: {[c.__name__ for c in all_components]}")
    
    # Inspect specific component
    info = app.inspect_component(NotificationService)
    print(f"\n🔬 NotificationService inspection:")
    print(f"  Can resolve: {info['can_resolve']}")
    print(f"  Scope: {info['scope']}")
    
    # Use with lifecycle
    async with app.lifespan():
        # Everything is ready to use
        service = await app.container.resolve(NotificationService)
        await service.notify_all("App is ready!", "admin@example.com")


async def demo_inject_with_discovery():
    """Demonstrate @inject with discovered components."""
    print("\n\n=== @inject with Discovery Demo ===\n")
    
    # Create and configure container
    container = Container()
    container.discover(__name__, auto_register=True)
    
    @inject
    async def send_notifications(
        service: NotificationService,
        message: str = "Default message"
    ):
        """Function with injected dependencies."""
        print(f"\n📤 Sending notifications: '{message}'")
        await service.notify_all(message, "everyone@example.com")
        return True
    
    # Call with injection
    result = await send_notifications(message="Custom message")
    print(f"Success: {result}")
    
    # The function can still be called normally if needed
    manual_service = await container.resolve(NotificationService)
    result2 = await send_notifications(service=manual_service)
    print(f"Manual call success: {result2}")


async def demo_dependency_graph():
    """Demonstrate dependency graph visualization."""
    print("\n\n=== Dependency Graph Demo ===\n")
    
    container = Container()
    container.discover(__name__, auto_register=True)
    
    inspector = container.inspect()
    graph = inspector.dependency_graph()
    
    print("🌳 Dependency graph:")
    for service, deps in graph.items():
        if deps:
            print(f"  {service.__name__} → {[d.__name__ for d in deps if hasattr(d, '__name__')]}")
        else:
            print(f"  {service.__name__} (no dependencies)")


async def main():
    """Run all demonstrations."""
    await demo_discovery()
    await demo_application_discovery()
    await demo_inject_with_discovery()
    await demo_dependency_graph()
    
    print("\n✅ All demonstrations completed!")


if __name__ == "__main__":
    asyncio.run(main())