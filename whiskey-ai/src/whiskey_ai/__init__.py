"""Whiskey AI extension - provides AI-specific scopes and functionality."""

from typing import TYPE_CHECKING

from .scopes import (
    AIContextScope,
    BatchScope,
    ConversationScope,
    SessionScope,
    StreamScope,
)

if TYPE_CHECKING:
    from whiskey import Application


def ai_extension(app: "Application") -> None:
    """AI extension that adds AI-specific scopes to Whiskey.
    
    Usage:
        from whiskey import Application
        from whiskey_ai import ai_extension
        
        app = Application()
        app.extend(ai_extension)
        
        # Or during construction:
        app = Application().extend(ai_extension)
    """
    # Register custom AI scopes
    app.container.register_scope("session", SessionScope())
    app.container.register_scope("conversation", ConversationScope())
    app.container.register_scope("ai_context", AIContextScope())
    app.container.register_scope("batch", BatchScope())
    app.container.register_scope("stream", StreamScope())


# For backwards compatibility
extend = ai_extension


__all__ = [
    "ai_extension",
    "extend",
    "AIContextScope",
    "BatchScope",
    "ConversationScope",
    "SessionScope",
    "StreamScope",
]