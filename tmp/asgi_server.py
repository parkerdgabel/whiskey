#!/usr/bin/env python
"""Simple ASGI server using Whiskey framework."""

from whiskey import Whiskey, inject, singleton
from whiskey_asgi import asgi_extension, Request


# Create the application
app = Whiskey()
app.use(asgi_extension)


# Services
@app.singleton
class GreetingService:
    def __init__(self):
        self.greetings = {
            "en": "Hello",
            "es": "Hola",
            "fr": "Bonjour",
            "de": "Hallo",
        }
    
    def greet(self, name: str, lang: str = "en") -> str:
        greeting = self.greetings.get(lang, self.greetings["en"])
        return f"{greeting}, {name}!"


@app.singleton
class CounterService:
    def __init__(self):
        self.count = 0
    
    def increment(self) -> int:
        self.count += 1
        return self.count
    
    def get_count(self) -> int:
        return self.count


# Routes
@app.get("/")
async def index():
    return {"message": "Welcome to Whiskey ASGI Server!", "status": "running"}


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "whiskey-asgi"}


@app.get("/greet/{name}")
@inject
async def greet(name: str, service: GreetingService, lang: str = "en"):
    message = service.greet(name, lang)
    return {"message": message}


@app.get("/count")
@inject
async def get_count(counter: CounterService):
    return {"count": counter.get_count()}


@app.post("/count/increment")
@inject
async def increment_count(counter: CounterService):
    new_count = counter.increment()
    return {"count": new_count, "message": "Counter incremented"}


@app.post("/echo")
@inject
async def echo(request: Request):
    body = await request.json()
    return {"echo": body, "method": request.method, "path": request.path}


# Middleware for logging
@app.middleware(priority=10)
@inject
async def logging_middleware(call_next, request: Request):
    print(f"[REQUEST] {request.method} {request.path}")
    response = await call_next(request)
    print(f"[RESPONSE] Completed {request.method} {request.path}")
    return response


# WebSocket endpoint
@app.websocket("/ws/echo")
async def websocket_echo(websocket):
    await websocket.accept()
    await websocket.send("Connected to echo server")
    
    try:
        async for message in websocket:
            # Echo the message back
            await websocket.send(f"Echo: {message}")
    except Exception as e:
        print(f"WebSocket error: {e}")


if __name__ == "__main__":
    # Run the server
    print("Starting Whiskey ASGI server on http://localhost:8000")
    print("Available endpoints:")
    print("  GET  /              - Welcome message")
    print("  GET  /health        - Health check")
    print("  GET  /greet/{name}  - Greet someone (add ?lang=es for Spanish)")
    print("  GET  /count         - Get current count")
    print("  POST /count/increment - Increment counter")
    print("  POST /echo          - Echo JSON body")
    print("  WS   /ws/echo       - WebSocket echo server")
    print("\nPress Ctrl+C to stop")
    
    app.run_asgi(host="0.0.0.0", port=8000)