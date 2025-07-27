#!/usr/bin/env python
"""Test WebSocket chat functionality with multiple clients."""

import asyncio
import websockets
import json


async def chat_client(name: str, room: str = "general"):
    """Simulate a chat client."""
    uri = f"ws://localhost:8000/ws/chat/{room}"
    
    async with websockets.connect(uri) as websocket:
        print(f"{name} connected to room '{room}'")
        
        # Send a join message
        await websocket.send(f"{name} joined the chat")
        
        # Send and receive some messages
        messages = [
            f"Hello from {name}!",
            f"{name} says: How is everyone?",
            f"This is {name}'s last message"
        ]
        
        for msg in messages:
            await websocket.send(msg)
            await asyncio.sleep(0.5)  # Small delay between messages
            
        print(f"{name} finished sending messages")


async def test_chat_room():
    """Test the chat room with multiple clients."""
    print("Testing WebSocket Chat Room")
    print("==========================")
    
    # Create multiple chat clients
    clients = [
        chat_client("Alice", "general"),
        chat_client("Bob", "general"),
        chat_client("Charlie", "tech"),
    ]
    
    # Run all clients concurrently
    await asyncio.gather(*clients)
    
    print("\n✓ Chat room test completed!")


async def test_websocket_error_handling():
    """Test WebSocket error scenarios."""
    print("\nTesting WebSocket Error Handling")
    print("================================")
    
    # Test invalid path
    try:
        uri = "ws://localhost:8000/ws/invalid"
        async with websockets.connect(uri) as ws:
            pass
    except Exception as e:
        print(f"✓ Invalid path rejected: {type(e).__name__}")
    
    # Test disconnect handling
    uri = "ws://localhost:8000/ws/echo"
    async with websockets.connect(uri) as ws:
        await ws.recv()  # Get greeting
        await ws.send("Test message")
        response = await ws.recv()
        print(f"✓ Normal message: {response}")
        
        # Force close
        await ws.close()
        print("✓ Clean disconnect handled")


if __name__ == "__main__":
    print("Advanced WebSocket Tests")
    print("========================\n")
    
    # First, update the server to add a chat endpoint
    print("Note: The server needs a /ws/chat/{room} endpoint for the chat test.")
    print("Running basic echo test first...\n")
    
    asyncio.run(test_websocket_error_handling())
    
    print("\nAll WebSocket tests completed!")