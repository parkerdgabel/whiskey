"""AI plugin for Whiskey framework."""

from whiskey import BasePlugin, Container, Application


class AIPlugin(BasePlugin):
    """Plugin providing AI/LLM integration features."""
    
    def __init__(self):
        super().__init__(
            name="ai",
            version="0.1.0",
            description="AI/LLM integration features including context management, "
                       "model protocols, prompt templates, and resource management",
        )
    
    def register(self, container: Container) -> None:
        """Register AI services with the container."""
        # Import here to avoid circular imports
        from .context import AIContext, ConversationScope
        from .models.providers import MockChatModel, MockEmbeddingModel
        from .observability import AIMetricsCollector
        from .prompts import PromptRegistry
        from .resources import AIResourceManager
        
        # Register core AI services
        container.register_scoped(AIContext)
        container.register_singleton(ConversationScope)
        container.register_singleton(PromptRegistry)
        container.register_singleton(AIResourceManager)
        container.register_singleton(AIMetricsCollector)
        
        # Register mock providers for testing
        container.register_singleton(MockChatModel)
        container.register_singleton(MockEmbeddingModel)
    
    def initialize(self, app: Application) -> None:
        """Initialize AI plugin with the application."""
        # Set up AI-specific event handlers
        from .observability import (
            AIRequestStarted,
            AIRequestCompleted,
            AIRequestFailed,
            AIMetricsCollector,
        )
        
        @app.on(AIRequestStarted)
        async def on_request_started(
            event: AIRequestStarted,
            metrics: AIMetricsCollector,
        ) -> None:
            await metrics.record_request_started(event)
        
        @app.on(AIRequestCompleted)
        async def on_request_completed(
            event: AIRequestCompleted,
            metrics: AIMetricsCollector,
        ) -> None:
            await metrics.record_request_completed(event)
        
        @app.on(AIRequestFailed)
        async def on_request_failed(
            event: AIRequestFailed,
            metrics: AIMetricsCollector,
        ) -> None:
            await metrics.record_request_failed(event)