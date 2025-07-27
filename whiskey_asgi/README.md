<<<<<<< HEAD
# Whiskey ASGI Extension 🌐

Build modern web applications with Whiskey's powerful dependency injection system. This extension provides a minimal yet complete ASGI framework that seamlessly integrates with Whiskey's IoC container.

## Why Whiskey ASGI?

While there are many Python web frameworks, Whiskey ASGI is designed specifically for dependency injection-first development:

- **True DI Integration**: Not just parameter injection - full container lifecycle management
- **Request Scoping**: Automatic per-request container isolation
- **Type-Safe Routes**: Full typing support with `Annotated` for explicit injection
- **Event-Driven**: Leverage Whiskey's event system for decoupled web applications
- **Minimal Core**: Just enough web framework, no bloat
=======
# Whiskey ASGI Plugin

A minimal ASGI web framework plugin for Whiskey that provides a foundation for building web applications with dependency injection.

## Features

- **ASGI 3.0 Compliant**: Full support for the ASGI specification
- **Dependency Injection**: Seamless integration with Whiskey's DI system
- **Request Scoping**: Automatic request-scoped container creation
- **Simple Routing**: Path-based routing with parameter extraction
- **Middleware Support**: Composable middleware chain
- **Type Safety**: Full type hints throughout
>>>>>>> origin/main

## Installation

```bash
<<<<<<< HEAD
pip install whiskey[web]  # Includes whiskey-asgi
# or
=======
>>>>>>> origin/main
pip install whiskey-asgi
```

## Quick Start

```python
<<<<<<< HEAD
from whiskey import Whiskey, inject
from whiskey_asgi import asgi_extension

# Create app with ASGI extension
app = Whiskey()
app.use(asgi_extension)

# Define your services
@app.component
class UserService:
    def __init__(self, db: Database):
        self.db = db
        
    async def get_user(self, user_id: int):
        return await self.db.query_one(
            "SELECT * FROM users WHERE id = ?", user_id
        )

# Create routes with dependency injection
@app.get("/users/{user_id}")
@inject
async def get_user(
    user_id: int,
    service: UserService
):
    user = await service.get_user(user_id)
    if not user:
        return {"error": "User not found"}, 404
    return {"id": user.id, "name": user.name}

# Run with any ASGI server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app.asgi, host="127.0.0.1", port=8000)
```

## Core Features

### 1. Route Registration

Define routes using familiar decorators:

```python
@app.get("/")
async def index():
    return {"message": "Welcome to Whiskey!"}

@app.post("/users")
@inject
async def create_user(
    data: dict,
    service: Annotated[UserService, Inject()]
):
    user = await service.create(data)
    return user, 201

@app.route("/health", methods=["GET", "HEAD"])
async def health():
    return {"status": "healthy"}
```

### 2. Request and Response Objects

Work with request data and build responses:

```python
@app.post("/upload")
async def upload(request: Request) -> Response:
    # Access request data
    form = await request.form()
    files = await request.files()
    json_data = await request.json()
    
    # Build response
    return Response(
        content={"uploaded": len(files)},
        status_code=200,
        headers={"X-Files-Count": str(len(files))}
    )
```

### 3. Dependency Injection in Routes

Full DI support with proper request scoping:

```python
# Request-scoped service
@scoped("request")
class RequestLogger:
    def __init__(self):
        self.request_id = generate_id()
        self.logs = []
        
    def log(self, message: str):
        self.logs.append(f"[{self.request_id}] {message}")

@app.get("/process")
@inject
async def process(
    logger: Annotated[RequestLogger, Inject()],
    processor: Annotated[DataProcessor, Inject()]
):
    logger.log("Starting processing")
    result = await processor.run()
    logger.log("Processing complete")
    return {"result": result, "logs": logger.logs}
```

### 4. Middleware System

Composable middleware with DI support:

```python
@app.middleware
@inject
async def timing_middleware(
    request: Request,
    call_next,
    metrics: Annotated[MetricsService, Inject()]
):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    
    await metrics.record("http.request.duration", duration, {
        "method": request.method,
        "path": request.path,
        "status": response.status_code
    })
    
    response.headers["X-Response-Time"] = f"{duration:.3f}s"
    return response

@app.middleware
async def cors_middleware(request: Request, call_next):
    # Handle preflight
    if request.method == "OPTIONS":
        return Response(
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "*",
                "Access-Control-Allow-Headers": "*",
            }
        )
    
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response
```

