# Autodiscovery in Whiskey

Whiskey provides Pythonic automatic component discovery that reduces boilerplate while maintaining explicit, readable code.

## How It Works

Whiskey discovers components using Python conventions:

1. **Type hints** in `__init__` methods for automatic dependency injection
2. **Naming conventions** for automatic scoping
3. **Module exports** via `__all__`
4. **Factory functions** following naming patterns

## Basic Usage

```python
from whiskey import Application, ApplicationConfig, autodiscover

# Enable autodiscovery for your application
app = Application(ApplicationConfig(
    component_scan_packages=["myapp.services", "myapp.repositories"],
    # Or scan specific paths
    component_scan_paths=["./src/components"],
))

# Or manually trigger discovery
autodiscover("myapp.services", "myapp.repositories")
```

## Discovery Rules

### 1. Type Hints Enable Injection

Classes with typed dependencies are automatically discovered:

```python
class UserService:
    def __init__(self, repository: UserRepository, cache: Cache):
        # Type hints enable automatic injection
        self.repository = repository
        self.cache = cache
```

### 2. Naming Conventions Determine Scope

| Suffix | Scope | Example |
|--------|-------|---------|
| `*Service` | Singleton | `UserService`, `EmailService` |
| `*Repository` | Singleton | `UserRepository`, `OrderRepository` |
| `*Controller` | Request | `UserController`, `APIController` |
| `*Handler` | Request | `EventHandler`, `RequestHandler` |
| `*Factory` | Singleton | `ConnectionFactory` |
| `*Manager` | Singleton | `CacheManager`, `SessionManager` |
| `*Provider` | Singleton | `ConfigProvider`, `DataProvider` |

### 3. File Naming Conventions

Files can also follow conventions:

```
services/
  user_service.py      # Classes here default to singleton
  email_service.py
repositories/
  user_repository.py   # Classes here default to singleton
controllers/
  api_controller.py    # Classes here default to request scope
```

### 4. Factory Functions

Functions with specific prefixes are registered as factories:

```python
def create_database(config: Config) -> Database:
    """Automatically registered as Database factory."""
    return Database(config.connection_string)

def make_cache(size: int = 1000) -> Cache:
    """Automatically registered as Cache factory."""
    return LRUCache(size)

def build_client(api_key: str) -> APIClient:
    """Automatically registered as APIClient factory."""
    return APIClient(api_key)
```

### 5. Module Exports

Use `__all__` to explicitly control what's discovered:

```python
# Only classes in __all__ will be discovered from this module
__all__ = ["PublicService", "PublicRepository"]

class PublicService:
    """This will be discovered."""
    pass

class _PrivateHelper:
    """This won't be discovered (not in __all__)."""
    pass

class InternalService:
    """This won't be discovered either."""
    pass
```

## Explicit Configuration

When conventions don't fit, use decorators:

```python
from whiskey import discoverable, scope, ScopeType

@discoverable
class SpecialComponent:
    """Mark for discovery when it doesn't follow conventions."""
    pass

@scope(ScopeType.REQUEST)
class CustomHandler:
    """Override the default scope."""
    pass
```

## Complete Example

```python
# app/services/user_service.py
from app.repositories import UserRepository
from app.core import Cache, Logger

class UserService:
    """Automatically singleton (ends with Service)."""
    
    def __init__(
        self, 
        repository: UserRepository,  # Auto-injected
        cache: Cache,               # Auto-injected
        logger: Logger,             # Auto-injected
    ):
        self.repository = repository
        self.cache = cache
        self.logger = logger
    
    async def get_user(self, user_id: str):
        # Check cache first
        if cached := await self.cache.get(f"user:{user_id}"):
            return cached
        
        # Fetch from repository
        user = await self.repository.find_by_id(user_id)
        await self.cache.set(f"user:{user_id}", user)
        return user

# app/repositories/user_repository.py
class UserRepository:
    """Automatically singleton (ends with Repository)."""
    
    def __init__(self, database: Database):
        self.db = database
    
    async def find_by_id(self, user_id: str):
        return await self.db.query_one("SELECT * FROM users WHERE id = ?", user_id)

# app/factories.py
def create_database(config: DatabaseConfig) -> Database:
    """Automatically registered as Database factory."""
    return PostgresDatabase(
        host=config.host,
        port=config.port,
        name=config.database,
    )

# main.py
from whiskey import Application, ApplicationConfig

app = Application(ApplicationConfig(
    component_scan_packages=["app.services", "app.repositories", "app.factories"],
))

if __name__ == "__main__":
    app.run()
```

## Best Practices

### 1. Use Type Hints

Always use type hints for dependencies:

```python
# Good - will be auto-injected
def __init__(self, service: UserService, config: Config):
    ...

# Bad - won't be auto-injected
def __init__(self, service, config):
    ...
```

### 2. Follow Naming Conventions

Use standard suffixes for clarity:

```python
# Good - intent is clear
class UserService: ...
class UserRepository: ...
class UserController: ...

# Less clear
class UserManager: ...  # Is this a service? A repository?
class UserHelper: ...   # Vague purpose
```

### 3. Organize by Feature

Structure your code to make discovery natural:

```
myapp/
  users/
    user_service.py
    user_repository.py
    user_controller.py
  orders/
    order_service.py
    order_repository.py
  shared/
    cache_manager.py
    config_provider.py
```

### 4. Be Explicit When Needed

Don't force conventions when they don't fit:

```python
# If a class doesn't fit conventions, be explicit
@provide(scope=ScopeType.SINGLETON)
class SpecialPurposeComponent:
    ...
```

## Comparison with Other Frameworks

Unlike Spring's classpath scanning or Django's app registry, Whiskey's approach:

- **No magic**: Discovery rules are simple and predictable
- **Type-safe**: Leverages Python's type hints
- **Pythonic**: Follows Python naming conventions
- **Explicit**: Use `__all__` for fine control
- **Fast**: No runtime reflection or metaclass magic

## Troubleshooting

### Components Not Found

Enable debug logging to see discovery details:

```python
import logging
logging.getLogger("whiskey.core.discovery").setLevel(logging.DEBUG)
```

### Circular Dependencies

The framework handles circular dependencies automatically through lazy resolution.

### Scope Conflicts

If automatic scope detection is wrong, override it:

```python
@scope(ScopeType.SINGLETON)  # Force singleton
class MyRequestHandler:
    ...
```