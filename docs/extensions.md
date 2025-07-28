# Extensions

Whiskey provides a rich ecosystem of extensions for different application types. Each extension adds domain-specific functionality while maintaining Whiskey's simple, Pythonic approach.

## Available Extensions

### whiskey-web (ASGI)

Build async web applications with ASGI support.

**Installation:**
```bash
pip install whiskey[web]
```

**Features:**
- ASGI application support
- Request/response handling
- WebSocket support
- Middleware system
- Route decorators
- Session management

**Example:**
```python
from whiskey import Whiskey
from whiskey_web import Router, Request, Response

app = Whiskey()
router = Router()

@router.get("/")
async def home(request: Request) -> Response:
    return Response({"message": "Hello, World!"})

@router.get("/users/{user_id}")
async def get_user(request: Request, user_id: int, db: Database) -> Response:
    user = await db.get_user(user_id)
    return Response(user)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app.asgi(), host="0.0.0.0", port=8000)
```

### whiskey-cli

Build command-line applications with automatic dependency injection.

**Installation:**
```bash
pip install whiskey[cli]
```

**Features:**
- Click integration
- Automatic argument parsing
- Dependency injection in commands
- Configuration management
- Progress bars and spinners

**Example:**
```python
from whiskey import Whiskey
from whiskey_cli import cli_app
import click

app = Whiskey()

@app.singleton
class ConfigService:
    def __init__(self):
        self.api_url = "https://api.example.com"

@cli_app.command()
@click.argument("name")
async def greet(name: str, config: ConfigService):
    """Greet a user with API URL"""
    click.echo(f"Hello, {name}!")
    click.echo(f"API URL: {config.api_url}")

@cli_app.command()
@click.option("--count", default=1)
async def process(count: int, service: ProcessingService):
    """Process items with injected service"""
    with click.progressbar(range(count)) as items:
        for item in items:
            await service.process_item(item)

if __name__ == "__main__":
    cli_app()
```

### whiskey-ai

AI and LLM application support with conversation scopes.

**Installation:**
```bash
pip install whiskey[ai]
```

**Features:**
- Conversation-scoped components
- Session management
- LLM provider abstraction
- Token counting and limits
- Conversation history
- Tool/function calling support

**Example:**
```python
from whiskey import Whiskey
from whiskey_ai import ConversationScope, LLMProvider, Message

app = Whiskey()

@app.scoped("conversation")
class ConversationMemory:
    def __init__(self):
        self.messages = []
    
    def add_message(self, message: Message):
        self.messages.append(message)

@app.singleton
class ChatService:
    def __init__(self, llm: LLMProvider, memory: ConversationMemory):
        self.llm = llm
        self.memory = memory
    
    async def chat(self, user_input: str) -> str:
        # Add user message to memory
        user_msg = Message(role="user", content=user_input)
        self.memory.add_message(user_msg)
        
        # Get response from LLM
        response = await self.llm.complete(self.memory.messages)
        
        # Add assistant message to memory
        assistant_msg = Message(role="assistant", content=response)
        self.memory.add_message(assistant_msg)
        
        return response

# Use conversation scope
async with app.container.scope("conversation") as conv_scope:
    chat = await conv_scope.resolve(ChatService)
    response = await chat.chat("Hello!")
```

### whiskey-sql

Database connection and transaction management.

**Installation:**
```bash
pip install whiskey[sql]
```

**Features:**
- Multiple database support (PostgreSQL, MySQL, SQLite, DuckDB)
- Connection pooling
- Transaction scopes
- Migration support
- Query builders

**Example:**
```python
from whiskey import Whiskey
from whiskey_sql import DatabaseManager, transaction

app = Whiskey()

@app.singleton
class DatabaseConfig:
    db_url = "postgresql://localhost/myapp"

@app.singleton
class Database:
    def __init__(self, config: DatabaseConfig):
        self.manager = DatabaseManager(config.db_url)
    
    async def get_user(self, user_id: int):
        async with self.manager.connection() as conn:
            return await conn.fetchone(
                "SELECT * FROM users WHERE id = $1", 
                user_id
            )

@app.component
class UserService:
    def __init__(self, db: Database):
        self.db = db
    
    @transaction
    async def create_user(self, name: str, email: str):
        # Automatic transaction management
        user = await self.db.create_user(name, email)
        await self.db.create_profile(user.id)
        return user
```

### whiskey-auth

Authentication and authorization for web applications.

**Installation:**
```bash
pip install whiskey[auth]
```

**Features:**
- JWT token support
- Session management
- User authentication
- Role-based access control
- OAuth integration
- Password hashing

**Example:**
```python
from whiskey import Whiskey
from whiskey_auth import AuthManager, require_auth, require_role
from whiskey_web import Router

app = Whiskey()
router = Router()

@app.singleton
class AuthService:
    def __init__(self, auth_manager: AuthManager):
        self.auth = auth_manager
    
    async def login(self, username: str, password: str):
        user = await self.verify_credentials(username, password)
        return self.auth.create_token(user)

@router.post("/login")
async def login(request: Request, auth: AuthService):
    data = await request.json()
    token = await auth.login(data["username"], data["password"])
    return Response({"token": token})

@router.get("/profile")
@require_auth
async def profile(request: Request, current_user: User):
    return Response({"user": current_user.dict()})

@router.get("/admin")
@require_role("admin")
async def admin_panel(request: Request):
    return Response({"message": "Admin access granted"})
```

### whiskey-jobs

Background job processing and scheduling.

**Installation:**
```bash
pip install whiskey[jobs]
```

