#!/usr/bin/env python
"""Basic ASGI API example - Getting started with Whiskey ASGI.

This example demonstrates:
- Creating a web API with Whiskey
- Defining HTTP routes (GET, POST, PUT, DELETE)
- Using dependency injection in route handlers
- Request/Response handling
- Running with the new standardized run API

Usage:
    python 01_basic_api.py

    Then test with:
    curl http://localhost:8000/
    curl http://localhost:8000/hello/World
    curl -X POST http://localhost:8000/items -H "Content-Type: application/json" -d '{"name":"Test"}'
"""

from typing import Optional

from whiskey import Whiskey, inject, singleton
from whiskey_asgi import Request, asgi_extension


# Domain models
class Item:
    """A simple item model."""

    def __init__(self, item_id: int, name: str, price: float = 0.0):
        self.id = item_id
        self.name = name
        self.price = price

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "price": self.price}


# Services
@singleton
class ItemService:
    """Service for managing items."""

    def __init__(self):
        self._items: dict[int, Item] = {}
        self._next_id = 1
        # Add some sample items
        self.create("Coffee", 3.50)
        self.create("Sandwich", 8.00)
        self.create("Salad", 6.50)

    def create(self, name: str, price: float = 0.0) -> Item:
        """Create a new item."""
        item = Item(self._next_id, name, price)
        self._items[self._next_id] = item
        self._next_id += 1
        return item

    def get_all(self) -> list[Item]:
        """Get all items."""
        return list(self._items.values())

    def get_by_id(self, item_id: int) -> Optional[Item]:
        """Get item by ID."""
        return self._items.get(item_id)

    def update(
        self, item_id: int, name: Optional[str] = None, price: Optional[float] = None
    ) -> Optional[Item]:
        """Update an item."""
        item = self._items.get(item_id)
        if item:
            if name is not None:
                item.name = name
            if price is not None:
                item.price = price
        return item

    def delete(self, item_id: int) -> bool:
        """Delete an item."""
        if item_id in self._items:
            del self._items[item_id]
            return True
        return False


# Create application
app = Whiskey()
app.use(asgi_extension)


# Define routes
@app.get("/")
async def index():
    """Welcome endpoint."""
    return {
        "message": "Welcome to Whiskey ASGI API",
        "version": "1.0.0",
        "endpoints": [
            "GET /items",
            "GET /items/{id}",
            "POST /items",
            "PUT /items/{id}",
            "DELETE /items/{id}",
        ],
    }


@app.get("/hello/{name}")
async def hello(name: str):
    """Simple greeting endpoint."""
    return {"message": f"Hello, {name}!"}


# RESTful API endpoints
@app.get("/items")
@inject
async def get_items(service: ItemService):
    """Get all items."""
    items = service.get_all()
    return {"items": [item.to_dict() for item in items], "count": len(items)}


@app.get("/items/{item_id}")
@inject
async def get_item(item_id: int, service: ItemService):
    """Get a specific item."""
    item = service.get_by_id(item_id)
    if item:
        return item.to_dict()
    return {"error": "Item not found"}, 404


@app.post("/items")
@inject
async def create_item(request: Request, service: ItemService):
    """Create a new item."""
    data = await request.json()

    # Validate input
    if "name" not in data:
        return {"error": "Name is required"}, 400

    # Create item
    item = service.create(name=data["name"], price=data.get("price", 0.0))

    return item.to_dict(), 201


@app.put("/items/{item_id}")
@inject
async def update_item(item_id: int, request: Request, service: ItemService):
    """Update an item."""
    data = await request.json()

    item = service.update(item_id, name=data.get("name"), price=data.get("price"))

    if item:
        return item.to_dict()
    return {"error": "Item not found"}, 404


@app.delete("/items/{item_id}")
@inject
async def delete_item(item_id: int, service: ItemService):
    """Delete an item."""
    if service.delete(item_id):
        return {"message": "Item deleted"}
    return {"error": "Item not found"}, 404


# Run the application
if __name__ == "__main__":
    print("🚀 Starting Whiskey ASGI API...")
    print("📝 API documentation available at: http://localhost:8000/")
    print("Press Ctrl+C to stop\n")

    # Use the new standardized run API
    # app.run() automatically detects and uses the ASGI runner
    app.run()

    # You can also use run_asgi directly for more control:
    # app.run_asgi(host="0.0.0.0", port=8000, reload=True)
