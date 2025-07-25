# Whiskey 🥃

Simple, Pythonic dependency injection for modern Python applications.

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Why Whiskey?

Whiskey is a dependency injection framework designed for Python developers who value simplicity and clarity. It provides powerful IoC (Inversion of Control) capabilities without the complexity often associated with enterprise DI frameworks.

### Key Principles

- **Pythonic**: Uses familiar Python idioms like dict-like containers and decorators
- **Type-Safe**: Full typing support with `Annotated` for explicit injection
- **Async-First**: Built for modern async/await Python applications
- **Zero Dependencies**: Core has no required dependencies
- **Extensible**: Rich extension system for different application types

## Quick Start

```python
from typing import Annotated
from whiskey import Container, Inject, inject
from whiskey.core.application import Whiskey as Application

# Simple container usage
container = Container()
container[Database] = Database("postgresql://...")
db = await container.resolve(Database)

# Or use the Whiskey class for rich features
app = Application()  # Application is imported as Whiskey

@app.component
class EmailService:
    def __init__(self, 
                 # Explicit injection with Annotated
                 smtp: Annotated[SmtpClient, Inject()],
                 # Regular parameter - not injected
                 sender: str = "noreply@example.com"):
        self.smtp = smtp
        self.sender = sender

# Automatic injection in functions
@inject
async def send_welcome_email(
    user: User,
    email_service: Annotated[EmailService, Inject()]
):
    await email_service.send(user.email, "Welcome!")

# Run with lifecycle management
async with app.lifespan():
    await send_welcome_email(new_user)
```

## Installation

```bash
# Core framework
pip install whiskey

# With extensions
pip install whiskey[ai]    # AI/LLM support
pip install whiskey[web]   # ASGI web framework
pip install whiskey[cli]   # CLI applications
pip install whiskey[all]   # Everything
```

## Core Concepts

### 1. Container - The Foundation

The Container is a dict-like object that manages your dependencies:

```python
from whiskey import Container

container = Container()

# Register services - feels like using a dict!
container[Logger] = Logger("app.log")              # Instance
container[Database] = Database                     # Class (lazy instantiation)
container[Cache] = lambda: RedisCache("localhost") # Factory function

# Named dependencies for multiple implementations
container[Database, "primary"] = PostgresDB("postgres://primary")
container[Database, "readonly"] = PostgresDB("postgres://readonly")

# Resolve dependencies
logger = await container.resolve(Logger)
primary_db = await container.resolve(Database, name="primary")

# Dict-like operations
if Logger in container:
    logger = container[Logger]  # Sync resolve for compatibility
if (Database, "primary") in container:
    db = container[Database, "primary"]
```

### 2. Dependency Injection

Whiskey supports explicit injection using `Annotated` types, including named dependencies and lazy resolution:

```python
from typing import Annotated
from whiskey import Inject, inject, Lazy

class UserRepository:
    def __init__(self,
                 # Named dependency injection
                 primary_db: Annotated[Database, Inject(name="primary")],
                 readonly_db: Annotated[Database, Inject(name="readonly")],
                 # Lazy dependency - resolved only when accessed
                 cache: Annotated[Lazy[Cache], Inject()],
                 # Won't be injected - just a type hint
                 table_name: str = "users"):
        self.primary_db = primary_db
        self.readonly_db = readonly_db
        self.cache = cache  # Not resolved yet!
        self.table_name = table_name
    
    async def find(self, user_id: int):
        # Lazy dependency resolved on first access
        cached = self.cache.value.get(f"user:{user_id}")
        if cached:
            return cached
        
        user = await self.readonly_db.query("SELECT * FROM users WHERE id = ?", user_id)
        self.cache.value.set(f"user:{user_id}", user)
        return user

# Inject into functions
@inject
async def get_user(
    user_id: int,
    repo: Annotated[UserRepository, Inject()]
) -> User:
    return await repo.find(user_id)
```

### 3. Scopes & Conditional Registration

Control the lifecycle of your services and register them conditionally:

