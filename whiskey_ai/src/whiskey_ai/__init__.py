"""Whiskey AI extension - Build AI-powered applications with OpenAI-compatible APIs."""

import contextlib
from typing import TYPE_CHECKING

from .agents import (
    Agent,
    AnalysisAgent,
    CodingAgent,
    ConversationMemory,
    LLMAgent,
    ResearchAgent,
)
from .conversation import (
    ChatSession,
    Conversation,
    ConversationManager,
)
from .extension import (
    # Managers
    AgentManager,
    # OpenAI-compatible types
    ChatCompletion,
    ChatCompletionChunk,
    Choice,
    Delta,
    Embedding,
    EmbeddingResponse,
    Function,
    FunctionCall,
    LLMClient,
    Message,
    ModelManager,
    ResponseFormat,
    StreamChoice,
    Tool,
    ToolCall,
    ToolManager,
    Usage,
    # Extension
    ai_extension,
)
from .providers import (
    AnthropicClient,
    MockLLMClient,
    OpenAIClient,
)
from .tools import (
    ToolExecutor,
    calculate,
    get_current_time,
    web_search,
)

if TYPE_CHECKING:
    from whiskey import Whiskey  # noqa: F401


__all__ = [
    # Agents
    "Agent",
    # Managers
    "AgentManager",
    "AnalysisAgent",
    "AnthropicClient",
    # Types
    "ChatCompletion",
    "ChatCompletionChunk",
    "ChatSession",
    "Choice",
    "CodingAgent",
    # Conversation
    "Conversation",
    "ConversationManager",
    "ConversationMemory",
    "Delta",
    "Embedding",
    "EmbeddingResponse",
    "Function",
    "FunctionCall",
    "LLMAgent",
    "LLMClient",
    "Message",
    # Providers
    "MockLLMClient",
    "ModelManager",
    "OpenAIClient",
    "ResearchAgent",
    "ResponseFormat",
    "StreamChoice",
    "Tool",
    "ToolCall",
    # Tools
    "ToolExecutor",
    "ToolManager",
    "Usage",
    # Extension
    "ai_extension",
    "calculate",
    "get_current_time",
    "web_search",
]

# Register CLI commands if available
with contextlib.suppress(ImportError):
    import whiskey_cli  # noqa: F401
    # CLI commands are automatically registered when ai_extension is used
    # after cli_extension in an app