### 5. WebSocket Support

Real-time communication with DI:

```python
@app.websocket("/ws")
@inject
async def websocket_endpoint(
    websocket: WebSocket,
    message_handler: Annotated[MessageHandler, Inject()],
    connection_manager: Annotated[ConnectionManager, Inject()]
):
    await websocket.accept()
    await connection_manager.add(websocket)
    
    try:
        async for message in websocket:
            response = await message_handler.process(message)
            await websocket.send_json(response)
            
            # Broadcast to all connections
            await connection_manager.broadcast(response)
    finally:
        await connection_manager.remove(websocket)
```

### 6. Request Context and Scoping

Automatic request-scoped container management:

```python
@scoped("request")
class RequestContext:
    def __init__(self):
        self.user = None
        self.trace_id = generate_trace_id()
        self.start_time = time.time()

@app.middleware
@inject
async def auth_middleware(
    request: Request,
    call_next,
    auth: Annotated[AuthService, Inject()],
    context: Annotated[RequestContext, Inject()]
):
    # Extract and verify token
    token = request.headers.get("Authorization")
    if token:
        user = await auth.verify_token(token)
        context.user = user
    
    response = await call_next(request)
    return response

@app.get("/profile")
@inject
async def get_profile(
    context: Annotated[RequestContext, Inject()]
):
    if not context.user:
        return {"error": "Unauthorized"}, 401
    
    return {
        "user": context.user,
        "request_id": context.trace_id
    }
```

### 7. Event Integration

Emit and handle events within web handlers:

```python
@app.post("/orders")
@inject
async def create_order(
    data: dict,
    order_service: Annotated[OrderService, Inject()]
):
    order = await order_service.create(data)
    
    # Emit event for other parts of the app
    await app.emit("order.created", {
        "order_id": order.id,
        "user_id": order.user_id,
        "total": order.total
    })
    
    return order, 201

# Handle the event elsewhere
@app.on("order.created")
@inject
async def send_order_email(
    data: dict,
    email_service: Annotated[EmailService, Inject()]
):
    await email_service.send_order_confirmation(data["order_id"])
```

### 8. Error Handling

Graceful error handling with custom handlers:

```python
@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return {
        "error": "Invalid value",
        "message": str(exc)
    }, 400

@app.exception_handler(404)
async def not_found_handler(request: Request, exc: Exception):
    return {
        "error": "Not found",
        "path": request.path
    }, 404

# Global error handler
@app.on_error
async def handle_errors(error_data):
    error = error_data["error"]
    if isinstance(error, ValidationError):
        return {
            "error": "Validation failed",
            "details": error.errors()
        }, 422
```

## Advanced Features

### Static Files and Templates

```python
from whiskey_asgi import StaticFiles, Jinja2Templates

# Serve static files
app.mount("/static", StaticFiles(directory="static"))

# Template rendering
templates = Jinja2Templates(directory="templates")

@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "title": "Welcome"
    })
```

### Background Tasks

```python
@app.post("/send-email")
@inject
async def send_email(
    data: dict,
    background_tasks: BackgroundTasks,
    email_service: Annotated[EmailService, Inject()]
):
    # Return immediately
    background_tasks.add_task(
        email_service.send,
        to=data["email"],
        subject=data["subject"],
        body=data["body"]
    )
    
    return {"message": "Email queued"}
```

### Testing Support

```python
import pytest
from whiskey.testing import TestClient

@pytest.fixture
def client(app):
    return TestClient(app)

def test_get_user(client):
    response = client.get("/users/123")
    assert response.status_code == 200
    assert response.json()["id"] == 123

@pytest.mark.asyncio
async def test_websocket(client):
    async with client.websocket_connect("/ws") as websocket:
        await websocket.send_json({"type": "ping"})
        data = await websocket.receive_json()
        assert data["type"] == "pong"
```

## Integration with Other Extensions

### With whiskey-config

