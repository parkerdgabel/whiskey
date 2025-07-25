"""Simple ASGI example showing the new API."""

from whiskey import Application, inject
from whiskey_asgi import asgi_extension, Request


# Service
class GreetingService:
    """Service that creates greetings."""
    
    def __init__(self):
        self._counter = 0
    
    def greet(self, name: str) -> str:
        self._counter += 1
        return f"Hello, {name}! (Request #{self._counter})"


# Create app with ASGI extension
app = Application()
app.use(asgi_extension)

# Register service
app.container[GreetingService] = GreetingService()


# Routes
@app.get("/")
async def index():
    """Home page."""
    return {
        "message": "Welcome to Whiskey ASGI!",
        "endpoints": [
            {"path": "/", "description": "This page"},
            {"path": "/hello/{name}", "description": "Greet someone"},
            {"path": "/api/data", "description": "JSON API"},
            {"path": "/inject", "description": "Dependency injection example"},
        ]
    }


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


@app.get("/inject")
@inject
async def injected_handler(request: Request, greeting: GreetingService):
    """Handler that uses dependency injection."""
    name = request.headers.get("x-user-name", "Whiskey User")
    greeting_msg = greeting.greet(name)
    return {"greeting": greeting_msg}


@app.post("/echo")
@inject
async def echo(request: Request):
    """Echo back the JSON body."""
    body = await request.json()
    return body, 201


# Middleware
@app.middleware()
async def logging_middleware(request: Request, call_next):
    """Simple logging middleware."""
    print(f"[{request.method}] {request.path}")
    response = await call_next(request)
    return response


@app.middleware(priority=10)  # Higher priority runs first
@inject
async def timing_middleware(request: Request, call_next):
    """Add timing header."""
    import time
    start = time.time()
    response = await call_next(request)
    # In a real implementation, we'd modify response headers
    print(f"Request took {time.time() - start:.3f}s")
    return response


# Run with uvicorn
if __name__ == "__main__":
    # This will use uvicorn to run the ASGI app
    app.run_asgi(host="0.0.0.0", port=8000)