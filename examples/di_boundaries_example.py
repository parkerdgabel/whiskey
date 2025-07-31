"""Example demonstrating dependency injection at all framework boundaries."""

import asyncio

from whiskey import Whiskey, inject


# Sample services
class Database:
    """Mock database service."""

    def __init__(self):
        self.connected = False
        self.queries = []

    async def connect(self):
        print("📦 Database: Connecting...")
        await asyncio.sleep(0.1)
        self.connected = True
        print("✅ Database: Connected")

    async def query(self, sql: str):
        self.queries.append(sql)
        return f"Result of: {sql}"


class EmailService:
    """Mock email service."""

    def __init__(self):
        self.sent_emails = []

    async def send(self, to: str, subject: str, body: str):
        email = {"to": to, "subject": subject, "body": body}
        self.sent_emails.append(email)
        print(f"📧 Email sent to {to}: {subject}")


class MetricsService:
    """Mock metrics collection service."""

    def __init__(self):
        self.metrics = {"events": 0, "tasks": 0, "requests": 0}

    def increment(self, metric: str):
        self.metrics[metric] = self.metrics.get(metric, 0) + 1

    def report(self):
        print(f"📊 Metrics: {self.metrics}")


# Create application
app = Whiskey()

# Register services as singletons so they share state
app.container.register(Database, scope="singleton")
app.container.register(EmailService, scope="singleton")
app.container.register(MetricsService, scope="singleton")


# Test 1: Main function with @inject
@app.main
@inject
async def main(db: Database, metrics: MetricsService):
    """Main entry point with dependency injection."""
    print("\n🚀 Main function (with DI)")
    await db.connect()
    metrics.increment("requests")

    # Emit some events
    await app.emit("user.created", {"id": 1, "email": "user@example.com"})
    await asyncio.sleep(0.5)  # Let background tasks run

    metrics.report()


# Test 2: Event handlers with @inject
@app.on("user.created")
@inject
async def handle_user_created(data: dict, email: EmailService, metrics: MetricsService):
    """Event handler with dependency injection."""
    print("\n📬 Event handler: user.created")
    await email.send(to=data["email"], subject="Welcome!", body="Thanks for signing up!")
    metrics.increment("events")


@app.on("user.*")  # Wildcard handler
@inject
async def log_user_events(data: dict, db: Database):
    """Log all user events to database."""
    await db.query(f"INSERT INTO event_log (data) VALUES ('{data}')")


# Test 3: Background tasks with @inject
@app.task
@inject
async def periodic_cleanup(db: Database, metrics: MetricsService):
    """Background task with dependency injection."""
    for i in range(3):
        print(f"\n🧹 Background task: Cleanup run {i + 1}")
        await db.query("DELETE FROM temp_data WHERE expired = true")
        metrics.increment("tasks")
        await asyncio.sleep(0.2)


# Test 4: Lifecycle hooks with @inject
@app.on_startup
@inject
async def initialize_services(db: Database):
    """Startup hook with dependency injection."""
    print("\n⚙️  Startup hook: Initializing database")
    await db.connect()


@app.on_ready
@inject
async def log_ready(metrics: MetricsService):
    """Ready hook with dependency injection."""
    print("\n✨ Ready hook: Application is ready!")
    metrics.increment("requests")


@app.on_shutdown
@inject
async def cleanup(db: Database, email: EmailService):
    """Shutdown hook with dependency injection."""
    print("\n🛑 Shutdown hook: Cleaning up")
    print(f"   - Database queries executed: {len(db.queries)}")
    print(f"   - Emails sent: {len(email.sent_emails)}")


# Test 5: Error handlers with @inject
@app.on_error
@inject
async def handle_errors(error_data: dict, email: EmailService):
    """Error handler with dependency injection."""
    print(f"\n❌ Error handler: {error_data['message']}")
    # In production, might send alert email
    # await email.send("admin@example.com", "Application Error", str(error_data))


# Alternative usage without @app.main decorator
async def alt_main(app: Whiskey):
    """Alternative main without @inject - receives app instance."""
    print("\n🎯 Alternative main (without DI)")
    # Manual resolution needed
    db = await app.container.resolve(Database)
    await db.connect()


# Function that doesn't use @inject
async def regular_function(db: Database, email: EmailService):
    """Regular function - no automatic injection."""
    print("\n📌 Regular function (no auto-injection)")
    await db.query("SELECT * FROM users")
    await email.send("test@example.com", "Test", "This is a test")


if __name__ == "__main__":
    print("=" * 50)
    print("Whiskey DI Boundaries Example")
    print("=" * 50)

    # Run with decorated main
    app.run()

    # Could also run with explicit main
    # app.run(alt_main)

    # Or with a lambda
    # app.run(lambda app: print("Lambda main!"))
