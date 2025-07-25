"""Whiskey AI extension - Build AI-powered applications with OpenAI-compatible APIs."""

from typing import TYPE_CHECKING

from .extension import (
    # Extension
    ai_extension,
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
    ResponseFormat,
    StreamChoice,
    Tool,
    ToolCall,
    Usage,
    # Managers
    AgentManager,
    ModelManager,
    ToolManager,
)
from .providers import (
    MockLLMClient,
    OpenAIClient,
    AnthropicClient,
)
from .agents import (
    Agent,
    LLMAgent,
    ResearchAgent,
    CodingAgent,
    AnalysisAgent,
    ConversationMemory,
)
from .conversation import (
    Conversation,
    ConversationManager,
    ChatSession,
)
from .tools import (
    ToolExecutor,
    calculate,
    web_search,
    get_current_time,
)

if TYPE_CHECKING:
    from whiskey import Application


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