"""Resource manager for AI operations."""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator, Dict, List, Optional

from whiskey.core.decorators import provide, singleton
from whiskey.core.scopes import SingletonScope

from .rate_limiter import RateLimiter
from .token_bucket import TokenBucket, TokenLease


@dataclass
class ResourceConfig:
    """Configuration for AI resource limits."""
    
    # Token limits
    max_tokens_per_minute: Optional[int] = None
    max_tokens_per_hour: Optional[int] = None
    max_tokens_per_day: Optional[int] = None
    
    # Request limits
    max_requests_per_minute: Optional[int] = None
    max_requests_per_hour: Optional[int] = None
    
    # Cost limits
    max_cost_per_hour: Optional[float] = None
    max_cost_per_day: Optional[float] = None


@singleton
class AIResourceManager:
    """Manages AI resource usage including tokens, rate limits, and costs."""
    
    def __init__(self):
        self._token_buckets: Dict[str, TokenBucket] = {}
        self._rate_limiters: Dict[str, RateLimiter] = {}
        self._cost_trackers: Dict[str, float] = {}
        self._configs: Dict[str, ResourceConfig] = {}
        self._lock = asyncio.Lock()
    
    async def configure_model(self, model: str, config: ResourceConfig) -> None:
        """Configure resource limits for a model.
        
        Args:
            model: Model identifier (e.g., "gpt-4")
            config: Resource configuration
        """
        async with self._lock:
            self._configs[model] = config
            
            # Create token buckets based on config
            if config.max_tokens_per_minute:
                bucket_key = f"{model}:tokens:minute"
                self._token_buckets[bucket_key] = TokenBucket(
                    capacity=config.max_tokens_per_minute,
                    refill_rate=config.max_tokens_per_minute / 60.0
                )
            
            if config.max_tokens_per_hour:
                bucket_key = f"{model}:tokens:hour"
                self._token_buckets[bucket_key] = TokenBucket(
                    capacity=config.max_tokens_per_hour,
                    refill_rate=config.max_tokens_per_hour / 3600.0
                )
            
            if config.max_tokens_per_day:
                bucket_key = f"{model}:tokens:day"
                self._token_buckets[bucket_key] = TokenBucket(
                    capacity=config.max_tokens_per_day,
                    refill_rate=config.max_tokens_per_day / 86400.0
                )
            
            # Create rate limiters
            rate_limiter = RateLimiter()
            
            if config.max_requests_per_minute:
                await rate_limiter.add_window(
                    "per_minute",
                    config.max_requests_per_minute,
                    60.0
                )
            
            if config.max_requests_per_hour:
                await rate_limiter.add_window(
                    "per_hour",
                    config.max_requests_per_hour,
                    3600.0
                )
            
            if rate_limiter.windows:
                self._rate_limiters[model] = rate_limiter
    
    async def acquire_tokens(
        self,
        model: str,
        count: int,
        wait: bool = True
    ) -> Optional[List[TokenLease]]:
        """Acquire tokens for a model.
        
        Args:
            model: Model identifier
            count: Number of tokens to acquire
            wait: Whether to wait for tokens to become available
            
        Returns:
            List of token leases if successful, None if not enough tokens
        """
        leases = []
        
        try:
            # Check all token buckets for this model
            for period in ["minute", "hour", "day"]:
                bucket_key = f"{model}:tokens:{period}"
                if bucket_key in self._token_buckets:
                    bucket = self._token_buckets[bucket_key]
                    
                    # Check if request exceeds capacity
                    if count > bucket.capacity:
                        # Release any leases we already got
                        for acquired_lease in leases:
                            await acquired_lease.release()
                        return None
                    
                    lease = await bucket.acquire(count, wait)
                    if not lease:
                        # Failed to acquire from this bucket
                        # Release any leases we already got
                        for acquired_lease in leases:
                            await acquired_lease.release()
                        return None
                    leases.append(lease)
            
            return leases if leases else [TokenLease(None, count, 0.0)]
            
        except Exception:
            # Release any leases on error
            for lease in leases:
                await lease.release()
            raise
    
    @asynccontextmanager
    async def acquire_tokens_context(
        self,
        model: str,
        count: int,
        wait: bool = True
    ) -> AsyncIterator[Optional[List[TokenLease]]]:
        """Context manager for acquiring tokens."""
        leases = await self.acquire_tokens(model, count, wait)
        try:
            yield leases
        finally:
            if leases:
                for lease in leases:
                    await lease.release()
    
    async def check_rate_limit(self, model: str) -> bool:
        """Check if a request can proceed for a model.
        
        Args:
            model: Model identifier
            
        Returns:
            True if request can proceed, False if rate limited
        """
        if model not in self._rate_limiters:
            return True
        
        return await self._rate_limiters[model].check()
    
    async def acquire_request_slot(self, model: str, wait: bool = True) -> bool:
        """Acquire a request slot for a model.
        
        Args:
            model: Model identifier
            wait: Whether to wait if rate limited
            
        Returns:
            True if acquired, False if rate limited and wait=False
        """
        if model not in self._rate_limiters:
            return True
        
        return await self._rate_limiters[model].acquire(wait)
    
    async def track_cost(self, model: str, cost: float) -> bool:
        """Track cost and check if within limits.
        
        Args:
            model: Model identifier
            cost: Cost to track
            
        Returns:
            True if within limits, False if exceeded
        """
        config = self._configs.get(model)
        if not config:
            return True
        
        # Simple cost tracking - in production would use sliding windows
        async with self._lock:
            current_cost = self._cost_trackers.get(model, 0.0)
            new_cost = current_cost + cost
            
            # Check limits
            if config.max_cost_per_hour and new_cost > config.max_cost_per_hour:
                return False
            
            if config.max_cost_per_day and new_cost > config.max_cost_per_day:
                return False
            
            self._cost_trackers[model] = new_cost
            return True
    
    async def get_token_availability(self, model: str) -> Dict[str, int]:
        """Get available tokens for all periods.
        
        Returns:
            Dictionary mapping period to available tokens
        """
        availability = {}
        
        for period in ["minute", "hour", "day"]:
            bucket_key = f"{model}:tokens:{period}"
            if bucket_key in self._token_buckets:
                bucket = self._token_buckets[bucket_key]
                availability[period] = await bucket.available()
        
        return availability
    
    async def get_wait_times(self, model: str, tokens: int) -> Dict[str, float]:
        """Get wait times for acquiring tokens.
        
        Returns:
            Dictionary mapping period to wait time in seconds
        """
        wait_times = {}
        
        # Token wait times
        for period in ["minute", "hour", "day"]:
            bucket_key = f"{model}:tokens:{period}"
            if bucket_key in self._token_buckets:
                bucket = self._token_buckets[bucket_key]
                wait_times[f"tokens_{period}"] = await bucket.wait_time(tokens)
        
        # Rate limit wait time
        if model in self._rate_limiters:
            wait_times["rate_limit"] = await self._rate_limiters[model].wait_time()
        
        return wait_times
    
    async def reset(self, model: Optional[str] = None) -> None:
        """Reset resource tracking.
        
        Args:
            model: Specific model to reset, or None to reset all
        """
        async with self._lock:
            if model:
                # Reset specific model
                self._cost_trackers.pop(model, None)
                
                # Reset rate limiter
                if model in self._rate_limiters:
                    await self._rate_limiters[model].reset()
            else:
                # Reset everything
                self._cost_trackers.clear()
                for limiter in self._rate_limiters.values():
                    await limiter.reset()