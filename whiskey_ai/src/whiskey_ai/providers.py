"""LLM provider implementations with OpenAI-compatible interfaces."""

from __future__ import annotations

import asyncio
import json
import uuid
<<<<<<< HEAD
from collections.abc import AsyncIterator
from typing import Any, Dict, List, Optional, Union

from .extension import (
    ChatCompletion,
    ChatCompletionChunk,
    Choice,
    Delta,
    Embedding,
    EmbeddingResponse,
    Message,
    StreamChoice,
    Usage,
=======
from typing import Any, AsyncIterator, Dict, List, Optional, Union

from .extension import (
    ChatCompletion, ChatCompletionChunk, Choice, Delta, Embedding,
    EmbeddingResponse, LLMClient, Message, StreamChoice, Usage
>>>>>>> origin/main
)


class MockLLMClient:
    """Mock LLM client for testing."""
<<<<<<< HEAD

=======
    
>>>>>>> origin/main
    def __init__(self, **kwargs):
        self.config = kwargs
        self.chat = MockChatCompletions()
        self.embeddings = MockEmbeddings()


class MockChatCompletions:
    """Mock chat completions for testing."""
<<<<<<< HEAD

=======
    
>>>>>>> origin/main
    async def create(
        self,
        *,
        model: str,
        messages: List[Dict[str, Any]],
        stream: Optional[bool] = False,
<<<<<<< HEAD
        **kwargs,
=======
        **kwargs
>>>>>>> origin/main
    ) -> Union[ChatCompletion, AsyncIterator[ChatCompletionChunk]]:
        """Create a mock chat completion."""
        if stream:
            return self._stream_response(model, messages, **kwargs)
<<<<<<< HEAD

        # Generate mock response
        last_message = messages[-1]["content"] if messages else ""
        response_content = f"Mock response to: {last_message[:50]}..."

=======
        
        # Generate mock response
        last_message = messages[-1]["content"] if messages else ""
        response_content = f"Mock response to: {last_message[:50]}..."
        
>>>>>>> origin/main
        # Handle tool calls if tools are provided
        tools = kwargs.get("tools", [])
        tool_calls = None
        finish_reason = "stop"
<<<<<<< HEAD

        if tools and "search" in last_message.lower():
            # Mock a tool call
            tool_calls = [
                {
                    "id": f"call_{uuid.uuid4().hex[:8]}",
                    "type": "function",
                    "function": {
                        "name": "web_search",
                        "arguments": json.dumps({"query": "test query"}),
                    },
                }
            ]
            finish_reason = "tool_calls"
            response_content = None

        return ChatCompletion(
            id=f"chatcmpl-{uuid.uuid4().hex[:8]}",
            model=model,
            choices=[
                Choice(
                    index=0,
                    message=Message(
                        role="assistant", content=response_content, tool_calls=tool_calls
                    ),
                    finish_reason=finish_reason,
                )
            ],
            usage=Usage(
                prompt_tokens=len(str(messages)) // 4,  # Rough estimate
                completion_tokens=len(response_content) // 4 if response_content else 10,
                total_tokens=len(str(messages)) // 4
                + (len(response_content) // 4 if response_content else 10),
            ),
        )

    async def _stream_response(
        self, model: str, messages: List[Dict[str, Any]], **kwargs
    ) -> AsyncIterator[ChatCompletionChunk]:
        """Stream a mock response."""
        last_message = messages[-1]["content"] if messages else ""
        response_parts = ["Mock", " streaming", " response", " to:", f" {last_message[:30]}..."]

        chunk_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"

=======
        
        if tools and "search" in last_message.lower():
            # Mock a tool call
            tool_calls = [{
                "id": f"call_{uuid.uuid4().hex[:8]}",
                "type": "function",
                "function": {
                    "name": "web_search",
                    "arguments": json.dumps({"query": "test query"})
                }
            }]
            finish_reason = "tool_calls"
            response_content = None
        
        return ChatCompletion(
            id=f"chatcmpl-{uuid.uuid4().hex[:8]}",
            model=model,
            choices=[Choice(
                index=0,
                message=Message(
                    role="assistant",
                    content=response_content,
                    tool_calls=tool_calls
                ),
                finish_reason=finish_reason
            )],
            usage=Usage(
                prompt_tokens=len(str(messages)) // 4,  # Rough estimate
                completion_tokens=len(response_content) // 4 if response_content else 10,
                total_tokens=len(str(messages)) // 4 + (len(response_content) // 4 if response_content else 10)
            )
        )
    
    async def _stream_response(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        **kwargs
    ) -> AsyncIterator[ChatCompletionChunk]:
        """Stream a mock response."""
        last_message = messages[-1]["content"] if messages else ""
        response_parts = [
            "Mock", " streaming", " response", " to:", f" {last_message[:30]}..."
        ]
        
        chunk_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
        
>>>>>>> origin/main
        for i, part in enumerate(response_parts):
            yield ChatCompletionChunk(
                id=chunk_id,
                model=model,
<<<<<<< HEAD
                choices=[
                    StreamChoice(
                        index=0,
                        delta=Delta(content=part, role="assistant" if i == 0 else None),
                        finish_reason=None,
                    )
                ],
            )
            await asyncio.sleep(0.1)  # Simulate streaming delay

=======
                choices=[StreamChoice(
                    index=0,
                    delta=Delta(
                        content=part,
                        role="assistant" if i == 0 else None
                    ),
                    finish_reason=None
                )]
            )
            await asyncio.sleep(0.1)  # Simulate streaming delay
        
>>>>>>> origin/main
        # Final chunk
        yield ChatCompletionChunk(
            id=chunk_id,
            model=model,
<<<<<<< HEAD
            choices=[StreamChoice(index=0, delta=Delta(), finish_reason="stop")],
=======
            choices=[StreamChoice(
                index=0,
                delta=Delta(),
                finish_reason="stop"
            )]
>>>>>>> origin/main
        )


class MockEmbeddings:
    """Mock embeddings for testing."""
<<<<<<< HEAD

    async def create(
        self, *, model: str, input: Union[str, List[str]], **kwargs
=======
    
    async def create(
        self,
        *,
        model: str,
        input: Union[str, List[str]],
        **kwargs
>>>>>>> origin/main
    ) -> EmbeddingResponse:
        """Create mock embeddings."""
        # Ensure input is a list
        inputs = [input] if isinstance(input, str) else input
<<<<<<< HEAD

=======
        
>>>>>>> origin/main
        # Generate mock embeddings (768 dimensions like ada-002)
        embeddings = []
        for i, text in enumerate(inputs):
            # Simple mock: use text length to vary embeddings
            base_value = len(text) / 100.0
            embedding = [base_value + (i * 0.001) + (j * 0.0001) for j in range(768)]
            embeddings.append(Embedding(index=i, embedding=embedding))
<<<<<<< HEAD

=======
        
>>>>>>> origin/main
        return EmbeddingResponse(
            data=embeddings,
            model=model,
            usage=Usage(
                prompt_tokens=sum(len(text) // 4 for text in inputs),
                completion_tokens=0,
<<<<<<< HEAD
                total_tokens=sum(len(text) // 4 for text in inputs),
            ),
=======
                total_tokens=sum(len(text) // 4 for text in inputs)
            )
>>>>>>> origin/main
        )


# OpenAI provider (requires openai package)
try:
    from openai import AsyncOpenAI
<<<<<<< HEAD

    class OpenAIClient:
        """OpenAI LLM client implementation."""

        def __init__(self, api_key: str, **kwargs):
            self.client = AsyncOpenAI(api_key=api_key, **kwargs)

=======
    
    class OpenAIClient:
        """OpenAI LLM client implementation."""
        
        def __init__(self, api_key: str, **kwargs):
            self.client = AsyncOpenAI(api_key=api_key, **kwargs)
        
>>>>>>> origin/main
        @property
        def chat(self):
            """Get chat completions interface."""
            return self.client.chat.completions
<<<<<<< HEAD

=======
        
>>>>>>> origin/main
        @property
        def embeddings(self):
            """Get embeddings interface."""
            return self.client.embeddings

except ImportError:
    # OpenAI package not installed
    class OpenAIClient:
        """Placeholder when OpenAI package is not installed."""
<<<<<<< HEAD

        def __init__(self, *args, **kwargs):
            raise ImportError(
                "OpenAI client requires 'openai' package. Install with: pip install openai"
=======
        
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "OpenAI client requires 'openai' package. "
                "Install with: pip install openai"
>>>>>>> origin/main
            )


# Anthropic provider adapter
try:
    from anthropic import AsyncAnthropic
<<<<<<< HEAD

    class AnthropicClient:
        """Anthropic client with OpenAI-compatible interface."""

=======
    
    class AnthropicClient:
        """Anthropic client with OpenAI-compatible interface."""
        
>>>>>>> origin/main
        def __init__(self, api_key: str, **kwargs):
            self.client = AsyncAnthropic(api_key=api_key, **kwargs)
            self.chat = AnthropicChatAdapter(self.client)
            self.embeddings = AnthropicEmbeddingsAdapter()
<<<<<<< HEAD

    class AnthropicChatAdapter:
        """Adapts Anthropic API to OpenAI interface."""

        def __init__(self, client: AsyncAnthropic):
            self.client = client

=======
    
    
    class AnthropicChatAdapter:
        """Adapts Anthropic API to OpenAI interface."""
        
        def __init__(self, client: AsyncAnthropic):
            self.client = client
        
>>>>>>> origin/main
        async def create(
            self,
            *,
            model: str,
            messages: List[Dict[str, Any]],
            stream: Optional[bool] = False,
<<<<<<< HEAD
            **kwargs,
=======
            **kwargs
>>>>>>> origin/main
        ) -> Union[ChatCompletion, AsyncIterator[ChatCompletionChunk]]:
            """Create chat completion using Anthropic API."""
            # Convert messages to Anthropic format
            system_message = None
            anthropic_messages = []
<<<<<<< HEAD

=======
            
>>>>>>> origin/main
            for msg in messages:
                if msg["role"] == "system":
                    system_message = msg["content"]
                elif msg["role"] in ["user", "assistant"]:
<<<<<<< HEAD
                    anthropic_messages.append({"role": msg["role"], "content": msg["content"]})

=======
                    anthropic_messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })
            
>>>>>>> origin/main
            # Map model names
            anthropic_model = model
            if model.startswith("gpt"):
                # Map OpenAI model to Claude
                anthropic_model = "claude-3-opus-20240229"
<<<<<<< HEAD

=======
            
>>>>>>> origin/main
            # Create completion
            response = await self.client.messages.create(
                model=anthropic_model,
                messages=anthropic_messages,
                system=system_message,
                max_tokens=kwargs.get("max_tokens", 1024),
                temperature=kwargs.get("temperature", 1.0),
<<<<<<< HEAD
                stream=stream,
            )

            if stream:
                return self._stream_adapter(response, model)

=======
                stream=stream
            )
            
            if stream:
                return self._stream_adapter(response, model)
            
>>>>>>> origin/main
            # Convert to OpenAI format
            return ChatCompletion(
                id=response.id,
                model=model,
<<<<<<< HEAD
                choices=[
                    Choice(
                        index=0,
                        message=Message(role="assistant", content=response.content[0].text),
                        finish_reason=self._map_stop_reason(response.stop_reason),
                    )
                ],
                usage=Usage(
                    prompt_tokens=response.usage.input_tokens,
                    completion_tokens=response.usage.output_tokens,
                    total_tokens=response.usage.input_tokens + response.usage.output_tokens,
                ),
            )

=======
                choices=[Choice(
                    index=0,
                    message=Message(
                        role="assistant",
                        content=response.content[0].text
                    ),
                    finish_reason=self._map_stop_reason(response.stop_reason)
                )],
                usage=Usage(
                    prompt_tokens=response.usage.input_tokens,
                    completion_tokens=response.usage.output_tokens,
                    total_tokens=response.usage.input_tokens + response.usage.output_tokens
                )
            )
        
