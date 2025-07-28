# API Reference

Complete API documentation for the Whiskey framework.

## Core Decorators

### @component

Register a class as a transient component (new instance each time).

```python
@component(
    key: type | str = None,
    name: str = None,
    scope: Scope = Scope.TRANSIENT,
    tags: set[str] = None,
    condition: Callable[[], bool] = None,
    lazy: bool = False
)
```

**Parameters:**
- `key`: Optional registration key (defaults to class type)
- `name`: Optional name for named resolution
- `scope`: Component lifecycle scope
- `tags`: Set of tags for categorization
- `condition`: Registration condition function
- `lazy`: Enable lazy initialization

**Example:**
```python
@component
class UserService:
    pass

@component(name="primary", tags={"core"})
class PrimaryDatabase:
    pass
```

### @singleton

Register a class as a singleton (one instance per application).

```python
@singleton(
    key: type | str = None,
    name: str = None,
    tags: set[str] = None,
    condition: Callable[[], bool] = None,
    lazy: bool = False
)
```

**Example:**
```python
@singleton
class Configuration:
    def __init__(self):
        self.settings = load_settings()
```

### @factory

Register a factory function for creating components.

```python
@factory(
    key: type | str,
    name: str = None,
    scope: Scope = Scope.TRANSIENT,
    tags: set[str] = None,
    condition: Callable[[], bool] = None,
    lazy: bool = False
)
```

**Example:**
```python
@factory(DatabaseConnection, scope=Scope.SINGLETON)
def create_database(config: Configuration):
    return DatabaseConnection(config.db_url)
```

### @scoped

Register a component with a custom scope.

```python
@scoped(
    scope_name: str = "default",
    key: type | str = None,
    name: str = None,
    tags: set[str] = None,
    condition: Callable[[], bool] = None,
    lazy: bool = False
)
```

**Example:**
```python
@scoped("request")
class RequestContext:
    pass
```

### @inject

Enable automatic dependency injection for functions.

```python
@inject
```

**Example:**
```python
@inject
async def process_user(user_id: int, service: UserService):
    return await service.get_user(user_id)
```

### @provide

Alias for `@component` (backward compatibility).

## Container API

### Container

The core service registry and dependency resolver.

```python
class Container:
    def __init__(self, name: str = "default")
```

#### Methods

##### add_singleton
```python
def add_singleton(
    self,
    key: type | str,
    instance: Any = None,
    *,
    factory: Callable = None,
    name: str = None,
    tags: set[str] = None
) -> None
```

Register a singleton component.

##### add_transient
```python
def add_transient(
    self,
    key: type | str,
    factory: Callable = None,
    *,
    implementation: type = None,
    name: str = None,
    tags: set[str] = None
) -> None
```

Register a transient component.

##### add_scoped
```python
def add_scoped(
    self,
    key: type | str,
    scope_name: str,
    factory: Callable = None,
    *,
    implementation: type = None,
    name: str = None,
    tags: set[str] = None
) -> None
```

Register a scoped component.

##### resolve
```python
async def resolve(
    self,
    key: type | str,
    *,
    name: str = None,
    scope: Scope = None
) -> Any
```

Resolve a component asynchronously.

##### resolve_sync
```python
def resolve_sync(
    self,
    key: type | str,
    *,
    name: str = None,
    scope: Scope = None
) -> Any
```

Resolve a component synchronously.

##### call
```python
async def call(
    self,
    func: Callable,
    *args,
    **kwargs
) -> Any
```

Call a function with dependency injection.

##### call_sync
```python
def call_sync(
    self,
    func: Callable,
    *args,
    **kwargs
) -> Any
```

Call a function synchronously with dependency injection.

##### scope
```python
def scope(self, name: str) -> Scope
```

Create a new scope context manager.

**Example:**
```python
container = Container()
container.add_singleton(Database)
container.add_transient(UserService)

async with container.scope("request") as request_scope:
    service = await request_scope.resolve(UserService)
```

## Application API

### Whiskey

The main application class with lifecycle management.

```python
class Whiskey:
    def __init__(
        self,
        name: str = "whiskey",
        version: str = "0.1.0",
        debug: bool = False
    )
```

#### Decorators

##### @app.component
```python
@app.component(
    key: type | str = None,
    name: str = None,
    scope: Scope = Scope.TRANSIENT,
    tags: set[str] = None,
    priority: int = 0,
    critical: bool = False
)
```

Register a component with the application.

##### @app.singleton
```python
@app.singleton(
    key: type | str = None,
    name: str = None,
    tags: set[str] = None,
    priority: int = 0,
    critical: bool = False
)
```

Register a singleton with the application.

##### @app.on_startup
```python
@app.on_startup
```

Register a startup callback.

##### @app.on_shutdown
```python
@app.on_shutdown
```

Register a shutdown callback.

##### @app.on_error
```python
@app.on_error(exception_type: type[Exception] = Exception)
```

