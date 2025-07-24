# Whiskey Plugin Development Guide

This guide explains how to develop plugins for the Whiskey framework.

## Overview

Whiskey uses a plugin system based on Python entry points. Plugins can:
- Register services with the DI container
- Add event handlers and middleware
- Extend framework functionality
- Depend on other plugins

## Plugin Types

### First-party Plugins
Distributed as package extras: `pip install whiskey[ai]`

### Third-party Plugins
Follow naming convention: `whiskey-{name}`
Example: `whiskey-redis`, `whiskey-auth`

## Creating a Plugin

### 1. Basic Plugin Structure

```python
from whiskey import BasePlugin, Container, Application

class MyPlugin(BasePlugin):
    def __init__(self):
        super().__init__(
            name="myplugin",
            version="1.0.0",
            description="My awesome Whiskey plugin"
        )
        # Declare dependencies on other plugins
        self._dependencies = ["ai"]  # Optional
    
    def register(self, container: Container) -> None:
        """Register services with the DI container."""
        from .services import MyService, MyRepository
        
        container.register_singleton(MyService)
        container.register_scoped(MyRepository)
    
    def initialize(self, app: Application) -> None:
        """Initialize plugin with the application."""
        from .events import MyEvent
        from .middleware import MyMiddleware
        
        # Register event handlers
        @app.on(MyEvent)
        async def handle_my_event(event: MyEvent, service: MyService):
            await service.process(event)
        
        # Register middleware
        @app.middleware
        class MyPluginMiddleware(MyMiddleware):
            pass
```

### 2. Package Structure

```
whiskey-myplugin/
├── pyproject.toml
├── README.md
├── whiskey_myplugin/
│   ├── __init__.py
│   ├── plugin.py      # Plugin class
│   ├── services.py    # Service implementations
│   ├── events.py      # Custom events
│   └── middleware.py  # Middleware classes
└── tests/
    └── test_plugin.py
```

### 3. Configure Entry Point

In `pyproject.toml`:

```toml
[project]
name = "whiskey-myplugin"
version = "1.0.0"
description = "My Whiskey plugin"
dependencies = [
    "whiskey>=0.1.0",
]

[project.entry-points."whiskey.plugins"]
myplugin = "whiskey_myplugin.plugin:MyPlugin"
```

## Plugin API

### Service Registration

```python
def register(self, container: Container) -> None:
    # Singleton - one instance for entire app lifetime
    container.register_singleton(MyService)
    
    # Scoped - new instance per scope (request, etc)
    container.register_scoped(MyRepository)
    
    # Transient - new instance every time
    container.register_transient(MyHelper)
    
    # Factory - custom creation logic
    container.register_factory(
        MyService,
        lambda c: MyService(c.resolve(Config))
    )
```

### Event Handling

```python
def initialize(self, app: Application) -> None:
    # Define custom events
    @dataclass
    class UserCreated:
        user_id: str
        email: str
    
    # Register handlers with DI
    @app.on(UserCreated)
    async def send_welcome_email(
        event: UserCreated,
        email_service: EmailService  # Auto-injected
    ):
        await email_service.send_welcome(event.email)
```

### Middleware

```python
def initialize(self, app: Application) -> None:
    @app.middleware
    class AuthMiddleware:
        def __init__(self, auth_service: AuthService):
            self.auth = auth_service
        
        async def process(self, event: Any, next: Callable):
            # Pre-processing
            if not await self.auth.is_authorized(event):
                raise UnauthorizedError()
            
            # Call next middleware/handler
            result = await next(event)
            
            # Post-processing
            return result
```

## Best Practices

### 1. Namespace Your Services
Prefix service names to avoid conflicts:
```python
container.register_singleton(
    MyService,
    name="myplugin.service"
)
```

### 2. Use Type Hints
Enable proper DI resolution:
```python
class MyService:
    def __init__(self, config: Config, logger: Logger):
        # Services are auto-injected based on type hints
        self.config = config
        self.logger = logger
```

### 3. Handle Dependencies
Declare plugin dependencies:
```python
def __init__(self):
    super().__init__(name="myplugin", version="1.0.0")
    self._dependencies = ["ai", "redis"]
```

### 4. Provide Configuration
Use environment variables or config files:
```python
@dataclass
class MyPluginConfig:
    api_key: str
    timeout: int = 30

def register(self, container: Container) -> None:
    config = MyPluginConfig(
        api_key=os.getenv("MYPLUGIN_API_KEY", ""),
        timeout=int(os.getenv("MYPLUGIN_TIMEOUT", "30"))
    )
    container.register_singleton(MyPluginConfig, instance=config)
```

## Testing Plugins

```python
import pytest
from whiskey import Container, Application
from whiskey.plugins import register_plugin_manually
from whiskey_myplugin import MyPlugin

@pytest.fixture
async def app():
    app = Application()
    
    # Manually register plugin for testing
    register_plugin_manually("myplugin", MyPlugin)
    
    async with app.lifespan():
        yield app

async def test_plugin_services(app):
    # Resolve and test services
    service = await app.container.resolve(MyService)
    assert service is not None
    
    result = await service.do_something()
    assert result == expected_value
```

## Example: Redis Cache Plugin

```python
# whiskey_redis/plugin.py
from whiskey import BasePlugin, Container, Application
import redis.asyncio as redis

class RedisPlugin(BasePlugin):
    def __init__(self):
        super().__init__(
            name="redis",
            version="1.0.0",
            description="Redis integration for Whiskey"
        )
    
    def register(self, container: Container) -> None:
        from .cache import RedisCache
        from .config import RedisConfig
        
        # Register configuration
        config = RedisConfig.from_env()
        container.register_singleton(RedisConfig, instance=config)
        
        # Register Redis client factory
        async def create_redis(config: RedisConfig) -> redis.Redis:
            return await redis.from_url(config.url)
        
        container.register_singleton(
            redis.Redis,
            factory=create_redis
        )
        
        # Register cache service
        container.register_singleton(RedisCache)
    
    def initialize(self, app: Application) -> None:
        # Ensure Redis connection on startup
        @app.on_startup
        async def connect_redis():
            client = await app.container.resolve(redis.Redis)
            await client.ping()
            logger.info("Redis connected")
        
        # Clean up on shutdown
        @app.on_shutdown
        async def disconnect_redis():
            client = await app.container.resolve(redis.Redis)
            await client.close()
            logger.info("Redis disconnected")
```

## Publishing Your Plugin

1. **Package Structure**: Follow Python packaging best practices
2. **Documentation**: Include README with usage examples
3. **Testing**: Comprehensive test suite
4. **Versioning**: Follow semantic versioning
5. **Distribution**: Publish to PyPI

```bash
# Build and publish
python -m build
python -m twine upload dist/*
```

## Plugin Discovery

Whiskey automatically discovers installed plugins via entry points:

```python
from whiskey import Application

app = Application()
# All installed plugins are discovered and loaded automatically

# Or selectively load plugins
app = Application(ApplicationConfig(
    plugins=["ai", "redis"],  # Only load these
    exclude_plugins=["slow_plugin"]  # Exclude these
))
```

## Debugging

Enable debug logging to see plugin loading:

```python
import logging
logging.getLogger("whiskey.plugins").setLevel(logging.DEBUG)
```

## Contributing

For first-party plugin contributions, see the main Whiskey repository contribution guidelines.