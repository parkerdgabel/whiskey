#!/usr/bin/env python
"""Test WebSocket using the standard websockets library."""

import asyncio
import json
import websockets


async def test_websocket():
    """Test the WebSocket echo server."""
    uri = "ws://localhost:8000/ws/echo"
    
    try:
        # Connect without specifying subprotocols
        async with websockets.connect(uri) as websocket:
            print("✓ Connected to WebSocket server")
            
            # Receive the initial greeting
            greeting = await websocket.recv()
            print(f"✓ Server greeting: {greeting}")
            
            # Test sending and receiving messages
            test_messages = [
                "Hello, WebSocket!",
                "Testing 123",
                json.dumps({"type": "test", "data": [1, 2, 3]}),
                "Final message 🎉"
            ]
            
            for msg in test_messages:
                print(f"\n→ Sending: {msg}")
                await websocket.send(msg)
                
                response = await websocket.recv()
                print(f"← Received: {response}")
                
                # Verify echo
                assert response == f"Echo: {msg}", f"Expected 'Echo: {msg}', got '{response}'"
            
            print("\n✓ All WebSocket tests passed!")
            
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"✗ WebSocket connection rejected: {e}")
        print("  Make sure the server has WebSocket support (uvicorn[standard])")
    except Exception as e:
        print(f"✗ WebSocket error: {type(e).__name__}: {e}")
        
        # Try to verify the server is at least running
        print("\nChecking if server is running...")
        import httpx
        try:
            resp = httpx.get("http://localhost:8000/health")
            print(f"✓ Server is running: {resp.json()}")
            print("  But WebSocket support may be missing")
        except Exception:
            print("✗ Server is not running")


if __name__ == "__main__":
    print("WebSocket Echo Test")
    print("==================")
    asyncio.run(test_websocket())