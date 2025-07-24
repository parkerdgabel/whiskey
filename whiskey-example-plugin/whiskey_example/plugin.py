"""Example Whiskey plugin demonstrating key concepts."""

import os
from dataclasses import dataclass
from typing import Any

from loguru import logger
from whiskey import Application, BasePlugin, Container


@dataclass
class ExampleConfig:
    """Configuration for the example plugin."""
    
    greeting: str = "Hello from Example Plugin!"
    max_items: int = 100
    
    @classmethod
    def from_env(cls) -> "ExampleConfig":
        """Load configuration from environment variables."""
        return cls(
            greeting=os.getenv("EXAMPLE_GREETING", cls.greeting),
            max_items=int(os.getenv("EXAMPLE_MAX_ITEMS", str(cls.max_items))),
        )


class ExamplePlugin(BasePlugin):
    """Example plugin showing how to create a Whiskey plugin."""
    
    def __init__(self):
        super().__init__(
            name="example",
            version="0.1.0",
            description="Example plugin for demonstration purposes",
        )
    
    def register(self, container: Container) -> None:
        """Register services with the container."""
        from .services import ExampleService, ItemRepository
        
        # Register configuration
        config = ExampleConfig.from_env()
        container.register_singleton(ExampleConfig, instance=config)
        
        # Register services
        container.register_singleton(ExampleService)
        container.register_scoped(ItemRepository)
        
        logger.info(f"Registered Example plugin services")
    
    def initialize(self, app: Application) -> None:
        """Initialize the plugin with the application."""
        from .events import ItemCreated, ItemDeleted
        from .services import ExampleService
        
        # Register event handlers
        @app.on(ItemCreated)
        async def on_item_created(
            event: ItemCreated,
            service: ExampleService,
        ) -> None:
            """Handle item creation events."""
            await service.process_new_item(event.item_id, event.name)
            logger.info(f"Processed new item: {event.name}")
        
        @app.on(ItemDeleted)
        async def on_item_deleted(
            event: ItemDeleted,
            service: ExampleService,
        ) -> None:
            """Handle item deletion events."""
            await service.cleanup_item(event.item_id)
            logger.info(f"Cleaned up item: {event.item_id}")
        
        # Register a background task
        @app.task(interval=300)  # Run every 5 minutes
        async def cleanup_old_items(service: ExampleService):
            """Periodically clean up old items."""
            count = await service.cleanup_old_items()
            if count > 0:
                logger.info(f"Cleaned up {count} old items")
        
        # Register startup/shutdown hooks
        @app.on_startup
        async def initialize_example():
            """Initialize example plugin resources."""
            service = await app.container.resolve(ExampleService)
            await service.initialize()
            logger.info("Example plugin initialized")
        
        @app.on_shutdown
        async def cleanup_example():
            """Clean up example plugin resources."""
            service = await app.container.resolve(ExampleService)
            await service.cleanup()
            logger.info("Example plugin cleaned up")