"""Tests for job manager implementation."""

import asyncio
from datetime import datetime

import pytest
from whiskey import Whiskey

from whiskey_jobs.manager import JobManager
from whiskey_jobs.types import JobPriority, JobStatus


class TestJobManager:
    """Test JobManager functionality."""

    @pytest.mark.asyncio
    async def test_manager_lifecycle(self, app_with_jobs: Whiskey):
        """Test starting and stopping manager."""
        manager = JobManager(app_with_jobs.container)

        assert not manager._running

        await manager.start()
        assert manager._running
        assert manager.worker_pool._running
        assert manager.scheduler._running

        await manager.stop()
        assert not manager._running

    def test_register_job(self, app_with_jobs: Whiskey):
        """Test registering jobs."""
        manager = JobManager(app_with_jobs.container)

        def test_func(x: int) -> int:
            return x * 2

        metadata = manager.register_job(
            func=test_func,
            name="double",
            queue="math",
            priority=JobPriority.HIGH,
            max_retries=5,
            timeout=30,
            tags=["math", "compute"],
            description="Doubles a number",
        )

        assert metadata.name == "double"
        assert metadata.queue == "math"
        assert metadata.priority == JobPriority.HIGH
        assert metadata.max_retries == 5
        assert metadata.timeout == 30
        assert "math" in metadata.tags
        assert metadata.description == "Doubles a number"

        # Check it's stored
        assert "double" in manager._job_metadata

    def test_register_job_defaults(self, app_with_jobs: Whiskey):
        """Test registering job with defaults."""
        manager = JobManager(app_with_jobs.container)

        def my_job():
            """Job docstring."""
            pass

        metadata = manager.register_job(my_job)

        assert metadata.name == "my_job"  # Function name
        assert metadata.queue == "default"
        assert metadata.priority == JobPriority.NORMAL
        assert metadata.description == "Job docstring."

    def test_register_scheduled_job(self, app_with_jobs: Whiskey):
        """Test registering scheduled jobs."""
        manager = JobManager(app_with_jobs.container)

        def scheduled_func():
            return "scheduled"

        # Cron-based
        metadata = manager.register_scheduled_job(
            func=scheduled_func, name="hourly", cron="0 * * * *", queue="scheduled"
        )

        assert metadata.name == "hourly"
        assert metadata.cron == "0 * * * *"
        assert metadata.interval is None

        # Interval-based
        metadata2 = manager.register_scheduled_job(
            func=scheduled_func,
            name="periodic",
            interval=300,  # 5 minutes
            start_date=datetime.now(),
            timezone="US/Eastern",
        )

        assert metadata2.interval == 300
        assert metadata2.cron is None
        assert metadata2.timezone == "US/Eastern"

    @pytest.mark.asyncio
    async def test_enqueue_registered_job(self, app_with_jobs: Whiskey):
        """Test enqueueing registered jobs."""
        manager = JobManager(app_with_jobs.container)

        # Register job
        async def process_data(data: dict) -> dict:
            return {"processed": True, **data}

        manager.register_job(process_data, queue="processing")

        # Enqueue
        job = await manager.enqueue("process_data", {"value": 42})

        assert job.name == "process_data"
        assert job.queue == "processing"
        assert job.args == ({"value": 42},)

        # Check it's in queue
        assert manager.queues.size("processing") == 1

    @pytest.mark.asyncio
    async def test_enqueue_unregistered_job_error(self, app_with_jobs: Whiskey):
        """Test error when enqueueing unregistered job."""
        manager = JobManager(app_with_jobs.container)

        with pytest.raises(ValueError, match="Job 'unknown' not registered"):
            await manager.enqueue("unknown")

    @pytest.mark.asyncio
    async def test_enqueue_func(self, app_with_jobs: Whiskey):
        """Test enqueueing ad-hoc functions."""
        manager = JobManager(app_with_jobs.container)

        def adhoc_func(x: int) -> int:
            return x + 1

        job = await manager.enqueue_func(adhoc_func, 5, queue="quick", priority=JobPriority.LOW)

        assert job.name == "adhoc_func"
        assert job.queue == "quick"
        assert job.priority == JobPriority.LOW
        assert job.args == (5,)

    @pytest.mark.asyncio
    async def test_wait_for_job(self, app_with_jobs: Whiskey):
        """Test waiting for job completion."""
        manager = JobManager(app_with_jobs.container)
        await manager.start()

        # Quick job
        async def quick_job():
            await asyncio.sleep(0.1)
            return "done"

        manager.register_job(quick_job)
        job = await manager.enqueue("quick_job")

        # Wait for completion
        result = await manager.wait_for_job(job, timeout=1)
        assert result.status == JobStatus.COMPLETED
        assert result.result == "done"

        # Test with job ID
        job2 = await manager.enqueue("quick_job")
        result2 = await manager.wait_for_job(job2.job_id, timeout=1)
        assert result2.status == JobStatus.COMPLETED

        await manager.stop()

    @pytest.mark.asyncio
    async def test_wait_for_job_timeout(self, app_with_jobs: Whiskey):
        """Test timeout when waiting for job."""
        manager = JobManager(app_with_jobs.container)

        # Don't start manager, so job won't complete
        async def slow_job():
            await asyncio.sleep(10)

        manager.register_job(slow_job)
        job = await manager.enqueue("slow_job")

        with pytest.raises(TimeoutError):
            await manager.wait_for_job(job, timeout=0.1)

    def test_list_jobs(self, app_with_jobs: Whiskey):
        """Test listing registered jobs."""
        manager = JobManager(app_with_jobs.container)

        # Register multiple jobs
        manager.register_job(lambda: None, name="job1")
        manager.register_job(lambda: None, name="job2")
        manager.register_job(lambda: None, name="job3")

        jobs = manager.list_jobs()
        assert len(jobs) == 3
        assert set(jobs) == {"job1", "job2", "job3"}

    def test_get_stats(self, app_with_jobs: Whiskey):
        """Test getting manager statistics."""
        manager = JobManager(app_with_jobs.container)

        manager.register_job(lambda: None, name="job1")
        manager.register_scheduled_job(lambda: None, name="scheduled1", interval=60)

        stats = manager.get_stats()

        assert stats["running"] is False
        assert stats["registered_jobs"] == 1
        assert stats["scheduled_jobs"] == 1
        assert "queues" in stats
        assert "worker_pool" in stats
        assert "scheduler" in stats

    @pytest.mark.asyncio
    async def test_clear_queue(self, app_with_jobs: Whiskey):
        """Test clearing queues."""
        manager = JobManager(app_with_jobs.container)

        # Add jobs to different queues
        await manager.enqueue_func(lambda: None, queue="q1")
        await manager.enqueue_func(lambda: None, queue="q1")
        await manager.enqueue_func(lambda: None, queue="q2")

        assert manager.queues.size() == 3

        # Clear specific queue
        await manager.clear_queue("q1")
        assert manager.queues.size("q1") == 0
        assert manager.queues.size("q2") == 1

        # Clear all
        await manager.clear_queue()
        assert manager.queues.size() == 0


