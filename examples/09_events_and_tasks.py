"""
Events and Background Tasks Example

This example demonstrates Whiskey's event system and background task capabilities:
- Event emission and handling
- Wildcard event patterns
- Background task management
- Event-driven architecture patterns
- Task coordination and lifecycle

Run this example:
    python examples/09_events_and_tasks.py
"""

import asyncio
from typing import Annotated

from whiskey import ApplicationConfig, Inject, inject

# Step 1: Core Services for Event-Driven Architecture
# ====================================================


class EventStore:
    """Simple event store to track events."""

    def __init__(self):
        self.events = []
        print("📚 EventStore initialized")

    def record_event(self, event_type: str, data: dict):
        """Record an event."""
        event = {"type": event_type, "data": data, "timestamp": asyncio.get_event_loop().time()}
        self.events.append(event)
        print(f"📝 Event recorded: {event_type}")

    def get_events(self, event_type: str = None) -> list:
        """Get events, optionally filtered by type."""
        if event_type:
            return [e for e in self.events if e["type"] == event_type]
        return self.events.copy()


class MetricsCollector:
    """Service that collects application metrics."""

    def __init__(self):
        self.metrics = {
            "events_processed": 0,
            "tasks_started": 0,
            "errors_occurred": 0,
            "uptime_seconds": 0,
        }
        self.running = False
        print("📊 MetricsCollector initialized")

    def increment(self, metric: str, value: int = 1):
        """Increment a metric."""
        if metric in self.metrics:
            self.metrics[metric] += value

    def get_metrics(self) -> dict:
        """Get current metrics."""
        return self.metrics.copy()

    async def start_collection(self):
        """Start background metrics collection."""
        self.running = True
        print("📊 Starting metrics collection...")

        try:
            while self.running:
                self.metrics["uptime_seconds"] += 1

                # Log metrics every 10 seconds
                if self.metrics["uptime_seconds"] % 10 == 0:
                    print(f"📈 Metrics: {self.metrics}")

                await asyncio.sleep(1)
        except asyncio.CancelledError:
            print("📊 Metrics collection cancelled")
            raise
        finally:
            self.running = False

    def stop(self):
        """Stop metrics collection."""
        self.running = False


class NotificationService:
    """Service for sending notifications."""

    def __init__(self):
        self.sent_notifications = 0
        print("📧 NotificationService initialized")

    async def send_email(self, recipient: str, subject: str, body: str):
        """Send an email notification."""
        self.sent_notifications += 1
        print(f"📧 Email to {recipient}: {subject}")
        await asyncio.sleep(0.1)  # Simulate sending

    async def send_sms(self, recipient: str, message: str):
        """Send an SMS notification."""
        self.sent_notifications += 1
        print(f"📱 SMS to {recipient}: {message}")
        await asyncio.sleep(0.05)  # Simulate sending

    def get_stats(self) -> dict:
        """Get notification statistics."""
        return {"sent_notifications": self.sent_notifications}


# Step 2: Business Services that Emit Events
# ===========================================


class UserService:
    """User service that emits events for user operations."""

    def __init__(
        self,
        metrics: Annotated[MetricsCollector, Inject()],
        event_store: Annotated[EventStore, Inject()],
    ):
        self.metrics = metrics
        self.event_store = event_store
        self.users = {}
        self.next_id = 1
        print("👤 UserService initialized")

    async def create_user(self, name: str, email: str) -> dict:
        """Create a user and emit user.created event."""
        user = {
            "id": self.next_id,
            "name": name,
            "email": email,
            "created_at": asyncio.get_event_loop().time(),
        }
        self.users[self.next_id] = user
        self.next_id += 1

        # Record in event store
        self.event_store.record_event("user.created", user)

        print(f"👤 Created user: {name} (ID: {user['id']})")
        return user

    async def update_user(self, user_id: int, **updates) -> dict:
        """Update a user and emit user.updated event."""
        if user_id not in self.users:
            raise ValueError(f"User {user_id} not found")

        old_user = self.users[user_id].copy()
        self.users[user_id].update(updates)
        updated_user = self.users[user_id]

        # Record in event store
        self.event_store.record_event(
            "user.updated",
            {
                "user_id": user_id,
                "old_data": old_user,
                "new_data": updated_user,
                "changes": updates,
            },
        )

        print(f"👤 Updated user {user_id}: {updates}")
        return updated_user

    async def delete_user(self, user_id: int):
        """Delete a user and emit user.deleted event."""
        if user_id not in self.users:
            raise ValueError(f"User {user_id} not found")

        deleted_user = self.users.pop(user_id)

        # Record in event store
        self.event_store.record_event(
            "user.deleted", {"user_id": user_id, "deleted_user": deleted_user}
        )

        print(f"👤 Deleted user {user_id}")
        return deleted_user


