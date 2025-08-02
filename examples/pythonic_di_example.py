"""Example of the simplified, Pythonic DI container."""

import asyncio

from whiskey.core.container import Container
from whiskey.core.decorators import inject, singleton, provide


# Simple services without decorators
class Database:
    def __init__(self, connection_string: str = "sqlite:///:memory:"):
        self.connection_string = connection_string

    async def query(self, sql: str) -> list:
        print(f"Querying: {sql}")
        return [{"id": 1, "name": "Alice"}]


class EmailService:
    async def send(self, to: str, message: str) -> None:
        print(f"📧 Sending email to {to}: {message}")


# Service with dependencies
class UserService:
    def __init__(self, db: Database, email: EmailService):
        self.db = db
        self.email = email

    async def create_user(self, name: str) -> dict:
        # Save to database
        await self.db.query(f"INSERT INTO users (name) VALUES ('{name}')")

        # Send welcome email
        await self.email.send(f"{name}@example.com", "Welcome!")

        return {"id": 1, "name": name}


async def main():
    """Demonstrate the Pythonic DI container."""

    print("=== Basic Usage ===")

    # Create container and register services
    container = Container()

    # Register instance
    container[Database] = Database("postgresql://localhost/mydb")

    # Register class (will be instantiated on resolve)
    container[EmailService] = EmailService

    # Register with dependencies (auto-resolved)
    container[UserService] = UserService

    # Resolve and use
    user_service = await container.resolve(UserService)
    user = await user_service.create_user("Bob")
    print(f"Created user: {user}")

    print("\n=== Dict-like Access ===")

    # Access using dict syntax
    db = await container.resolve(Database)
    print(f"Database connection: {db.connection_string}")

    # Check if registered
    print(f"UserService registered: {UserService in container}")
    print(f"NonExistent registered: {str in container}")

    print("\n=== Factory Functions ===")

    # Register a factory
    container.factory(Database, lambda: Database("mysql://localhost/testdb"))

    # Each resolve calls the factory
    db1 = await container.resolve(Database)
    db2 = await container.resolve(Database)
    print(f"Same instance: {db1 is db2}")  # False

    print("\n=== Singletons ===")

    # Register as singleton
    container.singleton(EmailService, EmailService())

    # Always returns same instance
    email1 = await container.resolve(EmailService)
    email2 = await container.resolve(EmailService)
    print(f"Same instance: {email1 is email2}")  # True

    print("\n=== Dependency Injection ===")

    # Use @inject decorator
    @inject
    async def send_notification(user_id: int, email: EmailService):
        await email.send(f"user{user_id}@example.com", "You have a notification!")

    # Dependencies are auto-resolved
    with container:  # Set as current container
        await send_notification(123)

    print("\n=== With Decorators ===")

    with container:
        # Decorators work with current container
        @singleton
        class ConfigService:
            def __init__(self):
                self.api_key = "secret-key-123"

        @provide
        class APIClient:
            def __init__(self, config: ConfigService):
                self.config = config

            async def call_api(self) -> str:
                return f"Called API with key: {self.config.api_key}"

    # Use the registered services
    client = await container.resolve(APIClient)
    result = await client.call_api()
    print(result)

    print("\n=== Simple Scopes ===")

    from whiskey.core.container_v2 import Scope

    # Create a request scope
    with Scope("request") as scope:
        # Create request-scoped service
        request_db = Database("request-specific-connection")
        scope.set(Database, request_db)

        # Use within scope
        db = scope.get(Database)
        await db.query("SELECT * FROM requests")
    # Scope cleaned up automatically


if __name__ == "__main__":
    asyncio.run(main())
