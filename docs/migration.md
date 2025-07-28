# Migration Guide

This guide helps you migrate from other dependency injection frameworks to Whiskey.

## From FastAPI's Depends

FastAPI users will find Whiskey's approach familiar but more flexible.

### FastAPI Pattern
```python
# FastAPI
from fastapi import FastAPI, Depends

app = FastAPI()

def get_db():
    db = Database()
    try:
        yield db
    finally:
        db.close()

def get_user_service(db: Database = Depends(get_db)):
    return UserService(db)

@app.get("/users/{user_id}")
async def get_user(
    user_id: int,
    service: UserService = Depends(get_user_service)
):
    return await service.get_user(user_id)
```

### Whiskey Pattern
```python
# Whiskey
from whiskey import Whiskey, singleton, component, inject
from whiskey_web import Router

app = Whiskey()
router = Router()

@singleton
class Database:
    def __init__(self):
        # Connection managed by lifecycle
        pass
    
    async def __aenter__(self):
        await self.connect()
        return self
    
    async def __aexit__(self, *args):
        await self.close()

@component
class UserService:
    def __init__(self, db: Database):
        self.db = db  # Auto-injected, no Depends needed

@router.get("/users/{user_id}")
async def get_user(user_id: int, service: UserService):
    # service is auto-injected
    return await service.get_user(user_id)
```

### Key Differences
- No explicit `Depends()` - injection is automatic
- Lifecycle managed by decorators (`@singleton`, `@component`)
- Cleaner syntax without dependency descriptors
- Works outside web context

## From Spring/Java DI

Coming from Spring? Here's how concepts translate.

### Spring Pattern
```java
// Spring Boot
@Service
public class UserService {
    @Autowired
    private UserRepository repository;
    
    @Autowired
    private EmailService emailService;
    
    public User getUser(Long id) {
        return repository.findById(id);
    }
}

@Repository
public class UserRepository {
    @Autowired
    private JdbcTemplate jdbcTemplate;
}

@Configuration
public class AppConfig {
    @Bean
    @Scope("prototype")
    public ProcessingService processingService() {
        return new ProcessingService();
    }
}
```

### Whiskey Pattern
```python
# Whiskey
@component  # Like @Service
class UserService:
    def __init__(self, 
        repository: UserRepository,
        email_service: EmailService
    ):
        # Constructor injection (preferred in Python)
        self.repository = repository
        self.email_service = email_service
    
    async def get_user(self, id: int):
        return await self.repository.find_by_id(id)

@singleton  # Like @Repository with singleton scope
class UserRepository:
    def __init__(self, db: Database):
        self.db = db

# Configuration
app = Whiskey()

@app.factory(ProcessingService, scope=Scope.TRANSIENT)  # Like @Bean + @Scope
def create_processing_service(config: Config):
    return ProcessingService(config.processing_options)
```

### Concept Mapping
| Spring | Whiskey |
|--------|---------|
| `@Component/@Service` | `@component` |
| `@Repository` | `@singleton` or `@component` |
| `@Configuration` | Direct registration or factories |
| `@Bean` | `@factory` |
| `@Scope("singleton")` | `@singleton` |
| `@Scope("prototype")` | `@component` (transient) |
| `@Scope("request")` | `@scoped("request")` |
| `@Autowired` | Automatic in constructor |
| `@Qualifier` | Named dependencies |
| `@Profile` | `@when_env` |

## From Django

Django developers can achieve similar patterns with Whiskey.

### Django Pattern
```python
# Django settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'mydb',
    }
}

# Django views.py
from django.conf import settings
from django.core.cache import cache

def get_user(request, user_id):
    # Manually access services
    cached = cache.get(f'user:{user_id}')
    if cached:
        return JsonResponse(cached)
    
    user = User.objects.get(id=user_id)
    cache.set(f'user:{user_id}', user)
    return JsonResponse(user)

# Django apps.py
class MyAppConfig(AppConfig):
    def ready(self):
        # Import signals, etc.
        pass
```

### Whiskey Pattern
```python
# Whiskey
@singleton
class Settings:
    def __init__(self):
        self.database_url = "postgresql://localhost/mydb"

@singleton
class Cache:
    def __init__(self):
        self._cache = {}
    
    async def get(self, key: str):
        return self._cache.get(key)
    
    async def set(self, key: str, value):
        self._cache[key] = value

@component
class UserService:
    def __init__(self, db: Database, cache: Cache):
        # Dependencies injected
        self.db = db
        self.cache = cache
    
    async def get_user(self, user_id: int):
        cached = await self.cache.get(f'user:{user_id}')
        if cached:
            return cached
        
        user = await self.db.get_user(user_id)
        await self.cache.set(f'user:{user_id}', user)
        return user

# Application setup
app = Whiskey()

@app.on_startup
async def configure():
    # Like Django's AppConfig.ready()
    print("Application ready")
```

## From Flask

Flask users will appreciate Whiskey's simplicity.

### Flask Pattern
```python
# Flask
from flask import Flask, g
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
db = SQLAlchemy(app)

def get_db():
    if 'db' not in g:
        g.db = create_connection()
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()

@app.route('/users/<int:user_id>')
def get_user(user_id):
    db = get_db()
    # Manual dependency management
    service = UserService(db)
    return service.get_user(user_id)
```

