"""Tests for queue implementations."""

import asyncio

import pytest

from whiskey_jobs.job import Job
from whiskey_jobs.queue import MemoryQueue, MultiQueue, PriorityQueue
from whiskey_jobs.types import JobMetadata, JobPriority


class TestMemoryQueue:
    """Test MemoryQueue implementation."""
    
    @pytest.mark.asyncio
    async def test_fifo_order(self):
        """Test FIFO ordering."""
        queue = MemoryQueue()
        
        # Create jobs
        jobs = []
        for i in range(5):
            metadata = JobMetadata(func=lambda: None, name=f"job{i}")
            job = Job(metadata)
            jobs.append(job)
            await queue.push(job)
        
        # Pop in FIFO order
        for i in range(5):
            popped = await queue.pop()
            assert popped is jobs[i]
        
        # Queue should be empty
        assert await queue.pop() is None
    
    @pytest.mark.asyncio
    async def test_peek(self):
        """Test peeking at queue."""
        queue = MemoryQueue()
        
        # Empty queue
        assert await queue.peek() is None
        
        # Add job
        metadata = JobMetadata(func=lambda: None, name="test")
        job = Job(metadata)
        await queue.push(job)
        
        # Peek should return job without removing
        peeked = await queue.peek()
        assert peeked is job
        assert queue.size() == 1
        
        # Pop should return same job
        popped = await queue.pop()
        assert popped is job
        assert queue.size() == 0
    
    def test_size_and_clear(self):
        """Test size and clear operations."""
        queue = MemoryQueue()
        
        assert queue.size() == 0
        
        # Add jobs synchronously (testing internal state)
        for i in range(3):
            metadata = JobMetadata(func=lambda: None, name=f"job{i}")
            job = Job(metadata)
            queue._queue.append(job)
        
        assert queue.size() == 3
        
        queue.clear()
        assert queue.size() == 0


class TestPriorityQueue:
    """Test PriorityQueue implementation."""
    
    @pytest.mark.asyncio
    async def test_priority_order(self):
        """Test priority ordering."""
        queue = PriorityQueue()
        
        # Add jobs with different priorities
        jobs = [
            (JobPriority.LOW, "low"),
            (JobPriority.CRITICAL, "critical"),
            (JobPriority.NORMAL, "normal"),
            (JobPriority.HIGH, "high"),
        ]
        
        for priority, name in jobs:
            metadata = JobMetadata(
                func=lambda: None,
                name=name,
                priority=priority
            )
            job = Job(metadata)
            await queue.push(job)
        
        # Should pop in priority order
        popped1 = await queue.pop()
        assert popped1.name == "critical"
        
        popped2 = await queue.pop()
        assert popped2.name == "high"
        
        popped3 = await queue.pop()
        assert popped3.name == "normal"
        
        popped4 = await queue.pop()
        assert popped4.name == "low"
    
    @pytest.mark.asyncio
    async def test_same_priority_fifo(self):
        """Test FIFO order for same priority."""
        queue = PriorityQueue()
        
        # Add multiple jobs with same priority
        jobs = []
        for i in range(3):
            metadata = JobMetadata(
                func=lambda: None,
                name=f"job{i}",
                priority=JobPriority.NORMAL
            )
            job = Job(metadata)
            jobs.append(job)
            await queue.push(job)
        
        # Should maintain FIFO for same priority
        for i in range(3):
            popped = await queue.pop()
            assert popped is jobs[i]
    
    @pytest.mark.asyncio
    async def test_peek_highest_priority(self):
        """Test peeking returns highest priority job."""
        queue = PriorityQueue()
        
        # Add low priority first
        low_metadata = JobMetadata(
            func=lambda: None,
            name="low",
            priority=JobPriority.LOW
        )
        low_job = Job(low_metadata)
        await queue.push(low_job)
        
        # Add high priority
        high_metadata = JobMetadata(
            func=lambda: None,
            name="high",
            priority=JobPriority.HIGH
        )
        high_job = Job(high_metadata)
        await queue.push(high_job)
        
        # Peek should return high priority
        peeked = await queue.peek()
        assert peeked is high_job


class TestMultiQueue:
    """Test MultiQueue implementation."""
    
    @pytest.mark.asyncio
    async def test_multiple_queues(self):
        """Test managing multiple named queues."""
        multi_queue = MultiQueue()
        
        # Add jobs to different queues
        for queue_name in ["emails", "uploads", "analytics"]:
            for i in range(2):
                metadata = JobMetadata(
                    func=lambda: None,
                    name=f"{queue_name}_job{i}",
                    queue=queue_name
                )
                job = Job(metadata)
                await multi_queue.push(job)
        
        # Check queue list
        queues = multi_queue.list_queues()
        assert set(queues) == {"emails", "uploads", "analytics"}
        
        # Check sizes
        assert multi_queue.size("emails") == 2
        assert multi_queue.size("uploads") == 2
        assert multi_queue.size("analytics") == 2
        assert multi_queue.size() == 6  # Total
        
        # Pop from specific queue
        email_job = await multi_queue.pop("emails")
        assert email_job.name.startswith("emails_job")
        assert multi_queue.size("emails") == 1
        assert multi_queue.size() == 5
    
    @pytest.mark.asyncio
    async def test_queue_factory(self):
        """Test custom queue factory."""
        # Use priority queues
        multi_queue = MultiQueue(queue_factory=PriorityQueue)
        
        # Add jobs with different priorities
        metadata1 = JobMetadata(
            func=lambda: None,
            name="low",
            queue="test",
            priority=JobPriority.LOW
        )
        metadata2 = JobMetadata(
            func=lambda: None,
            name="high",
            queue="test",
            priority=JobPriority.HIGH
        )
        
        job1 = Job(metadata1)
        job2 = Job(metadata2)
        
        await multi_queue.push(job1)
        await multi_queue.push(job2)
        
        # Should get high priority first
        popped = await multi_queue.pop("test")
        assert popped.name == "high"
    
    @pytest.mark.asyncio
    async def test_clear_operations(self):
        """Test clearing queues."""
        multi_queue = MultiQueue()
        
        # Add jobs to multiple queues
        for queue_name in ["q1", "q2"]:
            metadata = JobMetadata(
                func=lambda: None,
                name=f"{queue_name}_job",
                queue=queue_name
            )
            job = Job(metadata)
            await multi_queue.push(job)
        
        # Clear specific queue
        multi_queue.clear("q1")
        assert multi_queue.size("q1") == 0
        assert multi_queue.size("q2") == 1
        
        # Clear all
        multi_queue.clear()
        assert multi_queue.size() == 0
    
    @pytest.mark.asyncio
    async def test_auto_queue_creation(self):
        """Test automatic queue creation."""
        multi_queue = MultiQueue()
        
        # Get non-existent queue
        queue = await multi_queue.get_queue("new_queue")
        assert queue is not None
        assert isinstance(queue, MemoryQueue)
        
        # Should be in queue list now
        assert "new_queue" in multi_queue.list_queues()