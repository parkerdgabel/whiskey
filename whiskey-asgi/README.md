# Whiskey ASGI Plugin

A minimal ASGI web framework plugin for Whiskey that provides a foundation for building web applications with dependency injection.

## Features

- **ASGI 3.0 Compliant**: Full support for the ASGI specification
- **Dependency Injection**: Seamless integration with Whiskey's DI system
- **Request Scoping**: Automatic request-scoped container creation
- **Simple Routing**: Path-based routing with parameter extraction
- **Middleware Support**: Composable middleware chain
- **Type Safety**: Full type hints throughout

## Installation

```bash
pip install whiskey-asgi
```

## Quick Start

```python
from whiskey import Application, inject, singleton
from whiskey_asgi import ASGIApp

# Create Whiskey app with ASGI plugin
app = Application(plugins=["whiskey-asgi"])
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

1. **ASGIApp**: The main ASGI application that wraps a Whiskey Application
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