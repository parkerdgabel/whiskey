# Whiskey Architecture

## Overview

Whiskey is designed as a lightweight, modular dependency injection framework for Python. The architecture emphasizes simplicity, type safety, and extensibility while maintaining a small core footprint.

## Design Principles

### 1. **Simplicity First**
- Dict-like API for intuitive service registration
- Minimal abstractions - no unnecessary complexity
- Clear separation between core DI and additional features

### 2. **Type Safety**
- Full typing support with Python 3.9+ features
- Explicit injection using `Annotated` types
- IDE-friendly with complete type hints

### 3. **Async-First**
- Built for modern async Python applications
- Sync support where needed for compatibility
- Proper async context management

### 4. **Extensibility**
- Small core with extension points
- Plugin system for additional functionality
- Clear boundaries between layers

## Architecture Layers

```
┌─────────────────────────────────────────────────────────┐
│                    Extensions Layer                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │  ASGI    │ │   CLI    │ │    AI    │ │  Config  │  │
│  │  Web     │ │ Commands │ │  Agents  │ │   Mgmt   │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│                  Application Layer                       │
│  ┌─────────────────────────────────────────────────┐   │
│  │            Application Framework                  │   │
│  │  - Lifecycle Management                          │   │
│  │  - Event System                                  │   │
│  │  - Component Metadata                           │   │
│  │  - Extension Loading                            │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│                     Core DI Layer                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │Container │ │Decorators│ │  Scopes  │ │Discovery │  │
│  │  Dict    │ │ @inject  │ │ Lifetime │ │  Auto    │  │
│  │  API     │ │ @provide │ │  Mgmt    │ │  Scan    │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
└─────────────────────────────────────────────────────────┘
```

## Core Components

### Container (`core/container.py`)

The heart of Whiskey's DI system. Manages service registration and resolution.

```python
class Container:
    _services: dict[type, Any]      # Registered services/classes
    _factories: dict[type, Callable] # Factory functions
    _singletons: dict[type, Any]    # Singleton cache
    _scopes: dict[str, Scope]       # Active scopes
    _service_scopes: dict[type, str] # Service → scope mapping
```

**Key Features:**
- Dict-like interface for intuitive use
- Automatic dependency resolution
- Cycle detection
- Factory function support
- Scope management

**Resolution Process:**
1. Check if type is in singleton cache
2. Check if type has a scope and resolve within it
3. Check if type has a factory function
4. Check if type is registered as instance or class
5. If class, instantiate with dependency injection
6. Cache if singleton scope

### Decorators (`core/decorators.py`)

Provides the decorator-based API for registration and injection.

```python
# Registration decorators
@provide     # Register with transient scope
@singleton   # Register with singleton scope
@factory(T)  # Register factory function
@scoped(scope_name="x") # Register with custom scope

# Injection decorator
@inject      # Auto-inject dependencies marked with Inject()
```

**Inject Marker:**
- Uses `Annotated[T, Inject()]` for explicit injection
- Distinguishes DI parameters from regular parameters
- Supports named dependencies (future feature)

### Scopes (`core/scopes.py`)

Controls service lifetimes through context managers.

```python
class Scope:
    name: str
    _instances: dict[type, Any]
    
    def get(service_type) -> T | None
    def set(service_type, instance) -> None
    def clear() -> None  # Calls dispose() on instances
```

**Built-in Scopes:**
- `singleton`: One instance for app lifetime
- `transient`: New instance each time (default)

**Extension Scopes:**
- `request`: Per HTTP request (whiskey-asgi)
- `session`: Per user session (whiskey-ai)
- `conversation`: Per conversation (whiskey-ai)
- `cli_session`: Per CLI invocation (whiskey-cli)

### Application (`core/application.py`)

Rich application framework built on top of the container.

```python
class Whiskey:
    container: Container
    _components: dict[type, ComponentMetadata]
    _lifecycle_phases: list[str]
    _lifecycle_hooks: dict[str, list[Callable]]
    _event_handlers: dict[str, list[Callable]]
    _background_tasks: set[Task]
```

**Lifecycle Phases:**
1. `configure`: Extension configuration
2. `register`: Component registration  
3. `before_startup`: Pre-initialization
4. `startup`: Initialize components
5. `after_startup`: Post-initialization
6. `ready`: Application ready
7. `before_shutdown`: Pre-cleanup
8. `shutdown`: Component disposal
9. `after_shutdown`: Final cleanup

