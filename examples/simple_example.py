"""Simple example demonstrating Whiskey's core dependency injection features.

This example shows:
- Basic service registration with @provide and @singleton decorators
- Automatic dependency injection with @inject
- Manual container usage with dict-like API
- Factory functions for complex initialization

Run this example:
    python examples/simple_example.py
"""

import asyncio

from whiskey import Container, inject, provide, singleton

# Step 1: Define your services
