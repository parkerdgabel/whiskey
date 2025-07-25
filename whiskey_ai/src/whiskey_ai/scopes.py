"""AI-specific scopes for Whiskey framework."""

from whiskey.core.scopes import ContextVarScope


class SessionScope(ContextVarScope):
    """Scope for user session lifecycle."""

    def __init__(self):
        super().__init__("session")


class ConversationScope(ContextVarScope):
    """Scope for AI conversation lifecycle."""

    def __init__(self):
        super().__init__("conversation")


class AIContextScope(ContextVarScope):
    """Scope for AI context (prompt + response) lifecycle."""

    def __init__(self):
        super().__init__("ai_context")


class BatchScope(ContextVarScope):
    """Scope for batch processing lifecycle."""

    def __init__(self):
        super().__init__("batch")


class StreamScope(ContextVarScope):
    """Scope for streaming response lifecycle."""

    def __init__(self):
        super().__init__("stream")