**Event System:**
- Wildcard pattern matching (`user.*`, `*.created`)
- Async event handlers
- Event data passed as dict
- Error isolation (handler errors don't crash app)

### Discovery (`core/discovery.py`)

Automatic component discovery and introspection.

```python
class ComponentDiscoverer:
    def discover_module(module_name, predicate, decorator_name)
    def discover_package(package, recursive, predicate)
    def auto_register(components, scope, condition)

class ContainerInspector:
    def list_services(interface, scope, tags)
    def can_resolve(service_type)
    def resolution_report(service_type)
    def dependency_graph()
```

## Extension Architecture

Extensions are functions that configure an Application instance:

```python
def my_extension(app: Whiskey) -> None:
    # Add lifecycle phases
    app.add_lifecycle_phase("my_phase", after="startup")
    
    # Add decorators
    app.add_decorator("my_decorator", my_decorator_impl)
    
    # Register services
    app.container.register(MyService, scope="singleton")
    
    # Add event handlers
    @app.on("my_event")
    async def handle_my_event(data):
        pass
```

### Extension Patterns

1. **Scope Addition**
   ```python
   app.add_scope("request", RequestScope)
   ```

2. **Decorator Addition**
   ```python
   @app.route("/path")  # Added by ASGI extension
   @app.command()       # Added by CLI extension
   @app.agent("name")   # Added by AI extension
   ```

3. **Service Registration**
   ```python
   app.container[HTTPClient] = httpx.AsyncClient
   app.container[Database] = create_database
   ```

4. **Event Integration**
   ```python
   # Emit framework events
   await app.emit("http.request", {"path": "/", "method": "GET"})
   ```

## Data Flow

### Service Resolution Flow

```
resolve(UserService)
    ↓
Check scopes/singletons
    ↓
Get service registration
    ↓
Extract constructor signature
    ↓
For each parameter:
    - Check if Annotated[T, Inject()]
    - Recursively resolve T
    ↓
Instantiate with resolved deps
    ↓
Cache if scoped
    ↓
Return instance
```

### Request Flow (ASGI Example)

```
HTTP Request
    ↓
ASGI Middleware
    ↓
Create request scope
    ↓
Route matching
    ↓
Handler resolution
    ↓
Inject dependencies
    ↓
Execute handler
    ↓
Clean up scope
    ↓
HTTP Response
```

## Key Design Decisions

### 1. Explicit Injection with Annotated

**Why:** Makes it clear which parameters are injected vs regular parameters.

```python
# Clear what gets injected
def __init__(self,
             db: Annotated[Database, Inject()],    # Injected
             cache: Annotated[Cache, Inject()],     # Injected  
             table_name: str = "users"):            # Not injected
```

### 2. Dict-like Container API

**Why:** Pythonic and intuitive for Python developers.

```python
# Natural Python syntax
container[Service] = implementation
if Service in container:
    service = container[Service]
```

### 3. Async-First with Sync Support

**Why:** Modern Python is async, but compatibility matters.

```python
# Primary API is async
service = await container.resolve(Service)

# Sync available for compatibility
service = container.resolve_sync(Service)
```

### 4. Scope Context Managers

**Why:** Natural Python pattern for resource management.

```python
async with container.scope("request"):
    # Services resolved here share scope
    service1 = await container.resolve(Service)
    service2 = await container.resolve(Service)
    assert service1 is service2
# Cleanup happens automatically
```

### 5. Minimal Core Dependencies

**Why:** Reduces complexity and attack surface.

- Core has zero required dependencies
- Extensions add dependencies as needed
- Users only install what they use

## Performance Considerations

### Resolution Caching
- Singletons cached after first resolution
- Scoped instances cached within scope lifetime
- Constructor signatures cached after first inspection

### Async Overhead
- Minimal overhead for async resolution
- Sync resolution available for hot paths
- Background tasks properly managed

### Memory Management
- Scopes clean up instances automatically
- Weak references considered for future optimization
- Dispose protocol for resource cleanup

## Security Considerations

### Dependency Confusion
- Explicit registration required
- No automatic class discovery by default
- Clear boundaries between user and framework code

### Resource Management
- Proper cleanup through Disposable protocol
- Scope boundaries prevent leaks
- Connection pooling in extensions

## Future Architecture Considerations

### Planned Enhancements

1. **Named Dependencies**
   ```python
   container.register(Database, name="primary")
   container.register(Database, name="readonly")
   ```

2. **Conditional Registration**
   ```python
   @provide(condition=lambda: os.getenv("ENV") == "dev")
   class DevService:
       pass
   ```

3. **Lazy Resolution**
   ```python
   class Service:
       db: Lazy[Database]  # Resolved on first access
   ```

4. **Plugin Discovery**
   ```python
   app.discover_plugins("whiskey_plugins.*")
   ```

### Extension Points

The architecture is designed to be extended without modifying core:

- Custom scopes via Scope base class
- Custom decorators via Application.add_decorator
- Custom lifecycle phases
- Event system for cross-cutting concerns
- Discovery predicates for component selection

## Conclusion

Whiskey's architecture prioritizes simplicity and extensibility. The small core provides essential DI functionality, while the application layer and extensions add rich features for real-world applications. This layered approach keeps the framework approachable while remaining powerful enough for complex use cases.