"""Advanced ASGI example with session support, error handling, and more."""

import json
import time
from typing import Optional

from whiskey import Application, inject
from whiskey_asgi import Request, asgi_extension


# Services
class SessionService:
    """Simple in-memory session storage."""

    def __init__(self):
        self.sessions: dict[str, dict] = {}

    def get(self, session_id: str) -> dict:
        """Get session data."""
        return self.sessions.get(session_id, {})

    def set(self, session_id: str, data: dict) -> None:
        """Set session data."""
        self.sessions[session_id] = data

    def delete(self, session_id: str) -> None:
        """Delete session."""
        self.sessions.pop(session_id, None)


class UserService:
    """Mock user service."""

    def __init__(self):
        self.users = {
            1: {"id": 1, "name": "Alice", "email": "alice@example.com"},
            2: {"id": 2, "name": "Bob", "email": "bob@example.com"},
        }

    async def get_user(self, user_id: int) -> Optional[dict]:
        """Get user by ID."""
        return self.users.get(user_id)

    async def create_user(self, data: dict) -> dict:
        """Create a new user."""
        user_id = max(self.users.keys()) + 1
        user = {"id": user_id, **data}
        self.users[user_id] = user
        return user


# Create app
app = Application()
app.use(asgi_extension)

# Register services
app.container[SessionService] = SessionService()  # Singleton
app.container[UserService] = UserService()


# Session middleware
@app.middleware(priority=20)  # High priority - runs first
@inject
async def session_middleware(request: Request, call_next, sessions: SessionService):
    """Handle session cookies."""
    # Get session ID from cookie
    session_id = request.cookies.get("session_id", str(time.time()))

    # Load session data
    session_data = sessions.get(session_id)

    # Add session to request (in real app, would use request scope)
    request.session = session_data
    request.session_id = session_id

    # Process request
    response = await call_next(request)

    # Save session (in real app, would set cookie header)
    sessions.set(session_id, request.session)

    return response


# CORS middleware
@app.middleware(priority=15)
async def cors_middleware(request: Request, call_next):
    """Add CORS headers."""
    response = await call_next(request)

    # In real implementation, would modify response headers
    # For now, just log
    print(f"Would add CORS headers for {request.path}")

    return response


# Routes
@app.get("/")
async def index():
    """API documentation."""
    return {
        "name": "Advanced ASGI Example",
        "version": "1.0.0",
        "endpoints": {
            "GET /": "This documentation",
            "GET /users": "List all users",
            "GET /users/{id}": "Get user by ID",
            "POST /users": "Create new user",
            "GET /session": "Get session data",
            "POST /session": "Set session data",
            "GET /error": "Test error handling",
        },
    }


@app.get("/users")
@inject
async def list_users(user_service: UserService):
    """List all users."""
    users = list(user_service.users.values())
    return {"users": users, "count": len(users)}


@app.get("/users/{id}")
@inject
async def get_user(user_id: int, user_service: UserService):
    """Get user by ID."""
    user = await user_service.get_user(user_id)
    if not user:
        return {"error": "User not found"}, 404
    return user


@app.post("/users")
@inject
async def create_user(request: Request, user_service: UserService):
    """Create a new user."""
    try:
        data = await request.json()
    except json.JSONDecodeError:
        return {"error": "Invalid JSON"}, 400

    # Validate
    if not data.get("name") or not data.get("email"):
        return {"error": "Name and email are required"}, 400

    user = await user_service.create_user(data)
    return user, 201


@app.get("/session")
@inject
async def get_session(request: Request):
    """Get current session data."""
    return {
        "session_id": getattr(request, "session_id", None),
        "data": getattr(request, "session", {}),
    }


@app.post("/session")
@inject
async def set_session(request: Request):
    """Set session data."""
    try:
        data = await request.json()
    except json.JSONDecodeError:
        return {"error": "Invalid JSON"}, 400

    # Update session
    if hasattr(request, "session"):
        request.session.update(data)
    else:
        request.session = data

    return {"message": "Session updated", "data": request.session}


@app.get("/error")
async def test_error():
    """Test error handling."""
    raise RuntimeError("This is a test error")


# Error handlers (in real implementation)
@app.on_error
async def handle_errors(error: Exception):
    """Global error handler."""
    print(f"Error occurred: {type(error).__name__}: {error}")
    # In real app, would return proper error response


# Performance monitoring
@app.middleware()
async def performance_middleware(request: Request, call_next):
    """Log request performance."""
    start = time.time()

    try:
        response = await call_next(request)
        elapsed = time.time() - start
        print(f"{request.method} {request.path} took {elapsed:.3f}s")
        return response
    except Exception as e:
        elapsed = time.time() - start
        print(f"{request.method} {request.path} failed after {elapsed:.3f}s: {e}")
        raise


# Run the app
if __name__ == "__main__":
    print("Starting advanced ASGI example...")
    print("API docs at: http://localhost:8000/")
    app.run_asgi(host="0.0.0.0", port=8000)
