"""AI plugin for Whiskey framework."""

from whiskey.plugins import BasePlugin
from whiskey.core.container import Container
from whiskey.core.application import Application

from .scopes import (
    AIContextScope,
    BatchScope,
    ConversationScope,
    SessionScope,
    StreamScope,
)


class AIPlugin(BasePlugin):
    """Plugin that provides AI-specific functionality."""

    def __init__(self):
        super().__init__(
            name="whiskey-ai",
            version="0.1.0",
            description="AI/LLM integration for Whiskey framework",
        )
        self._dependencies = []

    def register(self, container: Container) -> None:
        """Register AI-specific scopes with the container."""
        # Register custom scopes
        container.register_scope("session", SessionScope())
        container.register_scope("conversation", ConversationScope())
        container.register_scope("ai_context", AIContextScope())
        container.register_scope("batch", BatchScope())
        container.register_scope("stream", StreamScope())

    def initialize(self, app: Application) -> None:
        """Initialize the plugin with the application."""
        # Additional initialization can be added here
        pass