### Whiskey Pattern
```python
# Whiskey
from whiskey import Whiskey, singleton, component
from whiskey_web import Router

app = Whiskey()
router = Router()

@singleton
class Database:
    # Lifecycle managed automatically
    async def __aenter__(self):
        self.connection = await create_connection()
        return self
    
    async def __aexit__(self, *args):
        await self.connection.close()

@component
class UserService:
    def __init__(self, db: Database):
        self.db = db  # Auto-injected

@router.get('/users/{user_id}')
async def get_user(user_id: int, service: UserService):
    # Dependencies resolved automatically
    return await service.get_user(user_id)
```

## From Injector

Python Injector users will find familiar concepts.

### Injector Pattern
```python
# Injector
from injector import Module, provider, Injector, inject, singleton

class DatabaseModule(Module):
    @singleton
    @provider
    def provide_database(self) -> Database:
        return Database("postgresql://localhost/db")
    
    @provider
    def provide_user_service(self, db: Database) -> UserService:
        return UserService(db)

class UserService:
    @inject
    def __init__(self, database: Database):
        self.database = database

# Usage
injector = Injector([DatabaseModule()])
service = injector.get(UserService)
```

### Whiskey Pattern
```python
# Whiskey
from whiskey import singleton, component

@singleton
class Database:
    def __init__(self):
        self.url = "postgresql://localhost/db"

@component
class UserService:
    def __init__(self, database: Database):
        self.database = database  # Auto-injected

# Usage - much simpler!
from whiskey import resolve
service = await resolve(UserService)
```

## Common Migration Patterns

### 1. Service Registration

Most frameworks require explicit registration:

```python
# Other frameworks
container.register(UserService)
container.register(Database, scope='singleton')
container.register_factory(Cache, cache_factory)

# Whiskey - decorators handle registration
@component
class UserService: pass

@singleton
class Database: pass

@factory(Cache)
def cache_factory(): pass
```

### 2. Configuration

Move from configuration files to code:

```python
# From XML/YAML/JSON config
# config.yaml:
# services:
#   database:
#     class: Database
#     arguments:
#       - "%database_url%"

# To Whiskey decorators
@singleton
class Database:
    def __init__(self, config: Config):
        self.url = config.database_url
```

### 3. Dependency Resolution

Replace manual resolution with automatic injection:

```python
# Manual resolution
db = container.get('database')
cache = container.get('cache')
service = UserService(db, cache)

# Whiskey - automatic
@inject
async def process(service: UserService):
    # service is ready to use with all dependencies
    pass
```

### 4. Scoped Dependencies

Convert request/session scoping:

```python
# Other frameworks
with container.request_scope() as scope:
    service = scope.resolve(RequestService)

# Whiskey
async with container.scope("request") as request_scope:
    service = await request_scope.resolve(RequestService)
```

### 5. Testing

Simplify test setup:

```python
# Complex mocking setup
mock_container = create_test_container()
mock_container.register(Database, MockDatabase)
mock_container.register(Cache, MockCache)

# Whiskey
from whiskey.testing import create_test_container

container = create_test_container(
    Database=MockDatabase(),
    Cache=MockCache()
)
```

## Step-by-Step Migration

### 1. Identify Components

List all your services, repositories, and dependencies:
- Singleton services (database, cache, config)
- Per-request services (context, session)
- Transient services (processors, handlers)

### 2. Map Lifecycles

| Your Framework | Whiskey Equivalent |
|----------------|-------------------|
| Singleton/Application | `@singleton` |
| Request/Session | `@scoped("request")` |
| Transient/Prototype | `@component` |

### 3. Convert Registration

Replace explicit registration with decorators:

```python
# Before
container = Container()
container.register_singleton(Database)
container.register_transient(UserService)

# After
@singleton
class Database: pass

@component
class UserService: pass
```

### 4. Update Injection Points

Remove manual dependency resolution:

```python
# Before
def handler(request):
    db = container.resolve(Database)
    service = UserService(db)
    return service.process(request)

# After
@inject
async def handler(request: Request, service: UserService):
    return await service.process(request)
```

### 5. Migrate Tests

Update test setup to use Whiskey patterns:

```python
# Before
def test_service():
    mock_db = Mock()
    service = UserService(mock_db)
    
# After
def test_service():
    container = create_test_container()
    container[Database] = Mock()
    service = container.resolve_sync(UserService)
```

## Framework-Specific Guides

### Migrating FastAPI Apps

1. Replace `Depends()` with type hints
2. Move startup/shutdown to lifecycle events
3. Keep your routes, just update dependency injection

### Migrating Django Apps

1. Create service layer with Whiskey components
2. Gradually move business logic from views
3. Keep Django ORM, inject as services

### Migrating Flask Apps

1. Replace Flask-specific extensions with Whiskey components
2. Move from `g` context to proper DI
3. Update route handlers to use injection

## Troubleshooting Migration

### Common Issues

1. **Circular Dependencies**
   - Review and refactor service dependencies
   - Use lazy initialization if needed

2. **Missing Registrations**
   - Ensure all components have decorators
   - Check for forgotten transitive dependencies

3. **Scope Mismatches**
   - Singleton can't depend on scoped
   - Review lifecycle requirements

4. **Initialization Order**
   - Use `@app.on_startup` for initialization
   - Dependencies are resolved in correct order

## Next Steps

- Start with a small module or service
- Gradually migrate components
- Run old and new systems in parallel
- Check out [Examples](examples.md) for complete applications
- Review [Testing](testing.md) for test migration strategies