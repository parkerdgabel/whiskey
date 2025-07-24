"""Example services demonstrating DI patterns."""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from loguru import logger
from whiskey import Disposable, Initializable

from .plugin import ExampleConfig


class Item:
    """Simple item model."""
    
    def __init__(self, id: str, name: str):
        self.id = id
        self.name = name
        self.created_at = datetime.utcnow()
        self.metadata: Dict[str, Any] = {}


class ItemRepository:
    """Repository for managing items (scoped service)."""
    
    def __init__(self):
        self._items: Dict[str, Item] = {}
        logger.debug("Created new ItemRepository instance")
    
    async def create(self, id: str, name: str) -> Item:
        """Create a new item."""
        item = Item(id, name)
        self._items[id] = item
        return item
    
    async def get(self, id: str) -> Optional[Item]:
        """Get an item by ID."""
        return self._items.get(id)
    
    async def delete(self, id: str) -> bool:
        """Delete an item."""
        if id in self._items:
            del self._items[id]
            return True
        return False
    
    async def list_all(self) -> List[Item]:
        """List all items."""
        return list(self._items.values())
    
    async def cleanup_old(self, max_age: timedelta) -> int:
        """Remove items older than max_age."""
        cutoff = datetime.utcnow() - max_age
        old_items = [
            id for id, item in self._items.items()
            if item.created_at < cutoff
        ]
        
        for id in old_items:
            del self._items[id]
        
        return len(old_items)


class ExampleService(Initializable, Disposable):
    """Main service for the example plugin (singleton)."""
    
    def __init__(self, config: ExampleConfig):
        self.config = config
        self._initialized = False
        self._stats = {
            "items_created": 0,
            "items_deleted": 0,
            "cleanups_run": 0,
        }
    
    async def initialize(self) -> None:
        """Initialize the service."""
        logger.info(f"Initializing ExampleService: {self.config.greeting}")
        self._initialized = True
    
    async def dispose(self) -> None:
        """Clean up service resources."""
        logger.info(f"Disposing ExampleService. Stats: {self._stats}")
    
    async def process_new_item(self, item_id: str, name: str) -> None:
        """Process a newly created item."""
        if not self._initialized:
            raise RuntimeError("Service not initialized")
        
        self._stats["items_created"] += 1
        
        # Simulate some processing
        logger.debug(f"Processing new item: {name} (ID: {item_id})")
    
    async def cleanup_item(self, item_id: str) -> None:
        """Clean up after an item is deleted."""
        self._stats["items_deleted"] += 1
        
        # Simulate cleanup
        logger.debug(f"Cleaned up item: {item_id}")
    
    async def cleanup_old_items(self) -> int:
        """Clean up old items across all repositories."""
        self._stats["cleanups_run"] += 1
        
        # In a real plugin, this might coordinate with repositories
        # For demo purposes, we'll just return a simulated count
        import random
        count = random.randint(0, 5)
        
        return count
    
    def get_stats(self) -> Dict[str, int]:
        """Get service statistics."""
        return self._stats.copy()