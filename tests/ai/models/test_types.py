"""Tests for AI model types."""

import time
from typing import List

import pytest

from whiskey.ai.models.types import (
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


@pytest.mark.unit
class TestMessage:
    """Test Message type."""
    
    def test_basic_message(self):
        """Test creating a basic message."""
        msg = Message(role="user", content="Hello!")
        assert msg.role == "user"
        assert msg.content == "Hello!"
        assert msg.name is None
        assert msg.function_call is None
        assert msg.tool_calls is None
    
    def test_message_with_all_fields(self):
        """Test message with all optional fields."""
        msg = Message(
            role="assistant",
            content="Response",
            name="assistant-1",
            function_call={"name": "test", "arguments": "{}"},
            tool_calls=[{"id": "1", "type": "function", "function": {"name": "test"}}]
        )
        assert msg.name == "assistant-1"
        assert msg.function_call["name"] == "test"
        assert len(msg.tool_calls) == 1


@pytest.mark.unit
class TestUsage:
    """Test Usage type."""
    
    def test_usage_calculation(self):
        """Test token usage calculations."""
        usage = Usage(prompt_tokens=10, completion_tokens=20, total_tokens=30)
        assert usage.prompt_tokens == 10
        assert usage.completion_tokens == 20
        assert usage.total_tokens == 30


@pytest.mark.unit
class TestChatCompletion:
    """Test ChatCompletion type."""
    
    def test_basic_completion(self):
        """Test creating a basic completion."""
        completion = ChatCompletion(
            id="test-123",
            model="gpt-4",
            choices=[
                Choice(
                    index=0,
                    message=Message(role="assistant", content="Hello!"),
                    finish_reason="stop"
                )
            ]
        )
        
        assert completion.id == "test-123"
        assert completion.object == "chat.completion"
        assert completion.model == "gpt-4"
        assert len(completion.choices) == 1
        assert completion.choices[0].message.content == "Hello!"
    
    def test_completion_with_usage(self):
        """Test completion with usage information."""
        completion = ChatCompletion(
            id="test-123",
            model="gpt-4",
            choices=[],
            usage=Usage(prompt_tokens=5, completion_tokens=10, total_tokens=15)
        )
        
        assert completion.usage.total_tokens == 15
    
    def test_default_timestamp(self):
        """Test that created timestamp is set by default."""
        before = int(time.time())
        completion = ChatCompletion(id="test", model="gpt-4")
        after = int(time.time())
        
        assert before <= completion.created <= after


@pytest.mark.unit
class TestStreamingTypes:
    """Test streaming-related types."""
    
    def test_delta(self):
        """Test Delta type."""
        delta = Delta(content="Hello")
        assert delta.content == "Hello"
        assert delta.role is None
        
        delta_with_role = Delta(role="assistant")
        assert delta_with_role.role == "assistant"
        assert delta_with_role.content is None
    
    def test_stream_choice(self):
        """Test StreamChoice type."""
        choice = StreamChoice(
            index=0,
            delta=Delta(content="test"),
            finish_reason="stop"
        )
        assert choice.index == 0
        assert choice.delta.content == "test"
        assert choice.finish_reason == "stop"
    
    def test_chat_completion_chunk(self):
        """Test ChatCompletionChunk type."""
        chunk = ChatCompletionChunk(
            id="stream-123",
            model="gpt-4",
            choices=[
                StreamChoice(index=0, delta=Delta(content="Hello"))
            ]
        )
        
        assert chunk.id == "stream-123"
        assert chunk.object == "chat.completion.chunk"
        assert chunk.model == "gpt-4"
        assert len(chunk.choices) == 1
        assert chunk.choices[0].delta.content == "Hello"


@pytest.mark.unit
class TestEmbeddingTypes:
    """Test embedding-related types."""
    
    def test_embedding_data(self):
        """Test EmbeddingData type."""
        embedding = EmbeddingData(
            index=0,
            embedding=[0.1, 0.2, 0.3]
        )
        assert embedding.index == 0
        assert embedding.embedding == [0.1, 0.2, 0.3]
        assert embedding.object == "embedding"
    
    def test_embedding_response(self):
        """Test EmbeddingResponse type."""
        response = EmbeddingResponse(
            model="text-embedding-ada-002",
            data=[
                EmbeddingData(index=0, embedding=[0.1, 0.2]),
                EmbeddingData(index=1, embedding=[0.3, 0.4])
            ],
            usage=Usage(prompt_tokens=10, completion_tokens=0, total_tokens=10)
        )
        
        assert response.object == "list"
        assert response.model == "text-embedding-ada-002"
        assert len(response.data) == 2
        assert response.data[0].embedding == [0.1, 0.2]
        assert response.usage.prompt_tokens == 10