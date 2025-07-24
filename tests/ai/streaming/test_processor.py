"""Tests for stream processor."""

import asyncio
from typing import AsyncIterator

import pytest

from whiskey.ai import AIContext
from whiskey.ai.models import ChatCompletionChunk, Delta, StreamChoice
from whiskey.ai.streaming import StreamProcessor, StreamStats


async def create_mock_stream(
    chunks: list[str],
    model: str = "test-model",
    delay: float = 0.01
) -> AsyncIterator[ChatCompletionChunk]:
    """Create a mock stream of completion chunks."""
    for i, content in enumerate(chunks):
        await asyncio.sleep(delay)
        
        finish_reason = "stop" if i == len(chunks) - 1 else None
        
        yield ChatCompletionChunk(
            id=f"test-{i}",
            model=model,
            choices=[
                StreamChoice(
                    index=0,
                    delta=Delta(content=content),
                    finish_reason=finish_reason
                )
            ]
        )


async def create_text_stream(
    chunks: list[str],
    delay: float = 0.01
) -> AsyncIterator[str]:
    """Create a simple text stream."""
    for chunk in chunks:
        await asyncio.sleep(delay)
        yield chunk


@pytest.mark.unit
class TestStreamProcessor:
    """Test stream processor."""
    
    @pytest.mark.asyncio
    async def test_basic_stream_processing(self):
        """Test basic stream processing."""
        processor = StreamProcessor()
        
        chunks = ["Hello", " ", "World", "!"]
        stream = create_mock_stream(chunks)
        
        content, stats = await processor.process_stream(stream)
        
        assert content == "Hello World!"
        assert stats.total_chunks == 4
        assert stats.total_content_length == 12
        assert stats.duration_ms > 0
    
    @pytest.mark.asyncio
    async def test_stream_with_callbacks(self):
        """Test stream processing with callbacks."""
        processor = StreamProcessor()
        
        received_chunks = []
        
        def on_chunk(content: str, index: int):
            received_chunks.append((content, index))
        
        chunks = ["First", " chunk", ", second", " chunk"]
        stream = create_mock_stream(chunks)
        
        content, stats = await processor.process_stream(
            stream,
            on_chunk=on_chunk
        )
        
        assert len(received_chunks) == 4
        assert received_chunks[0] == ("First", 0)
        assert received_chunks[-1] == (" chunk", 3)
    
    @pytest.mark.asyncio
    async def test_stream_with_context(self):
        """Test stream processing with AI context."""
        context = AIContext()
        processor = StreamProcessor(context=context)
        
        # Create stream with known token counts
        chunks = ["Hello world", "How are", "you today"]
        stream = create_mock_stream(chunks)
        
        content, stats = await processor.process_stream(stream)
        
        # Context should have token usage updated
        # (each chunk estimates tokens by word count)
        assert context.completion_tokens > 0
        assert context.total_tokens == context.completion_tokens
    
    @pytest.mark.asyncio
    async def test_stream_error_handling(self):
        """Test error handling during streaming."""
        processor = StreamProcessor()
        
        errors = []
        
        def on_error(e: Exception):
            errors.append(e)
        
        async def failing_stream():
            yield ChatCompletionChunk(
                id="test-1",
                model="test",
                choices=[StreamChoice(
                    index=0,
                    delta=Delta(content="Start")
                )]
            )
            raise ValueError("Stream error")
        
        content, stats = await processor.process_stream(
            failing_stream(),
            on_error=on_error,
            include_partial=True
        )
        
        assert content == "Start"  # Partial content returned
        assert len(errors) == 1
        assert isinstance(errors[0], ValueError)
        assert len(stats.errors) == 1
    
    @pytest.mark.asyncio
    async def test_stream_without_partial_on_error(self):
        """Test stream error without returning partial content."""
        processor = StreamProcessor()
        
        async def failing_stream():
            yield ChatCompletionChunk(
                id="test-1",
                model="test",
                choices=[StreamChoice(
                    index=0,
                    delta=Delta(content="Partial")
                )]
            )
            raise ValueError("Stream error")
        
        with pytest.raises(ValueError):
            await processor.process_stream(
                failing_stream(),
                include_partial=False
            )
    
    @pytest.mark.asyncio
    async def test_text_stream_processing(self):
        """Test simple text stream processing."""
        processor = StreamProcessor()
        
        chunks = ["Hello", " from", " text", " stream"]
        stream = create_text_stream(chunks)
        
        content, stats = await processor.process_text_stream(stream)
        
        assert content == "Hello from text stream"
        assert stats.total_chunks == 4
        assert stats.total_content_length == 22
    
    @pytest.mark.asyncio
    async def test_stream_stats(self):
        """Test stream statistics."""
        processor = StreamProcessor()
        
        chunks = ["A", "B", "C"]
        stream = create_mock_stream(chunks, delay=0.1)
        
        content, stats = await processor.process_stream(stream)
        
        assert stats.total_chunks == 3
        assert stats.duration_ms >= 200  # At least 3 * 0.1s * 1000
        assert stats.chunks_per_second > 0
        assert stats.chunks_per_second <= 15  # Should be around 10
    
    @pytest.mark.asyncio
    async def test_buffer_size_limit(self):
        """Test stream processing with buffer size limit."""
        processor = StreamProcessor(buffer_size=10)
        
        # Create chunks that exceed buffer
        chunks = ["Hello", " World", " This", " Is", " A", " Long", " Stream"]
        stream = create_mock_stream(chunks)
        
        content, stats = await processor.process_stream(stream)
        
        # With buffer limit, only last content that fits is retained
        assert len(content) <= 10
        assert content == " Stream"  # Last chunk that fits
        assert stats.total_chunks == len(chunks)
        # Total content length tracks all content, even if trimmed from buffer
        assert stats.total_content_length == sum(len(c) for c in chunks)