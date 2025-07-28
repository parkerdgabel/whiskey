# Examples

This guide provides an index of real-world examples demonstrating Whiskey in action. All examples are available in the [examples/](../examples/) directory.

## Basic Examples

### 01. Basic Dependency Injection
**File:** `examples/01_basic_di.py`

Learn the fundamentals of dependency injection with Whiskey:
- Component registration with decorators
- Constructor injection
- Singleton vs transient lifecycles
- Basic resolution patterns

```python
@singleton
class Database:
    def __init__(self):
        self.connected = True

@component
class UserService:
    def __init__(self, db: Database):
        self.db = db  # Automatically injected
```

### 02. Scopes and Lifecycle
**File:** `examples/02_scopes_and_lifecycle.py`

Understand component lifecycles and scoping:
- Request-scoped components
- Nested scopes
- Lifecycle management
- Resource cleanup

```python
@scoped("request")
class RequestContext:
    def __init__(self):
        self.request_id = generate_id()
```

### 03. Application Framework
**File:** `examples/03_application_framework.py`

Build complete applications with the Whiskey framework:
- Application lifecycle events
- Component priorities
- Error handling
- Background tasks

```python
app = Whiskey(name="my_app")

@app.on_startup
async def initialize():
    print("Starting application...")

@app.task(interval=60)
async def background_job():
    print("Running periodic task")
```

## Intermediate Examples

### 04. Named Dependencies
**File:** `examples/04_named_dependencies.py`

Work with multiple implementations of the same interface:
- Named component registration
- Resolving specific implementations
- Configuration-based selection

```python
@component(name="mysql")
class MySQLDatabase(Database):
    pass

@component(name="postgres")
class PostgresDatabase(Database):
    pass
```

### 05. Conditional Registration
**File:** `examples/05_conditional_registration.py`

Register components based on runtime conditions:
- Environment-based registration
- Feature flags
- Debug/production modes

```python
@component
@when_env("DATABASE_TYPE", "postgres")
class PostgresDatabase:
    pass

@component
@when_debug
class DebugLogger:
    pass
```

### 06. Lazy Resolution
**File:** `examples/06_lazy_resolution.py`

Optimize startup time with lazy initialization:
- Lazy singletons
- Deferred initialization
- Performance optimization

```python
@singleton(lazy=True)
class ExpensiveService:
    def __init__(self):
        # Only initialized when first used
        self.data = load_large_dataset()
```

### 07. Combined Features
**File:** `examples/07_combined_features.py`

See how different Whiskey features work together:
- Complex dependency graphs
- Mixed lifecycles
- Advanced patterns

## Advanced Examples

### 08. Discovery and Inspection
**File:** `examples/08_discovery_and_inspection.py`

Explore component discovery and runtime inspection:
- Component metadata
- Service discovery
- Dynamic registration
- Runtime introspection

```python
# Discover all registered components
components = container.get_components()
for comp in components:
    print(f"Component: {comp.key}, Scope: {comp.scope}")
```

### 09. Events and Tasks
**File:** `examples/09_events_and_tasks.py`

Build event-driven applications:
- Event emitter pattern
- Background task scheduling
- Async event handlers
- Task priorities

```python
@app.on("user:created")
async def send_welcome_email(user_id: int, email_service: EmailService):
    await email_service.send_welcome(user_id)

# Emit event
await app.emit("user:created", user_id=123)
```

### 10. Real-World Microservice
**File:** `examples/10_real_world_microservice.py`

Complete microservice implementation showcasing:
- REST API with dependency injection
- Database integration
- Authentication
- Background jobs
- Health checks
- Metrics collection

## Extension Examples

### Web Applications

#### Simple ASGI Application
**File:** `whiskey_asgi/examples/01_basic_api.py`

Basic web API with automatic dependency injection:
- Route handlers with DI
- Request/response handling
- JSON serialization

```python
@router.get("/users/{user_id}")
async def get_user(user_id: int, service: UserService):
    user = await service.get_user(user_id)
    return {"user": user}
```

#### WebSocket Support
**File:** `whiskey_asgi/examples/02_middleware_websocket.py`

Real-time communication with WebSockets:
- WebSocket handlers
- Connection management
- Broadcasting messages

### CLI Applications

#### Command-Line Tool
**File:** `whiskey_cli/examples/01_basic_cli.py`

