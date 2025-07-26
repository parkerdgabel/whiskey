"""Job worker implementation for whiskey_jobs."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, Set

from .job import Job
from .queue import MultiQueue
from .types import JobResult, JobStatus

logger = logging.getLogger(__name__)


class JobWorker:
    """Worker that processes jobs from queues."""
    
    def __init__(
        self,
        container: Any,
        queues: MultiQueue,
        name: str = "worker",
        concurrency: int = 10,
    ):
        """Initialize a job worker.
        
        Args:
            container: Whiskey container for dependency injection
            queues: MultiQueue instance
            name: Worker name
            concurrency: Maximum concurrent jobs
        """
        self.container = container
        self.queues = queues
        self.name = name
        self.concurrency = concurrency
        
        # Worker state
        self._running = False
        self._tasks: Set[asyncio.Task] = set()
        self._processed_count = 0
        self._failed_count = 0
        self._current_jobs: Dict[str, Job] = {}
        
        # Queues to monitor
        self._monitored_queues: List[str] = ["default"]
    
    def monitor_queues(self, *queue_names: str) -> None:
        """Set which queues this worker should monitor.
        
        Args:
            *queue_names: Queue names to monitor
        """
        self._monitored_queues = list(queue_names) or ["default"]
    
    async def start(self) -> None:
        """Start the worker."""
        if self._running:
            return
        
        self._running = True
        logger.info(f"Worker {self.name} started (concurrency={self.concurrency})")
        
        # Start queue monitoring tasks
        for queue_name in self._monitored_queues:
            task = asyncio.create_task(self._monitor_queue(queue_name))
            self._tasks.add(task)
    
    async def stop(self) -> None:
        """Stop the worker gracefully."""
        if not self._running:
            return
        
        logger.info(f"Stopping worker {self.name}...")
        self._running = False
        
        # Cancel monitoring tasks
        for task in self._tasks:
            task.cancel()
        
        # Wait for tasks to complete
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        
        # Wait for current jobs to complete
        if self._current_jobs:
            logger.info(f"Waiting for {len(self._current_jobs)} jobs to complete...")
            await asyncio.sleep(0.1)  # Brief wait for jobs to finish
        
        logger.info(
            f"Worker {self.name} stopped. "
            f"Processed: {self._processed_count}, Failed: {self._failed_count}"
        )
    
    async def _monitor_queue(self, queue_name: str) -> None:
        """Monitor a queue for jobs.
        
        Args:
            queue_name: Queue name to monitor
        """
        semaphore = asyncio.Semaphore(self.concurrency)
        
        while self._running:
            try:
                # Check for available slot
                async with semaphore:
                    # Get next job
                    queue = await self.queues.get_queue(queue_name)
                    job = await queue.pop()
                    
                    if job:
                        # Process job asynchronously
                        asyncio.create_task(
                            self._process_job_with_semaphore(job, semaphore)
                        )
                    else:
                        # No job available, wait briefly
                        await asyncio.sleep(0.1)
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error monitoring queue {queue_name}: {e}")
                await asyncio.sleep(1)  # Brief pause before retry
    
    async def _process_job_with_semaphore(
        self, job: Job, semaphore: asyncio.Semaphore
    ) -> None:
        """Process a job while holding semaphore.
        
        Args:
            job: Job to process
            semaphore: Concurrency semaphore
        """
        try:
            await self._process_job(job)
        finally:
            # Semaphore is automatically released when context exits
            pass
    
    async def _process_job(self, job: Job) -> JobResult:
        """Process a single job.
        
        Args:
            job: Job to process
            
        Returns:
            JobResult
        """
        logger.info(f"Worker {self.name} processing job {job.job_id} ({job.name})")
        self._current_jobs[job.job_id] = job
        
        try:
            # Execute the job
            result = await job.execute(self.container)
            
            if result.is_success:
                self._processed_count += 1
                logger.info(f"Job {job.job_id} completed successfully")
                
                # Handle success chaining
                if job._on_success:
                    await self.queues.push(job._on_success)
                    
            else:
                self._failed_count += 1
                logger.error(f"Job {job.job_id} failed: {result.error}")
                
                # Check for retry
                if job.should_retry():
                    job.increment_retry()
                    logger.info(
                        f"Retrying job {job.job_id} "
                        f"(attempt {job.retry_count}/{job.metadata.max_retries})"
                    )
                    
                    # Re-queue with delay
                    await asyncio.sleep(job.metadata.retry_delay)
                    await self.queues.push(job)
                else:
                    # Handle failure chaining
                    if job._on_failure:
                        await self.queues.push(job._on_failure)
            
            return result
            
        except Exception as e:
            logger.error(f"Unexpected error processing job {job.job_id}: {e}")
            raise
        finally:
            self._current_jobs.pop(job.job_id, None)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get worker statistics.
        
        Returns:
            Worker statistics
        """
        return {
            "name": self.name,
            "running": self._running,
            "processed": self._processed_count,
            "failed": self._failed_count,
            "current_jobs": len(self._current_jobs),
            "monitored_queues": self._monitored_queues,
        }


class WorkerPool:
    """Manages a pool of workers."""
    
    def __init__(
        self,
        container: Any,
        queues: MultiQueue,
        size: int = 4,
        concurrency_per_worker: int = 10,
    ):
        """Initialize a worker pool.
        
        Args:
            container: Whiskey container
            queues: MultiQueue instance
            size: Number of workers
            concurrency_per_worker: Concurrent jobs per worker
        """
        self.container = container
        self.queues = queues
        self.size = size
        self.concurrency_per_worker = concurrency_per_worker
        
        self._workers: List[JobWorker] = []
        self._running = False
    
    async def start(self) -> None:
        """Start all workers in the pool."""
        if self._running:
            return
        
        self._running = True
        
        # Create and start workers
        for i in range(self.size):
            worker = JobWorker(
                self.container,
                self.queues,
                name=f"worker-{i}",
                concurrency=self.concurrency_per_worker,
            )
            self._workers.append(worker)
            await worker.start()
        
        logger.info(f"Worker pool started with {self.size} workers")
    
    async def stop(self) -> None:
        """Stop all workers in the pool."""
        if not self._running:
            return
        
        self._running = False
        
        # Stop all workers
        await asyncio.gather(
            *[worker.stop() for worker in self._workers],
            return_exceptions=True
        )
        
        self._workers.clear()
        logger.info("Worker pool stopped")
    
    def scale(self, new_size: int) -> None:
        """Scale the worker pool size.
        
        Args:
            new_size: New number of workers
        """
        # This would need implementation for dynamic scaling
        raise NotImplementedError("Dynamic scaling not yet implemented")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics.
        
        Returns:
            Pool statistics
        """
        worker_stats = [worker.get_stats() for worker in self._workers]
        total_processed = sum(w["processed"] for w in worker_stats)
        total_failed = sum(w["failed"] for w in worker_stats)
        total_current = sum(w["current_jobs"] for w in worker_stats)
        
        return {
            "running": self._running,
            "size": len(self._workers),
            "total_processed": total_processed,
            "total_failed": total_failed,
            "total_current_jobs": total_current,
            "workers": worker_stats,
        }