```python
from whiskey_config import config_extension, Setting

app.use(config_extension)

@app.get("/api/status")
@inject
def status(
    debug: bool = Setting("debug"),
    version: str = Setting("app.version")
):
    return {
        "debug": debug,
        "version": version,
        "status": "ok"
    }
```

### With whiskey-ai

```python
from whiskey_ai import ai_extension

app.use(ai_extension)

@app.post("/chat")
@inject
async def chat(
    message: str,
    agent: Annotated[ChatAgent, Inject()]
):
    response = await agent.process(message)
    return {"response": response}
```

## Performance Considerations

1. **Request Scoping**: Each request gets its own scope, ensuring isolation
2. **Async First**: All handlers should be async for best performance
3. **Connection Pooling**: Services like databases should be singletons
4. **Middleware Order**: Place frequently-used middleware first

## Best Practices

### 1. Use Explicit Injection

```python
# ✅ Good - explicit about dependencies
@app.get("/users")
@inject
async def list_users(
    page: int = 1,
    service: Annotated[UserService, Inject()]
):
    return await service.list(page=page)

# ❌ Avoid - unclear what gets injected
@app.get("/users")
async def list_users(page: int, service: UserService):
    return await service.list(page=page)
```

### 2. Proper Scoping

```python
# Singleton for shared resources
@singleton
class DatabasePool:
    def __init__(self):
        self.pool = create_pool()

# Request scope for request-specific data
@scoped("request")
class RequestTracker:
    def __init__(self):
        self.events = []
```

### 3. Event-Driven Patterns

```python
# Emit events for cross-cutting concerns
@app.post("/users")
async def create_user(data: dict):
    user = await create_user_in_db(data)
    await app.emit("user.created", user)
    return user

# Handle in multiple places
@app.on("user.created")
async def log_user(user): ...

@app.on("user.created")
async def send_welcome_email(user): ...
```

## Architecture

The ASGI extension is built on:

1. **ASGIApp**: Main ASGI application implementing the ASGI3 protocol
2. **Router**: Fast path matching with parameter extraction
3. **Request/Response**: Thin wrappers providing convenient APIs
4. **Middleware Chain**: Composable middleware with proper ordering
5. **Scope Manager**: Automatic request scope creation and cleanup

## Examples

See the `examples/` directory for complete examples:
- `basic_api.py` - Simple REST API
- `websocket_chat.py` - Real-time chat with WebSockets
- `full_app.py` - Complete application with auth, database, and more

## Contributing

We welcome contributions! See the main [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](../LICENSE) for details.
=======
from whiskey import Whiskey, inject, singleton
from whiskey_asgi import ASGIApp

# Create Whiskey app with ASGI plugin
app = Whiskey(plugins=["whiskey-asgi"])
asgi = ASGIApp(app)

# Define a service
@singleton
class GreetingService:
    def greet(self, name: str) -> str:
        return f"Hello, {name}!"

# Define routes with DI
@asgi.get("/hello/{name}")
@inject
async def hello(request, response, greeting: GreetingService):
    name = request.route_params["name"]
    await response.text(greeting.greet(name))

# Run with uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(asgi, host="127.0.0.1", port=8000)
```

## Design Philosophy

This plugin follows Whiskey's philosophy of being minimal and extensible:

- **Minimal Core**: Only essential ASGI functionality is included
- **Leverage Whiskey**: Uses existing DI, scopes, and event systems
- **Extensible**: Other plugins can add features like JSON handling, templates, etc.
- **Type Safe**: Full type hints for better IDE support and fewer bugs

## Architecture

The plugin provides:

1. **ASGIApp**: The main ASGI application that wraps a Whiskey Whiskey
2. **Request/Response**: Minimal wrappers around ASGI scope and callables
3. **Router**: Simple path-based routing with parameter extraction
4. **Middleware**: Composable middleware interface
5. **Request Scope**: Automatic per-request container and scope management

## Extending

Other plugins can build on top of this foundation:

- **whiskey-json**: Advanced JSON serialization/validation
- **whiskey-templates**: Template rendering support
- **whiskey-auth**: Authentication and authorization
- **whiskey-orm**: Database integration
- **whiskey-openapi**: OpenAPI/Swagger support

## Examples

See the `examples/` directory for more usage examples.
>>>>>>> origin/main
