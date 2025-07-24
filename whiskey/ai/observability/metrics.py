"""AI metrics collection and aggregation."""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import DefaultDict, Dict, List, Optional

from whiskey.core.decorators import provide, singleton
from whiskey.core.events import EventBus

from .events import (
    AIRequestCompleted,
    AIRequestFailed,
    AIRequestStarted,
    AIStreamChunkReceived,
    AIStreamCompleted,
)


@dataclass
class ModelMetrics:
    """Metrics for a specific model."""
    
    request_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    total_duration_ms: float = 0.0
    
    # Error tracking
    errors_by_type: DefaultDict[str, int] = field(default_factory=lambda: defaultdict(int))
    
    # Percentiles tracking (simple implementation)
    durations: List[float] = field(default_factory=list)
    
    @property
    def average_duration_ms(self) -> float:
        """Calculate average request duration."""
        if self.request_count == 0:
            return 0.0
        return self.total_duration_ms / self.request_count
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.request_count == 0:
            return 0.0
        return self.success_count / self.request_count
    
    @property
    def average_tokens_per_request(self) -> float:
        """Calculate average tokens per request."""
        if self.request_count == 0:
            return 0.0
        return self.total_tokens / self.request_count
    
    def get_percentile(self, percentile: float) -> float:
        """Get duration percentile (e.g., 0.95 for p95)."""
        if not self.durations:
            return 0.0
        
        sorted_durations = sorted(self.durations)
        # For proper percentile calculation
        # Example: for 10 items, 50th percentile (0.5) should be at index 4 (0-based)
        # which is the 5th item (median of 10 items)
        index = int(len(sorted_durations) * percentile) - 1
        if index < 0:
            index = 0
        if index >= len(sorted_durations):
            index = len(sorted_durations) - 1
        return sorted_durations[index]


@dataclass
class StreamMetrics:
    """Metrics for streaming responses."""
    
    stream_count: int = 0
    total_chunks: int = 0
    total_stream_duration_ms: float = 0.0
    
    @property
    def average_chunks_per_stream(self) -> float:
        """Calculate average chunks per stream."""
        if self.stream_count == 0:
            return 0.0
        return self.total_chunks / self.stream_count
    
    @property
    def average_stream_duration_ms(self) -> float:
        """Calculate average stream duration."""
        if self.stream_count == 0:
            return 0.0
        return self.total_stream_duration_ms / self.stream_count