class OrderService:
    """Order service that emits events for order operations."""

    def __init__(
        self,
        user_service: Annotated[UserService, Inject()],
        event_store: Annotated[EventStore, Inject()],
    ):
        self.user_service = user_service
        self.event_store = event_store
        self.orders = {}
        self.next_id = 1000
        print("🛒 OrderService initialized")

    async def create_order(self, user_id: int, items: list, total: float) -> dict:
        """Create an order and emit order.created event."""
        # Verify user exists
        if user_id not in self.user_service.users:
            raise ValueError(f"User {user_id} not found")

        order = {
            "id": self.next_id,
            "user_id": user_id,
            "items": items,
            "total": total,
            "status": "pending",
            "created_at": asyncio.get_event_loop().time(),
        }
        self.orders[self.next_id] = order
        self.next_id += 1

        # Record in event store
        self.event_store.record_event("order.created", order)

        print(f"🛒 Created order {order['id']} for user {user_id}")
        return order

    async def process_order(self, order_id: int) -> dict:
        """Process an order and emit order.processed event."""
        if order_id not in self.orders:
            raise ValueError(f"Order {order_id} not found")

        order = self.orders[order_id]
        order["status"] = "processed"
        order["processed_at"] = asyncio.get_event_loop().time()

        # Emit processing event
        self.event_store.record_event("order.processed", {"order_id": order_id, "order": order})

        print(f"🛒 Processed order {order_id}")
        return order

    async def ship_order(self, order_id: int, tracking_number: str) -> dict:
        """Ship an order and emit order.shipped event."""
        if order_id not in self.orders:
            raise ValueError(f"Order {order_id} not found")

        order = self.orders[order_id]
        order["status"] = "shipped"
        order["tracking_number"] = tracking_number
        order["shipped_at"] = asyncio.get_event_loop().time()

        # Emit shipping event
        self.event_store.record_event(
            "order.shipped",
            {"order_id": order_id, "tracking_number": tracking_number, "order": order},
        )

        print(f"🛒 Shipped order {order_id} (tracking: {tracking_number})")
        return order


# Step 3: Create Application with Event Handlers and Tasks
# =========================================================


