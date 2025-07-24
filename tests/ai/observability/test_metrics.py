"""Tests for AI metrics collection."""

import pytest

from whiskey import Container, EventBus
from whiskey.ai.observability import (
    AIMetricsCollector,
    AIRequestCompleted,
    AIRequestFailed,
    AIRequestStarted,
    AIStreamChunkReceived,
    AIStreamCompleted,
)


@pytest.mark.unit
class TestAIMetricsCollector:
    """Test AI metrics collection."""
    
    @pytest.mark.asyncio
    async def test_basic_metrics_collection(self):
        """Test basic metrics collection without event bus."""
        collector = AIMetricsCollector()
        
        # Manually call event handlers
        await collector.on_request_started(AIRequestStarted(
            context_id="ctx-1",
            model="gpt-4",
            provider="openai",
            prompt_tokens=100
        ))
        
        await collector.on_request_completed(AIRequestCompleted(
            context_id="ctx-1",
            model="gpt-4",
            provider="openai",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            duration_ms=1000.0,
            cost=0.0075
        ))
        
        # Check metrics
        metrics = collector.get_model_metrics("gpt-4")
        assert metrics is not None
        assert metrics.request_count == 1
        assert metrics.success_count == 1
        assert metrics.failure_count == 0
        assert metrics.total_tokens == 150
        assert metrics.total_cost == 0.0075
        assert metrics.average_duration_ms == 1000.0
    
    @pytest.mark.asyncio
    async def test_failure_metrics(self):
        """Test failure metrics collection."""
        collector = AIMetricsCollector()
        
        # Start and fail a request
        await collector.on_request_started(AIRequestStarted(
            context_id="ctx-1",
            model="gpt-4",
            provider="openai",
            prompt_tokens=100
        ))
        
        await collector.on_request_failed(AIRequestFailed(
            context_id="ctx-1",
            model="gpt-4",
            provider="openai",
            error_type="RateLimitError",
            error_message="Rate limit exceeded",
            duration_ms=500.0,
            retryable=True
        ))
        
        # Check metrics
        metrics = collector.get_model_metrics("gpt-4")
        assert metrics.request_count == 1
        assert metrics.success_count == 0
        assert metrics.failure_count == 1
        assert metrics.errors_by_type["RateLimitError"] == 1
        assert metrics.success_rate == 0.0
    
    @pytest.mark.asyncio
    async def test_streaming_metrics(self):
        """Test streaming metrics collection."""
        collector = AIMetricsCollector()
        
        # Simulate streaming
        for i in range(5):
            await collector.on_stream_chunk(AIStreamChunkReceived(
                context_id="ctx-1",
                model="gpt-4",
                provider="openai",
                chunk_index=i,
                content=f"chunk {i}",
                tokens=2
            ))
        
        await collector.on_stream_completed(AIStreamCompleted(
            context_id="ctx-1",
            model="gpt-4",
            provider="openai",
            total_chunks=5,
            total_tokens=10,
            duration_ms=2000.0,
            cost=0.0005
        ))
        
        # Check stream metrics
        stream_metrics = collector.stream_metrics.get("gpt-4")
        assert stream_metrics is not None
        assert stream_metrics.stream_count == 1
        assert stream_metrics.total_chunks == 5
        assert stream_metrics.average_chunks_per_stream == 5.0
    
    @pytest.mark.asyncio
    async def test_percentile_calculations(self):
        """Test percentile calculations."""
        collector = AIMetricsCollector()
        
        # Add multiple requests with different durations
        durations = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
        
        for i, duration in enumerate(durations):
            await collector.on_request_started(AIRequestStarted(
                context_id=f"ctx-{i}",
                model="gpt-4",
                provider="openai",
                prompt_tokens=100
            ))
            
            await collector.on_request_completed(AIRequestCompleted(
                context_id=f"ctx-{i}",
                model="gpt-4",
                provider="openai",
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
                duration_ms=float(duration),
                cost=0.01
            ))
        
        metrics = collector.get_model_metrics("gpt-4")
        # With 10 items (100-1000), percentiles should be:
        # 50th percentile (0.5 * 10 - 1 = 4th index) = 500
        # 90th percentile (0.9 * 10 - 1 = 8th index) = 900  
        # 99th percentile (0.99 * 10 - 1 = 8.9 -> 8th index) = 900
        assert metrics.get_percentile(0.5) == 500.0  # Median
        assert metrics.get_percentile(0.9) == 900.0  # P90
        assert metrics.get_percentile(0.99) == 900.0  # P99 (clamped to 8th index)
    
    @pytest.mark.asyncio
    async def test_get_all_metrics(self):
        """Test getting all metrics as dictionary."""
        collector = AIMetricsCollector()
        
        # Add some data
        await collector.on_request_started(AIRequestStarted(
            context_id="ctx-1",
            model="gpt-4",
            provider="openai",
            prompt_tokens=100
        ))
        
        await collector.on_request_completed(AIRequestCompleted(
            context_id="ctx-1",
            model="gpt-4",
            provider="openai",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            duration_ms=1000.0,
            cost=0.0075
        ))
        
        # Get all metrics
        all_metrics = collector.get_all_metrics()
        
        assert "gpt-4" in all_metrics
        gpt4_metrics = all_metrics["gpt-4"]
        
        assert gpt4_metrics["requests"]["total"] == 1
        assert gpt4_metrics["requests"]["success"] == 1
        assert gpt4_metrics["tokens"]["total"] == 150
        assert gpt4_metrics["cost"]["total"] == 0.0075
        assert gpt4_metrics["duration"]["average_ms"] == 1000.0
    
    @pytest.mark.asyncio
    async def test_reset_functionality(self):
        """Test resetting metrics."""
        collector = AIMetricsCollector()
        
        # Add data for multiple models
        for model in ["gpt-4", "gpt-3.5"]:
            await collector.on_request_started(AIRequestStarted(
                context_id=f"ctx-{model}",
                model=model,
                provider="openai",
                prompt_tokens=100
            ))
            
            await collector.on_request_completed(AIRequestCompleted(
                context_id=f"ctx-{model}",
                model=model,
                provider="openai",
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
                duration_ms=1000.0,
                cost=0.01
            ))
        
        # Reset specific model
        collector.reset("gpt-4")
        assert collector.get_model_metrics("gpt-4") is None
        assert collector.get_model_metrics("gpt-3.5") is not None
        
        # Reset all
        collector.reset()
        assert len(collector.model_metrics) == 0
        assert len(collector.stream_metrics) == 0
    
    @pytest.mark.asyncio
    async def test_event_bus_integration(self):
        """Test integration with event bus."""
        container = Container()
        event_bus = EventBus()
        container.register(EventBus, instance=event_bus)
        
        # Create collector with event bus
        collector = AIMetricsCollector(event_bus)
        
        # Use emit_sync for synchronous event processing  
        await event_bus.emit_sync(AIRequestStarted(
            context_id="ctx-1",
            model="gpt-4",
            provider="openai",
            prompt_tokens=100
        ))
        
        await event_bus.emit_sync(AIRequestCompleted(
            context_id="ctx-1",
            model="gpt-4",
            provider="openai",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            duration_ms=1000.0,
            cost=0.0075
        ))
        
        # Check that metrics were collected
        metrics = collector.get_model_metrics("gpt-4")
        assert metrics is not None
        assert metrics.request_count == 1
        assert metrics.success_count == 1