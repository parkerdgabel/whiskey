# Whiskey User Guide

## Introduction

Whiskey is a dependency injection framework that brings the power of Inversion of Control (IoC) to Python applications without the complexity. This guide will walk you through building applications with Whiskey, from simple scripts to complex systems.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Core Concepts](#core-concepts)
3. [Building Applications](#building-applications)
4. [Working with Extensions](#working-with-extensions)
5. [Testing](#testing)
6. [Best Practices](#best-practices)
7. [Common Patterns](#common-patterns)
8. [Troubleshooting](#troubleshooting)

## Getting Started

### Installation

```bash
# Basic installation
pip install whiskey

# With specific extensions
pip install whiskey[ai]     # For AI/LLM applications
pip install whiskey[web]    # For web applications
pip install whiskey[cli]    # For CLI applications
pip install whiskey[all]    # Everything
```

### Your First Whiskey Application

Let's build a simple application that demonstrates core concepts:

```python
from whiskey import Container, inject, singleton
from whiskey.core.application import Whiskey

# 1. Create an application
app = Whiskey()

# 2. Define your services
@singleton
class Database:
    def __init__(self):
        self.connected = False
        
    async def connect(self):
        print("📦 Connecting to database...")
        self.connected = True
        
    async def disconnect(self):
        print("📦 Disconnecting from database...")
        self.connected = False

@app.component
class UserService:
    def __init__(self, db: Database):
        self.db = db
        print("👤 UserService created")
        
    async def get_user(self, user_id: int):
        if not self.db.connected:
            raise RuntimeError("Database not connected!")
        return {"id": user_id, "name": f"User {user_id}"}

# 3. Set up lifecycle hooks
@app.on_startup
async def startup():
    print("🚀 Starting application...")
    db = await app.container.resolve(Database)
    await db.connect()

@app.on_shutdown
async def shutdown():
    print("🛑 Shutting down...")
    db = await app.container.resolve(Database)
    await db.disconnect()

# 4. Create your main logic
@app.main
@inject
async def main(user_service: UserService):
    user = await user_service.get_user(123)
    print(f"✅ Found user: {user}")

# 5. Run the application
if __name__ == "__main__":
    app.run()
```

## Core Concepts

### Dependency Injection

Dependency Injection (DI) is a pattern where objects receive their dependencies rather than creating them. Whiskey makes this automatic:

```python
# Without DI - tight coupling
class EmailService:
    def __init__(self):
        self.smtp = SmtpClient("smtp.gmail.com")  # Creates dependency
        
# With DI - loose coupling
class EmailService:
    def __init__(self, smtp: SmtpClient):
        self.smtp = smtp  # Receives dependency
```

### The Container

The Container is Whiskey's core - it manages all your dependencies:

```python
container = Container()

# Register services (like a dict!)
container[Logger] = Logger("app.log")
container[Database] = lambda: Database(get_connection_string())

# Resolve with automatic injection
service = await container.resolve(MyService)
```

### Pythonic Injection with Type Hints

Whiskey uses simple type hints for automatic injection:

```python
class OrderService:
    def __init__(self,
                 # These will be injected (no default values)
                 db: Database,
                 logger: Logger,
                 # These won't be injected (have defaults)  
                 table_name: str = "orders",
                 timeout: int = 30):
        pass
```

The rule is simple: parameters with type hints but no default values get injected!

### Scopes

Scopes control the lifecycle of your services:

```python
# Singleton - shared instance
@singleton
class Configuration:
    def __init__(self):
        self.settings = load_from_file()

# Transient - new instance each time (default)
@provide
class EmailSender:
    def __init__(self):
        self.sent_count = 0

# Request-scoped (with whiskey-asgi)
@scoped(scope_name="request")
class RequestContext:
    def __init__(self):
        self.user = None
        self.trace_id = generate_trace_id()
```

## Building Applications

### Application Structure

A typical Whiskey application follows this structure:

```
myapp/
├── __init__.py
├── services/         # Business logic
│   ├── __init__.py
│   ├── auth.py
│   ├── database.py
│   └── email.py
├── models/          # Data models
│   ├── __init__.py
│   └── user.py
├── config.py        # Configuration
├── app.py          # Application setup
└── main.py         # Entry point
```

### Service Organization

Group related functionality into services:

```python
# services/auth.py
from whiskey import inject, scoped

@scoped(scope_name="request")
class AuthService:
    def __init__(self,
                 db: Database,
                 hasher: PasswordHasher):
        self.db = db
        self.hasher = hasher
        
    async def authenticate(self, username: str, password: str):
        user = await self.db.get_user(username)
        if user and self.hasher.verify(password, user.password_hash):
            return user
        return None
        
    async def create_user(self, username: str, password: str):
        password_hash = self.hasher.hash(password)
        return await self.db.create_user(username, password_hash)
```

### Using Component Discovery

Instead of manually registering each service, use discovery:

```python
# app.py
from whiskey.core.application import Whiskey

def create_app():
    app = Whiskey()
    
    # Discover and register all services
    app.discover("myapp.services", auto_register=True)
    
    # Discover models with custom marker
    app.discover("myapp.models", 
                decorator_name="_entity",
                auto_register=True)
    
    return app
```

### Event-Driven Architecture

Whiskey's event system enables loose coupling between components:

```python
# Emit events
@app.component
class OrderService:
    @inject
    async def create_order(self, order_data: dict):
        order = await self.db.create_order(order_data)
        
        # Notify interested parties
        await app.emit("order.created", {
            "order_id": order.id,
            "user_id": order.user_id,
            "total": order.total
        })
        
        return order

# Handle events
@app.on("order.created")
@inject
async def send_order_confirmation(
    event_data: dict,
    email_service: EmailService
):
    await email_service.send_confirmation(event_data["order_id"])

@app.on("order.*")  # Wildcard - handle all order events
async def log_order_activity(event_data: dict):
    print(f"Order event: {event_data}")
```

### Background Tasks

Run background tasks with automatic dependency injection:

```python
@app.task
@inject
async def cleanup_old_sessions(
    db: Database,
    config: Config
):
    while True:
        await asyncio.sleep(config.cleanup_interval)
        deleted = await db.delete_old_sessions()
        print(f"Cleaned up {deleted} sessions")
```

## Working with Extensions

### Web Applications (whiskey-asgi)

Build web APIs with dependency injection:

```python
from whiskey import inject
from whiskey.core.application import Whiskey
from whiskey_asgi import asgi_extension

app = Whiskey()
app.use(asgi_extension)

# Define routes with DI
@app.get("/users/{user_id}")
@inject
async def get_user(
    user_id: int,
    user_service: UserService
):
    user = await user_service.get_user(user_id)
    if not user:
        return {"error": "User not found"}, 404
    return user

# Middleware with DI
@app.middleware
@inject
async def auth_middleware(
    request: Request,
    call_next,
    auth_service: AuthService
):
    token = request.headers.get("Authorization")
    if token:
        user = await auth_service.verify_token(token)
        request.state.user = user
    
    response = await call_next(request)
    return response

# WebSocket support
@app.websocket("/ws")
@inject
async def websocket_endpoint(
    websocket: WebSocket,
    message_service: MessageService
):
    await websocket.accept()
    
    async for message in websocket:
        response = await message_service.process(message)
        await websocket.send_json(response)
```

### CLI Applications (whiskey-cli)

Create command-line tools with automatic DI:

```python
from whiskey import inject
from whiskey.core.application import Whiskey
from whiskey_cli import cli_extension

app = Whiskey()
app.use(cli_extension)

# Commands with dependency injection
@app.command()
@app.argument("username")
@app.option("--admin", is_flag=True, help="Create admin user")
@inject
async def create_user(
    username: str,
    admin: bool,
    user_service: UserService
):
    """Create a new user."""
    user = await user_service.create_user(username, is_admin=admin)
    print(f"✅ Created user: {user.username}")

# Command groups
@app.command(group="db")
async def migrate():
    """Run database migrations."""
    print("Running migrations...")

@app.command(group="db")
@inject
async def seed(
    db: Database
):
    """Seed the database."""
    await db.seed_data()
    print("✅ Database seeded")
```

### AI Applications (whiskey-ai)

Build AI-powered applications:

```python
from whiskey import inject
from whiskey.core.application import Whiskey
from whiskey_ai import ai_extension

app = Whiskey()
app.use(ai_extension)

# Configure LLM
app.configure_llm(
    provider="openai",
    api_key=os.getenv("OPENAI_API_KEY"),
    model="gpt-4"
)

# Define an agent
@app.agent("assistant")
class AssistantAgent:
    def __init__(self):
        self.system_prompt = "You are a helpful assistant."
    
    @inject
    async def process(self,
                     message: str,
                     llm: LLMClient,
                     context: ConversationContext):
        # Add message to context
        context.add_message("user", message)
        
        # Get LLM response
        response = await llm.complete(
            messages=context.messages,
            system=self.system_prompt
        )
        
        # Save response
        context.add_message("assistant", response)
        return response

# Use the agent
@inject
async def chat_with_assistant(
    user_input: str,
    agent: AssistantAgent
):
    response = await agent.process(user_input)
    print(f"Assistant: {response}")
```

### Configuration Management (whiskey-config)

Manage configuration with hot reloading:

```python
from dataclasses import dataclass
from whiskey import inject
from whiskey.core.application import Whiskey
from whiskey_config import config_extension, Setting

app = Whiskey()
app.use(config_extension)

# Define configuration schema
@dataclass
class DatabaseConfig:
    host: str = "localhost"
    port: int = 5432
    name: str = "myapp"
    
@dataclass
class AppConfig:
    debug: bool = False
    database: DatabaseConfig = None
    secret_key: str = ""
    
    def __post_init__(self):
        if self.database is None:
            self.database = DatabaseConfig()

# Configure sources
app.configure_config(
    schema=AppConfig,
    sources=[
        "config.yaml",      # File configuration
        "config.local.yaml", # Local overrides
        "ENV"               # Environment variables
    ],
    env_prefix="MYAPP_",
    watch=True  # Enable hot reloading
)

# Use configuration values
@inject
async def connect_database(
    db_host: str = Setting("database.host"),
    db_port: int = Setting("database.port"),
    db_name: str = Setting("database.name")
):
    return await create_connection(
        host=db_host,
        port=db_port,
        database=db_name
    )

# React to configuration changes
@app.on("config.changed")
async def on_config_change(event_data):
    if event_data["path"].startswith("database."):
        print("Database configuration changed, reconnecting...")
        await reconnect_database()
```

## Testing

### Unit Testing Services

Test services in isolation using mock dependencies:

```python
import pytest
from unittest.mock import AsyncMock
from whiskey import Container

# Create a test fixture for the container
@pytest.fixture
def container():
    container = Container()
    
    # Register mock dependencies
    container[Database] = AsyncMock(spec=Database)
    container[EmailService] = AsyncMock(spec=EmailService)
    
    return container

# Test a service
@pytest.mark.asyncio
async def test_user_service_create_user(container):
    # Arrange
    mock_db = container[Database]
    mock_db.create_user.return_value = {"id": 1, "username": "testuser"}
    
    # Act
    user_service = await container.resolve(UserService)
    user = await user_service.create_user("testuser", "password123")
    
    # Assert
    assert user["username"] == "testuser"
    mock_db.create_user.assert_called_once()
```

### Integration Testing

Test complete application flows:

```python
@pytest.fixture
async def app():
    from whiskey.core.application import Whiskey
    app = Whiskey()
    
    # Use test configuration
    app.use(config_extension)
    app.configure_config(
        sources=["config.test.yaml"],
        env_prefix="TEST_"
    )
    
    # Set up test services
    app.container[Database] = TestDatabase()
    
    async with app.lifespan():
        yield app

@pytest.mark.asyncio
async def test_full_user_flow(app):
    # Create user
    user_service = await app.container.resolve(UserService)
    user = await user_service.create_user("test@example.com", "password")
    
    # Authenticate
    auth_service = await app.container.resolve(AuthService)
    token = await auth_service.authenticate("test@example.com", "password")
    
    assert token is not None
    assert user["email"] == "test@example.com"
```

### Testing Event Handlers

```python
@pytest.mark.asyncio
async def test_order_created_event(app):
    # Track event emissions
    events = []
    
    @app.on("order.created")
    async def track_event(data):
        events.append(data)
    
    # Trigger the event
    await app.emit("order.created", {"order_id": 123})
    
    # Verify
    assert len(events) == 1
    assert events[0]["order_id"] == 123
```

## Best Practices

### 1. Use Explicit Injection

Use type hints to control what gets injected:

```python
# ✅ Good - clear what gets injected
def __init__(self,
             db: Database,
             logger: Logger,
             cache_ttl: int = 3600):  # Not injected
    pass

# ❌ Bad - ambiguous
def __init__(self, db: Database, logger: Logger, cache_ttl: int = 3600):
    pass
```

### 2. Prefer Constructor Injection

Inject dependencies through constructors, not properties:

```python
# ✅ Good - dependencies clear at construction
@app.component
class UserService:
    def __init__(self, db: Database):
        self.db = db

# ❌ Avoid - dependencies set after construction
@app.component
class UserService:
    db: Database = None  # Set later
```

### 3. Use Appropriate Scopes

Choose the right scope for your services:

```python
# Singleton for stateless services
@singleton
class EmailTemplateRenderer:
    def render(self, template: str, data: dict) -> str:
        return template.format(**data)

# Request scope for request-specific state
@scoped(scope_name="request")
class RequestLogger:
    def __init__(self):
        self.logs = []
        self.request_id = generate_id()

# Transient for stateful services
@provide
class FileProcessor:
    def __init__(self):
        self.processed_count = 0
```

### 4. Organize by Feature

Structure your application by feature, not by type:

```
# ✅ Good - organized by feature
myapp/
├── auth/
│   ├── __init__.py
│   ├── services.py
│   ├── models.py
│   └── handlers.py
├── orders/
│   ├── __init__.py
│   ├── services.py
│   ├── models.py
│   └── handlers.py

# ❌ Avoid - organized by type
myapp/
├── services/
├── models/
├── handlers/
```

### 5. Use Interfaces (Protocols)

Define interfaces for better abstraction:

```python
from typing import Protocol

class CacheProtocol(Protocol):
    async def get(self, key: str) -> Any: ...
    async def set(self, key: str, value: Any, ttl: int = None) -> None: ...
    async def delete(self, key: str) -> None: ...

# Register implementation
container[CacheProtocol] = RedisCache()

# Use interface in services
class UserService:
    def __init__(self, cache: CacheProtocol):
        self.cache = cache
```

## Common Patterns

### Repository Pattern

```python
from typing import Protocol, Generic, TypeVar

T = TypeVar('T')

class Repository(Protocol, Generic[T]):
    async def find(self, id: int) -> T | None: ...
    async def find_all(self) -> list[T]: ...
    async def save(self, entity: T) -> T: ...
    async def delete(self, id: int) -> bool: ...

@app.component
class UserRepository:
    def __init__(self, db: Database):
        self.db = db
        
    async def find(self, id: int) -> User | None:
        return await self.db.query_one(
            "SELECT * FROM users WHERE id = ?", id
        )
    
    async def save(self, user: User) -> User:
        if user.id:
            await self.db.execute(
                "UPDATE users SET ... WHERE id = ?", 
                user.dict(), user.id
            )
        else:
            user.id = await self.db.execute(
                "INSERT INTO users (...) VALUES (...)",
                user.dict()
            )
        return user

# Register as the Repository implementation for User
container[Repository[User]] = UserRepository
```

### Unit of Work Pattern

```python
@scoped(scope_name="request")
class UnitOfWork:
    def __init__(self, db: Database):
        self.db = db
        self._transaction = None
        
    async def __aenter__(self):
        self._transaction = await self.db.begin()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            await self._transaction.rollback()
        else:
            await self._transaction.commit()
            
    async def commit(self):
        await self._transaction.commit()
        
    async def rollback(self):
        await self._transaction.rollback()

# Usage
@inject
async def transfer_funds(
    from_id: int,
    to_id: int,
    amount: float,
    uow: UnitOfWork,
    account_service: AccountService
):
    async with uow:
        await account_service.debit(from_id, amount)
        await account_service.credit(to_id, amount)
        # Automatically commits or rolls back
```

### Factory Pattern

```python
@app.component
class ConnectionFactory:
    def __init__(self, config: Config):
        self.config = config
        
    def create_database_connection(self, name: str) -> Database:
        db_config = self.config.databases[name]
        if db_config.type == "postgres":
            return PostgresDatabase(db_config)
        elif db_config.type == "mysql":
            return MySQLDatabase(db_config)
        else:
            raise ValueError(f"Unknown database type: {db_config.type}")

# Usage
@inject
async def get_user_data(
    factory: ConnectionFactory
):
    # Get specific database
    user_db = factory.create_database_connection("users")
    analytics_db = factory.create_database_connection("analytics")
    
    # Use them
    users = await user_db.query("SELECT * FROM users")
    stats = await analytics_db.query("SELECT * FROM user_stats")
```

## Troubleshooting

### Common Issues

#### 1. "Service not registered" errors

```python
# Problem: KeyError: "Service UserService not registered"

# Solution 1: Ensure service is registered
app.component(UserService)  # or
container[UserService] = UserService

# Solution 2: Use discovery
app.discover("myapp.services", auto_register=True)

# Solution 3: Check for typos in imports
from myapp.services import UserService  # Correct module?
```

#### 2. Circular dependencies

```python
# Problem: RecursionError in dependency resolution

# Solution: Break the cycle with lazy injection
@app.component
class ServiceA:
    def __init__(self, container: Container):
        self._container = container
        
    async def get_service_b(self):
        # Resolve B only when needed
        return await self._container.resolve(ServiceB)
```

#### 3. Async/await issues

```python
# Problem: "coroutine was never awaited"

# Solution: Ensure you're using async properly
service = await container.resolve(MyService)  # ✅
service = container.resolve(MyService)       # ❌ Missing await

# For sync contexts, use resolve_sync
service = container.resolve_sync(MyService)  # ✅ In sync function
```

#### 4. Scope confusion

```python
# Problem: Getting different instances when expecting the same

# Solution: Check scope configuration
@singleton  # ✅ One instance for app
@scoped(scope_name="request")  # ❌ New instance per request
class ConfigService:
    pass

# Note: Container doesn't expose scope() method directly
# Scope management requires custom implementation or using
# the internal _resolve_scoped method with proper context
```

### Debugging Tips

#### 1. Use the inspector

```python
inspector = container.inspect()

# Check if service can be resolved
if not inspector.can_resolve(MyService):
    print("MyService cannot be resolved!")
    
# Get detailed report
report = inspector.resolution_report(MyService)
print(f"Dependencies: {report['dependencies']}")
print(f"Missing: {[d for d, info in report['dependencies'].items() 
                   if not info['registered']]}")
```

#### 2. Enable debug logging

```python
import logging

logging.basicConfig(level=logging.DEBUG)

# Whiskey will log registration and resolution details
```

#### 3. List all registered services

```python
# See what's available
services = container.inspect().list_services()
print("Registered services:")
for service in services:
    print(f"  - {service.__name__}")
```

#### 4. Trace event flow

```python
@app.on("*")  # Listen to ALL events
async def trace_events(event_data):
    print(f"Event: {event_data}")
```

## Next Steps

Now that you understand Whiskey's core concepts:

1. **Explore Extensions**: Try building a web API with `whiskey-asgi` or a CLI tool with `whiskey-cli`
2. **Read the API Reference**: Dive deeper into specific features in the [API documentation](api.md)
3. **Check Examples**: Look at complete applications in the `examples/` directory
4. **Join the Community**: Get help and share your experiences

Happy coding with Whiskey! 🥃