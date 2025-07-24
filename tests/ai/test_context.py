"""Tests for AI context management."""

import asyncio
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from whiskey.ai.context import AIContext
from whiskey.ai.context.ai_context import (
    AIContextManager,
    get_current_context,
    set_current_context,
)


class TestAIContext:
    """Test AIContext functionality."""
    
    @pytest.mark.unit
    def test_ai_context_creation(self):
        """Test creating AI context with defaults."""
        ctx = AIContext()
        
        assert isinstance(ctx.id, UUID)
        assert ctx.conversation_id is None
        assert isinstance(ctx.created_at, datetime)
        assert ctx.prompt_tokens == 0
        assert ctx.completion_tokens == 0
        assert ctx.total_tokens == 0
        assert ctx.prompt_cost == 0.0
        assert ctx.completion_cost == 0.0
        assert ctx.total_cost == 0.0
        assert ctx.model is None
        assert ctx.provider is None
        assert ctx.metadata == {}
        assert ctx.messages == []
        assert ctx.parent is None
    
    @pytest.mark.unit
    def test_ai_context_with_values(self):
        """Test creating AI context with custom values."""
        conv_id = uuid4()
        ctx = AIContext(
            conversation_id=conv_id,
            model="gpt-4",
            provider="openai",
            metadata={"temperature": 0.7}
        )
        
        assert ctx.conversation_id == conv_id
        assert ctx.model == "gpt-4"
        assert ctx.provider == "openai"
        assert ctx.metadata["temperature"] == 0.7
    
    @pytest.mark.unit
    def test_add_usage(self):
        """Test adding token usage and costs."""
        ctx = AIContext()
        
        ctx.add_usage(
            prompt_tokens=100,
            completion_tokens=50,
            prompt_cost=0.01,
            completion_cost=0.02
        )
        
        assert ctx.prompt_tokens == 100
        assert ctx.completion_tokens == 50
        assert ctx.total_tokens == 150
        assert ctx.prompt_cost == 0.01
        assert ctx.completion_cost == 0.02
        assert ctx.total_cost == 0.03
        
        # Add more usage
        ctx.add_usage(
            prompt_tokens=50,
            completion_tokens=25,
            prompt_cost=0.005,
            completion_cost=0.01
        )
        
        assert ctx.prompt_tokens == 150
        assert ctx.completion_tokens == 75
        assert ctx.total_tokens == 225
        assert ctx.prompt_cost == 0.015
        assert ctx.completion_cost == 0.03
        assert ctx.total_cost == 0.045
    
    @pytest.mark.unit
    def test_add_message(self):
        """Test adding messages to conversation history."""
        ctx = AIContext()
        
        ctx.add_message("user", "Hello")
        ctx.add_message("assistant", "Hi there!", model="gpt-4")
        
        assert len(ctx.messages) == 2
        
        assert ctx.messages[0]["role"] == "user"
        assert ctx.messages[0]["content"] == "Hello"
        assert "timestamp" in ctx.messages[0]
        
        assert ctx.messages[1]["role"] == "assistant"
        assert ctx.messages[1]["content"] == "Hi there!"
        assert ctx.messages[1]["model"] == "gpt-4"
    
    @pytest.mark.unit
    def test_create_child(self):
        """Test creating child context."""
        parent = AIContext(
            model="gpt-4",
            provider="openai"
        )
        
        child = parent.create_child()
        
        assert child.parent is parent
        assert child.conversation_id == parent.id
        assert child.model == parent.model
        assert child.provider == parent.provider
        assert child.id != parent.id
    
    @pytest.mark.unit
    def test_create_child_with_conversation_id(self):
        """Test creating child context when parent has conversation_id."""
        conv_id = uuid4()
        parent = AIContext(
            conversation_id=conv_id,
            model="gpt-4"
        )
        
        child = parent.create_child()
        
        assert child.conversation_id == conv_id
        assert child.parent is parent
    
    @pytest.mark.unit
    def test_get_conversation_history(self):
        """Test getting conversation history."""
        ctx = AIContext()
        
        ctx.add_message("user", "Message 1")
        ctx.add_message("assistant", "Response 1")
        ctx.add_message("user", "Message 2")
        ctx.add_message("assistant", "Response 2")
        
        # Get all messages
        history = ctx.get_conversation_history()
        assert len(history) == 4
        assert history[0]["content"] == "Message 1"
        
        # Get last 2 messages
        recent = ctx.get_conversation_history(max_messages=2)
        assert len(recent) == 2
        assert recent[0]["content"] == "Message 2"
        assert recent[1]["content"] == "Response 2"
    
    @pytest.mark.unit
    def test_to_dict(self):
        """Test converting context to dictionary."""
        ctx = AIContext(
            model="gpt-4",
            provider="openai",
            metadata={"temperature": 0.7}
        )
        
        ctx.add_usage(prompt_tokens=100, completion_tokens=50)
        ctx.add_message("user", "Test message")
        
        data = ctx.to_dict()
        
        assert isinstance(data["id"], str)
        assert data["conversation_id"] is None
        assert isinstance(data["created_at"], str)
        assert data["prompt_tokens"] == 100
        assert data["completion_tokens"] == 50
        assert data["total_tokens"] == 150
        assert data["model"] == "gpt-4"
        assert data["provider"] == "openai"
        assert data["metadata"] == {"temperature": 0.7}
        assert data["message_count"] == 1


