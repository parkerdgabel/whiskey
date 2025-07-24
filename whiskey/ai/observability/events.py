"""AI-specific events for observability."""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from whiskey.core.events import Event


@dataclass
class AIRequestStarted(Event):
    """Event emitted when an AI request starts."""
    
    context_id: str = ""
    model: str = ""
    provider: str = ""
    prompt_tokens: int = 0
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None


@dataclass
class AIRequestCompleted(Event):
    """Event emitted when an AI request completes successfully."""
    
    context_id: str = ""
    model: str = ""
    provider: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    duration_ms: float = 0.0
    cost: float = 0.0
    finish_reason: Optional[str] = None


@dataclass
class AIRequestFailed(Event):
    """Event emitted when an AI request fails."""
    
    context_id: str = ""
    model: str = ""
    provider: str = ""
    error_type: str = ""
    error_message: str = ""
    duration_ms: float = 0.0
    retryable: bool = False


@dataclass
class AIStreamChunkReceived(Event):
    """Event emitted when a streaming chunk is received."""
    
    context_id: str = ""
    model: str = ""
    provider: str = ""
    chunk_index: int = 0
    content: Optional[str] = None
    tokens: Optional[int] = None


@dataclass
class AIStreamCompleted(Event):
    """Event emitted when a streaming response completes."""
    
    context_id: str = ""
    model: str = ""
    provider: str = ""
    total_chunks: int = 0
    total_tokens: int = 0
    duration_ms: float = 0.0
    cost: float = 0.0
    finish_reason: Optional[str] = None