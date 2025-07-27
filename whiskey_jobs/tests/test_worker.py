"""Tests for job worker implementation."""

import asyncio

import pytest
from whiskey import Whiskey

from whiskey_jobs.job import Job
from whiskey_jobs.queue import MultiQueue
from whiskey_jobs.types import JobMetadata
from whiskey_jobs.worker import JobWorker, WorkerPool


class TestJobWorker:
    """Test JobWorker functionality."""

    @pytest.mark.asyncio
    async def test_worker_basic_processing(self, app_with_jobs: Whiskey):
        """Test basic job processing."""
        queues = MultiQueue()
        worker = JobWorker(app_with_jobs.container, queues, name="test-worker")

        # Add a simple job
        async def simple_job():
            return "completed"

        metadata = JobMetadata(func=simple_job, name="simple")
        job = Job(metadata)
        await queues.push(job)

        # Start worker
        await worker.start()

        # Wait for job to be processed
        await asyncio.sleep(0.2)

        # Check stats
        stats = worker.get_stats()
        assert stats["name"] == "test-worker"
        assert stats["processed"] == 1
        assert stats["failed"] == 0

        await worker.stop()

    @pytest.mark.asyncio
    async def test_worker_multiple_queues(self, app_with_jobs: Whiskey):
        """Test worker monitoring multiple queues."""
        queues = MultiQueue()
        worker = JobWorker(app_with_jobs.container, queues)

        # Monitor specific queues
        worker.monitor_queues("emails", "uploads")

        # Add jobs to different queues
        for queue_name in ["emails", "uploads", "other"]:
            metadata = JobMetadata(
                func=lambda q=queue_name: f"processed_{q}",
                name=f"{queue_name}_job",
                queue=queue_name,
            )
            job = Job(metadata)
            await queues.push(job)

        await worker.start()
        await asyncio.sleep(0.3)

        # Workers now monitor all queues by default (monitor_queues is ignored)
        assert worker._processed_count == 3
        assert queues.size("other") == 0

        await worker.stop()

    @pytest.mark.asyncio
    async def test_worker_failure_handling(self, app_with_jobs: Whiskey):
        """Test handling job failures."""
        queues = MultiQueue()
        worker = JobWorker(app_with_jobs.container, queues)

        async def failing_job():
            raise ValueError("Test failure")

        metadata = JobMetadata(
            func=failing_job,
            name="failing",
            max_retries=0,  # No retries
        )
        job = Job(metadata)
        await queues.push(job)

        await worker.start()
        await asyncio.sleep(0.2)

        assert worker._failed_count == 1
        assert worker._processed_count == 0

        await worker.stop()

    @pytest.mark.asyncio
    async def test_worker_retry_logic(self, app_with_jobs: Whiskey):
        """Test job retry logic."""
        queues = MultiQueue()
        worker = JobWorker(app_with_jobs.container, queues)

        call_count = 0

        async def flaky_job():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Still failing")
            return "success"

        metadata = JobMetadata(func=flaky_job, name="flaky", max_retries=3, retry_delay=0.1)
        job = Job(metadata)
        await queues.push(job)

        await worker.start()
        await asyncio.sleep(1)  # Allow time for retries

        # Should eventually succeed
        assert call_count == 3
        assert worker._processed_count == 1

        await worker.stop()

    @pytest.mark.asyncio
    async def test_worker_concurrency(self, app_with_jobs: Whiskey):
        """Test concurrent job processing."""
        queues = MultiQueue()
        worker = JobWorker(app_with_jobs.container, queues, concurrency=3)

        # Track concurrent executions
        concurrent_count = 0
        max_concurrent = 0
        lock = asyncio.Lock()

        async def concurrent_job():
            nonlocal concurrent_count, max_concurrent
            async with lock:
                concurrent_count += 1
                max_concurrent = max(max_concurrent, concurrent_count)

            await asyncio.sleep(0.2)

            async with lock:
                concurrent_count -= 1
            return "done"

        # Add more jobs than concurrency limit
        for i in range(6):
            metadata = JobMetadata(func=concurrent_job, name=f"job{i}")
            job = Job(metadata)
            await queues.push(job)

        await worker.start()
        await asyncio.sleep(0.5)

        # Should respect concurrency limit
        assert max_concurrent <= 3
        assert worker._processed_count == 6

        await worker.stop()

    @pytest.mark.asyncio
    async def test_worker_job_chaining(self, app_with_jobs: Whiskey):
        """Test job chaining execution."""
        queues = MultiQueue()
        worker = JobWorker(app_with_jobs.container, queues)

        results = []

        async def job1():
            results.append("job1")
            return "success"

        async def job2():
            results.append("job2")
            return "success"

        async def job3():
            results.append("job3")
            return "success"

        # Create chained jobs
        metadata1 = JobMetadata(func=job1, name="job1")
        metadata2 = JobMetadata(func=job2, name="job2")
        metadata3 = JobMetadata(func=job3, name="job3")

        j1 = Job(metadata1)
        j2 = Job(metadata2)
        j3 = Job(metadata3)

        j1.on_success(j2)
        j1.on_failure(j3)

        await queues.push(j1)

        await worker.start()
        await asyncio.sleep(0.5)

        # Should execute job1 then job2 (success chain)
        assert results == ["job1", "job2"]

        await worker.stop()


class TestWorkerPool:
    """Test WorkerPool functionality."""

    @pytest.mark.asyncio
    async def test_pool_creation(self, app_with_jobs: Whiskey):
        """Test creating a worker pool."""
        queues = MultiQueue()
        pool = WorkerPool(app_with_jobs.container, queues, size=4, concurrency_per_worker=5)

        await pool.start()

        assert pool._running
        assert len(pool._workers) == 4

        # Check worker configuration
        for worker in pool._workers:
            assert worker.concurrency == 5

        await pool.stop()

    @pytest.mark.asyncio
    async def test_pool_processing(self, app_with_jobs: Whiskey):
        """Test pool processing jobs."""
        queues = MultiQueue()
        pool = WorkerPool(app_with_jobs.container, queues, size=2)

        # Add multiple jobs
        for i in range(10):
            metadata = JobMetadata(func=lambda x=i: f"result_{x}", name=f"job{i}")
            job = Job(metadata)
            await queues.push(job)

        await pool.start()
        await asyncio.sleep(0.5)

        # All jobs should be processed
        stats = pool.get_stats()
        assert stats["total_processed"] == 10
        assert stats["size"] == 2

        await pool.stop()

    @pytest.mark.asyncio
    async def test_pool_stats(self, app_with_jobs: Whiskey):
        """Test pool statistics aggregation."""
        queues = MultiQueue()
        pool = WorkerPool(app_with_jobs.container, queues, size=3)

        # Add mix of successful and failing jobs
        async def success_job():
            return "ok"

        async def fail_job():
            raise ValueError("fail")

        for i in range(6):
            if i % 2 == 0:
                metadata = JobMetadata(func=success_job, name=f"success{i}")
            else:
                metadata = JobMetadata(func=fail_job, name=f"fail{i}", max_retries=0)
            job = Job(metadata)
            await queues.push(job)

        await pool.start()
        await asyncio.sleep(0.5)

        stats = pool.get_stats()
        assert stats["total_processed"] == 3
        assert stats["total_failed"] == 3
        assert len(stats["workers"]) == 3

        await pool.stop()

    def test_pool_scale_not_implemented(self, app_with_jobs: Whiskey):
        """Test that scaling is not implemented."""
        queues = MultiQueue()
        pool = WorkerPool(app_with_jobs.container, queues)

        with pytest.raises(NotImplementedError):
            pool.scale(5)
