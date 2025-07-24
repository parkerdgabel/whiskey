"""Tests for AI resource manager."""

import asyncio

import pytest

from whiskey.ai.resources import AIResourceManager
from whiskey.ai.resources.manager import ResourceConfig
from whiskey.core.decorators import get_default_container


@pytest.mark.unit
class TestAIResourceManager:
    """Test AIResourceManager implementation."""
    
    @pytest.mark.asyncio
    async def test_basic_configuration(self):
        """Test basic model configuration."""
        manager = AIResourceManager()
        
        config = ResourceConfig(
            max_tokens_per_minute=1000,
            max_requests_per_minute=10
        )
        
        await manager.configure_model("gpt-4", config)
        
        # Should be able to check availability
        availability = await manager.get_token_availability("gpt-4")
        assert "minute" in availability
        assert availability["minute"] == 1000
    
    @pytest.mark.asyncio
    async def test_token_acquisition(self):
        """Test token acquisition across periods."""
        manager = AIResourceManager()
        
        config = ResourceConfig(
            max_tokens_per_minute=100,
            max_tokens_per_hour=1000
        )
        
        await manager.configure_model("gpt-4", config)
        
        # Acquire tokens
        leases = await manager.acquire_tokens("gpt-4", 50)
        assert leases is not None
        assert len(leases) == 2  # One for minute, one for hour
        
        # Check availability
        availability = await manager.get_token_availability("gpt-4")
        assert availability["minute"] == 50
        assert availability["hour"] == 950
        
        # Release tokens
        for lease in leases:
            await lease.release()
        
        # Should be back to full
        availability = await manager.get_token_availability("gpt-4")
        assert availability["minute"] == 100
        assert availability["hour"] == 1000
    
    @pytest.mark.asyncio
    async def test_token_acquisition_failure(self):
        """Test token acquisition when not enough tokens."""
        manager = AIResourceManager()
        
        config = ResourceConfig(max_tokens_per_minute=50)
        await manager.configure_model("gpt-4", config)
        
        # Try to acquire more than available
        leases = await manager.acquire_tokens("gpt-4", 60, wait=False)
        assert leases is None
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        """Test request rate limiting."""
        manager = AIResourceManager()
        
        config = ResourceConfig(
            max_requests_per_minute=3,
            max_requests_per_hour=100
        )
        
        await manager.configure_model("gpt-4", config)
        
        # First 3 requests should succeed
        for i in range(3):
            assert await manager.acquire_request_slot("gpt-4")
        
        # 4th request should fail without wait
        assert not await manager.acquire_request_slot("gpt-4", wait=False)
    
    @pytest.mark.asyncio
    async def test_cost_tracking(self):
        """Test cost tracking and limits."""
        manager = AIResourceManager()
        
        config = ResourceConfig(
            max_cost_per_hour=10.0,
            max_cost_per_day=100.0
        )
        
        await manager.configure_model("gpt-4", config)
        
        # Track costs within limits
        assert await manager.track_cost("gpt-4", 5.0)
        assert await manager.track_cost("gpt-4", 4.0)
        
        # Should fail when exceeding hourly limit
        assert not await manager.track_cost("gpt-4", 2.0)
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test token acquisition with context manager."""
        manager = AIResourceManager()
        
        config = ResourceConfig(max_tokens_per_minute=100)
        await manager.configure_model("gpt-4", config)
        
        async with manager.acquire_tokens_context("gpt-4", 40) as leases:
            assert leases is not None
            availability = await manager.get_token_availability("gpt-4")
            assert availability["minute"] == 60
        
        # Should be released
        availability = await manager.get_token_availability("gpt-4")
        assert availability["minute"] == 100
    
    @pytest.mark.asyncio
    async def test_wait_times(self):
        """Test wait time calculations."""
        manager = AIResourceManager()
        
        config = ResourceConfig(
            max_tokens_per_minute=100,
            max_requests_per_minute=2
        )
        
        await manager.configure_model("gpt-4", config)
        
        # Use up tokens
        await manager.acquire_tokens("gpt-4", 80)
        
        # Check wait times
        wait_times = await manager.get_wait_times("gpt-4", 40)
        assert "tokens_minute" in wait_times
        assert wait_times["tokens_minute"] > 0  # Need to wait for tokens
    
    @pytest.mark.asyncio
    async def test_model_without_limits(self):
        """Test model without configured limits."""
        manager = AIResourceManager()
        
        # Should work without limits
        assert await manager.check_rate_limit("gpt-3.5")
        assert await manager.acquire_request_slot("gpt-3.5")
        assert await manager.track_cost("gpt-3.5", 100.0)
        
        leases = await manager.acquire_tokens("gpt-3.5", 1000)
        assert leases is not None
        assert len(leases) == 1  # Default lease
    
    @pytest.mark.asyncio
    async def test_reset_functionality(self):
        """Test resetting resource tracking."""
        manager = AIResourceManager()
        
        config = ResourceConfig(
            max_cost_per_hour=10.0,
            max_requests_per_minute=5
        )
        
        await manager.configure_model("gpt-4", config)
        
        # Use up some resources
        await manager.track_cost("gpt-4", 8.0)
        for _ in range(3):
            await manager.acquire_request_slot("gpt-4")
        
        # Reset specific model
        await manager.reset("gpt-4")
        
        # Should be able to use resources again
        assert await manager.track_cost("gpt-4", 8.0)
    
    @pytest.mark.asyncio
    async def test_singleton_behavior(self):
        """Test that resource manager is a singleton."""
        container = get_default_container()
        
        manager1 = await container.resolve(AIResourceManager)
        manager2 = await container.resolve(AIResourceManager)
        
        assert manager1 is manager2