>>>>>>> origin/main
        def _map_stop_reason(self, reason: Optional[str]) -> str:
            """Map Anthropic stop reason to OpenAI."""
            if reason == "end_turn":
                return "stop"
            elif reason == "max_tokens":
                return "length"
            return reason or "stop"
<<<<<<< HEAD

        async def _stream_adapter(
            self, stream: AsyncIterator, model: str
        ) -> AsyncIterator[ChatCompletionChunk]:
            """Adapt Anthropic stream to OpenAI format."""
            chunk_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"

=======
        
        async def _stream_adapter(
            self,
            stream: AsyncIterator,
            model: str
        ) -> AsyncIterator[ChatCompletionChunk]:
            """Adapt Anthropic stream to OpenAI format."""
            chunk_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
            
>>>>>>> origin/main
            async for event in stream:
                if event.type == "content_block_delta":
                    yield ChatCompletionChunk(
                        id=chunk_id,
                        model=model,
<<<<<<< HEAD
                        choices=[
                            StreamChoice(
                                index=0, delta=Delta(content=event.delta.text), finish_reason=None
                            )
                        ],
=======
                        choices=[StreamChoice(
                            index=0,
                            delta=Delta(content=event.delta.text),
                            finish_reason=None
                        )]
>>>>>>> origin/main
                    )
                elif event.type == "message_stop":
                    yield ChatCompletionChunk(
                        id=chunk_id,
                        model=model,
<<<<<<< HEAD
                        choices=[StreamChoice(index=0, delta=Delta(), finish_reason="stop")],
                    )

    class AnthropicEmbeddingsAdapter:
        """Anthropic doesn't provide embeddings - use a different service."""

        async def create(self, **kwargs) -> EmbeddingResponse:
            raise NotImplementedError(
                "Anthropic doesn't provide embeddings. Use OpenAI or another embedding service."
=======
                        choices=[StreamChoice(
                            index=0,
                            delta=Delta(),
                            finish_reason="stop"
                        )]
                    )
    
    
    class AnthropicEmbeddingsAdapter:
        """Anthropic doesn't provide embeddings - use a different service."""
        
        async def create(self, **kwargs) -> EmbeddingResponse:
            raise NotImplementedError(
                "Anthropic doesn't provide embeddings. "
                "Use OpenAI or another embedding service."
>>>>>>> origin/main
            )

except ImportError:
    # Anthropic package not installed
    class AnthropicClient:
        """Placeholder when Anthropic package is not installed."""
<<<<<<< HEAD

        def __init__(self, *args, **kwargs):
            raise ImportError(
                "Anthropic client requires 'anthropic' package. Install with: pip install anthropic"
            )
=======
        
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "Anthropic client requires 'anthropic' package. "
                "Install with: pip install anthropic"
            )
>>>>>>> origin/main
