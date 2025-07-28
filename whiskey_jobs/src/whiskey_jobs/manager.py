"""Job manager implementation for whiskey_jobs."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from .job import Job
from .queue import MultiQueue, PriorityQueue
from .scheduler import JobScheduler
from .types import JobMetadata, JobPriority, JobResult, ScheduledJobMetadata
from .worker import WorkerPool

logger = logging.getLogger(__name__)


class JobManager:
    """Central manager for jobs, queues, workers, and scheduling."""

    def __init__(
        self,
        container: Any,
        worker_pool_size: int = 4,
        worker_concurrency: int = 10,
        use_priority_queues: bool = True,
    ):
        """Initialize the job manager.

        Args:
            container: Whiskey container for dependency injection
            worker_pool_size: Number of workers in the pool
            worker_concurrency: Concurrent jobs per worker
            use_priority_queues: Use priority queues instead of FIFO
        """
        self.container = container

        # Initialize components
        queue_type = PriorityQueue if use_priority_queues else None
        self.queues = MultiQueue(queue_type)
        self.scheduler = JobScheduler(self.queues)
        self.worker_pool = WorkerPool(
            container,
            self.queues,
            size=worker_pool_size,
            concurrency_per_worker=worker_concurrency,
            result_callback=self._store_job_result,
        )

        # Job tracking
        self._job_results: dict[str, JobResult] = {}
        self._job_metadata: dict[str, JobMetadata] = {}
        self._scheduled_metadata: dict[str, ScheduledJobMetadata] = {}

        self._running = False

    async def start(self) -> None:
        """Start the job manager and all components."""
        if self._running:
            return

        self._running = True
        logger.info("Starting job manager...")

        # Start components
        await self.worker_pool.start()
        await self.scheduler.start()

        logger.info("Job manager started")

    async def stop(self) -> None:
        """Stop the job manager and all components."""
        if not self._running:
            return

        self._running = False
        logger.info("Stopping job manager...")

        # Stop components
        await self.scheduler.stop()
        await self.worker_pool.stop()

        logger.info("Job manager stopped")

    def _store_job_result(self, job_id: str, result: JobResult) -> None:
        """Store a job result.

        Args:
            job_id: Job ID
            result: Job result
        """
        self._job_results[job_id] = result

    def register_job(
        self,
        func: Callable,
        name: str | None = None,
        queue: str = "default",
        priority: JobPriority = JobPriority.NORMAL,
        max_retries: int = 3,
        retry_delay: float = 60.0,
        timeout: float | None = None,
        tags: list[str] | None = None,
        description: str | None = None,
    ) -> JobMetadata:
        """Register a job function.

        Args:
            func: Job function
            name: Job name (defaults to function name)
            queue: Queue name
            priority: Job priority
            max_retries: Maximum retry attempts
            retry_delay: Delay between retries in seconds
            timeout: Job timeout in seconds
            tags: Job tags
            description: Job description

        Returns:
            JobMetadata instance
        """
        if name is None:
            name = func.__name__

        metadata = JobMetadata(
            func=func,
            name=name,
            queue=queue,
            priority=priority,
            max_retries=max_retries,
            retry_delay=retry_delay,
            timeout=timeout,
            tags=tags or [],
            description=description or func.__doc__,
        )

        self._job_metadata[name] = metadata
        logger.info(f"Registered job: {name}")

        return metadata

    def register_scheduled_job(
        self,
        func: Callable,
        name: str | None = None,
        cron: str | None = None,
        interval: float | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        timezone: str = "UTC",
        queue: str = "default",
        priority: JobPriority = JobPriority.NORMAL,
        max_retries: int = 3,
        retry_delay: float = 60.0,
        timeout: float | None = None,
        tags: list[str] | None = None,
        description: str | None = None,
    ) -> ScheduledJobMetadata:
        """Register a scheduled job.

        Args:
            func: Job function
            name: Job name (defaults to function name)
            cron: Cron expression (e.g., "0 * * * *" for hourly)
            interval: Interval in seconds (alternative to cron)
            start_date: When to start scheduling
            end_date: When to stop scheduling
            timezone: Timezone for cron expressions
            queue: Queue name
            priority: Job priority
            max_retries: Maximum retry attempts
            retry_delay: Delay between retries in seconds
            timeout: Job timeout in seconds
            tags: Job tags
            description: Job description

        Returns:
            ScheduledJobMetadata instance
        """
        if name is None:
            name = func.__name__

        metadata = ScheduledJobMetadata(
            func=func,
            name=name,
            cron=cron,
            interval=interval,
            start_date=start_date,
            end_date=end_date,
            timezone=timezone,
            queue=queue,
            priority=priority,
            max_retries=max_retries,
            retry_delay=retry_delay,
            timeout=timeout,
            tags=tags or [],
            description=description or func.__doc__,
        )

        self._scheduled_metadata[name] = metadata
        self.scheduler.add_scheduled_job(metadata)
        logger.info(f"Registered scheduled job: {name}")

        return metadata

    async def enqueue(self, job_name: str, *args, **kwargs) -> Job:
        """Enqueue a registered job for execution.

        Args:
            job_name: Name of registered job.
            *args: Positional arguments for the job function.
            **kwargs: Keyword arguments for the job function.

        Returns:
            Created Job instance.
            
        Raises:
            ValueError: If job_name is not registered.
        """
        if job_name not in self._job_metadata:
            raise ValueError(f"Job '{job_name}' not registered")

        metadata = self._job_metadata[job_name]
        job = Job(metadata, args, kwargs)

        await self.queues.push(job)
        logger.info(f"Enqueued job {job.job_id} ({job_name}) to queue '{job.queue}'")

        return job

    async def enqueue_func(
        self,
        func: Callable,
        *args,
        queue: str = "default",
        priority: JobPriority = JobPriority.NORMAL,
        **kwargs,
    ) -> Job:
        """Enqueue a function directly without prior registration.

        Args:
            func: Function to execute.
            *args: Positional arguments for the function.
            queue: Queue name. Defaults to "default".
            priority: Job priority. Defaults to NORMAL.
            **kwargs: Keyword arguments for the function.

        Returns:
            Created Job instance.
        """
        metadata = JobMetadata(
            func=func,
            name=func.__name__,
            queue=queue,
            priority=priority,
        )

        job = Job(metadata, args, kwargs)
        await self.queues.push(job)
        logger.info(f"Enqueued ad-hoc job {job.job_id} ({func.__name__})")

        return job

    def get_job_result(self, job_id: str) -> JobResult | None:
        """Get the result of a completed job.

        Args:
            job_id: Unique job identifier.

        Returns:
            JobResult if available, None otherwise.
        """
        return self._job_results.get(job_id)

    async def wait_for_job(self, job: Job | str, timeout: float | None = None) -> JobResult:
        """Wait for a job to complete.

        Args:
            job: Job instance or job ID string.
            timeout: Maximum wait time in seconds. Defaults to None.

        Returns:
            JobResult containing execution results.

        Raises:
            TimeoutError: If timeout is exceeded.
        """
        job_id = job.job_id if isinstance(job, Job) else job

        # Poll for completion
        start_time = asyncio.get_event_loop().time()
        while True:
            result = self.get_job_result(job_id)
            if result:
                return result

            if timeout and (asyncio.get_event_loop().time() - start_time) > timeout:
                raise TimeoutError(f"Job {job_id} did not complete within {timeout}s")

            await asyncio.sleep(0.1)

    def list_jobs(self) -> list[str]:
        """Return a list of all registered job names."""
        return list(self._job_metadata.keys())

    def list_scheduled_jobs(self) -> list[dict[str, Any]]:
        """Return information about all scheduled jobs.
        
        Returns:
            List of dictionaries containing scheduled job information.
        """
        return self.scheduler.list_jobs()

    def get_stats(self) -> dict[str, Any]:
        """Get comprehensive job system statistics.

        Returns:
            Dictionary containing statistics about jobs, queues, workers, and scheduler.
        """
        return {
            "running": self._running,
            "registered_jobs": len(self._job_metadata),
            "scheduled_jobs": len(self._scheduled_metadata),
            "queues": {
                "names": self.queues.list_queues(),
                "total_jobs": self.queues.size(),
            },
            "worker_pool": self.worker_pool.get_stats(),
            "scheduler": self.scheduler.get_stats(),
        }

    async def clear_queue(self, queue_name: str | None = None) -> None:
        """Clear pending jobs from a queue.

        Args:
            queue_name: Queue name to clear. Clears all queues if None.
        """
        self.queues.clear(queue_name)
        logger.info(f"Cleared queue: {queue_name or 'all'}")

    def create_job_chain(self) -> JobChainBuilder:
        """Create a job chain builder for sequential job execution.

        Returns:
            JobChainBuilder instance for fluent chain construction.
        """
        return JobChainBuilder(self)


class JobChainBuilder:
    """Build chains of jobs for sequential execution.
    
    The JobChainBuilder provides a fluent interface for creating
    sequences of jobs where each job executes after the previous
    one completes successfully.
    """

    def __init__(self, manager: JobManager):
        """Initialize the chain builder.

        Args:
            manager: JobManager instance for job execution.
        """
        self.manager = manager
        self._jobs: list[Job] = []

    def add(self, job_name: str, *args, **kwargs) -> JobChainBuilder:
        """Add a job to the chain.

        Args:
            job_name: Registered job name
            *args: Job arguments
            **kwargs: Job keyword arguments

        Returns:
            Self for chaining
        """
        if job_name not in self.manager._job_metadata:
            raise ValueError(f"Job '{job_name}' not registered")

        metadata = self.manager._job_metadata[job_name]
        job = Job(metadata, args, kwargs)

        # Chain to previous job if any
        if self._jobs:
            self._jobs[-1].on_success(job)

        self._jobs.append(job)
        return self

    async def enqueue(self) -> Job:
        """Enqueue the job chain.

        Returns:
            The first job in the chain
        """
        if not self._jobs:
            raise ValueError("No jobs in chain")

        # Only enqueue the first job; others will be chained
        first_job = self._jobs[0]
        await self.manager.queues.push(first_job)

        logger.info(f"Enqueued job chain starting with {first_job.job_id}")
        return first_job
