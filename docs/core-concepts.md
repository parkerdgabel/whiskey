# Core Concepts

This guide explains the fundamental concepts behind Whiskey and dependency injection in Python.

## What is Dependency Injection?

Dependency Injection (DI) is a design pattern where objects receive their dependencies from external sources rather than creating them internally. This promotes:

- **Loose Coupling**: Components depend on abstractions, not concrete implementations
- **Testability**: Easy to swap implementations for testing
- **Flexibility**: Change behaviors without modifying code
- **Maintainability**: Clear separation of concerns

### Without Dependency Injection

```python
class EmailService:
    def __init__(self):
        # Tight coupling - creates its own dependencies
        self.smtp_client = SmtpClient("smtp.gmail.com", 587)
        self.template_engine = TemplateEngine()
        self.logger = Logger("email.log")
    
    def send_email(self, to: str, subject: str):
        # Hard to test - depends on real SMTP server
        self.smtp_client.send(to, subject)
```

### With Dependency Injection

```python
class EmailService:
    def __init__(self, smtp_client: SmtpClient, template_engine: TemplateEngine, logger: Logger):
        # Dependencies are injected - loose coupling
        self.smtp_client = smtp_client
        self.template_engine = template_engine
        self.logger = logger
    
    def send_email(self, to: str, subject: str):
        # Easy to test with mock implementations
        self.smtp_client.send(to, subject)
```

## Whiskey's Approach

Whiskey makes dependency injection Pythonic and intuitive:

### 1. Type-Based Resolution

Whiskey uses Python's type hints to automatically resolve dependencies:

```python
@component
class UserService:
    def __init__(self, db: Database, cache: Cache):
        # Whiskey knows what to inject based on type hints
        self.db = db
        self.cache = cache
```

### 2. Decorator-Based Registration

Simple decorators register your components:

```python
@singleton  # One instance for the entire application
class Database:
    pass

@component  # New instance each time
class UserRepository:
    pass

@scoped("request")  # One instance per request
class RequestContext:
    pass
```

### 3. Automatic Injection

The `@inject` decorator enables automatic dependency resolution:

```python
@inject
async def handle_request(
    user_id: int,                    # Regular parameter - must be provided
    user_service: UserService,       # Injected automatically
    logger: Logger = None           # Optional injection
):
    user = await user_service.get_user(user_id)
    if logger:
        logger.info(f"Retrieved user {user_id}")
    return user
```

## Component Lifecycles

Understanding component lifecycles is crucial for proper application design:

### Transient (Default)

New instance created every time it's requested:

```python
@component  # or @component(scope=Scope.TRANSIENT)
class TransientService:
    def __init__(self):
        self.id = uuid.uuid4()  # Different ID each time
```

**Use for**: Stateless services, lightweight objects, request handlers

### Singleton

One instance shared across the entire application:

```python
@singleton  # or @component(scope=Scope.SINGLETON)
class ConfigurationService:
    def __init__(self):
        self.settings = load_settings()  # Loaded once
```

**Use for**: Configuration, connection pools, caches, expensive resources

### Scoped

One instance per scope (e.g., per request, per user session):

```python
@scoped("request")
class RequestContext:
    def __init__(self):
        self.request_id = generate_request_id()
        self.user = None
```

**Use for**: Request-specific data, user sessions, transactions

## The Container

The container is Whiskey's service registry and resolver:

```python
from whiskey import Container

# Create a container
container = Container()

# Register services
container.add_singleton(Database)
container.add_transient(UserService)

# Resolve services
db = await container.resolve(Database)
user_service = await container.resolve(UserService)
```

### Container as a Dict

Whiskey's container behaves like a Python dict:

```python
# Direct registration
container[Database] = Database()
container["api_key"] = "secret-key-123"

# Resolution
db = container[Database]
api_key = container["api_key"]
```

## Dependency Resolution

Whiskey resolves dependencies through a smart algorithm:

### Resolution Process

1. **Check if type is registered**: Look up the component in the container
2. **Analyze constructor**: Inspect `__init__` parameters
3. **Resolve dependencies**: Recursively resolve each parameter
4. **Create instance**: Call constructor with resolved dependencies
5. **Manage lifecycle**: Store singleton, return transient, etc.

### Resolution Rules

