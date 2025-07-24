"""AI context management implementation."""

from __future__ import annotations

import contextvars
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from loguru import logger


@dataclass
class AIContext:
    """
    Context for AI operations, tracking metadata and state.
    
    This context is automatically injected and provides:
    - Unique request/conversation ID
    - Token usage tracking
    - Cost tracking
    - Timing information
    - Custom metadata
    """

    id: UUID = field(default_factory=uuid4)
    conversation_id: UUID | None = None
    created_at: datetime = field(default_factory=datetime.now)
    
    # Token tracking
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    
    # Cost tracking
    prompt_cost: float = 0.0
    completion_cost: float = 0.0
    total_cost: float = 0.0
    
    # Model information
    model: str | None = None
    provider: str | None = None
    
    # Custom metadata
    metadata: dict[str, Any] = field(default_factory=dict)
    
    # Message history (for conversations)
    messages: list[dict[str, Any]] = field(default_factory=list)
    
    # Parent context (for nested operations)
    parent: AIContext | None = None

    def add_usage(
        self,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        prompt_cost: float = 0.0,
        completion_cost: float = 0.0,
    ) -> None:
        """Add token usage and cost to the context."""
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens
        self.total_tokens = self.prompt_tokens + self.completion_tokens
        
        self.prompt_cost += prompt_cost
        self.completion_cost += completion_cost
        self.total_cost = self.prompt_cost + self.completion_cost
        
        logger.debug(
            f"Context {self.id}: Added {prompt_tokens} prompt tokens, "
            f"{completion_tokens} completion tokens, ${self.total_cost:.4f} total cost"
        )

    def add_message(self, role: str, content: str, **kwargs: Any) -> None:
        """Add a message to the conversation history."""
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now(),
            **kwargs,
        }
        self.messages.append(message)

    def create_child(self) -> AIContext:
        """Create a child context for nested operations."""
        return AIContext(
            conversation_id=self.conversation_id or self.id,
            model=self.model,
            provider=self.provider,
            parent=self,
        )

    def get_conversation_history(self, max_messages: int | None = None) -> list[dict[str, Any]]:
        """Get conversation history, optionally limited to recent messages."""
        if max_messages is None:
            return self.messages.copy()
        return self.messages[-max_messages:].copy()

    def to_dict(self) -> dict[str, Any]:
        """Convert context to dictionary for serialization."""
        return {
            "id": str(self.id),
            "conversation_id": str(self.conversation_id) if self.conversation_id else None,
            "created_at": self.created_at.isoformat(),
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "prompt_cost": self.prompt_cost,
            "completion_cost": self.completion_cost,
            "total_cost": self.total_cost,
            "model": self.model,
            "provider": self.provider,
            "metadata": self.metadata,
            "message_count": len(self.messages),
        }


# Context variable for current AI context
_current_context: contextvars.ContextVar[AIContext | None] = contextvars.ContextVar(
    "whiskey_ai_context", default=None
)


def get_current_context() -> AIContext | None:
    """Get the current AI context."""
    return _current_context.get()


def set_current_context(context: AIContext) -> contextvars.Token:
    """Set the current AI context."""
    return _current_context.set(context)


class AIContextManager:
    """Context manager for AI operations."""

    def __init__(
        self,
        conversation_id: UUID | None = None,
        model: str | None = None,
        provider: str | None = None,
        **metadata: Any,
    ):
        self.context = AIContext(
            conversation_id=conversation_id,
            model=model,
            provider=provider,
            metadata=metadata,
        )
        self._token: contextvars.Token | None = None

    async def __aenter__(self) -> AIContext:
        """Enter the context."""
        self._token = set_current_context(self.context)
        logger.debug(f"Entered AI context {self.context.id}")
        return self.context

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit the context."""
        if self._token:
            _current_context.reset(self._token)
        
        # Log final stats
        logger.info(
            f"AI context {self.context.id} completed: "
            f"{self.context.total_tokens} tokens, ${self.context.total_cost:.4f}"
        )

    def __enter__(self) -> AIContext:
        """Sync enter."""
        self._token = set_current_context(self.context)
        logger.debug(f"Entered AI context {self.context.id}")
        return self.context

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Sync exit."""
        if self._token:
            _current_context.reset(self._token)
        
        # Log final stats
        logger.info(
            f"AI context {self.context.id} completed: "
            f"{self.context.total_tokens} tokens, ${self.context.total_cost:.4f}"
        )