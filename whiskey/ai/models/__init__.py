"""AI model abstractions for Whiskey framework."""

from .base import ChatCompletionModel, EmbeddingModel, CompletionModel
from .types import (
    ChatCompletion,
    ChatCompletionChunk,
    Choice,
    Delta,
    EmbeddingData,
    EmbeddingResponse,
    Message,
    StreamChoice,
    Usage,
)

__all__ = [
    # Base protocols
    "ChatCompletionModel",
    "CompletionModel",
    "EmbeddingModel",
    # Types
    "ChatCompletion",
    "ChatCompletionChunk",
    "Choice",
    "Delta",
    "EmbeddingData",
    "EmbeddingResponse",
    "Message",
    "StreamChoice",
    "Usage",
]