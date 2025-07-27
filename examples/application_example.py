"""Rich application example demonstrating Whiskey's Application framework.

This example shows:
- Full application lifecycle management
- Component initialization and disposal
- Event system with wildcard patterns
- Background tasks
- Health checking
- Error handling
- Component metadata and priority

Run this example:
    python examples/application_example.py
"""

import asyncio
from typing import Annotated

from whiskey import Whiskey, Disposable, Initializable, Inject, inject

# Step 1: Define services with lifecycle hooks
        if not self.connected:
            raise RuntimeError("Database not connected")
        return f"Results for: {sql}"


class CacheService(Initializable):
    """Cache service that only needs initialization."""

    def __init__(self):
        self.cache = {}
        self.initialized = False

    async def initialize(self):
        """Warm up the cache on startup."""
        print("🗄️  Initializing cache...")
        # Pre-load some data
        self.cache["config"] = {"version": "1.0", "features": ["auth", "api"]}
        self.initialized = True
        print("✅ Cache initialized")

    async def get(self, key: str) -> any:
        """Get value from cache."""
        return self.cache.get(key)

    async def set(self, key: str, value: any) -> None:
        """Set value in cache."""
        self.cache[key] = value


# Step 2: Create services that use dependency injection
