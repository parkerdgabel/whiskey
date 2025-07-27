"""Tests for Job class."""

import asyncio

import pytest
from whiskey import Whiskey

from whiskey_jobs.job import Job
from whiskey_jobs.types import JobMetadata, JobPriority, JobStatus


class TestJob:
    """Test Job class functionality."""

    def test_job_creation(self):
        """Test creating a job instance."""

        def dummy_func():
            return "test"

        metadata = JobMetadata(
            func=dummy_func,
            name="test_job",
            queue="default",
            priority=JobPriority.NORMAL,
        )

        job = Job(metadata, args=(1, 2), kwargs={"key": "value"})

        assert job.name == "test_job"
        assert job.queue == "default"
        assert job.priority == JobPriority.NORMAL
        assert job.status == JobStatus.PENDING
        assert job.args == (1, 2)
        assert job.kwargs == {"key": "value"}
        assert job.job_id is not None

    def test_job_properties(self):
        """Test job property methods."""
        metadata = JobMetadata(func=lambda: None, name="test")
        job = Job(metadata)

        # Test duration when not run
        assert job.duration is None

        # Test to_result
        result = job.to_result()
        assert result.job_id == job.job_id
        assert result.status == JobStatus.PENDING

    @pytest.mark.asyncio
    async def test_job_execute_success(self, app_with_jobs: Whiskey):
        """Test successful job execution."""

        async def async_job(x: int, y: int) -> int:
            return x + y

        metadata = JobMetadata(func=async_job, name="math_job")
        job = Job(metadata, args=(5, 3))

        result = await job.execute(app_with_jobs.container)

        assert result.status == JobStatus.COMPLETED
        assert result.result == 8
        assert result.error is None
        assert result.started_at is not None
        assert result.completed_at is not None
        assert result.duration is not None
        assert result.duration > 0

    @pytest.mark.asyncio
    async def test_job_execute_sync_function(self, app_with_jobs: Whiskey):
        """Test executing synchronous functions."""

        def sync_job(message: str) -> str:
            return f"Processed: {message}"

        metadata = JobMetadata(func=sync_job, name="sync_job")
        job = Job(metadata, args=("test",))

        result = await job.execute(app_with_jobs.container)

        assert result.status == JobStatus.COMPLETED
        assert result.result == "Processed: test"

    @pytest.mark.asyncio
    async def test_job_execute_failure(self, app_with_jobs: Whiskey):
        """Test job execution failure."""

        async def failing_job():
            raise ValueError("Test error")

        metadata = JobMetadata(func=failing_job, name="failing_job")
        job = Job(metadata)

        result = await job.execute(app_with_jobs.container)

        assert result.status == JobStatus.FAILED
        assert result.error is not None
        assert "ValueError: Test error" in result.error
        assert result.result is None

    @pytest.mark.asyncio
    async def test_job_timeout(self, app_with_jobs: Whiskey):
        """Test job timeout."""

        async def slow_job():
            await asyncio.sleep(2)
            return "done"

        metadata = JobMetadata(
            func=slow_job,
            name="slow_job",
            timeout=0.1,  # 100ms timeout
        )
        job = Job(metadata)

        result = await job.execute(app_with_jobs.container)

        assert result.status == JobStatus.FAILED
        assert "timed out" in result.error

    @pytest.mark.asyncio
    async def test_job_with_dependency_injection(self, app_with_jobs: Whiskey):
        """Test job with dependency injection."""

        # Register a service
        @app_with_jobs.singleton
        class TestService:
            def get_value(self) -> str:
                return "injected_value"

        async def job_with_di(service: TestService) -> str:
            return service.get_value()

        metadata = JobMetadata(func=job_with_di, name="di_job")
        job = Job(metadata)

        result = await job.execute(app_with_jobs.container)

        assert result.status == JobStatus.COMPLETED
        assert result.result == "injected_value"

    def test_job_retry_logic(self):
        """Test job retry logic."""
        metadata = JobMetadata(func=lambda: None, name="retry_job", max_retries=3)
        job = Job(metadata)

        # Initially should not retry
        assert not job.should_retry()

        # After failure, should retry
        job.status = JobStatus.FAILED
        assert job.should_retry()

        # Increment retries
        job.increment_retry()
        assert job.retry_count == 1
        assert job.status == JobStatus.RETRYING

        # After max retries, should not retry
        job.retry_count = 3
        job.status = JobStatus.FAILED
        assert not job.should_retry()

    def test_job_chaining(self):
        """Test job chaining."""
        metadata1 = JobMetadata(func=lambda: None, name="job1")
        metadata2 = JobMetadata(func=lambda: None, name="job2")
        metadata3 = JobMetadata(func=lambda: None, name="job3")

        job1 = Job(metadata1)
        job2 = Job(metadata2)
        job3 = Job(metadata3)

        # Chain jobs
        returned_job = job1.on_success(job2)
        assert returned_job is job2
        assert job1._on_success is job2

        returned_job = job1.on_failure(job3)
        assert returned_job is job3
        assert job1._on_failure is job3

    def test_job_repr(self):
        """Test job string representation."""
        metadata = JobMetadata(func=lambda: None, name="test_job", queue="special")
        job = Job(metadata)
        job.status = JobStatus.RUNNING

        repr_str = repr(job)
        assert "test_job" in repr_str
        assert "special" in repr_str
        assert "running" in repr_str
        assert job.job_id in repr_str
