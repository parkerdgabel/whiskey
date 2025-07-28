# Whiskey Documentation

Welcome to the Whiskey framework documentation! Whiskey is a modern, Pythonic dependency injection framework that makes building scalable applications simple and intuitive.

## 📚 Documentation Overview

### Getting Started
- **[Getting Started Guide](getting-started.md)** - Installation, setup, and your first Whiskey app
- **[Core Concepts](core-concepts.md)** - Understanding dependency injection and Whiskey's approach
- **[Examples](examples.md)** - Real-world examples and patterns

### Reference
- **[API Reference](api-reference.md)** - Complete API documentation
- **[Extensions](extensions.md)** - Available extensions and integrations
- **[Testing](testing.md)** - Testing strategies and utilities

### Advanced Topics
- **[Advanced Patterns](advanced.md)** - Performance optimization and complex scenarios
- **[Migration Guide](migration.md)** - Migrating from other DI frameworks

## 🚀 Quick Start

```python
from whiskey import component, singleton, inject

@singleton
class Database:
    def __init__(self):
        self.connection = "connected"

@component
class UserService:
    def __init__(self, db: Database):
        self.db = db  # Automatically injected!

@inject
async def get_users(service: UserService):
    return await service.fetch_all()

# Run your application
if __name__ == "__main__":
    import asyncio
    from whiskey import get_app
    
    app = get_app()
    asyncio.run(app.run(get_users))
```

## 🎯 Key Features

- **Simple & Pythonic** - Natural Python syntax with type hints
- **Async-First** - Built for modern async Python applications
- **Zero Configuration** - Works out of the box with sensible defaults
- **Extensible** - Rich ecosystem of extensions for web, CLI, AI, and more
- **Type-Safe** - Full typing support for better IDE experience
- **Lightweight** - Minimal dependencies, maximum performance

## 📖 Learning Path

1. Start with the [Getting Started Guide](getting-started.md) to install Whiskey and build your first app
2. Learn the [Core Concepts](core-concepts.md) to understand how dependency injection works
3. Explore [Examples](examples.md) to see real-world patterns
4. Dive into [Extensions](extensions.md) for specific use cases (web, CLI, AI)
5. Master [Advanced Patterns](advanced.md) for complex applications

## 🤝 Getting Help

- **GitHub Issues**: [Report bugs or request features](https://github.com/your-org/whiskey/issues)
- **Discussions**: [Ask questions and share ideas](https://github.com/your-org/whiskey/discussions)
- **Examples**: Check the [examples/](../examples/) directory for working code

## 🔧 Available Extensions

| Extension | Description | Install |
|-----------|-------------|---------|
| **whiskey-web** | ASGI web framework support | `pip install whiskey[web]` |
| **whiskey-cli** | CLI application utilities | `pip install whiskey[cli]` |
| **whiskey-ai** | AI/LLM integration scopes | `pip install whiskey[ai]` |
| **whiskey-sql** | Database connection management | `pip install whiskey[sql]` |
| **whiskey-auth** | Authentication and authorization | `pip install whiskey[auth]` |
| **whiskey-jobs** | Background job processing | `pip install whiskey[jobs]` |

## 📝 License

Whiskey is open source software licensed under the MIT license.