"""OpenAI-compatible type definitions for AI models."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Union


@dataclass
class Message:
    """Chat message compatible with OpenAI format."""
    
    role: Literal["system", "user", "assistant", "function", "tool"]
    content: str
    name: Optional[str] = None
    function_call: Optional[Dict[str, Any]] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None


@dataclass
class Usage:
    """Token usage information."""
    
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass
class Choice:
    """Single choice in a completion response."""
    
    index: int
    message: Message
    finish_reason: Optional[str] = None
    logprobs: Optional[Any] = None


@dataclass
class ChatCompletion:
    """OpenAI-compatible chat completion response."""
    
    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int = field(default_factory=lambda: int(time.time()))
    model: str = ""
    choices: List[Choice] = field(default_factory=list)
    usage: Optional[Usage] = None
    system_fingerprint: Optional[str] = None


@dataclass
class Delta:
    """Delta content for streaming responses."""
    
    content: Optional[str] = None
    role: Optional[str] = None
    function_call: Optional[Dict[str, Any]] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None


@dataclass
class StreamChoice:
    """Single choice in a streaming response."""
    
    index: int
    delta: Delta
    finish_reason: Optional[str] = None
    logprobs: Optional[Any] = None


@dataclass
class ChatCompletionChunk:
    """OpenAI-compatible streaming chunk."""
    
    id: str
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    created: int = field(default_factory=lambda: int(time.time()))
    model: str = ""
    choices: List[StreamChoice] = field(default_factory=list)
    system_fingerprint: Optional[str] = None


@dataclass
class EmbeddingData:
    """Single embedding vector."""
    
    index: int
    embedding: List[float]
    object: Literal["embedding"] = "embedding"


@dataclass
class EmbeddingResponse:
    """OpenAI-compatible embedding response."""
    
    object: Literal["list"] = "list"
    data: List[EmbeddingData] = field(default_factory=list)
    model: str = ""
    usage: Optional[Usage] = None


import time  # Import at the end to avoid circular imports