async def main():
    """Demonstrate events and background tasks."""

    print("🥃 Whiskey Events and Background Tasks Example")
    print("=" * 55)

    # Create application
    app = Application(ApplicationConfig(name="EventDrivenApp", version="1.0.0", debug=True))

    # Register services
    app.component(EventStore)
    app.component(MetricsCollector)
    app.component(NotificationService)
    app.component(UserService)
    app.component(OrderService)

    # Step 3a: Event Handlers
    # =======================

    @app.on("user.created")
    @inject
    async def send_welcome_email(
        data: dict, notifier: NotificationService, metrics: MetricsCollector
    ):
        """Send welcome email when user is created."""
        user = data
        await notifier.send_email(
            user["email"], "Welcome!", f"Welcome to our platform, {user['name']}!"
        )
        metrics.increment("events_processed")
        print(f"✅ Welcome email sent to {user['name']}")

    @app.on("user.updated")
    @inject
    async def handle_user_update(data: dict, metrics: MetricsCollector):
        """Handle user update events."""
        changes = data["changes"]
        user_id = data["user_id"]
        print(f"🔄 User {user_id} updated: {list(changes.keys())}")
        metrics.increment("events_processed")

    @app.on("user.deleted")
    @inject
    async def handle_user_deletion(data: dict, metrics: MetricsCollector):
        """Handle user deletion events."""
        user_id = data["user_id"]
        deleted_user = data["deleted_user"]
        print(f"🗑️ User {user_id} ({deleted_user['name']}) has been deleted")
        metrics.increment("events_processed")

    @app.on("order.created")
    @inject
    async def handle_order_created(
        data: dict, notifier: NotificationService, metrics: MetricsCollector
    ):
        """Handle new order creation."""
        order = data
        user_service = await app.container.resolve(UserService)
        user = user_service.users[order["user_id"]]

        # Send order confirmation
        await notifier.send_email(
            user["email"], "Order Confirmation", f"Your order #{order['id']} has been received!"
        )

        # Send SMS notification
        await notifier.send_sms(
            "+1234567890",  # Mock phone number
            f"Order #{order['id']} confirmed - ${order['total']}",
        )

        metrics.increment("events_processed")
        print(f"✅ Order confirmation sent for order {order['id']}")

    @app.on("order.processed")
    @inject
    async def handle_order_processed(data: dict, metrics: MetricsCollector):
        """Handle order processing."""
        order_id = data["order_id"]
        print(f"⚙️ Order {order_id} has been processed")
        metrics.increment("events_processed")

    @app.on("order.shipped")
    @inject
    async def handle_order_shipped(
        data: dict, notifier: NotificationService, metrics: MetricsCollector
    ):
        """Handle order shipping."""
        order_id = data["order_id"]
        tracking = data["tracking_number"]
        order = data["order"]

        # Get user info
        user_service = await app.container.resolve(UserService)
        user = user_service.users[order["user_id"]]

        # Send shipping notification
        await notifier.send_email(
            user["email"],
            "Order Shipped",
            f"Your order #{order_id} has shipped! Tracking: {tracking}",
        )

        metrics.increment("events_processed")
        print(f"✅ Shipping notification sent for order {order_id}")

    # Wildcard handlers for logging
    @app.on("user.*")
    @inject
    async def log_all_user_events(data: dict, event_store: EventStore):
        """Log all user events for auditing."""
        # This handler catches all user.* events
        print(f"📋 User event logged: {len(event_store.get_events())} total events")

    @app.on("order.*")
    @inject
    async def log_all_order_events(data: dict, event_store: EventStore):
        """Log all order events for auditing."""
        # This handler catches all order.* events
        print(f"📋 Order event logged: {len(event_store.get_events())} total events")

    # System event handlers
    @app.on("system.error")
    @inject
    async def handle_system_error(
        data: dict, metrics: MetricsCollector, notifier: NotificationService
    ):
        """Handle system errors."""
        error_msg = data.get("error", "Unknown error")
        print(f"🚨 System error: {error_msg}")

        # Send alert to admin
        await notifier.send_email(
            "admin@company.com", "System Error Alert", f"System error occurred: {error_msg}"
        )

        metrics.increment("errors_occurred")

    # Step 3b: Background Tasks
    # =========================

    @app.task
    @inject
    async def metrics_collection_task(metrics: MetricsCollector):
        """Background task for collecting metrics."""
        metrics.increment("tasks_started")
        try:
            await metrics.start_collection()
        except asyncio.CancelledError:
            print("📊 Metrics collection task stopped")
            raise

    @app.task
    @inject
    async def order_processing_task(order_service: OrderService):
        """Background task that processes pending orders."""
        print("🔄 Order processing task started")

        try:
            while True:
                await asyncio.sleep(5)  # Check every 5 seconds

                # Find pending orders
                pending_orders = [
                    order for order in order_service.orders.values() if order["status"] == "pending"
                ]

                if pending_orders:
                    print(f"🔄 Processing {len(pending_orders)} pending orders...")
                    for order in pending_orders:
                        await order_service.process_order(order["id"])
                        await asyncio.sleep(0.5)  # Small delay between processing

        except asyncio.CancelledError:
            print("🔄 Order processing task stopped")
            raise

    @app.task
    @inject
    async def shipping_task(order_service: OrderService):
        """Background task that ships processed orders."""
        print("📦 Shipping task started")

        try:
            while True:
                await asyncio.sleep(8)  # Check every 8 seconds

                # Find processed orders ready for shipping
                ready_orders = [
                    order
                    for order in order_service.orders.values()
                    if order["status"] == "processed"
                ]

                if ready_orders:
                    print(f"📦 Shipping {len(ready_orders)} processed orders...")
                    for order in ready_orders:
                        tracking = f"TRK{order['id']}{int(asyncio.get_event_loop().time())}"
                        await order_service.ship_order(order["id"], tracking)
                        await asyncio.sleep(0.3)  # Small delay between shipping

        except asyncio.CancelledError:
            print("📦 Shipping task stopped")
            raise

    @app.task
    @inject
    async def health_monitor_task(event_store: EventStore, metrics: MetricsCollector):
        """Background task for health monitoring."""
        print("🏥 Health monitor task started")

        try:
            while True:
                await asyncio.sleep(15)  # Check every 15 seconds

                # Check system health
                total_events = len(event_store.get_events())
                current_metrics = metrics.get_metrics()

                print(f"🏥 Health check - Events: {total_events}, Metrics: {current_metrics}")

                # Simulate occasional errors for demonstration
                if total_events > 0 and total_events % 7 == 0:
                    await app.emit(
                        "system.error",
                        {
                            "error": f"Simulated error after {total_events} events",
                            "timestamp": asyncio.get_event_loop().time(),
                        },
                    )

        except asyncio.CancelledError:
            print("🏥 Health monitor task stopped")
            raise

    # Step 4: Application Lifecycle and Event Processing
    # ===================================================

    @app.on_startup
    async def on_startup():
        """Handle application startup."""
        print("\n🚀 Application starting up...")
        print("✅ Event handlers registered")
        print("✅ Background tasks will start")

    @app.on_ready
    async def on_ready():
        """Handle application ready."""
        print("🎉 Application is ready!")
        print("📡 Event processing active")
        print("⚙️ Background tasks running\n")

    @app.on_shutdown
    async def on_shutdown():
        """Handle application shutdown."""
        print("\n👋 Application shutting down...")
        print("🛑 Stopping background tasks")
        print("📊 Final metrics will be displayed")

    # Step 5: Run the Application and Generate Events
    # ================================================

    try:
        async with app.lifespan():
            print("--- EVENT-DRIVEN PROCESSING DEMONSTRATION ---\n")

            # Get services
            user_service = await app.container.resolve(UserService)
            order_service = await app.container.resolve(OrderService)
            event_store = await app.container.resolve(EventStore)
            metrics = await app.container.resolve(MetricsCollector)
            notifier = await app.container.resolve(NotificationService)

            # Create some users (triggers events)
            alice = await user_service.create_user("Alice Smith", "alice@example.com")
            bob = await user_service.create_user("Bob Johnson", "bob@example.com")
            charlie = await user_service.create_user("Charlie Brown", "charlie@example.com")

            # Wait for event processing
            await asyncio.sleep(1)

            # Update a user (triggers events)
            await user_service.update_user(
                alice["id"], name="Alice Smith-Jones", phone="+1234567890"
            )

            # Create some orders (triggers events)
            order1 = await order_service.create_order(alice["id"], ["Widget", "Gadget"], 49.99)
            order2 = await order_service.create_order(bob["id"], ["Book", "Pen"], 29.99)
            order3 = await order_service.create_order(charlie["id"], ["Laptop"], 999.99)

            # Wait for event processing
            await asyncio.sleep(2)

            print("\n--- SYSTEM STATUS AFTER INITIAL ACTIVITY ---")
            print(f"📊 Current metrics: {metrics.get_metrics()}")
            print(f"📧 Notifications sent: {notifier.get_stats()}")
            print(f"📚 Total events recorded: {len(event_store.get_events())}")

            # Let background tasks run and process orders
            print("\n--- LETTING BACKGROUND TASKS RUN (30 seconds) ---")
            print(
                "⏳ Background tasks are processing orders, collecting metrics, and monitoring health..."
            )

            await asyncio.sleep(30)

            # Show final status
            print("\n--- FINAL STATUS ---")
            print(f"📊 Final metrics: {metrics.get_metrics()}")
            print(f"📧 Total notifications: {notifier.get_stats()}")
            print(f"📚 Total events: {len(event_store.get_events())}")

            # Show event breakdown
            user_events = event_store.get_events("user.created")
            order_events = [e for e in event_store.get_events() if e["type"].startswith("order.")]
            print(f"👤 User events: {len(user_events)}")
            print(f"🛒 Order events: {len(order_events)}")

            # Show final order statuses
            print("\n📦 Final order statuses:")
            for order_id, order in order_service.orders.items():
                print(f"  Order {order_id}: {order['status']}")

            # Delete a user to show deletion events
            print("\n--- DEMONSTRATING USER DELETION ---")
            await user_service.delete_user(charlie["id"])
            await asyncio.sleep(1)
            print(f"📚 Events after deletion: {len(event_store.get_events())}")

    except KeyboardInterrupt:
        print("\n⚠️ Interrupted by user")
    except Exception as e:
        print(f"\n💥 Application error: {e}")
        # Emit error event
        await app.emit("system.error", {"error": str(e)})
        raise


if __name__ == "__main__":
    print("🥃 Whiskey Events and Background Tasks")
    print("=" * 45)
    print("Features demonstrated:")
    print("✅ Event emission and handling")
    print("✅ Wildcard event patterns")
    print("✅ Background task management")
    print("✅ Event-driven architecture")
    print("✅ Task coordination and lifecycle")
    print("✅ System monitoring and health checks")
    print()

    asyncio.run(main())
