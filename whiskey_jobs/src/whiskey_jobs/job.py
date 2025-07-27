"""Job implementation for whiskey_jobs."""

from __future__ import annotations

import asyncio
import traceback
import uuid
from datetime import UTC, datetime
from typing import Any

from .types import JobMetadata, JobPriority, JobResult, JobStatus


class Job:
    """Represents a job to be executed."""

    def __init__(
        self,
        metadata: JobMetadata,
        args: tuple = (),
        kwargs: dict[str, Any] | None = None,
        job_id: str | None = None,
    ):
        """Initialize a job.

        Args:
            metadata: Job metadata
            args: Positional arguments for the job function
            kwargs: Keyword arguments for the job function
            job_id: Optional job ID (auto-generated if not provided)
        """
        self.metadata = metadata
        self.args = args
        self.kwargs = kwargs or {}
        self.job_id = job_id or str(uuid.uuid4())

        # Execution state
        self.status = JobStatus.PENDING
        self.result: Any = None
        self.error: str | None = None
        self.started_at: datetime | None = None
        self.completed_at: datetime | None = None
        self.retry_count = 0

        # For job chaining
        self._on_success: Job | None = None
        self._on_failure: Job | None = None

    @property
    def name(self) -> str:
        """Get job name."""
        return self.metadata.name

    @property
    def queue(self) -> str:
        """Get job queue."""
        return self.metadata.queue

    @property
    def priority(self) -> JobPriority | int:
        """Get job priority."""
        return self.metadata.priority

    @property
    def duration(self) -> float | None:
        """Get job execution duration in seconds."""
        if self.started_at is not None and self.completed_at is not None:
            delta = self.completed_at - self.started_at
            return delta.total_seconds()
        return None

    def to_result(self) -> JobResult:
        """Convert job to result object."""
        return JobResult(
            job_id=self.job_id,
            status=self.status,
            result=self.result,
            error=self.error,
            started_at=self.started_at,
            completed_at=self.completed_at,
            duration=self.duration,
            retry_count=self.retry_count,
        )

    async def execute(self, container: Any) -> JobResult:
        """Execute the job with dependency injection.

        Args:
            container: Whiskey container for dependency injection

        Returns:
            JobResult object
        """
        self.status = JobStatus.RUNNING
        self.started_at = datetime.now(UTC)

        try:
            # Execute with timeout if specified
            if self.metadata.timeout:
                self.result = await asyncio.wait_for(
                    self._execute_with_injection(container), timeout=self.metadata.timeout
                )
            else:
                self.result = await self._execute_with_injection(container)

            self.status = JobStatus.COMPLETED
            self.error = None

        except TimeoutError:
            self.status = JobStatus.FAILED
            self.error = f"Job timed out after {self.metadata.timeout} seconds"

        except Exception as e:
            self.status = JobStatus.FAILED
            self.error = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"

        finally:
            self.completed_at = datetime.now(UTC)

        return self.to_result()

    async def _execute_with_injection(self, container: Any) -> Any:
        """Execute the job function with dependency injection.

        Args:
            container: Whiskey container

        Returns:
            Job function result
        """
        # Merge provided kwargs with args
        call_kwargs = self.kwargs.copy()

        # Call the function with DI
        if asyncio.iscoroutinefunction(self.metadata.func):
            return await container.call(self.metadata.func, *self.args, **call_kwargs)
        else:
            # Run sync function in executor
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, lambda: container.call_sync(self.metadata.func, *self.args, **call_kwargs)
            )

    def should_retry(self) -> bool:
        """Check if job should be retried."""
        return self.status == JobStatus.FAILED and self.retry_count < self.metadata.max_retries

    def increment_retry(self) -> None:
        """Increment retry count."""
        self.retry_count += 1
        self.status = JobStatus.RETRYING

    def on_success(self, job: Job) -> Job:
        """Chain a job to run on success.

        Args:
            job: Job to run if this job succeeds

        Returns:
            The chained job for fluent API
        """
        self._on_success = job
        return job

    def on_failure(self, job: Job) -> Job:
        """Chain a job to run on failure.

        Args:
            job: Job to run if this job fails

        Returns:
            The chained job for fluent API
        """
        self._on_failure = job
        return job

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"Job(id={self.job_id}, name={self.name}, "
            f"status={self.status.value}, queue={self.queue})"
        )
