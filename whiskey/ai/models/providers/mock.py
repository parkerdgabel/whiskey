"""Mock provider implementation for testing."""

import asyncio
import time
import uuid
from typing import Any, AsyncIterator, Dict, List, Optional, Union

from whiskey.core.decorators import provide

from ..base import ChatCompletionModel, EmbeddingModel
from ..types import (
    ChatCompletion,
    ChatCompletionChunk,
    Choice,
    Delta,
    EmbeddingData,
    EmbeddingResponse,
    Message,
    StreamChoice,
    Usage,
)


@provide
class MockChatModel(ChatCompletionModel):
    """Mock chat completion model for testing."""
    
    def __init__(self, response_template: str = "Mock response: {prompt}"):
        self.response_template = response_template
        self.call_count = 0
    
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
        """Create a mock chat completion."""
        self.call_count += 1
        
        # Extract the last user message as prompt
        prompt = ""
        for msg in reversed(messages):
            if msg.role == "user":
                prompt = msg.content
                break
        
        if stream:
            return self._stream_response(prompt, model)
        else:
            return await self._complete_response(prompt, model, n)
    
    async def _complete_response(self, prompt: str, model: str, n: int) -> ChatCompletion:
        """Generate a complete response."""
        # Simulate some processing time
        await asyncio.sleep(0.1)
        
        response_text = self.response_template.format(prompt=prompt)
        
        # Calculate token counts (rough estimation)
        prompt_tokens = len(prompt.split())
        completion_tokens = len(response_text.split())
        
        choices = [
            Choice(
                index=i,
                message=Message(role="assistant", content=f"{response_text} (choice {i+1})"),
                finish_reason="stop"
            )
            for i in range(n)
        ]
        
        return ChatCompletion(
            id=f"mock-{uuid.uuid4()}",
            model=model,
            choices=choices,
            usage=Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens * n,
                total_tokens=prompt_tokens + (completion_tokens * n)
            )
        )
    
    async def _stream_response(self, prompt: str, model: str) -> AsyncIterator[ChatCompletionChunk]:
        """Stream a response word by word."""
        response_text = self.response_template.format(prompt=prompt)
        words = response_text.split()
        
        completion_id = f"mock-{uuid.uuid4()}"
        
        # First chunk with role
        yield ChatCompletionChunk(
            id=completion_id,
            model=model,
            choices=[StreamChoice(index=0, delta=Delta(role="assistant"))]
        )
        
        # Stream each word
        for i, word in enumerate(words):
            await asyncio.sleep(0.05)  # Simulate streaming delay
            
            # Add space before word (except first)
            content = f" {word}" if i > 0 else word
            
            yield ChatCompletionChunk(
                id=completion_id,
                model=model,
                choices=[StreamChoice(index=0, delta=Delta(content=content))]
            )
        
        # Final chunk with finish reason
        yield ChatCompletionChunk(
            id=completion_id,
            model=model,
            choices=[StreamChoice(index=0, delta=Delta(), finish_reason="stop")]
        )


@provide
class MockEmbeddingModel(EmbeddingModel):
    """Mock embedding model for testing."""
    
    def __init__(self, embedding_dim: int = 1536):
        self.embedding_dim = embedding_dim
        self.call_count = 0
    
    async def create(
        self,
        input: Union[str, List[str]],
        model: str,
        encoding_format: str = "float",
        user: Optional[str] = None,
        **kwargs: Any
    ) -> EmbeddingResponse:
        """Create mock embeddings."""
        self.call_count += 1
        
        # Ensure input is a list
        inputs = [input] if isinstance(input, str) else input
        
        # Simulate some processing time
        await asyncio.sleep(0.05 * len(inputs))
        
        # Generate mock embeddings
        data = []
        total_tokens = 0
        
        for i, text in enumerate(inputs):
            # Create a deterministic but varied embedding based on text
            embedding = [
                float(hash(f"{text}_{j}") % 1000) / 1000.0
                for j in range(self.embedding_dim)
            ]
            
            data.append(EmbeddingData(index=i, embedding=embedding))
            total_tokens += len(text.split())
        
        return EmbeddingResponse(
            model=model,
            data=data,
            usage=Usage(
                prompt_tokens=total_tokens,
                completion_tokens=0,
                total_tokens=total_tokens
            )
        )