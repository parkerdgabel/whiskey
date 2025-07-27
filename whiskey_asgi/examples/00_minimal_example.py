"""Basic ASGI application example using Whiskey."""

from whiskey import Whiskey, inject
from whiskey_asgi import Request, asgi_extension


# Service definitions
class GreetingService:
    """A simple service that generates greetings."""

    def __init__(self):
        self._counter = 0

    def greet(self, name: str) -> str:
        self._counter += 1
        return f"Hello, {name}! (Request #{self._counter})"


# Create the Whiskey application with ASGI extension
app = Whiskey()
app.use(asgi_extension)

# Register service as singleton
app.container[GreetingService] = GreetingService()


# Define routes
@app.get("/")
async def index():
    """Home page."""
    html = """
    <h1>Whiskey ASGI Example</h1>
    <p>Welcome to the Whiskey ASGI framework!</p>
    <ul>
        <li><a href="/hello/World">Say hello</a></li>
        <li><a href="/api/data">JSON API</a></li>
        <li><a href="/inject">Dependency injection example</a></li>
    </ul>
    """
    return html, 200  # Can return HTML with status


@app.get("/hello/{name}")
async def hello(name: str):
    """Greet a user by name."""
    return f"Hello, {name}!"


@app.get("/api/data")
@inject
async def api_data(request: Request):
    """Return JSON data."""
    return {
        "message": "This is JSON data",
        "method": request.method,
        "path": request.path,
        "headers": dict(request.headers),
    }


# Example with dependency injection
@app.get("/inject")
@inject
async def injected_handler(request: Request, greeting_service: GreetingService):
    """Handler that uses dependency injection."""
    # Get name from query string
    name = "Whiskey User"
    if request.query_string:
        params = {}
        for item in request.query_string.decode().split("&"):
            if "=" in item:
                k, v = item.split("=", 1)
                params[k] = v
        name = params.get("name", name)

    greeting = greeting_service.greet(name)
    return {"greeting": greeting}


# Add middleware
@app.middleware()
async def logging_middleware(request: Request, call_next):
    """Simple logging middleware."""
    print(f"[{request.method}] {request.path}")
    response = await call_next(request)
    return response


# Run the application
if __name__ == "__main__":
    # To run this example:
    # pip install uvicorn
    # python basic_app.py

    # New way: Use app.run() which automatically uses the ASGI runner
    app.run()

    # Or explicitly use run_asgi for more control over host/port:
    # app.run_asgi(host="127.0.0.1", port=8000)
