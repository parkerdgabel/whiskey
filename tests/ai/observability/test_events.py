"""Tests for AI observability events."""

import pytest

from whiskey.ai.observability.events import (
    AIRequestCompleted,
    AIRequestFailed,
    AIRequestStarted,
    AIStreamChunkReceived,
    AIStreamCompleted,
)
from whiskey.core.events import Event


@pytest.mark.unit
class TestAIEvents:
    """Test AI observability events."""
    
    def test_request_started_event(self):
        """Test AIRequestStarted event."""
        event = AIRequestStarted(
            context_id="ctx-123",
            model="gpt-4",
            provider="openai",
            prompt_tokens=100,
            max_tokens=500,
            temperature=0.7
        )
        
        assert isinstance(event, Event)
        assert event.context_id == "ctx-123"
        assert event.model == "gpt-4"
        assert event.provider == "openai"
        assert event.prompt_tokens == 100
        assert event.max_tokens == 500
        assert event.temperature == 0.7
        assert hasattr(event, 'metadata')  # Inherited from Event base class
    
    def test_request_completed_event(self):
        """Test AIRequestCompleted event."""
        event = AIRequestCompleted(
            context_id="ctx-123",
            model="gpt-4",
            provider="openai",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            duration_ms=1234.5,
            cost=0.0075,
            finish_reason="stop"
        )
        
        assert isinstance(event, Event)
        assert event.total_tokens == 150
        assert event.duration_ms == 1234.5
        assert event.cost == 0.0075
        assert event.finish_reason == "stop"
    
    def test_request_failed_event(self):
        """Test AIRequestFailed event."""
        event = AIRequestFailed(
            context_id="ctx-123",
            model="gpt-4",
            provider="openai",
            error_type="RateLimitError",
            error_message="Rate limit exceeded",
            duration_ms=500.0,
            retryable=True
        )
        
        assert isinstance(event, Event)
        assert event.error_type == "RateLimitError"
        assert event.error_message == "Rate limit exceeded"
        assert event.retryable is True
    
    def test_stream_chunk_event(self):
        """Test AIStreamChunkReceived event."""
        event = AIStreamChunkReceived(
            context_id="ctx-123",
            model="gpt-4",
            provider="openai",
            chunk_index=5,
            content="Hello",
            tokens=1
        )
        
        assert isinstance(event, Event)
        assert event.chunk_index == 5
        assert event.content == "Hello"
        assert event.tokens == 1
    
    def test_stream_completed_event(self):
        """Test AIStreamCompleted event."""
        event = AIStreamCompleted(
            context_id="ctx-123",
            model="gpt-4",
            provider="openai",
            total_chunks=20,
            total_tokens=150,
            duration_ms=3000.0,
            cost=0.0075,
            finish_reason="stop"
        )
        
        assert isinstance(event, Event)
        assert event.total_chunks == 20
        assert event.total_tokens == 150
        assert event.duration_ms == 3000.0
    
    def test_event_metadata(self):
        """Test event metadata handling."""
        # Events inherit metadata from Event base class
        event = AIRequestStarted(
            context_id="ctx-123",
            model="gpt-4",
            provider="openai",
            prompt_tokens=100
        )
        
        # Should have metadata field from base class
        assert hasattr(event, 'metadata')
        assert isinstance(event.metadata, dict)
        
        # Can add metadata after creation
        event.metadata["user_id"] = "user-456"
        assert event.metadata["user_id"] == "user-456"