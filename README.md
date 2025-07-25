# Whiskey 🥃

A simple, Pythonic dependency injection framework for AI applications.

## Features

- **Simple API**: Dict-like container interface that feels natural
- **Async-First**: Built for modern async Python applications
- **Minimal Core**: Under 500 lines of code with zero required dependencies
- **Type-Safe**: Full type hints and IDE support
- **Flexible Scopes**: Singleton, transient, and custom scopes
- **Easy Extensions**: Extend with simple functions, not complex plugins
- **AI-Ready**: Perfect for LLM apps with conversation and session scopes

## Quick Start

```python
from whiskey import Application, inject, singleton

# Define services
@singleton
class ConfigService:
    def __init__(self):
        self.api_key = "your-api-key"

@singleton
class AIService:
    def __init__(self, config: ConfigService):
        self.config = config
    
    async def process(self, prompt: str):
        # Your AI logic here
        return f"Processed: {prompt}"

# Create application
app = Application()

# Use with automatic injection
@inject
async def handle_request(prompt: str, ai: AIService):
    return await ai.process(prompt)

# Run it
async with app.lifespan():
    result = await handle_request("Hello AI!")
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

### Extensions

Extend Whiskey with simple functions:

```python
# Create an extension
def redis_extension(app):
    @singleton
    class RedisClient:
        async def get(self, key): ...
        async def set(self, key, value): ...
    
    app.container.register_singleton(RedisClient)

# Use extensions
app = Application()
app.extend(redis_extension)

# Or chain multiple
from whiskey_ai import ai_extension
from whiskey_asgi import asgi_extension

app = Application().use(
    ai_extension,    # Adds AI-specific scopes
    asgi_extension,  # Adds web framework support
    redis_extension, # Your custom extension
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