@singleton
class AIMetricsCollector:
    """Collects and aggregates AI operation metrics."""
    
    def __init__(self, event_bus: Optional[EventBus] = None):
        self.model_metrics: Dict[str, ModelMetrics] = {}
        self.stream_metrics: Dict[str, StreamMetrics] = {}
        self.active_requests: Dict[str, float] = {}  # context_id -> start_time
        self.active_streams: Dict[str, int] = {}  # context_id -> chunk_count
        
        # Subscribe to events if event bus provided
        if event_bus:
            self._subscribe_to_events(event_bus)
    
    def _subscribe_to_events(self, event_bus: EventBus) -> None:
        """Subscribe to AI events."""
        event_bus.on(AIRequestStarted, self.on_request_started)
        event_bus.on(AIRequestCompleted, self.on_request_completed)
        event_bus.on(AIRequestFailed, self.on_request_failed)
        event_bus.on(AIStreamChunkReceived, self.on_stream_chunk)
        event_bus.on(AIStreamCompleted, self.on_stream_completed)
    
    async def on_request_started(self, event: AIRequestStarted) -> None:
        """Handle request started event."""
        # Track active request
        self.active_requests[event.context_id] = time.time() * 1000  # ms
        
        # Initialize metrics if needed
        if event.model not in self.model_metrics:
            self.model_metrics[event.model] = ModelMetrics()
        
        # Increment request count
        self.model_metrics[event.model].request_count += 1
    
    async def on_request_completed(self, event: AIRequestCompleted) -> None:
        """Handle request completed event."""
        metrics = self.model_metrics.get(event.model)
        if not metrics:
            return
        
        # Update success metrics
        metrics.success_count += 1
        metrics.total_prompt_tokens += event.prompt_tokens
        metrics.total_completion_tokens += event.completion_tokens
        metrics.total_tokens += event.total_tokens
        metrics.total_cost += event.cost
        metrics.total_duration_ms += event.duration_ms
        metrics.durations.append(event.duration_ms)
        
        # Clean up active request
        self.active_requests.pop(event.context_id, None)
    
    async def on_request_failed(self, event: AIRequestFailed) -> None:
        """Handle request failed event."""
        metrics = self.model_metrics.get(event.model)
        if not metrics:
            return
        
        # Update failure metrics
        metrics.failure_count += 1
        metrics.errors_by_type[event.error_type] += 1
        metrics.total_duration_ms += event.duration_ms
        metrics.durations.append(event.duration_ms)
        
        # Clean up active request
        self.active_requests.pop(event.context_id, None)
    
    async def on_stream_chunk(self, event: AIStreamChunkReceived) -> None:
        """Handle stream chunk event."""
        # Track chunk count
        if event.context_id not in self.active_streams:
            self.active_streams[event.context_id] = 0
        self.active_streams[event.context_id] += 1
    
    async def on_stream_completed(self, event: AIStreamCompleted) -> None:
        """Handle stream completed event."""
        # Initialize stream metrics if needed
        if event.model not in self.stream_metrics:
            self.stream_metrics[event.model] = StreamMetrics()
        
        metrics = self.stream_metrics[event.model]
        metrics.stream_count += 1
        metrics.total_chunks += event.total_chunks
        metrics.total_stream_duration_ms += event.duration_ms
        
        # Also update model metrics
        if event.model in self.model_metrics:
            model_metrics = self.model_metrics[event.model]
            model_metrics.total_tokens += event.total_tokens
            model_metrics.total_cost += event.cost
        
        # Clean up active stream
        self.active_streams.pop(event.context_id, None)
    
    def get_model_metrics(self, model: str) -> Optional[ModelMetrics]:
        """Get metrics for a specific model."""
        return self.model_metrics.get(model)
    
    def get_all_metrics(self) -> Dict[str, Dict[str, any]]:
        """Get all metrics as a dictionary."""
        result = {}
        
        for model, metrics in self.model_metrics.items():
            result[model] = {
                "requests": {
                    "total": metrics.request_count,
                    "success": metrics.success_count,
                    "failure": metrics.failure_count,
                    "success_rate": metrics.success_rate,
                },
                "tokens": {
                    "prompt": metrics.total_prompt_tokens,
                    "completion": metrics.total_completion_tokens,
                    "total": metrics.total_tokens,
                    "average_per_request": metrics.average_tokens_per_request,
                },
                "cost": {
                    "total": metrics.total_cost,
                    "average_per_request": metrics.total_cost / max(1, metrics.request_count),
                },
                "duration": {
                    "total_ms": metrics.total_duration_ms,
                    "average_ms": metrics.average_duration_ms,
                    "p50_ms": metrics.get_percentile(0.5),
                    "p95_ms": metrics.get_percentile(0.95),
                    "p99_ms": metrics.get_percentile(0.99),
                },
                "errors": dict(metrics.errors_by_type),
            }
            
            # Add streaming metrics if available
            if model in self.stream_metrics:
                stream = self.stream_metrics[model]
                result[model]["streaming"] = {
                    "total_streams": stream.stream_count,
                    "total_chunks": stream.total_chunks,
                    "average_chunks_per_stream": stream.average_chunks_per_stream,
                    "average_duration_ms": stream.average_stream_duration_ms,
                }
        
        return result
    
    def reset(self, model: Optional[str] = None) -> None:
        """Reset metrics.
        
        Args:
            model: Specific model to reset, or None to reset all
        """
        if model:
            self.model_metrics.pop(model, None)
            self.stream_metrics.pop(model, None)
        else:
            self.model_metrics.clear()
            self.stream_metrics.clear()
            self.active_requests.clear()
            self.active_streams.clear()