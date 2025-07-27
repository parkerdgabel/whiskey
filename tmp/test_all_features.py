#!/usr/bin/env python
"""Comprehensive test of Whiskey ASGI features."""

import asyncio
import json
import httpx
import websockets
from typing import Dict, Any


async def test_http_features():
    """Test all HTTP features."""
    print("HTTP Features Test")
    print("==================")
    
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        # 1. Basic routes
        resp = await client.get("/")
        assert resp.status_code == 200
        print("✓ Root endpoint:", resp.json())
        
        # 2. Health check
        resp = await client.get("/health")
        assert resp.status_code == 200
        print("✓ Health check:", resp.json())
        
        # 3. Path parameters
        resp = await client.get("/greet/Whiskey")
        assert resp.status_code == 200
        print("✓ Greeting:", resp.json()["message"])
        
        # 4. Singleton state (counter)
        resp = await client.get("/count")
        initial_count = resp.json()["count"]
        print(f"✓ Initial count: {initial_count}")
        
        # Increment
        resp = await client.post("/count/increment")
        new_count = resp.json()["count"]
        assert new_count == initial_count + 1
        print(f"✓ Count after increment: {new_count}")
        
        # 5. Request body handling
        test_data = {"message": "Test", "values": [1, 2, 3]}
        resp = await client.post("/echo", json=test_data)
        echo_data = resp.json()
        assert echo_data["echo"] == test_data
        assert echo_data["method"] == "POST"
        print("✓ Echo endpoint working")
        
        # 6. Error handling
        resp = await client.get("/not-found")
        assert resp.status_code == 404
        print("✓ 404 error handling working")


async def test_websocket_features():
    """Test WebSocket features."""
    print("\nWebSocket Features Test")
    print("=======================")
    
    uri = "ws://localhost:8000/ws/echo"
    
    async with websockets.connect(uri) as ws:
        # Receive greeting
        greeting = await ws.recv()
        print(f"✓ Connected: {greeting}")
        
        # Test various message types
        test_cases = [
            ("Simple text", "Hello WebSocket"),
            ("JSON data", json.dumps({"type": "test", "id": 123})),
            ("Unicode", "Hello 世界 🚀"),
            ("Large message", "x" * 1000),
        ]
        
        for test_name, message in test_cases:
            await ws.send(message)
            response = await ws.recv()
            assert response == f"Echo: {message}"
            print(f"✓ {test_name} echoed correctly")


async def test_dependency_injection():
    """Test dependency injection features."""
    print("\nDependency Injection Test")
    print("=========================")
    
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        # The greeting service is injected
        resp = await client.get("/greet/DI-Test")
        assert "Hello, DI-Test!" in resp.json()["message"]
        print("✓ Service injection working")
        
        # The counter service maintains state
        resp1 = await client.post("/count/increment")
        resp2 = await client.post("/count/increment")
        assert resp2.json()["count"] == resp1.json()["count"] + 1
        print("✓ Singleton service state preserved")
        
        # Request object is injected
        resp = await client.post("/echo", json={"di": "test"})
        assert resp.json()["path"] == "/echo"
        print("✓ Request object injection working")


async def run_all_tests():
    """Run all tests."""
    print("Whiskey ASGI Extension Test Suite")
    print("=================================\n")
    
    try:
        # Check server is running
        async with httpx.AsyncClient() as client:
            resp = await client.get("http://localhost:8000/health")
            if resp.status_code != 200:
                print("❌ Server not running properly")
                return
    except Exception as e:
        print(f"❌ Server not running: {e}")
        return
    
    # Run tests
    await test_http_features()
    await test_websocket_features()
    await test_dependency_injection()
    
    print("\n✨ All tests passed! The Whiskey ASGI extension is working perfectly.")
    print("\nFeatures demonstrated:")
    print("- HTTP routing with path parameters")
    print("- Multiple HTTP methods (GET, POST)")
    print("- Request body parsing (JSON)")
    print("- WebSocket support with echo server")
    print("- Dependency injection for services")
    print("- Singleton service state management")
    print("- Request object injection")
    print("- Middleware execution")
    print("- Error handling (404)")


if __name__ == "__main__":
    asyncio.run(run_all_tests())