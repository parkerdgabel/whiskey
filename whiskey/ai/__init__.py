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
from .prompts import (
    PromptRegistry,
    PromptTemplate,
    PromptVariable,
    Validator,
)
from .resources import AIResourceManager, TokenBucket, TokenLease
from .streaming import StreamProcessor

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
    # Prompts
    "PromptTemplate",
    "PromptVariable",
    "PromptRegistry",
    "Validator",
    # Streaming
    "StreamProcessor",
]