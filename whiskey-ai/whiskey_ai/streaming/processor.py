"""Stream processor for AI responses."""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, List, Optional

from ..context import AIContext
from ..models.types import ChatCompletionChunk
from ..observability.events import AIStreamChunkReceived, AIStreamCompleted
from whiskey.core.decorators import provide
from whiskey.core.events import EventBus

from .buffer import StreamBuffer, TokenBuffer


@dataclass
class StreamStats:
    """Statistics for a streaming session."""
    
    start_time: float = 0.0
    end_time: float = 0.0
    total_chunks: int = 0
    total_tokens: int = 0
    total_content_length: int = 0
    errors: List[Exception] = field(default_factory=list)
    
    @property
    def duration_ms(self) -> float:
        """Get streaming duration in milliseconds."""
        if self.end_time == 0:
            return 0.0
        return (self.end_time - self.start_time) * 1000
    
    @property
    def chunks_per_second(self) -> float:
        """Calculate chunks per second."""
        duration_s = (self.end_time - self.start_time)
        if duration_s <= 0:
            return 0.0
        return self.total_chunks / duration_s
    
    @property
    def tokens_per_second(self) -> float:
        """Calculate tokens per second."""
        duration_s = (self.end_time - self.start_time)
        if duration_s <= 0:
            return 0.0
        return self.total_tokens / duration_s


StreamCallback = Callable[[str, int], None]
ErrorCallback = Callable[[Exception], None]


@provide
class StreamProcessor:
    """Processes streaming AI responses with buffering and tracking."""
    
    def __init__(
        self,
        context: Optional[AIContext] = None,
        event_bus: Optional[EventBus] = None,
        buffer_size: Optional[int] = None,
        emit_events: bool = True
    ):
        """Initialize stream processor.
        
        Args:
            context: AI context for tracking
            event_bus: Event bus for emitting events
            buffer_size: Maximum buffer size
            emit_events: Whether to emit streaming events
        """
        self.context = context
        self.event_bus = event_bus
        self.buffer_size = buffer_size
        self.emit_events = emit_events
    
    async def process_stream(
        self,
        stream: AsyncIterator[ChatCompletionChunk],
        *,
        on_chunk: Optional[StreamCallback] = None,
        on_error: Optional[ErrorCallback] = None,
        include_partial: bool = True
    ) -> tuple[str, StreamStats]:
        """Process a streaming response.
        
        Args:
            stream: Async iterator of completion chunks
            on_chunk: Callback for each chunk (content, chunk_index)
            on_error: Callback for errors
            include_partial: Include partial content on error
            
        Returns:
            Tuple of (complete_content, statistics)
        """
        buffer = StreamBuffer(self.buffer_size)
        token_buffer = TokenBuffer()
        stats = StreamStats(start_time=time.time())
        
        chunk_index = 0
        model = ""
        provider = ""
        context_id = self.context.id if self.context else ""
        
        try:
            async for chunk in stream:
                chunk_time = time.time()
                
                # Extract content and metadata
                content = ""
                tokens = 0
                
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    # Estimate tokens (simple word count)
                    tokens = len(content.split())
                
                # Update model info from first chunk
                if chunk_index == 0 and chunk.model:
                    model = chunk.model
                
                # Buffer content
                if content:
                    await buffer.append(content)
                    stats.total_content_length += len(content)
                
                # Track tokens
                if tokens > 0:
                    await token_buffer.add_tokens(tokens, chunk_time)
                    stats.total_tokens += tokens
                
                # Update context if available
                if self.context and tokens > 0:
                    self.context.add_usage(completion_tokens=tokens)
                
                # Emit event
                if self.emit_events and self.event_bus:
                    await self.event_bus.emit(AIStreamChunkReceived(
                        context_id=context_id,
                        model=model,
                        provider=provider,
                        chunk_index=chunk_index,
                        content=content,
                        tokens=tokens
                    ))
                
                # Callback
                if on_chunk and content:
                    on_chunk(content, chunk_index)
                
                chunk_index += 1
                stats.total_chunks += 1
                
                # Check for finish reason
                if (chunk.choices and 
                    chunk.choices[0].finish_reason is not None):
                    break
            
        except Exception as e:
            stats.errors.append(e)
            if on_error:
                on_error(e)
            if not include_partial:
                raise
        
        finally:
            stats.end_time = time.time()
            
            # Get final content
            final_content = await buffer.get_content()
            
            # Calculate cost if context available
            cost = 0.0
            if self.context:
                # Simple cost estimation (would be provider-specific)
                cost = stats.total_tokens * 0.00005  # Example rate
            
            # Emit completion event
            if self.emit_events and self.event_bus:
                await self.event_bus.emit(AIStreamCompleted(
                    context_id=context_id,
                    model=model,
                    provider=provider,
                    total_chunks=stats.total_chunks,
                    total_tokens=stats.total_tokens,
                    duration_ms=stats.duration_ms,
                    cost=cost,
                    finish_reason="stop" if not stats.errors else "error"
                ))
        
        return final_content, stats
    
    async def process_text_stream(
        self,
        stream: AsyncIterator[str],
        *,
        on_chunk: Optional[StreamCallback] = None,
        on_error: Optional[ErrorCallback] = None,
        estimate_tokens: bool = True
    ) -> tuple[str, StreamStats]:
        """Process a simple text stream.
        
        Args:
            stream: Async iterator of text chunks
            on_chunk: Callback for each chunk
            on_error: Error callback
            estimate_tokens: Whether to estimate token count
            
        Returns:
            Tuple of (complete_content, statistics)
        """
        buffer = StreamBuffer(self.buffer_size)
        stats = StreamStats(start_time=time.time())
        
        chunk_index = 0
        
        try:
            async for chunk in stream:
                # Buffer content
                await buffer.append(chunk)
                stats.total_content_length += len(chunk)
                
                # Estimate tokens
                if estimate_tokens:
                    tokens = len(chunk.split())
                    stats.total_tokens += tokens
                
                # Callback
                if on_chunk:
                    on_chunk(chunk, chunk_index)
                
                chunk_index += 1
                stats.total_chunks += 1
                
        except Exception as e:
            stats.errors.append(e)
            if on_error:
                on_error(e)
            raise
        
        finally:
            stats.end_time = time.time()
        
        return await buffer.get_content(), stats