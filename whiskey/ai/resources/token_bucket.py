"""Token bucket implementation for rate limiting AI operations."""

import asyncio
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator, Optional


@dataclass
class TokenLease:
    """Represents a lease of tokens from a bucket."""
    
    bucket: "TokenBucket"
    tokens: int
    acquired_at: float
    released: bool = False
    
    async def release(self) -> None:
        """Release the tokens back to the bucket."""
        if not self.released:
            await self.bucket.release(self.tokens)
            self.released = True


class TokenBucket:
    """Token bucket for rate limiting.
    
    Implements a token bucket algorithm where:
    - Tokens are consumed when making requests
    - Tokens are replenished at a fixed rate
    - Maximum capacity prevents token accumulation
    """
    
    def __init__(
        self,
        capacity: int,
        refill_rate: float,
        initial_tokens: Optional[int] = None
    ):
        """Initialize token bucket.
        
        Args:
            capacity: Maximum number of tokens the bucket can hold
            refill_rate: Number of tokens to add per second
            initial_tokens: Initial number of tokens (defaults to capacity)
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = float(initial_tokens if initial_tokens is not None else capacity)
        self.last_refill = time.time()
        self._lock = asyncio.Lock()
    
    async def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        
        # Add tokens based on refill rate
        tokens_to_add = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now
    
    async def acquire(self, tokens: int, wait: bool = True) -> Optional[TokenLease]:
        """Acquire tokens from the bucket.
        
        Args:
            tokens: Number of tokens to acquire
            wait: Whether to wait for tokens to become available
            
        Returns:
            TokenLease if successful, None if not enough tokens and wait=False
        """
        if tokens > self.capacity:
            raise ValueError(f"Cannot acquire {tokens} tokens from bucket with capacity {self.capacity}")
        
        async with self._lock:
            while True:
                await self._refill()
                
                if self.tokens >= tokens:
                    # We have enough tokens
                    self.tokens -= tokens
                    return TokenLease(
                        bucket=self,
                        tokens=tokens,
                        acquired_at=time.time()
                    )
                
                if not wait:
                    # Not enough tokens and not waiting
                    return None
                
                # Calculate wait time
                tokens_needed = tokens - self.tokens
                wait_time = tokens_needed / self.refill_rate
                
                # Wait for tokens to be available
                await asyncio.sleep(min(wait_time, 0.1))  # Check every 100ms max
    
    @asynccontextmanager
    async def acquire_context(self, tokens: int, wait: bool = True) -> AsyncIterator[Optional[TokenLease]]:
        """Context manager for acquiring tokens.
        
        Automatically releases tokens when context exits.
        """
        lease = await self.acquire(tokens, wait)
        try:
            yield lease
        finally:
            if lease:
                await lease.release()
    
    async def release(self, tokens: int) -> None:
        """Release tokens back to the bucket.
        
        Useful for returning unused tokens.
        """
        async with self._lock:
            self.tokens = min(self.capacity, self.tokens + tokens)
    
    async def available(self) -> int:
        """Get the number of available tokens."""
        async with self._lock:
            await self._refill()
            return int(self.tokens)
    
    async def wait_time(self, tokens: int) -> float:
        """Calculate wait time for acquiring tokens.
        
        Returns:
            Seconds to wait, or 0 if tokens are available now
        """
        if tokens > self.capacity:
            return float('inf')
        
        async with self._lock:
            await self._refill()
            
            if self.tokens >= tokens:
                return 0.0
            
            tokens_needed = tokens - self.tokens
            return tokens_needed / self.refill_rate