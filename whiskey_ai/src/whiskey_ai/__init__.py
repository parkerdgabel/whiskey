"""Whiskey AI extension - Build AI-powered applications with OpenAI-compatible APIs."""

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
    from whiskey import Whiskey


__all__ = [
    # Extension
    "ai_extension",
    # Types
    "ChatCompletion",
    "ChatCompletionChunk",
    "Choice",
    "Delta",
    "Embedding",
    "EmbeddingResponse",
    "Function",
    "FunctionCall",
    "LLMClient",
    "Message",
    "ResponseFormat",
    "StreamChoice",
    "Tool",
    "ToolCall",
    "Usage",
    # Managers
    "AgentManager",
    "ModelManager",
    "ToolManager",
    # Providers
    "MockLLMClient",
    "OpenAIClient",
    "AnthropicClient",
    # Agents
    "Agent",
    "LLMAgent",
    "ResearchAgent",
    "CodingAgent",
    "AnalysisAgent",
    "ConversationMemory",
    # Conversation
    "Conversation",
    "ConversationManager",
    "ChatSession",
    # Tools
    "ToolExecutor",
    "calculate",
    "web_search",
    "get_current_time",
]

# Register CLI commands if available
try:
    from whiskey_cli import cli_extension
    # CLI commands are automatically registered when ai_extension is used
    # after cli_extension in an app
except ImportError:
    # CLI extension not available
    pass
