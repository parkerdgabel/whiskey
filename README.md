# Whiskey 🥃

A simple, Pythonic dependency injection framework for AI applications.

## Features

- **Simple API**: Dict-like container interface that feels natural
- **Rich IoC**: Full lifecycle management with events and metadata
- **Async-First**: Built for modern async Python applications
- **Zero Dependencies**: Core has no required dependencies
- **Event-Driven**: Built-in event emitter with wildcard support
- **Extensible**: Rich extension API for building any kind of app
- **Type-Safe**: Full type hints and IDE support
- **AI-Ready**: Perfect for LLM apps with specialized extensions

## Quick Start

```python
from whiskey import Application, inject

# Create application
app = Application()

# Register components with metadata
@app.component
@app.priority(10)  # Startup order
@app.provides("database")
class Database:
    async def initialize(self):
        print("Connected to database")

@app.component
@app.requires(Database)
class UserService:
    def __init__(self, db: Database):
        self.db = db

# Event handlers
@app.on("user.created")
async def send_welcome(user):
    print(f"Welcome {user['name']}!")

# Lifecycle hooks
@app.on_ready
async def ready():
    print("Application ready!")

# Run with automatic lifecycle
async with app.lifespan():
    await app.emit("user.created", {"name": "Alice"})
```

## Core Concepts

### Simple Container API

Whiskey's container works like a Python dict:

```python
from whiskey import Container

container = Container()

# Register services
container[Database] = Database("postgresql://...")
container[EmailService] = EmailService
container[Cache] = lambda: RedisCache("localhost")

# Resolve services
db = await container.resolve(Database)

# Dict-like operations
if Database in container:
    db = await container.resolve(Database)

# Context manager for scoping
with container:
    service = await container.resolve(MyService)
```

### Scopes

Core scopes (built-in):
- `singleton` - One instance for the entire application
- `transient` - New instance for each request (default)
- `request` - One instance per HTTP request

AI scopes (via whiskey-ai extension):
- `session` - One instance per user session  
- `conversation` - One instance per AI conversation
- `ai_context` - One instance per AI operation

### Decorators

- `@provide` - Register a class as an injectable service
- `@singleton` - Register as a singleton service
- `@inject` - Automatically inject dependencies into functions
- `@factory` - Register a factory function

### Rich Lifecycle & Events

```python
# Lifecycle phases
@app.before_startup
async def init_resources():
    print("Initializing...")

@app.after_shutdown  
async def cleanup():
    print("Cleaning up...")

# Event system with wildcards
@app.on("http.request.*")
async def log_requests(event_data):
    print(f"HTTP Event: {event_data}")

# Error handling
@app.on_error
async def handle_errors(error):
    print(f"Error: {error['message']}")
```

### Extensions

Extensions can add new features to the Application:

```python
# Create an extension
def monitoring_extension(app):
    # Add custom lifecycle phase
    app.add_lifecycle_phase("metrics_init", after="startup")
    
    # Add custom decorator
    def tracked(cls):
        cls._metrics_enabled = True
        return cls
    
    app.add_decorator("tracked", tracked)
    
    # Listen to events
    @app.on("application.*")
    async def monitor_app(event):
        print(f"Monitor: {event}")

# Use extensions
app = Application().use(
    monitoring_extension,
    # ... other extensions
)
```

### First-Party Extensions

- **whiskey-ai**: AI/LLM-specific scopes and utilities
- **whiskey-asgi**: ASGI web framework support
- **whiskey-cli**: CLI application support

## Installation

```bash
pip install whiskey
```

## Development

```bash
# Install with dev dependencies
uv sync

# Run tests
uv run pytest

# Format code
uv run ruff format

# Lint
uv run ruff check
```

## License

MIT