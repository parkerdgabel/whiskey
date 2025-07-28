# Getting Started with Whiskey

This guide will help you install Whiskey and build your first dependency injection application in Python.

## Installation

### Basic Installation

```bash
pip install whiskey
```

### Installation with Extensions

```bash
# For web applications
pip install whiskey[web]

# For CLI applications  
pip install whiskey[cli]

# For AI/LLM applications
pip install whiskey[ai]

# Install everything
pip install whiskey[all]
```

### Development Installation

```bash
# Clone the repository
git clone https://github.com/your-org/whiskey.git
cd whiskey

# Install with development dependencies
pip install -e ".[dev]"
```

## Your First Whiskey Application

Let's build a simple application that demonstrates Whiskey's core features.

### Step 1: Define Your Services

```python
from whiskey import singleton, component

@singleton
class DatabaseConnection:
    """A singleton database connection"""
    def __init__(self):
        self.url = "sqlite:///app.db"
        print(f"Connecting to {self.url}")
    
    def query(self, sql: str):
        return f"Results from: {sql}"

@component
class UserRepository:
    """A transient component - new instance per injection"""
    def __init__(self, db: DatabaseConnection):
        self.db = db  # Automatically injected!
    
    def find_user(self, user_id: int):
        return self.db.query(f"SELECT * FROM users WHERE id = {user_id}")
```

### Step 2: Use Dependency Injection

```python
from whiskey import inject

@inject
async def get_user_handler(user_id: int, repo: UserRepository):
    """Function with automatic dependency injection"""
    # user_id must be provided, repo is auto-injected
    user = repo.find_user(user_id)
    return {"user": user}

# Call the function - dependencies are resolved automatically
result = await get_user_handler(user_id=123)
print(result)  # {'user': 'Results from: SELECT * FROM users WHERE id = 123'}
```

### Step 3: Build an Application

```python
from whiskey import Whiskey

# Create an application
app = Whiskey(name="my_app")

# Register components using decorators
@app.singleton
class ConfigService:
    def __init__(self):
        self.debug = True

@app.component
class EmailService:
    def __init__(self, config: ConfigService):
        self.config = config
    
    async def send_email(self, to: str, subject: str):
        if self.config.debug:
            print(f"[DEBUG] Email to {to}: {subject}")
        else:
            # Actually send email
            pass

# Define startup tasks
@app.on_startup
async def initialize():
    print("Application starting...")

# Run the application
if __name__ == "__main__":
    import asyncio
    
    async def main():
        async with app:
            # Resolve and use components
            email = await app.resolve(EmailService)
            await email.send_email("user@example.com", "Welcome!")
    
    asyncio.run(main())
```

## Understanding Scopes

Whiskey supports different component lifecycles:

```python
from whiskey import component, singleton, scoped
from whiskey.core import Scope

# Transient - New instance every time
@component
class TransientService:
    def __init__(self):
        print("Creating new TransientService")

# Singleton - One instance per application
@singleton  
class SingletonService:
    def __init__(self):
        print("Creating SingletonService (only once)")

# Scoped - One instance per scope (e.g., request)
@scoped("request")
class RequestScopedService:
    def __init__(self):
        print("Creating RequestScopedService for this request")
```

## Working with Async

Whiskey is built for modern async Python:

```python
@singleton
class AsyncDatabase:
    async def connect(self):
        # Simulate async connection
        await asyncio.sleep(0.1)
        return self
    
    async def fetch_users(self):
        await asyncio.sleep(0.1)
        return ["Alice", "Bob"]

@component
class AsyncUserService:
    def __init__(self, db: AsyncDatabase):
        self.db = db
    
    async def get_all_users(self):
        return await self.db.fetch_users()

@inject
async def list_users(service: AsyncUserService):
    users = await service.get_all_users()
    for user in users:
        print(f"User: {user}")
```

## Factory Functions

Use factory functions for complex initialization:

```python
from whiskey import factory
import redis

@factory(redis.Redis, scope=Scope.SINGLETON)
def create_redis_client(config: ConfigService):
    """Factory function to create Redis client"""
    return redis.Redis(
        host=config.redis_host,
        port=config.redis_port,
        decode_responses=True
    )

# Now redis.Redis can be injected anywhere
@inject
async def cache_user(user_id: int, redis_client: redis.Redis):
    redis_client.set(f"user:{user_id}", "data")
```

## Next Steps

Now that you've built your first Whiskey application:

1. Read [Core Concepts](core-concepts.md) to understand dependency injection patterns
2. Explore [API Reference](api-reference.md) for detailed documentation
3. Check out [Examples](examples.md) for real-world patterns
4. Learn about [Extensions](extensions.md) for web, CLI, and AI applications

## Common Patterns

### Configuration Management

```python
@singleton
class Settings:
    def __init__(self):
        self.database_url = os.getenv("DATABASE_URL", "sqlite:///app.db")
        self.debug = os.getenv("DEBUG", "false").lower() == "true"
        self.port = int(os.getenv("PORT", "8000"))
```

### Lazy Initialization

```python
from whiskey import singleton

@singleton(lazy=True)
class ExpensiveService:
    def __init__(self):
        print("This is only created when first used")
        self.data = self._load_expensive_data()
    
    def _load_expensive_data(self):
        # Expensive operation
        return "data"
```

### Conditional Registration

```python
from whiskey import component, when_env

@component
@when_env("ENVIRONMENT", "production")
class ProductionLogger:
    def log(self, message: str):
        # Send to logging service
        pass

@component
@when_env("ENVIRONMENT", "development")
class DevelopmentLogger:
    def log(self, message: str):
        print(f"[DEV] {message}")
```

## Troubleshooting

### Common Issues

1. **Circular Dependencies**
   ```python
   # This will fail
   @component
   class A:
       def __init__(self, b: B): pass
   
   @component
   class B:
       def __init__(self, a: A): pass
   
   # Solution: Use lazy injection or refactor
   ```

2. **Missing Dependencies**
   ```python
   # Always register all dependencies
   @component
   class Service:
       def __init__(self, missing: MissingDep):  # Error if MissingDep not registered
           pass
   ```

3. **Scope Mismatches**
   ```python
   # Singleton cannot depend on scoped
   @singleton
   class SingletonService:
       def __init__(self, scoped: RequestScoped):  # Error!
           pass
   ```

### Debug Mode

Enable debug logging to troubleshoot:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Or use Whiskey's debug mode
app = Whiskey(debug=True)
```