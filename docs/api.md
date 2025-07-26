# Whiskey API Reference

## Core Module (`whiskey`)

### Container

The foundation of Whiskey's dependency injection system.

```python
class Container:
    """A simple dependency injection container with dict-like interface."""
```

#### Methods

##### `__setitem__(service_type: type[T], value: T | type[T] | Callable[..., T]) -> None`
Register a service, class, or factory.

```python
container[Database] = Database("postgresql://...")  # Instance
container[Logger] = Logger                          # Class
container[Cache] = lambda: RedisCache()             # Factory
```

##### `__getitem__(service_type: type[T]) -> T`
Get a service synchronously (for backwards compatibility).

```python
db = container[Database]
```

##### `__contains__(service_type: type) -> bool`
Check if a service is registered.

```python
if Database in container:
    db = await container.resolve(Database)
```

##### `async resolve(service_type: type[T], name: str | None = None) -> T`
Resolve a service asynchronously with dependency injection.

```python
service = await container.resolve(UserService)
```

##### `resolve_sync(service_type: type[T], name: str | None = None) -> T`
Resolve a service synchronously.

```python
service = container.resolve_sync(UserService)
```

##### `register(service_type: type[T], implementation: type[T] | T | None = None, *, scope: str = "transient", name: str | None = None, factory: Callable[..., T] | None = None) -> None`
Register a service with advanced options.

```python
container.register(UserService, scope="singleton")
container.register(Database, factory=create_database)
```

##### `discover(module_or_package: str, **kwargs) -> set[type]`
Discover components in a module or package.

```python
components = container.discover("myapp.services", auto_register=True)
```

##### `inspect() -> ContainerInspector`
Get an inspector for introspection.

```python
inspector = container.inspect()
services = inspector.list_services()
```

Note: Scope management methods (`enter_scope`, `exit_scope`) have been moved to the test compatibility module (`whiskey.core.testing`). For production use, manage scopes through the Application class or custom scope managers.

### Whiskey (Application)

Rich IoC container for building applications.

```python
from whiskey.core.application import Whiskey

class Whiskey:
    """Rich IoC container for building any Python application."""
```

#### Attributes

- `container: Container` - The underlying dependency injection container
- `config: ApplicationConfig` - Application configuration

#### Component Registration

##### `component(cls: type | None = None, **kwargs)`
Register a component (decorator or method).

```python
@app.component
class UserService:
    pass

# Or with options
app.component(UserService, scope="singleton")
```

Note: The decorator aliases `provider`, `managed`, and `system` have been removed for a cleaner API. Use `@app.component` for transient services and `@app.singleton` for singleton services.

#### Lifecycle Management

##### `on(event: str) -> Callable`
Register an event handler.

```python
@app.on("user.created")
async def handle_user_created(data):
    print(f"User created: {data}")

@app.on("http.*")  # Wildcard support
async def log_http(data):
    pass
```

##### `on_startup(func: Callable) -> Callable`
Register a startup hook.

```python
@app.on_startup
async def initialize():
    await db.connect()
```

##### `on_ready(func: Callable) -> Callable`
Register a ready hook (runs after startup).

##### `on_shutdown(func: Callable) -> Callable`
Register a shutdown hook.

##### `on_error(func: Callable) -> Callable`
Register an error handler.

```python
@app.on_error
async def handle_error(error_data):
    print(f"Error: {error_data['error']}")
```

##### `async emit(event: str, data: Any = None) -> None`
Emit an event to all listeners.

```python
await app.emit("user.created", {"id": 123, "name": "Alice"})
```

#### Component Metadata

##### `priority(level: int) -> Callable`
Set component initialization priority.

```python
@app.component
@app.priority(10)  # Higher priority = earlier initialization
class CriticalService:
    pass
```

##### `critical(cls: type) -> type`
Mark a component as critical (must initialize successfully).

##### `requires(*dependencies: type) -> Callable`
Specify component dependencies.

```python
@app.component
@app.requires(Database, Cache)
class UserService:
    pass
```

##### `provides(*capabilities: str) -> Callable`
Declare what capabilities a component provides.

##### `tag(*tags: str) -> Callable`
Add tags to a component.

#### Discovery

