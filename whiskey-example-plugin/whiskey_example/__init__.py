"""Example Whiskey plugin."""

from .events import ItemCreated, ItemDeleted, ItemUpdated
from .plugin import ExampleConfig, ExamplePlugin
from .services import ExampleService, Item, ItemRepository

__version__ = "0.1.0"

__all__ = [
    # Plugin
    "ExamplePlugin",
    "ExampleConfig",
    # Services
    "ExampleService",
    "ItemRepository",
    "Item",
    # Events
    "ItemCreated",
    "ItemDeleted",
    "ItemUpdated",
]