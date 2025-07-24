"""Tests for mock AI model provider."""

import pytest

from whiskey import Container
from whiskey.ai.models import ChatCompletion, ChatCompletionChunk, EmbeddingResponse, Message
from whiskey.ai.models.providers import MockChatModel, MockEmbeddingModel


@pytest.mark.unit
class TestMockChatModel:
    """Test the mock chat model implementation."""
    
    @pytest.mark.asyncio
    async def test_create_completion(self):
        """Test creating a basic completion."""
        model = MockChatModel()
        messages = [
            Message(role="system", content="You are a helpful assistant."),
            Message(role="user", content="Hello, world!")
        ]
        
        response = await model.create(
            messages=messages,
            model="mock-model",
            temperature=0.7
        )
        
        assert isinstance(response, ChatCompletion)
        assert response.model == "mock-model"
        assert len(response.choices) == 1
        assert response.choices[0].message.role == "assistant"
        assert "Hello, world!" in response.choices[0].message.content
        assert response.usage.prompt_tokens > 0
        assert response.usage.completion_tokens > 0
    
    @pytest.mark.asyncio
    async def test_create_multiple_choices(self):
        """Test creating completion with multiple choices."""
        model = MockChatModel()
        messages = [Message(role="user", content="Test prompt")]
        
        response = await model.create(
            messages=messages,
            model="mock-model",
            n=3
        )
        
        assert len(response.choices) == 3
        for i, choice in enumerate(response.choices):
            assert choice.index == i
            assert f"choice {i+1}" in choice.message.content
    
    @pytest.mark.asyncio
    async def test_streaming_response(self):
        """Test streaming response."""
        model = MockChatModel(response_template="Word1 Word2 Word3")
        messages = [Message(role="user", content="Test")]
        
        stream = await model.create(
            messages=messages,
            model="mock-model",
            stream=True
        )
        
        chunks = []
        async for chunk in stream:
            assert isinstance(chunk, ChatCompletionChunk)
            chunks.append(chunk)
        
        # First chunk should have role
        assert chunks[0].choices[0].delta.role == "assistant"
        
        # Middle chunks should have content
        content_chunks = [c for c in chunks if c.choices[0].delta.content]
        assert len(content_chunks) == 3
        
        # Last chunk should have finish reason
        assert chunks[-1].choices[0].finish_reason == "stop"
        
        # Reconstruct the message
        full_content = "".join(
            c.choices[0].delta.content or ""
            for c in chunks
        )
        assert full_content == "Word1 Word2 Word3"
    
    @pytest.mark.asyncio
    async def test_call_tracking(self):
        """Test that calls are tracked."""
        model = MockChatModel()
        assert model.call_count == 0
        
        await model.create([Message(role="user", content="Test")], "mock")
        assert model.call_count == 1
        
        await model.create([Message(role="user", content="Test")], "mock")
        assert model.call_count == 2


@pytest.mark.unit
class TestMockEmbeddingModel:
    """Test the mock embedding model implementation."""
    
    @pytest.mark.asyncio
    async def test_create_single_embedding(self):
        """Test creating embedding for single text."""
        model = MockEmbeddingModel(embedding_dim=10)
        
        response = await model.create(
            input="Test text",
            model="mock-embedding"
        )
        
        assert isinstance(response, EmbeddingResponse)
        assert response.model == "mock-embedding"
        assert len(response.data) == 1
        assert response.data[0].index == 0
        assert len(response.data[0].embedding) == 10
        assert all(0 <= x <= 1 for x in response.data[0].embedding)
        assert response.usage.prompt_tokens == 2  # "Test text"
    
    @pytest.mark.asyncio
    async def test_create_multiple_embeddings(self):
        """Test creating embeddings for multiple texts."""
        model = MockEmbeddingModel(embedding_dim=5)
        
        texts = ["First text", "Second text", "Third text"]
        response = await model.create(
            input=texts,
            model="mock-embedding"
        )
        
        assert len(response.data) == 3
        for i, data in enumerate(response.data):
            assert data.index == i
            assert len(data.embedding) == 5
            assert data.object == "embedding"
        
        assert response.usage.prompt_tokens == 6  # Total words
    
    @pytest.mark.asyncio
    async def test_deterministic_embeddings(self):
        """Test that embeddings are deterministic for same input."""
        model = MockEmbeddingModel()
        
        response1 = await model.create("Test input", "mock")
        response2 = await model.create("Test input", "mock")
        
        assert response1.data[0].embedding == response2.data[0].embedding
    
    @pytest.mark.asyncio
    async def test_different_embeddings_for_different_inputs(self):
        """Test that different inputs produce different embeddings."""
        model = MockEmbeddingModel(embedding_dim=100)
        
        response1 = await model.create("First input", "mock")
        response2 = await model.create("Second input", "mock")
        
        embedding1 = response1.data[0].embedding
        embedding2 = response2.data[0].embedding
        
        # Embeddings should be different
        assert embedding1 != embedding2
        
        # But same length
        assert len(embedding1) == len(embedding2) == 100


@pytest.mark.unit
class TestDIIntegration:
    """Test integration with DI container."""
    
    @pytest.mark.asyncio
    async def test_models_can_be_resolved_from_container(self):
        """Test that models can be resolved from container."""
        from whiskey.core.decorators import get_default_container
        
        # Models should be auto-registered via @provide to default container
        container = get_default_container()
        chat_model = await container.resolve(MockChatModel)
        embedding_model = await container.resolve(MockEmbeddingModel)
        
        assert isinstance(chat_model, MockChatModel)
        assert isinstance(embedding_model, MockEmbeddingModel)
    
    @pytest.mark.asyncio
    async def test_models_can_be_injected(self):
        """Test that models can be injected into services."""
        from whiskey import inject
        
        @inject
        async def use_models(
            chat: MockChatModel,
            embeddings: MockEmbeddingModel
        ) -> tuple:
            return (chat, embeddings)
        
        chat, embeddings = await use_models()
        assert isinstance(chat, MockChatModel)
        assert isinstance(embeddings, MockEmbeddingModel)