##### `discover(module_or_package: str, *, auto_register: bool = False, decorator_name: str | None = None, **kwargs) -> set[type]`
Discover components in modules/packages.

```python
# Discover and auto-register
components = app.discover("myapp.services", auto_register=True)

# Find decorated classes
entities = app.discover("myapp.models", decorator_name="_entity")
```

##### `list_components(*, interface: type | None = None, scope: str | None = None, tags: set[str] | None = None) -> list[type]`
List registered components with filters.

```python
# All singletons
singletons = app.list_components(scope="singleton")

# Components with specific interface
handlers = app.list_components(interface=EventHandler)
```

##### `inspect_component(component_type: type) -> dict[str, Any]`
Get detailed component information.

```python
info = app.inspect_component(UserService)
print(f"Dependencies: {info['dependencies']}")
print(f"Can resolve: {info['can_resolve']}")
```

#### Execution

##### `run(main: Callable | None = None) -> None`
Run the application with lifecycle management.

```python
# Run with default behavior
app.run()

# Run with custom main
async def main():
    print("Running!")

app.run(main)
```

##### `async lifespan()`
Context manager for application lifecycle.

```python
async with app.lifespan():
    # Application is initialized
    await do_work()
    # Application will shutdown on exit
```

### Decorators

#### `@inject`
Automatically inject dependencies into functions.

```python
@inject
async def process_user(
    user_id: int,      # Regular parameter
    service: UserService  # Automatically injected
):
    return await service.get_user(user_id)
```

#### `@provide`
Register a class with the default container.

```python
@provide
class EmailService:
    pass
```

#### `@singleton`
Register a class as a singleton.

```python
@singleton
class Configuration:
    def __init__(self):
        self.settings = load_settings()
```

#### `@factory(service_type: type[T])`
Register a factory function.

```python
@factory(Database)
def create_database() -> Database:
    return Database(os.getenv("DATABASE_URL"))
```

#### `@scoped(scope_name: str)`
Register a class with a custom scope.

```python
@scoped(scope_name="request")
class RequestContext:
    pass
```

### Types

#### `Inject`
Marker for explicit dependency injection in type annotations.

Whiskey uses automatic injection based on type hints. Parameters with type hints but no default values are automatically injected:

```python
class Service:
    def __init__(self,
                 # Will be injected (has type hint, no default)
                 db: Database,
                 # Won't be injected (has default value)
                 timeout: int = 30):
        pass
```

#### `Scope`
Base class for custom scopes.

```python
class Scope:
    """Base class for dependency scopes."""
    
    def get(self, key: str) -> Any | None:
        """Get a service instance from the scope."""
        
    def set(self, key: str, instance: Any) -> None:
        """Store a service instance in the scope."""
        
    def clear(self) -> None:
        """Clear all instances from the scope."""
```

#### `Initializable`
Protocol for components with initialization.

```python
class Initializable(Protocol):
    async def initialize(self) -> None:
        """Initialize the component."""
```

#### `Disposable`
Protocol for components with cleanup.

```python
class Disposable(Protocol):
    async def dispose(self) -> None:
        """Clean up resources."""
```

### Discovery

#### `ComponentDiscoverer`
Discovers components in modules and packages.

```python
discoverer = ComponentDiscoverer(container)
components = discoverer.discover_module("myapp.services")
discoverer.auto_register(components)
```

#### `ContainerInspector`
Provides introspection capabilities.

```python
inspector = ContainerInspector(container)

# List services
services = inspector.list_services(scope="singleton")

# Check resolution
can_resolve = inspector.can_resolve(UserService)

# Get detailed report
report = inspector.resolution_report(UserService)

# Build dependency graph
graph = inspector.dependency_graph()
```

#### `discover_components()`
Convenience function for discovery.

```python
components = discover_components(
    "myapp.services",
    container=container,
    auto_register=True,
    predicate=lambda cls: hasattr(cls, "_service")
)
```

## Extension APIs

### whiskey-ai

#### `ai_extension(app: Whiskey)`
Adds AI/LLM capabilities to applications.

#### Decorators

##### `@app.agent(name: str)`
Register an AI agent.

```python
@app.agent("translator")
class TranslatorAgent:
    @inject
    async def process(self, text: str, llm: LLMClient):
        return await llm.complete(f"Translate: {text}")
```