Register an error handler.

##### @app.task
```python
@app.task(
    interval: float = None,
    cron: str = None,
    run_at_startup: bool = False
)
```

Register a background task.

#### Methods

##### run
```python
async def run(
    self,
    main_func: Callable = None,
    *,
    host: str = "0.0.0.0",
    port: int = 8000
) -> None
```

Run the application.

##### resolve
```python
async def resolve(
    self,
    key: type | str,
    *,
    name: str = None
) -> Any
```

Resolve a component from the application container.

**Example:**
```python
app = Whiskey(name="my_app", debug=True)

@app.singleton
class Database:
    pass

@app.component
class UserService:
    def __init__(self, db: Database):
        self.db = db

@app.on_startup
async def initialize():
    print("Starting application...")

if __name__ == "__main__":
    asyncio.run(app.run())
```

## Scope API

### Scope

Manages component lifecycles within a specific scope.

```python
class Scope:
    def __init__(self, name: str, parent: Container = None)
```

#### Constants

```python
class Scope(Enum):
    TRANSIENT = "transient"
    SINGLETON = "singleton"
    SCOPED = "scoped"
```

#### Methods

##### resolve
```python
async def resolve(
    self,
    key: type | str,
    *,
    name: str = None
) -> Any
```

Resolve a component within this scope.

##### scope
```python
def scope(self, name: str) -> Scope
```

Create a nested scope.

**Example:**
```python
async with container.scope("request") as request_scope:
    # Components resolved here are scoped to request
    ctx = await request_scope.resolve(RequestContext)
    
    async with request_scope.scope("transaction") as tx_scope:
        # Nested scope
        service = await tx_scope.resolve(Service)
```

## Type Definitions

### ComponentMetadata

```python
@dataclass
class ComponentMetadata:
    key: type | str
    name: str | None = None
    scope: Scope = Scope.TRANSIENT
    tags: set[str] = field(default_factory=set)
    factory: Callable | None = None
    implementation: type | None = None
    priority: int = 0
    critical: bool = False
    lazy: bool = False
    condition: Callable[[], bool] | None = None
```

### ServiceDescriptor

```python
@dataclass
class ServiceDescriptor:
    key: type | str
    lifetime: ServiceLifetime
    factory: Callable | None = None
    implementation: type | None = None
    instance: Any = None
    name: str | None = None
    tags: set[str] = field(default_factory=set)
```

### ServiceLifetime

```python
class ServiceLifetime(Enum):
    TRANSIENT = "transient"
    SINGLETON = "singleton"
    SCOPED = "scoped"
```

## Utility Functions

### resolve

```python
def resolve(key: type | str, *, app: Whiskey = None) -> Any
```

Global function to resolve a component.

### resolve_async

```python
async def resolve_async(key: type | str, *, app: Whiskey = None) -> Any
```

Global async function to resolve a component.

### call

```python
async def call(func: Callable, *args, app: Whiskey = None, **kwargs) -> Any
```

Global function to call with dependency injection.

### call_sync

```python
def call_sync(func: Callable, *args, app: Whiskey = None, **kwargs) -> Any
```

Global function to call synchronously with dependency injection.

### get_app

```python
def get_app() -> Whiskey
```

Get the default application instance.

### configure_app

```python
def configure_app(config_func: Callable[[Whiskey], None]) -> None
```

Configure the default application.

## Conditional Decorators

### @when_env

```python
@when_env(var_name: str, expected_value: str = None)
```

Register component only when environment variable matches.

**Example:**
```python
@component
@when_env("ENVIRONMENT", "production")
class ProductionLogger:
    pass
```

### @when_debug

```python
@when_debug
```

Register component only in debug mode.

### @when_production

```python
@when_production
```

Register component only in production mode.

## Error Types

### CircularDependencyError

Raised when circular dependencies are detected.

```python
class CircularDependencyError(Exception):
    def __init__(self, chain: list[type | str])
```

### ComponentNotFoundError

Raised when a requested component is not registered.

```python
class ComponentNotFoundError(Exception):
    def __init__(self, key: type | str, name: str = None)
```

### ScopeError

Raised when there are scope-related issues.

```python
class ScopeError(Exception):
    pass
```

### ContainerError

Base exception for container-related errors.

```python
class ContainerError(Exception):
    pass
```

## Testing Utilities

### create_test_container

```python
def create_test_container(**overrides) -> Container
```

Create a container for testing with overrides.

### mock_component

```python
def mock_component(key: type | str, mock_instance: Any) -> None
```

Register a mock component for testing.

**Example:**
```python
from whiskey.testing import create_test_container, mock_component

def test_user_service():
    container = create_test_container()
    
    # Mock the database
    mock_db = Mock()
    mock_component(Database, mock_db)
    
    service = container.resolve_sync(UserService)
    assert service.db is mock_db
```