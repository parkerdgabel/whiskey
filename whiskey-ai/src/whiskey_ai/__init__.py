"""Whiskey AI plugin - provides AI-specific scopes and functionality."""

from .plugin import AIPlugin
from .scopes import (
    AIContextScope,
    BatchScope,
    ConversationScope,
    SessionScope,
    StreamScope,
)

__all__ = [
    "AIPlugin",
    "AIContextScope",
    "BatchScope",
    "ConversationScope",
    "SessionScope",
    "StreamScope",
]