class TestJobChainBuilder:
    """Test JobChainBuilder functionality."""

    @pytest.mark.asyncio
    async def test_simple_chain(self, app_with_jobs: Whiskey):
        """Test building a simple job chain."""
        manager = JobManager(app_with_jobs.container)

        # Register jobs
        manager.register_job(lambda: "step1", name="step1")
        manager.register_job(lambda x: f"step2_{x}", name="step2")
        manager.register_job(lambda: "step3", name="step3")

        # Build chain
        chain = manager.create_job_chain()
        first_job = await chain.add("step1").add("step2", "data").add("step3").enqueue()

        assert first_job.name == "step1"
        assert first_job._on_success.name == "step2"
        assert first_job._on_success._on_success.name == "step3"

        # Only first job should be queued
        assert manager.queues.size() == 1

    @pytest.mark.asyncio
    async def test_chain_with_unregistered_job(self, app_with_jobs: Whiskey):
        """Test chain with unregistered job."""
        manager = JobManager(app_with_jobs.container)

        chain = manager.create_job_chain()

        with pytest.raises(ValueError, match="Job 'unknown' not registered"):
            chain.add("unknown")

    @pytest.mark.asyncio
    async def test_empty_chain_error(self, app_with_jobs: Whiskey):
        """Test error with empty chain."""
        manager = JobManager(app_with_jobs.container)

        chain = manager.create_job_chain()

        with pytest.raises(ValueError, match="No jobs in chain"):
            await chain.enqueue()