class TestContextManagement:
    """Test context variable management."""
    
    @pytest.mark.unit
    def test_get_current_context_none(self):
        """Test getting context when none is set."""
        ctx = get_current_context()
        assert ctx is None
    
    @pytest.mark.unit
    def test_set_get_current_context(self):
        """Test setting and getting current context."""
        ctx = AIContext(model="gpt-4")
        
        token = set_current_context(ctx)
        
        current = get_current_context()
        assert current is ctx
        assert current.model == "gpt-4"
        
        # Reset context
        import contextvars
        contextvars.copy_context()
    
    @pytest.mark.unit
    async def test_context_isolation_async(self):
        """Test context isolation between async tasks."""
        results = []
        
        async def task_with_context(model: str):
            ctx = AIContext(model=model)
            set_current_context(ctx)
            
            await asyncio.sleep(0.01)
            
            current = get_current_context()
            results.append(current.model)
        
        # Run multiple tasks concurrently
        await asyncio.gather(
            task_with_context("gpt-3.5"),
            task_with_context("gpt-4"),
            task_with_context("claude")
        )
        
        # Each task should see its own context
        assert sorted(results) == ["claude", "gpt-3.5", "gpt-4"]


class TestAIContextManager:
    """Test AIContextManager functionality."""
    
    @pytest.mark.unit
    async def test_async_context_manager(self):
        """Test async context manager."""
        assert get_current_context() is None
        
        async with AIContextManager(model="gpt-4") as ctx:
            assert get_current_context() is ctx
            assert ctx.model == "gpt-4"
        
        assert get_current_context() is None
    
    @pytest.mark.unit
    def test_sync_context_manager(self):
        """Test sync context manager."""
        assert get_current_context() is None
        
        with AIContextManager(model="gpt-4") as ctx:
            assert get_current_context() is ctx
            assert ctx.model == "gpt-4"
        
        assert get_current_context() is None
    
    @pytest.mark.unit
    async def test_context_manager_with_metadata(self):
        """Test context manager with metadata."""
        async with AIContextManager(
            model="gpt-4",
            provider="openai",
            temperature=0.7,
            max_tokens=1000
        ) as ctx:
            assert ctx.model == "gpt-4"
            assert ctx.provider == "openai"
            assert ctx.metadata["temperature"] == 0.7
            assert ctx.metadata["max_tokens"] == 1000
    
    @pytest.mark.unit
    async def test_nested_context_managers(self):
        """Test nested context managers."""
        async with AIContextManager(model="gpt-4") as ctx1:
            assert get_current_context() is ctx1
            
            async with AIContextManager(model="gpt-3.5") as ctx2:
                assert get_current_context() is ctx2
                assert ctx2.model == "gpt-3.5"
            
            # Back to ctx1
            assert get_current_context() is ctx1
            assert ctx1.model == "gpt-4"
    
    @pytest.mark.unit
    async def test_context_manager_with_conversation_id(self):
        """Test context manager with conversation ID."""
        conv_id = uuid4()
        
        async with AIContextManager(conversation_id=conv_id) as ctx:
            assert ctx.conversation_id == conv_id
    
    @pytest.mark.unit
    async def test_context_usage_tracking(self):
        """Test usage tracking within context."""
        async with AIContextManager(model="gpt-4") as ctx:
            ctx.add_usage(
                prompt_tokens=100,
                completion_tokens=50,
                prompt_cost=0.01,
                completion_cost=0.02
            )
            
            assert ctx.total_tokens == 150
            assert ctx.total_cost == 0.03
    
    @pytest.mark.unit
    async def test_concurrent_contexts(self):
        """Test concurrent context managers."""
        results = []
        
        async def task_with_context_manager(model: str):
            async with AIContextManager(model=model) as ctx:
                await asyncio.sleep(0.01)
                ctx.add_usage(prompt_tokens=100)
                results.append((model, ctx.prompt_tokens))
        
        await asyncio.gather(
            task_with_context_manager("gpt-3.5"),
            task_with_context_manager("gpt-4"),
            task_with_context_manager("claude")
        )
        
        # Each context should track its own usage
        assert len(results) == 3
        for model, tokens in results:
            assert tokens == 100