"""Tests for token bucket implementation."""

import asyncio
import time

import pytest

from whiskey.ai.resources import TokenBucket, TokenLease


@pytest.mark.unit
class TestTokenBucket:
    """Test TokenBucket implementation."""
    
    @pytest.mark.asyncio
    async def test_basic_acquire_release(self):
        """Test basic token acquisition and release."""
        bucket = TokenBucket(capacity=100, refill_rate=10.0)
        
        # Initial capacity should be available
        assert await bucket.available() == 100
        
        # Acquire some tokens
        lease = await bucket.acquire(30)
        assert isinstance(lease, TokenLease)
        assert lease.tokens == 30
        assert await bucket.available() == 70
        
        # Release tokens
        await lease.release()
        assert await bucket.available() == 100
    
    @pytest.mark.asyncio
    async def test_refill_mechanism(self):
        """Test token refill over time."""
        bucket = TokenBucket(capacity=100, refill_rate=50.0, initial_tokens=0)
        
        # Start with no tokens
        assert await bucket.available() == 0
        
        # Wait for tokens to refill
        await asyncio.sleep(0.1)  # Should add ~5 tokens
        available = await bucket.available()
        assert 4 <= available <= 6  # Allow for timing variations
        
        # Wait more
        await asyncio.sleep(0.1)  # Should add ~5 more tokens
        available = await bucket.available()
        assert 9 <= available <= 11
    
    @pytest.mark.asyncio
    async def test_capacity_limit(self):
        """Test that tokens don't exceed capacity."""
        bucket = TokenBucket(capacity=50, refill_rate=100.0, initial_tokens=40)
        
        # Wait for refill
        await asyncio.sleep(0.2)  # Would add 20 tokens
        
        # Should be capped at capacity
        assert await bucket.available() == 50
    
    @pytest.mark.asyncio
    async def test_acquire_more_than_capacity(self):
        """Test acquiring more tokens than capacity."""
        bucket = TokenBucket(capacity=50, refill_rate=10.0)
        
        with pytest.raises(ValueError, match="Cannot acquire 60 tokens"):
            await bucket.acquire(60)
    
    @pytest.mark.asyncio
    async def test_acquire_no_wait(self):
        """Test acquiring without waiting."""
        bucket = TokenBucket(capacity=100, refill_rate=10.0, initial_tokens=30)
        
        # Can acquire available tokens
        lease = await bucket.acquire(20, wait=False)
        assert lease is not None
        assert lease.tokens == 20
        
        # Cannot acquire more than available
        lease = await bucket.acquire(20, wait=False)
        assert lease is None
    
    @pytest.mark.asyncio
    async def test_acquire_with_wait(self):
        """Test acquiring with waiting."""
        bucket = TokenBucket(capacity=100, refill_rate=100.0, initial_tokens=10)
        
        start = time.time()
        
        # Need 30 tokens, have 10, need to wait for 20
        # At 100 tokens/sec, should take ~0.2 seconds
        lease = await bucket.acquire(30, wait=True)
        
        elapsed = time.time() - start
        assert lease is not None
        assert 0.15 <= elapsed <= 0.25  # Allow for timing variations
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test context manager for automatic release."""
        bucket = TokenBucket(capacity=100, refill_rate=10.0)
        
        async with bucket.acquire_context(40) as lease:
            assert lease is not None
            assert await bucket.available() == 60
        
        # Should be released automatically
        assert await bucket.available() == 100
    
    @pytest.mark.asyncio
    async def test_wait_time_calculation(self):
        """Test wait time calculation."""
        bucket = TokenBucket(capacity=100, refill_rate=50.0, initial_tokens=20)
        
        # No wait for available tokens
        assert await bucket.wait_time(10) == 0.0
        
        # Calculate wait for unavailable tokens
        # Need 50 tokens, have 20, need 30 more
        # At 50 tokens/sec, should take 0.6 seconds
        wait = await bucket.wait_time(50)
        assert 0.55 <= wait <= 0.65
        
        # Infinite wait for more than capacity
        assert await bucket.wait_time(150) == float('inf')
    
    @pytest.mark.asyncio
    async def test_concurrent_access(self):
        """Test concurrent token acquisition."""
        bucket = TokenBucket(capacity=100, refill_rate=0.0, initial_tokens=100)
        
        # Create multiple concurrent acquirers
        async def acquire_tokens(amount: int) -> TokenLease:
            return await bucket.acquire(amount)
        
        # Run concurrent acquisitions
        leases = await asyncio.gather(
            acquire_tokens(20),
            acquire_tokens(30),
            acquire_tokens(25),
            acquire_tokens(25)
        )
        
        # All should succeed and total to 100
        assert all(lease is not None for lease in leases)
        assert sum(lease.tokens for lease in leases) == 100
        assert await bucket.available() == 0
    
    @pytest.mark.asyncio
    async def test_double_release_protection(self):
        """Test that double release is protected."""
        bucket = TokenBucket(capacity=100, refill_rate=10.0)
        
        lease = await bucket.acquire(30)
        assert await bucket.available() == 70
        
        # First release
        await lease.release()
        assert await bucket.available() == 100
        
        # Second release should do nothing
        await lease.release()
        assert await bucket.available() == 100  # Still 100, not 130