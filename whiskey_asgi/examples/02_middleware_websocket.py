#!/usr/bin/env python
"""Middleware and WebSocket example.

This example demonstrates:
- Custom middleware for logging, authentication, and timing
- WebSocket connections with dependency injection
- Real-time broadcasting to multiple clients
- Request/Response interceptors
- Mixed HTTP and WebSocket endpoints

Usage:
    python 02_middleware_websocket.py

    Then open multiple browser tabs to:
    http://localhost:8000/

    The page will connect via WebSocket and show real-time messages.
"""

import json
import time

from whiskey import Whiskey, inject, singleton
from whiskey_asgi import Request, WebSocket, asgi_extension


# Services
@singleton
class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self):
        self.active_connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        """Accept and track a new connection."""
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        """Remove a connection."""
        self.active_connections.discard(websocket)

    async def broadcast(self, message: str):
        """Send message to all connected clients."""
        # Remove disconnected clients
        disconnected = set()

        for connection in self.active_connections:
            try:
                await connection.send(message)
            except Exception:
                disconnected.add(connection)

        # Clean up disconnected
        self.active_connections -= disconnected


@singleton
class MessageHistory:
    """Stores message history."""

    def __init__(self):
        self.messages = []
        self.max_history = 50

    def add(self, message: dict):
        """Add a message to history."""
        self.messages.append(message)
        if len(self.messages) > self.max_history:
            self.messages.pop(0)

    def get_all(self):
        """Get all messages."""
        return self.messages


# Create application
app = Whiskey()
app.use(asgi_extension)


# Middleware
@app.middleware(priority=100)  # Higher priority runs first
async def timing_middleware(request: Request, call_next):
    """Add request timing."""
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    # Add timing header (in real app, might log this)
    print(f"⏱️  {request.method} {request.path} - {duration:.3f}s")
    return response


@app.middleware(priority=50)
async def logging_middleware(request: Request, call_next):
    """Log all requests."""
    print(f"📥 {request.method} {request.path}")
    response = await call_next(request)
    return response


@app.middleware()
@inject
async def auth_middleware(request: Request, call_next, connections: ConnectionManager):
    """Simple auth check (demo only)."""
    # Skip auth for WebSocket and root
    if request.path in ["/", "/ws", "/messages"]:
        return await call_next(request)

    # Check for auth header (demo - not real auth!)
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return {"error": "Unauthorized"}, 401

    # Add user info to request (in real app, would verify token)
    request.user = auth.replace("Bearer ", "")

    return await call_next(request)


# HTTP Routes
@app.get("/")
async def index():
    """Serve the WebSocket client page."""
    return (
        """
    <html>
    <head>
        <title>Whiskey WebSocket Demo</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            #messages { border: 1px solid #ccc; height: 300px; overflow-y: auto; padding: 10px; margin: 20px 0; }
            .message { margin: 5px 0; padding: 5px; background: #f0f0f0; border-radius: 5px; }
            .system { color: #666; font-style: italic; }
            input { padding: 5px; width: 300px; }
            button { padding: 5px 10px; }
        </style>
    </head>
    <body>
        <h1>Whiskey WebSocket Chat</h1>
        <div id="messages"></div>
        <input type="text" id="messageInput" placeholder="Type a message..." />
        <button onclick="sendMessage()">Send</button>
        <button onclick="connect()">Reconnect</button>
        
        <script>
            let ws = null;
            const messages = document.getElementById('messages');
            const input = document.getElementById('messageInput');
            
            function addMessage(text, isSystem = false) {
                const div = document.createElement('div');
                div.className = isSystem ? 'message system' : 'message';
                div.textContent = text;
                messages.appendChild(div);
                messages.scrollTop = messages.scrollHeight;
            }
            
            function connect() {
                if (ws) ws.close();
                
                ws = new WebSocket('ws://localhost:8000/ws');
                
                ws.onopen = () => {
                    addMessage('Connected to server', true);
                };
                
                ws.onmessage = (event) => {
                    const data = JSON.parse(event.data);
                    if (data.type === 'history') {
                        data.messages.forEach(msg => {
                            addMessage(`${msg.user}: ${msg.text}`);
                        });
                    } else {
                        addMessage(`${data.user}: ${data.text}`);
                    }
                };
                
                ws.onclose = () => {
                    addMessage('Disconnected from server', true);
                };
                
                ws.onerror = (error) => {
                    addMessage('Connection error', true);
                };
            }
            
            function sendMessage() {
                if (ws && ws.readyState === WebSocket.OPEN && input.value) {
                    ws.send(input.value);
                    input.value = '';
                }
            }
            
            input.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') sendMessage();
            });
            
            // Connect on load
            connect();
        </script>
    </body>
    </html>
    """,
        200,
        {"Content-Type": "text/html"},
    )


@app.get("/messages")
@inject
async def get_messages(history: MessageHistory):
    """Get message history."""
    return {"messages": history.get_all()}


@app.post("/broadcast")
@inject
async def broadcast_message(request: Request, manager: ConnectionManager):
    """Broadcast a message to all connected clients (requires auth)."""
    if not hasattr(request, "user"):
        return {"error": "Unauthorized"}, 401

    data = await request.json()
    message = json.dumps({"type": "broadcast", "user": "System", "text": data.get("message", "")})

    await manager.broadcast(message)
    return {"status": "broadcasted", "clients": len(manager.active_connections)}


# WebSocket endpoint
@app.websocket("/ws")
@inject
async def websocket_endpoint(
    websocket: WebSocket, manager: ConnectionManager, history: MessageHistory
):
    """Handle WebSocket connections."""
    # Accept connection
    await manager.connect(websocket)
    client_id = f"User{len(manager.active_connections)}"

    try:
        # Send history to new client
        await websocket.send(json.dumps({"type": "history", "messages": history.get_all()}))

        # Notify others
        await manager.broadcast(
            json.dumps(
                {"type": "message", "user": "System", "text": f"{client_id} joined the chat"}
            )
        )

        # Handle messages
        async for message in websocket:
            # Create message object
            msg_obj = {
                "type": "message",
                "user": client_id,
                "text": message if isinstance(message, str) else message.decode(),
            }

            # Store in history
            history.add(msg_obj)

            # Broadcast to all
            await manager.broadcast(json.dumps(msg_obj))

    except Exception as e:
        print(f"WebSocket error: {e}")

    finally:
        # Cleanup on disconnect
        manager.disconnect(websocket)
        await manager.broadcast(
            json.dumps({"type": "message", "user": "System", "text": f"{client_id} left the chat"})
        )


# Run the application
if __name__ == "__main__":
    print("🚀 Starting Whiskey WebSocket Demo...")
    print("🌐 Open http://localhost:8000/ in multiple browsers")
    print("📡 WebSocket endpoint: ws://localhost:8000/ws")
    print("Press Ctrl+C to stop\n")

    # Use the standardized run API
    app.run()

    # Or with specific configuration:
    # app.run_asgi(host="0.0.0.0", port=8000, log_level="info")
