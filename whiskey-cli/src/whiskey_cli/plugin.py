"""CLI plugin for Whiskey framework."""

from whiskey import Application, Container
from whiskey.plugins import BasePlugin


class CLIPlugin(BasePlugin):
    """Plugin that provides CLI framework functionality."""

    def __init__(self):
        super().__init__(
            name="whiskey-cli",
            version="0.1.0",
            description="CLI framework integration for Whiskey",
        )
        self._dependencies = []

    def register(self, container: Container) -> None:
        """Register CLI services with the container."""
        # CLI-specific services can be registered here
        pass

    def initialize(self, app: Application) -> None:
        """Initialize the plugin with the application."""
        # CLI-specific initialization
        pass