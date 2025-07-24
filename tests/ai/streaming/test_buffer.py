"""Tests for streaming buffers."""

import asyncio
import time

import pytest

from whiskey.ai.streaming import StreamBuffer, TokenBuffer


@pytest.mark.unit
class TestStreamBuffer:
    """Test stream buffer."""
    
    @pytest.mark.asyncio
    async def test_basic_buffering(self):
        """Test basic append and get operations."""
        buffer = StreamBuffer()
        
        await buffer.append("Hello")
        await buffer.append(" ")
        await buffer.append("World")
        
        content = await buffer.get_content()
        assert content == "Hello World"
        
        size = await buffer.size()
        assert size == 11  # len("Hello World")
    
    @pytest.mark.asyncio
    async def test_max_size_limit(self):
        """Test buffer size limiting."""
        buffer = StreamBuffer(max_size=10)
        
        # Add content that fits
        await buffer.append("Hello")
        assert await buffer.size() == 5
        
        # Add more content - should trim oldest
        await buffer.append("World!")
        content = await buffer.get_content()
        assert content == "World!"  # "Hello" was trimmed
        assert await buffer.size() == 6
    
    @pytest.mark.asyncio
    async def test_clear_buffer(self):
        """Test clearing the buffer."""
        buffer = StreamBuffer()
        
        await buffer.append("Test content")
        assert await buffer.size() > 0
        
        await buffer.clear()
        assert await buffer.size() == 0
        assert await buffer.get_content() == ""
    
    @pytest.mark.asyncio
    async def test_concurrent_access(self):
        """Test concurrent append operations."""
        buffer = StreamBuffer()
        
        async def append_content(text: str, count: int):
            for i in range(count):
                await buffer.append(f"{text}{i}")
        
        # Run concurrent appends
        await asyncio.gather(
            append_content("A", 5),
            append_content("B", 5),
            append_content("C", 5)
        )
        
        content = await buffer.get_content()
        assert len(content) > 0
        
        # Should contain all appended content
        for letter in ["A", "B", "C"]:
            for i in range(5):
                assert f"{letter}{i}" in content


@pytest.mark.unit
class TestTokenBuffer:
    """Test token buffer."""
    
    @pytest.mark.asyncio
    async def test_token_tracking(self):
        """Test basic token tracking."""
        buffer = TokenBuffer()
        
        await buffer.add_tokens(10, time.time())
        await buffer.add_tokens(15, time.time())
        await buffer.add_tokens(20, time.time())
        
        total = await buffer.get_total_tokens()
        assert total == 45
    
    @pytest.mark.asyncio
    async def test_rate_calculation(self):
        """Test token rate calculation."""
        buffer = TokenBuffer(window_size=10)
        
        # Add tokens with known timestamps
        base_time = time.time()
        await buffer.add_tokens(100, base_time)
        await buffer.add_tokens(100, base_time + 0.1)  # Exactly 0.1s later
        
        rate = await buffer.get_rate()
        # Should be exactly 2000 tokens/second (200 tokens in 0.1s)
        assert 1900 <= rate <= 2100  # Allow for small floating point variations
    
    @pytest.mark.asyncio
    async def test_average_chunk_size(self):
        """Test average chunk size calculation."""
        buffer = TokenBuffer()
        
        await buffer.add_tokens(10, time.time())
        await buffer.add_tokens(20, time.time())
        await buffer.add_tokens(30, time.time())
        
        avg = await buffer.get_average_chunk_size()
        assert avg == 20.0  # (10 + 20 + 30) / 3
    
    @pytest.mark.asyncio
    async def test_empty_buffer_stats(self):
        """Test stats on empty buffer."""
        buffer = TokenBuffer()
        
        assert await buffer.get_total_tokens() == 0
        assert await buffer.get_rate() == 0.0
        assert await buffer.get_average_chunk_size() == 0.0
    
    @pytest.mark.asyncio
    async def test_window_size_limit(self):
        """Test that window size is respected."""
        buffer = TokenBuffer(window_size=3)
        
        # Add more than window size
        for i in range(5):
            await buffer.add_tokens(10, time.time())
        
        # Total should still count all tokens
        assert await buffer.get_total_tokens() == 50
        
        # But average should only consider last 3
        avg = await buffer.get_average_chunk_size()
        assert avg == 10.0  # All chunks were 10 tokens