```python
from whiskey import scoped, singleton, provide
from whiskey.core.conditions import env_equals, env_exists
import os

# Singleton - one instance for the entire app
@singleton
class Configuration:
    def __init__(self):
        self.settings = load_settings()

# Conditional registration based on environment
@provide(condition=env_equals("ENV", "development"))
class DevEmailService:
    def send(self, to: str, subject: str, body: str):
        print(f"DEV: Email to {to}: {subject}")

@provide(condition=env_equals("ENV", "production"))
class ProdEmailService:
    def send(self, to: str, subject: str, body: str):
        # Actually send email
        smtp.send(to, subject, body)

# Named conditional services
@singleton(name="cache", condition=env_exists("REDIS_URL"))
class RedisCache:
    def __init__(self):
        self.client = redis.from_url(os.getenv("REDIS_URL"))

@singleton(name="cache", condition=lambda: not env_exists("REDIS_URL")())
class MemoryCache:
    def __init__(self):
        self.data = {}

# Scoped - different instance per scope
@scoped(scope_name="request")
class RequestContext:
    def __init__(self):
        self.request_id = generate_id()

# Note: Scope management requires custom implementation
# as Container doesn't expose scope() method directly
```

### 4. Component Discovery

Automatically discover and register components:

```python
# Discover all classes in a module
components = container.discover("myapp.services", auto_register=True)

# With filtering
handlers = container.discover(
    "myapp.handlers",
    predicate=lambda cls: cls.__name__.endswith("Handler"),
    auto_register=True
)

# Inspect what's available
inspector = container.inspect()
print(inspector.list_services())              # All services
print(inspector.can_resolve(UserService))     # Check before resolving
print(inspector.resolution_report(Service))   # Detailed analysis
```

### 5. Application Class

For full-featured applications with lifecycle management:

```python
from whiskey.core.application import Whiskey

app = Whiskey()

# Register components with metadata
@app.component
@app.priority(10)
@app.critical  # Must initialize successfully
class DatabaseService:
    async def initialize(self):
        await self.connect()
    
    async def dispose(self):
        await self.disconnect()

# Lifecycle hooks
@app.on_startup
async def configure():
    print("Starting up...")

@app.on_ready
async def ready():
    print("Application ready!")

# Event-driven
@app.on("user.created")
async def send_welcome_email(user_data):
    print(f"Welcome {user_data['name']}!")

# Run with automatic lifecycle
if __name__ == "__main__":
    app.run()
```

## Extensions

### 🤖 whiskey-ai

AI/LLM application support with specialized scopes and utilities:

```python
from whiskey_ai import ai_extension
from whiskey.core.application import Whiskey

app = Whiskey()
app.use(ai_extension)

@app.agent("translator")
class TranslatorAgent:
    @inject
    async def process(self, 
                     text: str,
                     llm: Annotated[LLMClient, Inject()]):
        return await llm.complete(f"Translate to Spanish: {text}")

# Scoped to conversation
@scoped(scope_name="conversation")
class ConversationMemory:
    def __init__(self):
        self.messages = []
```

### 🌐 whiskey-asgi

Build web applications with dependency injection:

```python
from whiskey_asgi import asgi_extension
from whiskey.core.application import Whiskey

app = Whiskey()
app.use(asgi_extension)

@app.get("/users/{user_id}")
@inject
async def get_user(
    user_id: int,
    repo: Annotated[UserRepository, Inject()]
) -> dict:
    user = await repo.find(user_id)
    return {"id": user.id, "name": user.name}

# Middleware with DI
@app.middleware
@inject
async def log_requests(
    request: Request,
    call_next,
    logger: Annotated[Logger, Inject()]
):
    logger.info(f"{request.method} {request.url}")
    return await call_next(request)
```

### 💻 whiskey-cli

Create CLI applications with automatic DI:

```python
from whiskey_cli import cli_extension
from whiskey.core.application import Whiskey

app = Whiskey()
app.use(cli_extension)

@app.command()
@app.argument("name")
@inject
async def greet(
    name: str,
    greeter: Annotated[GreetingService, Inject()]
):
    """Greet someone."""
    message = await greeter.create_greeting(name)
    print(message)

# Run: python app.py greet Alice
```

### 🔧 whiskey-config

Configuration management with hot reloading:

