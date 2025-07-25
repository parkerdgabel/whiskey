"""WebSocket example with dependency injection."""

import asyncio
from typing import Set

from whiskey import Application, inject
from whiskey_asgi import asgi_extension, WebSocket


# Service for managing chat rooms
class ChatService:
    """Service that manages chat rooms and connections."""
    
    def __init__(self):
        self.rooms: dict[str, Set[WebSocket]] = {}
        self.user_names: dict[WebSocket, str] = {}
    
    async def join_room(self, room_id: str, websocket: WebSocket, username: str) -> None:
        """Add a user to a room."""
        if room_id not in self.rooms:
            self.rooms[room_id] = set()
        
        self.rooms[room_id].add(websocket)
        self.user_names[websocket] = username
        
        # Notify others
        await self.broadcast(room_id, f"{username} joined the room", exclude=websocket)
    
    async def leave_room(self, room_id: str, websocket: WebSocket) -> None:
        """Remove a user from a room."""
        if room_id in self.rooms and websocket in self.rooms[room_id]:
            self.rooms[room_id].remove(websocket)
            username = self.user_names.pop(websocket, "Unknown")
            
            # Notify others
            await self.broadcast(room_id, f"{username} left the room", exclude=websocket)
            
            # Clean up empty rooms
            if not self.rooms[room_id]:
                del self.rooms[room_id]
    
    async def broadcast(self, room_id: str, message: str, exclude: WebSocket = None) -> None:
        """Broadcast a message to all users in a room."""
        if room_id not in self.rooms:
            return
        
        # Send to all connections in the room
        tasks = []
        for ws in self.rooms[room_id]:
            if ws != exclude:
                tasks.append(ws.send(message))
        
        # Send all messages concurrently
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


# Create app with ASGI extension
app = Application()
app.use(asgi_extension)

# Register service as singleton
app.container[ChatService] = ChatService()


# WebSocket routes
@app.websocket("/ws/chat/{room_id}")
@inject
async def chat_handler(websocket: WebSocket, room_id: str, chat: ChatService):
    """WebSocket chat handler with rooms."""
    await websocket.accept()
    
    # Get username from query params or headers
    username = websocket.headers.get("x-username", f"User_{id(websocket)}")
    
    # Join the room
    await chat.join_room(room_id, websocket, username)
    await websocket.send(f"Welcome to room {room_id}, {username}!")
    
    try:
        # Handle messages
        async for message in websocket:
            if isinstance(message, str):
                # Broadcast to room
                formatted = f"{username}: {message}"
                await chat.broadcast(room_id, formatted)
    finally:
        # Leave room on disconnect
        await chat.leave_room(room_id, websocket)


@app.websocket("/ws/echo")
async def echo_handler(websocket: WebSocket):
    """Simple echo WebSocket handler."""
    await websocket.accept()
    
    try:
        async for message in websocket:
            # Echo back the message
            await websocket.send(f"Echo: {message}")
    except ConnectionError:
        pass


# HTTP routes for testing
@app.get("/")
async def index():
    """Home page with WebSocket info."""
    return {
        "message": "WebSocket Example",
        "endpoints": [
            {
                "path": "/ws/chat/{room_id}",
                "protocol": "websocket",
                "description": "Join a chat room"
            },
            {
                "path": "/ws/echo",
                "protocol": "websocket", 
                "description": "Echo service"
            }
        ],
        "example": "Connect to ws://localhost:8000/ws/chat/general"
    }


# HTML client for testing
@app.get("/client")
async def client():
    """Simple HTML client for testing WebSockets."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>WebSocket Test</title>
    </head>
    <body>
        <h1>WebSocket Chat</h1>
        <div>
            <input type="text" id="room" placeholder="Room ID" value="general">
            <input type="text" id="username" placeholder="Username" value="User">
            <button onclick="connect()">Connect</button>
            <button onclick="disconnect()">Disconnect</button>
        </div>
        <div>
            <input type="text" id="message" placeholder="Message">
            <button onclick="send()">Send</button>
        </div>
        <div id="messages" style="border: 1px solid #ccc; height: 300px; overflow-y: scroll; margin-top: 10px; padding: 10px;">
        </div>
        
        <script>
            let ws = null;
            
            function connect() {
                const room = document.getElementById('room').value;
                const username = document.getElementById('username').value;
                
                ws = new WebSocket(`ws://localhost:8000/ws/chat/${room}`);
                
                ws.onopen = () => {
                    addMessage('Connected to ' + room);
                };
                
                ws.onmessage = (event) => {
                    addMessage(event.data);
                };
                
                ws.onclose = () => {
                    addMessage('Disconnected');
                    ws = null;
                };
                
                ws.onerror = (error) => {
                    addMessage('Error: ' + error);
                };
            }
            
            function disconnect() {
                if (ws) {
                    ws.close();
                }
            }
            
            function send() {
                const input = document.getElementById('message');
                if (ws && input.value) {
                    ws.send(input.value);
                    input.value = '';
                }
            }
            
            function addMessage(msg) {
                const messages = document.getElementById('messages');
                messages.innerHTML += '<div>' + msg + '</div>';
                messages.scrollTop = messages.scrollHeight;
            }
            
            // Send on Enter
            document.getElementById('message').addEventListener('keypress', (e) => {
                if (e.key === 'Enter') send();
            });
        </script>
    </body>
    </html>
    """, 200  # Return HTML with 200 status


# Run with uvicorn
if __name__ == "__main__":
    print("WebSocket server starting...")
    print("Test the chat at: http://localhost:8000/client")
    app.run_asgi(host="0.0.0.0", port=8000)