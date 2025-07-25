"""ASGI plugin for Whiskey framework."""

from whiskey import Application, Container
from whiskey.plugins import BasePlugin

from .app import ASGIApp


class ASGIPlugin(BasePlugin):
    """Plugin that provides ASGI web framework functionality."""

    def __init__(self):
        super().__init__(
            name="whiskey-asgi",
            version="0.1.0",
            description="ASGI web framework integration for Whiskey",
        )
        self._dependencies = []

    def register(self, container: Container) -> None:
        """Register ASGI services with the container."""
        # Register ASGIApp as a singleton
        container.register_singleton(ASGIApp, ASGIApp)

    def initialize(self, app: Application) -> None:
        """Initialize the plugin with the application."""
        # The ASGIApp will be created with the application instance
        pass