##### `@app.tool(name: str, description: str)`
Register a tool for function calling.

```python
@app.tool("search", "Search the web")
async def search_tool(query: str) -> str:
    return f"Results for: {query}"
```

#### Classes

- `LLMClient` - Base LLM client interface
- `OpenAIClient` - OpenAI API implementation
- `Message` - Chat message
- `Conversation` - Conversation management
- `Agent` - Base agent class

### whiskey-asgi

#### `asgi_extension(app: Whiskey)`
Adds ASGI web framework support.

#### Route Decorators

```python
@app.get("/path")
@app.post("/path")
@app.put("/path")
@app.delete("/path")
@app.patch("/path")
@app.options("/path")
@app.head("/path")
```

#### Middleware

```python
@app.middleware
async def cors_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response
```

#### Classes

- `Request` - ASGI request wrapper
- `Response` - ASGI response
- `WebSocket` - WebSocket connection
- `Router` - URL routing

### whiskey-cli

#### `cli_extension(app: Whiskey)`
Adds CLI application support.

#### Command Registration

```python
@app.command(name="greet", group="utils")
@app.argument("name", help="Name to greet")
@app.option("--loud", "-l", is_flag=True, help="Shout the greeting")
async def greet_command(name: str, loud: bool):
    greeting = f"Hello, {name}!"
    print(greeting.upper() if loud else greeting)
```

#### Methods

- `app.run_cli()` - Run as CLI application
- `app.group(name, help)` - Create command group

### whiskey-config

#### `config_extension(app: Application)`
Adds configuration management.

#### Configuration

```python
app.configure_config(
    schema=AppConfig,           # Dataclass schema
    sources=["config.yaml", "ENV"],  # Config sources
    env_prefix="MYAPP_",       # Environment variable prefix
    watch=True,                # Hot reload
    watch_interval=1.0         # Check interval
)
```

#### Providers

##### `Setting`
Inject configuration values.

```python
@inject
def create_server(
    port: int = Setting("server.port", default=8000),
    debug: bool = Setting("debug")
):
    return Server(port, debug)
```

##### `ConfigSection`
Inject typed configuration sections.

```python
@inject
def create_database(
    config: DatabaseConfig = ConfigSection(DatabaseConfig, "database")
):
    return Database(config.url)
```

#### Decorators

```python
@app.config("database")
@dataclass
class DatabaseConfig:
    host: str = "localhost"
    port: int = 5432
```

## Scopes

### Built-in Scopes

- `singleton` - One instance for entire application lifetime
- `transient` - New instance for each resolution (default)

### Extension Scopes

#### whiskey-asgi
- `request` - One instance per HTTP request
- `session` - One instance per HTTP session

#### whiskey-ai  
- `conversation` - One instance per conversation
- `ai_context` - One instance per AI operation

### Custom Scopes

```python
from whiskey import Scope

class TenantScope(Scope):
    """Scope for multi-tenant applications."""
    
    def __init__(self):
        super().__init__("tenant")
        self._tenants = {}
    
    def set_tenant(self, tenant_id: str):
        self._current_tenant = tenant_id
        if tenant_id not in self._tenants:
            self._tenants[tenant_id] = {}
    
    def get(self, key: str) -> Any:
        tenant_data = self._tenants.get(self._current_tenant, {})
        return tenant_data.get(key)
    
    def set(self, key: str, instance: Any):
        tenant_data = self._tenants.setdefault(self._current_tenant, {})
        tenant_data[key] = instance

# Register the scope
app.add_scope("tenant", TenantScope)
```

## Type Annotations

Whiskey leverages Python's type system for dependency injection:

### Using `Annotated`

```python
from typing import Annotated

# Explicit injection
db: Annotated[Database, Inject()]

# Named injection (future feature)
primary_db: Annotated[Database, Inject(name="primary")]

# No injection - just type hint
table_name: str
```

### Protocol Types

```python
from typing import Protocol

class Cache(Protocol):
    async def get(self, key: str) -> Any: ...
    async def set(self, key: str, value: Any) -> None: ...

# Register implementation
container[Cache] = RedisCache()

# Inject protocol
@inject
async def get_user(
    user_id: int,
    cache: Annotated[Cache, Inject()]
):
    return await cache.get(f"user:{user_id}")
```