**Features:**
- Background job queues
- Scheduled tasks
- Cron expressions
- Job retries
- Job priorities
- Worker pools

**Example:**
```python
from whiskey import Whiskey
from whiskey_jobs import JobQueue, scheduled, background

app = Whiskey()

@app.singleton
class EmailService:
    async def send_email(self, to: str, subject: str, body: str):
        # Send email implementation
        pass

@background
async def send_welcome_email(user_id: int, email_service: EmailService):
    """Background job with dependency injection"""
    user = await get_user(user_id)
    await email_service.send_email(
        user.email,
        "Welcome!",
        f"Hello {user.name}!"
    )

@scheduled(cron="0 0 * * *")  # Daily at midnight
async def cleanup_old_data(db: Database):
    """Scheduled job that runs daily"""
    await db.delete_old_records()

# Queue a job
await send_welcome_email.queue(user_id=123)
```

### whiskey-config

Advanced configuration management.

**Installation:**
```bash
pip install whiskey[config]
```

**Features:**
- Environment variable parsing
- Configuration files (YAML, JSON, TOML)
- Configuration validation
- Hot reloading
- Secrets management

**Example:**
```python
from whiskey import Whiskey
from whiskey_config import Config, EnvVar, SecretVar

app = Whiskey()

@app.singleton
class AppConfig(Config):
    # Environment variables with types and defaults
    port: int = EnvVar("PORT", default=8000)
    debug: bool = EnvVar("DEBUG", default=False)
    
    # Secret management
    api_key: str = SecretVar("API_KEY")
    
    # Nested configuration
    database = {
        "host": EnvVar("DB_HOST", default="localhost"),
        "port": EnvVar("DB_PORT", default=5432, type=int),
        "name": EnvVar("DB_NAME", default="myapp")
    }

@app.component
class Service:
    def __init__(self, config: AppConfig):
        self.config = config
        print(f"Running on port {config.port}")
```

## Creating Custom Extensions

Extensions are simple functions that configure the container:

```python
# my_extension.py
from whiskey import Container

def configure_my_extension(container: Container, **options):
    """Configure custom extension"""
    
    # Add custom scopes
    container.add_scope("my_scope")
    
    # Register components
    @container.singleton
    class MyExtensionService:
        def __init__(self):
            self.configured = True
    
    # Add lifecycle hooks
    @container.on_startup
    async def initialize_extension():
        print("My extension initialized!")
    
    return container

# Usage
from whiskey import Whiskey
from my_extension import configure_my_extension

app = Whiskey()
configure_my_extension(app.container, option1="value1")
```

## Extension Patterns

### 1. Scope Extensions

Add domain-specific scopes:

```python
def configure_request_scope(container: Container):
    """Add HTTP request scope"""
    
    @container.scoped("request")
    class RequestContext:
        def __init__(self):
            self.request_id = generate_id()
            self.user = None
```

### 2. Provider Extensions

Add specialized providers:

```python
def configure_cache_providers(container: Container):
    """Add caching providers"""
    
    @container.factory(Cache, scope=Scope.SINGLETON)
    def create_cache(config: Config):
        if config.cache_type == "redis":
            return RedisCache(config.redis_url)
        else:
            return MemoryCache()
```

### 3. Middleware Extensions

Add processing pipelines:

```python
def configure_middleware(container: Container):
    """Add middleware support"""
    
    class MiddlewareChain:
        def __init__(self):
            self.middlewares = []
        
        def add(self, middleware):
            self.middlewares.append(middleware)
        
        async def process(self, request):
            for mw in self.middlewares:
                request = await mw.process(request)
            return request
    
    container.add_singleton(MiddlewareChain)
```

## Best Practices

### 1. Extension Naming

Follow consistent naming conventions:
- Package: `whiskey-{domain}`
- Module: `whiskey_{domain}`
- Function: `configure_{domain}`

### 2. Configuration Options

Accept configuration through kwargs:

```python
def configure_extension(container: Container, **options):
    debug = options.get("debug", False)
    timeout = options.get("timeout", 30)
```

### 3. Lazy Loading

Only import heavy dependencies when needed:

```python
def configure_ml_extension(container: Container):
    @container.factory(MLModel, scope=Scope.SINGLETON)
    def create_model():
        # Import only when creating model
        import tensorflow as tf
        return tf.keras.models.load_model("model.h5")
```

### 4. Documentation

Provide clear examples and API documentation:

```python
def configure_extension(container: Container, **options):
    """Configure MyExtension for Whiskey.
    
    Args:
        container: Whiskey container to configure
        **options: Configuration options
            - debug (bool): Enable debug mode
            - timeout (int): Request timeout in seconds
    
    Example:
        >>> app = Whiskey()
        >>> configure_extension(app.container, debug=True)
    """
```

## Extension Compatibility

Extensions should be compatible with each other:

```python
from whiskey import Whiskey
from whiskey_web import configure_web
from whiskey_auth import configure_auth
from whiskey_sql import configure_sql

app = Whiskey()

# Extensions work together
configure_sql(app.container, db_url="postgresql://localhost/app")
configure_auth(app.container, secret_key="super-secret")
configure_web(app.container, port=8000)

# Components can use features from multiple extensions
@app.component
class UserAPI:
    def __init__(self, db: Database, auth: AuthManager):
        self.db = db
        self.auth = auth
```

## Next Steps

- Explore specific extension documentation
- Build your own extensions
- Check out [Examples](examples.md) using extensions
- Learn about [Testing](testing.md) with extensions