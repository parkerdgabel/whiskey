"""Rate limiter implementation for AI operations."""

import asyncio
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Optional


@dataclass
class RateLimitWindow:
    """Sliding window for rate limiting."""
    
    max_requests: int
    window_seconds: float
    
    def __post_init__(self):
        self.requests: Deque[float] = deque()
        self._lock = asyncio.Lock()
    
    async def _cleanup_old_requests(self, now: float) -> None:
        """Remove requests outside the current window."""
        cutoff = now - self.window_seconds
        while self.requests and self.requests[0] < cutoff:
            self.requests.popleft()
    
    async def check(self) -> bool:
        """Check if a request can proceed without recording it."""
        async with self._lock:
            now = time.time()
            await self._cleanup_old_requests(now)
            return len(self.requests) < self.max_requests
    
    async def acquire(self, wait: bool = True) -> bool:
        """Try to acquire permission for a request.
        
        Args:
            wait: Whether to wait if rate limit is exceeded
            
        Returns:
            True if request can proceed, False if rate limited and wait=False
        """
        while True:
            async with self._lock:
                now = time.time()
                await self._cleanup_old_requests(now)
                
                if len(self.requests) < self.max_requests:
                    # We can proceed
                    self.requests.append(now)
                    return True
                
                if not wait:
                    return False
                
                # Calculate wait time until oldest request expires
                oldest_request = self.requests[0]
                wait_time = (oldest_request + self.window_seconds) - now
            
            # Wait outside the lock
            await asyncio.sleep(max(0.01, wait_time))
    
    async def wait_time(self) -> float:
        """Calculate wait time until next request can proceed.
        
        Returns:
            Seconds to wait, or 0 if request can proceed now
        """
        async with self._lock:
            now = time.time()
            await self._cleanup_old_requests(now)
            
            if len(self.requests) < self.max_requests:
                return 0.0
            
            # Time until oldest request expires
            oldest_request = self.requests[0]
            return max(0.0, (oldest_request + self.window_seconds) - now)
    
    async def reset(self) -> None:
        """Reset the rate limiter, clearing all recorded requests."""
        async with self._lock:
            self.requests.clear()


class RateLimiter:
    """Rate limiter with multiple windows for different time periods."""
    
    def __init__(self):
        self.windows: dict[str, RateLimitWindow] = {}
        self._lock = asyncio.Lock()
    
    async def add_window(self, name: str, max_requests: int, window_seconds: float) -> None:
        """Add a rate limit window.
        
        Args:
            name: Name of the window (e.g., "per_minute", "per_hour")
            max_requests: Maximum requests allowed in the window
            window_seconds: Size of the window in seconds
        """
        async with self._lock:
            self.windows[name] = RateLimitWindow(max_requests, window_seconds)
    
    async def check(self) -> bool:
        """Check if a request can proceed across all windows."""
        for window in self.windows.values():
            if not await window.check():
                return False
        return True
    
    async def acquire(self, wait: bool = True) -> bool:
        """Try to acquire permission across all windows.
        
        Args:
            wait: Whether to wait if any rate limit is exceeded
            
        Returns:
            True if request can proceed, False if rate limited and wait=False
        """
        # Check all windows first
        if not wait and not await self.check():
            return False
        
        # Acquire from all windows
        for window in self.windows.values():
            if not await window.acquire(wait):
                return False
        
        return True
    
    async def wait_time(self) -> float:
        """Calculate maximum wait time across all windows.
        
        Returns:
            Seconds to wait until request can proceed
        """
        max_wait = 0.0
        for window in self.windows.values():
            wait = await window.wait_time()
            max_wait = max(max_wait, wait)
        return max_wait
    
    async def reset(self, window_name: Optional[str] = None) -> None:
        """Reset rate limiter windows.
        
        Args:
            window_name: Specific window to reset, or None to reset all
        """
        if window_name:
            if window_name in self.windows:
                await self.windows[window_name].reset()
        else:
            for window in self.windows.values():
                await window.reset()