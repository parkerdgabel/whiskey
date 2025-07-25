"""Basic ASGI application example using Whiskey."""

import asyncio
from typing import Dict

from whiskey import Application, ApplicationConfig, inject, singleton
from whiskey_asgi import ASGIApp, Request, Response, middleware


# Service definitions
@singleton
class GreetingService:
    """A simple service that generates greetings."""
    
    def __init__(self):
        self._counter = 0
    
    def greet(self, name: str) -> str:
        self._counter += 1
        return f"Hello, {name}! (Request #{self._counter})"


# Create the Whiskey application and extend with ASGI
from whiskey_asgi import asgi_extension

app = Application(ApplicationConfig(
    name="WhiskeyASGIExample",
)).extend(asgi_extension)

# Get the ASGI app from the container
async def get_asgi():
    return await app.container.resolve(ASGIApp)

# For module-level usage, we need to run async code
asgi = asyncio.run(get_asgi())


# Define routes
@asgi.get("/")
async def index(request: Request, response: Response) -> None:
    """Home page."""
    await response.html("""
    <h1>Whiskey ASGI Example</h1>
    <p>Welcome to the Whiskey ASGI framework!</p>
    <ul>
        <li><a href="/hello/World">Say hello</a></li>
        <li><a href="/api/data">JSON API</a></li>
        <li><a href="/inject">Dependency injection example</a></li>
    </ul>
    """)


@asgi.get("/hello/{name}")
async def hello(request: Request, response: Response) -> None:
    """Greet a user by name."""
    name = request.route_params.get("name", "Anonymous")  # type: ignore
    await response.text(f"Hello, {name}!")


@asgi.get("/api/data")
async def api_data(request: Request, response: Response) -> None:
    """Return JSON data."""
    data = {
        "message": "This is JSON data",
        "method": request.method,
        "path": request.path,
        "query_params": dict(request.query_params),
    }
    await response.json(data)


# Example with dependency injection
@asgi.get("/inject")
@inject
async def injected_handler(
    request: Request,
    response: Response,
    greeting_service: GreetingService,
) -> None:
    """Handler that uses dependency injection."""
    name = request.query_param("name", "Whiskey User")
    greeting = greeting_service.greet(name)
    await response.text(greeting)


# Add middleware
@middleware
def logging_middleware(handler):
    """Simple logging middleware."""
    async def wrapper(request: Request, response: Response):
        print(f"[{request.method}] {request.path}")
        await handler(request, response)
        print(f"[{response.status}] Response sent")
    return wrapper


asgi.add_middleware(logging_middleware)


# Run with uvicorn
if __name__ == "__main__":
    # To run this example:
    # pip install uvicorn
    # python basic_app.py
    import uvicorn
    uvicorn.run(asgi, host="127.0.0.1", port=8000)