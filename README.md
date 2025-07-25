# Whiskey >C

A next-generation dependency injection and IoC framework for Python AI applications.

## Features

- **AI-First Design**: Built specifically for AI workloads with native support for model management, token tracking, and conversation contexts
- **Simple Extensions**: Extend functionality with plain Python functions - no complex plugin system
- **Zero-Config Magic**: Convention-over-configuration with intelligent defaults
- **Autodiscovery**: Automatic component discovery based on Python conventions
- **Type-Safe**: Full type hints and runtime validation
- **Async-Native**: First-class support for async/await patterns
- **Framework Agnostic**: Works with FastAPI, Django, Flask, and pure Python

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

### Container Syntactic Sugar

Whiskey's container provides Pythonic shortcuts for common operations:

```python
from whiskey import Container, singleton

container = Container()

# Dict-like access
service = container[MyService]  # Same as container.resolve_sync(MyService)

# Safe access with defaults
service = container.get(MyService, default=None)  # Returns None if not found

# Check if registered
if MyService in container:
    service = container[MyService]

# Context manager for automatic cleanup
with Container() as temp_container:
    temp_container.register_singleton(Database, Database)
    # Container is disposed when exiting context

# Iteration and dict methods
for service_type in container:
    print(service_type)

for key, descriptor in container.items():
    print(f"{key}: {descriptor.scope}")
```

### Scopes

Whiskey provides several built-in scopes:

- `singleton` - One instance for the entire application
- `transient` - New instance for each request
- `request` - One instance per HTTP request
- `session` - One instance per user session
- `conversation` - One instance per AI conversation
- `ai_context` - One instance per AI operation

### Decorators

- `@provide` - Register a class as an injectable service
- `@singleton` - Register as a singleton service
- `@inject` - Automatically inject dependencies into functions
- `@factory` - Register a factory function

### Extensions

Whiskey uses simple functions to extend functionality:

```python
# Create an extension
def redis_extension(app):
    @app.service
    class RedisClient:
        async def get(self, key): ...
        async def set(self, key, value): ...

# Use extensions
app = Application()
app.extend(redis_extension)

# Or use multiple at once
from whiskey_ai import ai_extension
from whiskey_asgi import asgi_extension

app = Application().use(
    ai_extension,    # Adds AI-specific scopes
    asgi_extension,  # Adds web framework support
    redis_extension, # Adds Redis client
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