Build CLI tools with dependency injection:
- Click integration
- Command parameters
- Service injection

```python
@cli.command()
@click.argument("name")
async def greet(name: str, service: GreetingService):
    message = await service.create_greeting(name)
    click.echo(message)
```

#### Todo Application
**File:** `whiskey_cli/examples/02_todo_app.py`

Complete CLI application with:
- Multiple commands
- Database persistence
- Interactive prompts

### AI/LLM Applications

#### Conversation Management
**File:** `whiskey_ai/examples/conversation_example.py`

Build AI assistants with conversation scopes:
- Conversation memory
- LLM integration
- Context management

```python
@scoped("conversation")
class ConversationMemory:
    def __init__(self):
        self.messages = []

@component
class ChatBot:
    def __init__(self, memory: ConversationMemory, llm: LLMProvider):
        self.memory = memory
        self.llm = llm
```

### Background Jobs

#### Job Processing
**File:** `whiskey_jobs/examples/basic_jobs.py`

Process background jobs with dependency injection:
- Job queues
- Worker pools
- Retry logic

```python
@background
async def process_upload(file_id: str, processor: FileProcessor):
    await processor.process_file(file_id)

# Queue the job
await process_upload.queue(file_id="123")
```

#### Scheduled Tasks
**File:** `whiskey_jobs/examples/scheduled_jobs.py`

Schedule recurring tasks:
- Cron expressions
- Periodic tasks
- Task management

```python
@scheduled(cron="0 * * * *")  # Every hour
async def cleanup_old_files(storage: StorageService):
    await storage.cleanup_old_files()
```

### Database Examples

#### Multi-Database Support
**File:** `whiskey_sql/examples/basic_usage.py`

Work with different databases:
- PostgreSQL
- MySQL
- SQLite
- DuckDB

```python
@singleton
class DatabaseManager:
    def __init__(self, config: Config):
        self.primary = PostgresDatabase(config.primary_db)
        self.analytics = DuckDBDatabase(config.analytics_db)
```

## Pattern Examples

### Repository Pattern
**File:** `examples/patterns/repository.py`

Implement the repository pattern:
- Abstract repositories
- Concrete implementations
- Unit of work

### CQRS Pattern
**File:** `examples/patterns/cqrs.py`

Command Query Responsibility Segregation:
- Command handlers
- Query handlers
- Event sourcing

### Middleware Pattern
**File:** `examples/patterns/middleware.py`

Build middleware pipelines:
- Request/response middleware
- Error handling
- Logging and metrics

## Testing Examples

### Unit Testing
**File:** `examples/testing/unit_tests.py`

Test components in isolation:
- Mocking dependencies
- Test containers
- Assertion patterns

### Integration Testing
**File:** `examples/testing/integration_tests.py`

Test component interactions:
- Real dependencies
- Database testing
- API testing

## Running Examples

### Basic Setup

1. Clone the repository:
```bash
git clone https://github.com/your-org/whiskey.git
cd whiskey
```

2. Install dependencies:
```bash
pip install -e ".[all]"
```

3. Run an example:
```bash
python examples/01_basic_di.py
```

### Running Web Examples

For ASGI examples:
```bash
cd whiskey_asgi/examples
uvicorn 01_basic_api:app --reload
```

### Running CLI Examples

For CLI examples:
```bash
cd whiskey_cli/examples
python 01_basic_cli.py --help
```

## Creating Your Own Examples

When creating examples:

1. **Keep it focused** - Each example should demonstrate specific features
2. **Add comments** - Explain what's happening and why
3. **Include imports** - Make examples self-contained
4. **Test it works** - Ensure examples run without errors
5. **Document usage** - Include instructions for running

Example template:
```python
#!/usr/bin/env python3
"""
Example: [Feature Name]

This example demonstrates:
- Point 1
- Point 2
- Point 3

Usage:
    python example_name.py
"""

from whiskey import Whiskey, component, singleton, inject

# Example implementation...

if __name__ == "__main__":
    # Run the example
    import asyncio
    asyncio.run(main())
```

## Contributing Examples

We welcome example contributions! Please:

1. Follow the existing structure
2. Include clear documentation
3. Test on Python 3.8+
4. Submit a pull request

## Next Steps

- Pick an example that matches your use case
- Modify it for your needs
- Check the [API Reference](api-reference.md) for details
- Join our community for help and discussion