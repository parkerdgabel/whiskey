"""Buffering utilities for streaming responses."""

import asyncio
from collections import deque
from dataclasses import dataclass
from typing import Deque, List, Optional


@dataclass
class StreamBuffer:
    """Buffer for streaming text content."""
    
    def __init__(self, max_size: Optional[int] = None):
        """Initialize buffer.
        
        Args:
            max_size: Maximum buffer size in characters
        """
        self.max_size = max_size
        self._buffer: List[str] = []
        self._total_size = 0
        self._lock = asyncio.Lock()
    
    async def append(self, content: str) -> None:
        """Append content to buffer.
        
        Args:
            content: Text to append
        """
        async with self._lock:
            if self.max_size and self._total_size + len(content) > self.max_size:
                # Trim buffer to make room
                while self._buffer and self._total_size + len(content) > self.max_size:
                    removed = self._buffer.pop(0)
                    self._total_size -= len(removed)
            
            self._buffer.append(content)
            self._total_size += len(content)
    
    async def get_content(self) -> str:
        """Get full buffer content."""
        async with self._lock:
            return "".join(self._buffer)
    
    async def clear(self) -> None:
        """Clear the buffer."""
        async with self._lock:
            self._buffer.clear()
            self._total_size = 0
    
    async def size(self) -> int:
        """Get current buffer size in characters."""
        async with self._lock:
            return self._total_size


@dataclass 
class TokenBuffer:
    """Buffer for tracking token usage in streams."""
    
    def __init__(self, window_size: int = 100):
        """Initialize token buffer.
        
        Args:
            window_size: Size of sliding window for rate calculation
        """
        self.window_size = window_size
        self._tokens: Deque[int] = deque(maxlen=window_size)
        self._timestamps: Deque[float] = deque(maxlen=window_size)
        self._total_tokens = 0
        self._lock = asyncio.Lock()
    
    async def add_tokens(self, count: int, timestamp: float) -> None:
        """Add token count with timestamp.
        
        Args:
            count: Number of tokens
            timestamp: Time when tokens were received
        """
        async with self._lock:
            self._tokens.append(count)
            self._timestamps.append(timestamp)
            self._total_tokens += count
    
    async def get_total_tokens(self) -> int:
        """Get total tokens processed."""
        async with self._lock:
            return self._total_tokens
    
    async def get_rate(self) -> float:
        """Calculate tokens per second over the window.
        
        Returns:
            Tokens per second, or 0 if insufficient data
        """
        async with self._lock:
            if len(self._timestamps) < 2:
                return 0.0
            
            time_span = self._timestamps[-1] - self._timestamps[0]
            if time_span <= 0:
                return 0.0
            
            total_window_tokens = sum(self._tokens)
            return total_window_tokens / time_span
    
    async def get_average_chunk_size(self) -> float:
        """Get average tokens per chunk.
        
        Returns:
            Average chunk size, or 0 if no data
        """
        async with self._lock:
            if not self._tokens:
                return 0.0
            return sum(self._tokens) / len(self._tokens)