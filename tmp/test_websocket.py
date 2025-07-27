#!/usr/bin/env python
"""Test WebSocket connection."""

import asyncio
import websockets


async def test_websocket():
    uri = "ws://localhost:8000/ws/echo"
    
    async with websockets.connect(uri, subprotocols=[]) as websocket:
        print("Connected to WebSocket")
        
        # Receive initial message
        greeting = await websocket.recv()
        print(f"Server says: {greeting}")
        
        # Send some messages
        messages = ["Hello WebSocket!", "Testing 123", "Final message"]
        
        for msg in messages:
            print(f"Sending: {msg}")
            await websocket.send(msg)
            
            # Receive echo
            response = await websocket.recv()
            print(f"Received: {response}")
        
        print("WebSocket test completed!")


if __name__ == "__main__":
    asyncio.run(test_websocket())