```python
class ExampleService:
    def __init__(self,
        # Injected - has type hint, no default
        database: Database,
        
        # NOT injected - has default value  
        timeout: int = 30,
        
        # Injected if available - Optional type
        logger: Optional[Logger] = None,
        
        # NOT injected - built-in type
        name: str,
        
        # Injected - custom type with default None
        cache: Cache = None
    ):
        pass
```

## Injection Patterns

### Constructor Injection

The primary pattern - dependencies injected via `__init__`:

```python
@component
class OrderService:
    def __init__(self, db: Database, payment: PaymentGateway):
        self.db = db
        self.payment = payment
```

### Function Injection

Dependencies injected into standalone functions:

```python
@inject
async def process_order(
    order_id: int,  # Regular parameter
    service: OrderService  # Injected
):
    return await service.process(order_id)
```

### Factory Pattern

For complex initialization logic:

```python
@factory(DatabaseConnection, scope=Scope.SINGLETON)
def create_database(config: Config):
    return DatabaseConnection(
        host=config.db_host,
        port=config.db_port,
        pool_size=config.db_pool_size
    )
```

### Named Dependencies

Multiple implementations of the same interface:

```python
# Register named implementations
@component(name="primary")
class PrimaryDatabase(Database):
    pass

@component(name="replica")
class ReplicaDatabase(Database):
    pass

# Resolve by name
primary_db = await container.resolve(Database, name="primary")
replica_db = await container.resolve(Database, name="replica")
```

## Advanced Concepts

### Lazy Resolution

Defer expensive initialization:

```python
@singleton(lazy=True)
class ExpensiveService:
    def __init__(self):
        print("Only created when first used")
        self._load_data()
```

### Conditional Registration

Register components based on conditions:

```python
@component
@when_env("FEATURE_FLAG", "enabled")
class NewFeatureService:
    pass

@component
@when_debug
class DebugService:
    pass
```

### Circular Dependencies

Whiskey detects and prevents circular dependencies:

```python
# This will raise CircularDependencyError
@component
class ServiceA:
    def __init__(self, b: ServiceB):
        pass

@component  
class ServiceB:
    def __init__(self, a: ServiceA):
        pass
```

**Solutions**:
1. Refactor to remove circular dependency
2. Use lazy initialization
3. Use setter injection (not recommended)

### Scope Hierarchies

Scopes can be nested:

```python
async with container.scope("request") as request_scope:
    async with request_scope.scope("transaction") as tx_scope:
        # Components resolved here live in transaction scope
        service = await tx_scope.resolve(Service)
```

## Best Practices

### 1. Prefer Constructor Injection

```python
# Good
class Service:
    def __init__(self, dep: Dependency):
        self.dep = dep

# Avoid
class Service:
    def set_dependency(self, dep: Dependency):
        self.dep = dep
```

### 2. Use Appropriate Scopes

- **Singleton**: Shared state, expensive resources
- **Scoped**: Request-specific, user-specific
- **Transient**: Stateless, lightweight

### 3. Depend on Abstractions

```python
from abc import ABC, abstractmethod

class Repository(ABC):
    @abstractmethod
    async def find(self, id: int): pass

@component
class SqlRepository(Repository):
    async def find(self, id: int):
        # SQL implementation
        pass

@component
class Service:
    def __init__(self, repo: Repository):  # Depend on abstraction
        self.repo = repo
```

### 4. Keep Constructors Simple

```python
# Good - simple initialization
@component
class Service:
    def __init__(self, db: Database):
        self.db = db
    
    async def initialize(self):
        # Complex setup in separate method
        await self.db.connect()

# Avoid - complex constructor
@component
class Service:
    def __init__(self, db: Database):
        self.db = db
        self.connection = db.connect()  # Blocks!
```

### 5. Use Type Hints

Always use type hints for better IDE support and clarity:

```python
@component
class UserService:
    def __init__(self, 
        db: Database,
        cache: Cache,
        logger: Logger
    ) -> None:
        self.db = db
        self.cache = cache
        self.logger = logger
    
    async def get_user(self, user_id: int) -> User:
        return await self.db.find_user(user_id)
```

## Next Steps

- Explore the [API Reference](api-reference.md) for detailed documentation
- Check out [Examples](examples.md) for real-world patterns
- Learn about [Testing](testing.md) with dependency injection
- Discover [Extensions](extensions.md) for specific use cases