```python
from whiskey_config import config_extension, Setting
from whiskey.core.application import Whiskey

app = Whiskey()
app.use(config_extension)

@dataclass
class AppConfig:
    debug: bool = False
    database_url: str = "sqlite:///app.db"
    port: int = 8000

app.configure_config(
    schema=AppConfig,
    sources=["config.yaml", "ENV"],
    watch=True  # Hot reload
)

# Inject configuration values
@inject
def create_server(
    port: int = Setting("port"),
    debug: bool = Setting("debug")
):
    return Server(port=port, debug=debug)
```

## New Features

### Named Dependencies

Register multiple implementations of the same interface:

```python
from whiskey import Container, provide, singleton
from typing import Annotated

# Register multiple database connections
container[Database, "primary"] = PostgresDB("postgres://primary")
container[Database, "analytics"] = PostgresDB("postgres://analytics")
container[Database, "cache"] = RedisDB("redis://cache")

# Use with decorators
@provide(name="email")
class SMTPService:
    pass

@provide(name="sms")
class TwilioService:
    pass

# Inject named dependencies
class NotificationService:
    def __init__(self,
                 email: Annotated[SMTPService, Inject(name="email")],
                 sms: Annotated[TwilioService, Inject(name="sms")]):
        self.email = email
        self.sms = sms
```

### Conditional Registration

Register services based on runtime conditions:

```python
from whiskey.core.conditions import (
    env_equals, env_exists, env_truthy,
    all_conditions, any_conditions, not_condition
)

# Environment-based registration
@provide(condition=env_equals("ENV", "development"))
class DevLogger:
    def log(self, msg): print(f"DEV: {msg}")

@provide(condition=env_equals("ENV", "production"))
class ProdLogger:
    def log(self, msg): syslog.info(msg)

# Feature flags
@singleton(condition=env_truthy("ENABLE_CACHING"))
class CacheService:
    pass

# Complex conditions
@provide(condition=all_conditions(
    env_exists("API_KEY"),
    not_condition(env_equals("ENV", "test"))
))
class ExternalAPIClient:
    pass

# Custom conditions
@provide(condition=lambda: datetime.now().hour < 18)  # Only during business hours
class BusinessHoursService:
    pass
```

### Lazy Resolution

Defer expensive dependency resolution until needed:

```python
from whiskey import Lazy
from typing import Annotated

class ExpensiveService:
    def __init__(self):
        print("Expensive initialization!")
        self.data = load_big_dataset()

class ConsumerService:
    def __init__(self,
                 # Lazy dependency - not initialized yet
                 expensive: Lazy[ExpensiveService],
                 # Regular dependency - initialized immediately
                 cheap: Annotated[CheapService, Inject()]):
        self.expensive = expensive
        self.cheap = cheap
        print("Consumer created - expensive service not yet initialized")
    
    def use_expensive(self):
        # First access triggers initialization
        return self.expensive.value.data
    
    def check_if_loaded(self) -> bool:
        return self.expensive.is_resolved

# Lazy with named dependencies
class DatabaseService:
    def __init__(self,
                 primary: Annotated[Lazy[Database], Inject(name="primary")],
                 replica: Annotated[Lazy[Database], Inject(name="replica")]):
        self.primary = primary
        self.replica = replica
    
    async def read(self, query: str):
        # Use replica for reads (resolved lazily)
        return await self.replica.value.execute(query)
    
    async def write(self, query: str):
        # Use primary for writes (resolved lazily)
        return await self.primary.value.execute(query)

# Lazy descriptors for class-level lazy attributes
from whiskey.core.lazy import LazyDescriptor

class ServiceWithLazyAttrs:
    database = LazyDescriptor(Database)
    cache = LazyDescriptor(Cache, name="redis")
    
    def __init__(self):
        pass  # No dependencies resolved yet
    
    def do_work(self):
        # First access creates Lazy instances and resolves them
        data = self.database.value.query("SELECT * FROM items")
        self.cache.value.set("items", data)
        return data
```

## Advanced Features

### Event System

Built-in event emitter with wildcard support:

```python
# Emit events
await app.emit("user.created", {"id": 123, "email": "user@example.com"})

# Listen to specific events
@app.on("user.created")
async def on_user_created(data):
    print(f"User {data['id']} created")

# Wildcard listeners
@app.on("user.*")
async def on_any_user_event(data):
    print(f"User event: {data}")
```

### Error Handling

Graceful error handling throughout the lifecycle:

