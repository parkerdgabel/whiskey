#!/usr/bin/env python
"""Simple WebSocket test using httpx-ws."""

import asyncio
from contextlib import asynccontextmanager
import httpx
from httpx_ws import aconnect_ws


async def test_websocket():
    """Test WebSocket connection with httpx-ws."""
    try:
        async with httpx.AsyncClient() as client:
            async with aconnect_ws("ws://localhost:8000/ws/echo", client) as ws:
                print("Connected to WebSocket!")
                
                # Receive initial message
                initial = await ws.receive_text()
                print(f"Server: {initial}")
                
                # Send and receive messages
                messages = ["Hello", "World", "WebSocket test!"]
                for msg in messages:
                    print(f"Sending: {msg}")
                    await ws.send_text(msg)
                    
                    response = await ws.receive_text()
                    print(f"Received: {response}")
                
                print("Test completed successfully!")
                
    except Exception as e:
        print(f"Error: {e}")
        print("Falling back to basic HTTP test to verify server is running...")
        
        # Test if server is running
        import httpx
        try:
            response = httpx.get("http://localhost:8000/health")
            print(f"Server health check: {response.json()}")
        except Exception as e2:
            print(f"Server not running: {e2}")


if __name__ == "__main__":
    asyncio.run(test_websocket())