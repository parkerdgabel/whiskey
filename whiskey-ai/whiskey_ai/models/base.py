"""Base protocols for AI models following OpenAI API patterns."""

from typing import Any, AsyncIterator, Dict, List, Optional, Protocol, Union, runtime_checkable

from .types import ChatCompletion, ChatCompletionChunk, EmbeddingResponse, Message


@runtime_checkable
class ChatCompletionModel(Protocol):
    """Protocol for chat completion models compatible with OpenAI API."""
    
    async def create(
        self,
        messages: List[Message],
        model: str,
        temperature: float = 1.0,
        top_p: float = 1.0,
        n: int = 1,
        stream: bool = False,
        stop: Optional[Union[str, List[str]]] = None,
        max_tokens: Optional[int] = None,
        presence_penalty: float = 0.0,
        frequency_penalty: float = 0.0,
        logit_bias: Optional[Dict[str, float]] = None,
        user: Optional[str] = None,
        **kwargs: Any
    ) -> Union[ChatCompletion, AsyncIterator[ChatCompletionChunk]]:
        """Create a chat completion.
        
        Args:
            messages: List of messages in the conversation
            model: Model identifier (e.g., "gpt-4")
            temperature: Sampling temperature (0-2)
            top_p: Nucleus sampling parameter
            n: Number of completions to generate
            stream: Whether to stream the response
            stop: Stop sequences
            max_tokens: Maximum tokens to generate
            presence_penalty: Presence penalty (-2 to 2)
            frequency_penalty: Frequency penalty (-2 to 2)
            logit_bias: Token bias dictionary
            user: User identifier for tracking
            **kwargs: Additional provider-specific parameters
            
        Returns:
            ChatCompletion if stream=False, AsyncIterator[ChatCompletionChunk] if stream=True
        """
        ...


@runtime_checkable
class CompletionModel(Protocol):
    """Protocol for text completion models (legacy format)."""
    
    async def create(
        self,
        prompt: Union[str, List[str]],
        model: str,
        temperature: float = 1.0,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        **kwargs: Any
    ) -> Union[Dict[str, Any], AsyncIterator[Dict[str, Any]]]:
        """Create a text completion.
        
        Args:
            prompt: Text prompt(s) to complete
            model: Model identifier
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            stream: Whether to stream the response
            **kwargs: Additional provider-specific parameters
            
        Returns:
            Completion response dict or async iterator of response chunks
        """
        ...


@runtime_checkable
class EmbeddingModel(Protocol):
    """Protocol for embedding models compatible with OpenAI API."""
    
    async def create(
        self,
        input: Union[str, List[str]],
        model: str,
        encoding_format: str = "float",
        user: Optional[str] = None,
        **kwargs: Any
    ) -> EmbeddingResponse:
        """Create embeddings for the input text(s).
        
        Args:
            input: Text or list of texts to embed
            model: Model identifier (e.g., "text-embedding-ada-002")
            encoding_format: Format of the embeddings ("float" or "base64")
            user: User identifier for tracking
            **kwargs: Additional provider-specific parameters
            
        Returns:
            EmbeddingResponse containing the embeddings
        """
        ...