```python
@app.on_error
async def handle_errors(error_data):
    error = error_data["error"]
    phase = error_data["phase"]
    print(f"Error in {phase}: {error}")
    
    # Optionally, stop propagation
    if isinstance(error, CriticalError):
        raise

# Errors in handlers won't crash the app
@app.on("user.created")
async def buggy_handler(data):
    raise ValueError("Oops!")  # Will be caught and logged
```

### Custom Extensions

Create your own extensions:

```python
def metrics_extension(app: Whiskey):
    """Add metrics collection to any Whiskey app."""
    
    # Add custom lifecycle phase
    app.add_lifecycle_phase("metrics_setup", after="startup")
    
    # Add custom decorator
    def measured(cls):
        original_init = cls.__init__
        
        def __init__(self, *args, **kwargs):
            start = time.time()
            original_init(self, *args, **kwargs)
            duration = time.time() - start
            app.emit("metric.timing", {
                "class": cls.__name__,
                "phase": "init",
                "duration": duration
            })
        
        cls.__init__ = __init__
        return cls
    
    app.add_decorator("measured", measured)
    
    # Add metrics service
    @app.component
    @singleton
    class MetricsCollector:
        def __init__(self):
            self.metrics = []
        
        @app.on("metric.*")
        async def collect(self, data):
            self.metrics.append(data)

# Use the extension
app.use(metrics_extension)
```

## Best Practices

### 1. Use Explicit Injection

```python
# ✅ Good - explicit about what gets injected
def __init__(self,
             db: Annotated[Database, Inject()],
             cache: Annotated[Cache, Inject()],
             timeout: int = 30):
    ...

# ❌ Avoid - unclear what gets injected
def __init__(self, db: Database, cache: Cache, timeout: int = 30):
    ...
```

### 2. Leverage Type Safety

```python
# Use Protocol for interfaces
from typing import Protocol

class Repository(Protocol):
    async def find(self, id: int) -> Model: ...
    async def save(self, model: Model) -> None: ...

# Register implementations
container[Repository] = PostgresRepository()
```

### 3. Organize with Discovery

```python
# Instead of manual registration
container[ServiceA] = ServiceA
container[ServiceB] = ServiceB
container[ServiceC] = ServiceC

# Use discovery
container.discover("myapp.services", auto_register=True)
```

### 4. Scope Appropriately

```python
# Singleton for stateless services
@singleton
class EmailSender:
    def __init__(self, smtp_client: SmtpClient):
        self.client = smtp_client

# Request scope for stateful contexts
@scoped(scope_name="request")
class RequestContext:
    def __init__(self):
        self.user = None
        self.permissions = []
```

## Testing

Whiskey makes testing easy with its container approach:

```python
import pytest
from whiskey import Container

@pytest.fixture
def container():
    container = Container()
    # Register test doubles
    container[Database] = MockDatabase()
    container[EmailService] = MockEmailService()
    return container

async def test_user_service(container):
    service = await container.resolve(UserService)
    user = await service.create_user("test@example.com")
    assert user.email == "test@example.com"
```

## Development

```bash
# Clone the repository
git clone https://github.com/yourusername/whiskey.git
cd whiskey

# Install with dev dependencies
uv sync

# Run tests
uv run pytest

# Run specific test
uv run pytest tests/test_container.py -v

# Format code
uv run ruff format

# Lint
uv run ruff check

# Type check
uv run mypy src/whiskey
```

## Architecture

Whiskey follows a modular architecture:

```
whiskey/
├── src/whiskey/
│   ├── core/           # Core DI framework
│   │   ├── container.py    # Dict-like container
│   │   ├── decorators.py   # @inject, @singleton, etc.
│   │   ├── discovery.py    # Component discovery
│   │   ├── scopes.py       # Scope management
│   │   └── application.py  # Rich Application class
│   └── __init__.py
├── whiskey_ai/         # AI/LLM extension
├── whiskey_asgi/       # Web framework extension
├── whiskey_cli/        # CLI extension
├── whiskey_config/     # Configuration extension
└── examples/           # Example applications
```

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

Whiskey is inspired by dependency injection frameworks across many languages, particularly:
- Python: FastAPI, Injector, Dependency Injector
- C#: ASP.NET Core DI, Autofac
- Java: Spring, Guice
- TypeScript: InversifyJS, TSyringe

Special thanks to the Python community for feedback and contributions.