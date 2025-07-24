"""AI-specific features for Whiskey framework."""

from .context import AIContext
from .models import (
    ChatCompletion,
    ChatCompletionChunk,
    ChatCompletionModel,
    Choice,
    CompletionModel,
    Delta,
    EmbeddingData,
    EmbeddingModel,
    EmbeddingResponse,
    Message,
    StreamChoice,
    Usage,
)
from .models.providers import MockChatModel, MockEmbeddingModel
from .observability import (
    AIMetricsCollector,
    AIRequestCompleted,
    AIRequestFailed,
    AIRequestStarted,
    AIStreamChunkReceived,
    AIStreamCompleted,
)
from .resources import AIResourceManager, TokenBucket, TokenLease

__all__ = [
    # Context
    "AIContext",
    # Models - Protocols
    "ChatCompletionModel",
    "CompletionModel", 
    "EmbeddingModel",
    # Models - Types
    "ChatCompletion",
    "ChatCompletionChunk",
    "Choice",
    "Delta",
    "EmbeddingData",
    "EmbeddingResponse",
    "Message",
    "StreamChoice",
    "Usage",
    # Providers
    "MockChatModel",
    "MockEmbeddingModel",
    # Resources
    "AIResourceManager",
    "TokenBucket",
    "TokenLease",
    # Observability
    "AIRequestStarted",
    "AIRequestCompleted",
    "AIRequestFailed",
    "AIStreamChunkReceived",
    "AIStreamCompleted",
    "AIMetricsCollector",
]