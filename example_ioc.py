"""Example demonstrating IoC features in Whiskey."""

import asyncio
from dataclasses import dataclass
from typing import Any

from loguru import logger

from whiskey.core.application import Application, ApplicationConfig
from whiskey.core.commands import Command, CommandBus, Query
from whiskey.core.events import Event, EventBus
from whiskey.core.types import Disposable, Initializable


# Configuration
@dataclass
class DatabaseConfig:
    host: str = "localhost"
    port: int = 5432
    database: str = "whiskey_demo"


# Services with lifecycle
@dataclass
class User:
    id: str
    name: str
    email: str


class UserRepository(Initializable, Disposable):
    """Repository with IoC lifecycle management."""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.users: dict[str, User] = {}
        logger.info(f"UserRepository created with DB: {config.database}")
    
    async def initialize(self):
        """Called automatically by IoC on startup."""
        logger.info(f"Connecting to database at {self.config.host}:{self.config.port}")
        # Simulate DB connection
        await asyncio.sleep(0.1)
        
        # Add some test data
        self.users["1"] = User("1", "Alice", "alice@example.com")
        self.users["2"] = User("2", "Bob", "bob@example.com")
        logger.info("UserRepository initialized with test data")
    
    async def dispose(self):
        """Called automatically by IoC on shutdown."""
        logger.info("Closing database connection")
        self.users.clear()
    
    async def get(self, user_id: str) -> User | None:
        return self.users.get(user_id)
    
    async def save(self, user: User) -> None:
        self.users[user.id] = user
        logger.info(f"Saved user: {user.name}")


# Events
@dataclass
class UserCreated(Event):
    user: User | None = None


@dataclass
class UserUpdated(Event):
    user: User | None = None
    changes: dict[str, Any] | None = None


# Commands and Queries
@dataclass
class CreateUserCommand(Command):
    name: str
    email: str


@dataclass
class GetUserQuery(Query[User | None]):
    user_id: str


# Application setup
def create_app() -> Application:
    """Create and configure the application with IoC."""
    
    config = ApplicationConfig(
        name="WhiskeyDemo",
        version="0.1.0",
        debug=True,
    )
    
    app = Application(config)
    
    # Register services with lifecycle
    @app.service
    class EmailService(Initializable):
        """Email service managed by IoC."""
        
        async def initialize(self):
            logger.info("Email service ready")
        
        async def send_welcome(self, user: User):
            logger.info(f"Sending welcome email to {user.email}")
            await asyncio.sleep(0.1)  # Simulate email sending
    
    # Register configuration
    app.container.register_singleton(DatabaseConfig, instance=DatabaseConfig())
    
    # Register the repository
    app.container.register_singleton(UserRepository, implementation=UserRepository)
    
    # Command Bus
    command_bus = CommandBus()
    app.container.register_singleton(CommandBus, instance=command_bus)
    
    # Command Handlers with DI
    @command_bus.command(CreateUserCommand)
    async def handle_create_user(
        cmd: CreateUserCommand,
        repo: UserRepository,
        event_bus: EventBus,
    ) -> User:
        # Create user
        user_id = str(len(repo.users) + 1)
        user = User(user_id, cmd.name, cmd.email)
        
        # Save to repository
        await repo.save(user)
        
        # Emit event
        await event_bus.emit(UserCreated(user=user))
        
        return user
    
    @command_bus.handle_query(GetUserQuery)
    async def handle_get_user(
        query: GetUserQuery,
        repo: UserRepository,
    ) -> User | None:
        return await repo.get(query.user_id)
    
    # Event Handlers with DI
    @app.on(UserCreated)
    async def on_user_created(event: UserCreated, email_service: EmailService):
        logger.info(f"Handling UserCreated event for {event.user.name}")
        await email_service.send_welcome(event.user)
    
    # Background Tasks
    @app.task(interval=5.0)
    async def health_check(repo: UserRepository):
        user_count = len(repo.users)
        logger.info(f"Health check: {user_count} users in system")
    
    # Middleware
    @app.middleware
    class LoggingMiddleware:
        async def process(self, event: Event, next):
            logger.debug(f"Processing event: {type(event).__name__}")
            result = await next(event)
            logger.debug(f"Completed event: {type(event).__name__}")
            return result
    
    # Startup/Shutdown hooks
    @app.on_startup
    async def startup_message():
        logger.info("🚀 Application is starting up!")
    
    @app.on_shutdown
    async def shutdown_message():
        logger.info("👋 Application is shutting down!")
    
    return app


async def demo_commands(app: Application):
    """Demonstrate command/query handling."""
    command_bus = await app.container.resolve(CommandBus)
    
    # Create users
    logger.info("\n=== Creating Users ===")
    user1 = await command_bus.execute(
        CreateUserCommand(name="Charlie", email="charlie@example.com")
    )
    logger.info(f"Created user: {user1}")
    
    user2 = await command_bus.execute(
        CreateUserCommand(name="Diana", email="diana@example.com")
    )
    logger.info(f"Created user: {user2}")
    
    # Query users
    logger.info("\n=== Querying Users ===")
    found_user = await command_bus.query(GetUserQuery(user_id="1"))
    logger.info(f"Found user: {found_user}")
    
    not_found = await command_bus.query(GetUserQuery(user_id="999"))
    logger.info(f"User not found: {not_found}")


async def main():
    """Run the IoC demo."""
    # Configure logging
    logger.remove()
    logger.add(
        lambda msg: print(msg),
        format="<green>{time:HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>",
        level="INFO"
    )
    
    # Create application
    app = create_app()
    
    # Run with lifecycle management
    async with app.lifespan():
        logger.info("\n🎉 Application is running with full IoC!")
        
        # Give services time to initialize
        await asyncio.sleep(0.5)
        
        # Run demo
        await demo_commands(app)
        
        # Let background tasks run
        logger.info("\n⏰ Background tasks running...")
        await asyncio.sleep(11)  # See 2 health checks
    
    logger.info("\n✅ Demo completed!")


if __name__ == "__main__":
    asyncio.run(main())