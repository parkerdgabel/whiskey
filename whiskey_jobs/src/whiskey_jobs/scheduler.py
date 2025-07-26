"""Job scheduler implementation for whiskey_jobs."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

try:
    from croniter import croniter
except ImportError:
    croniter = None

from .job import Job
from .queue import MultiQueue
from .types import ScheduledJobMetadata

logger = logging.getLogger(__name__)


class ScheduledJob:
    """Represents a scheduled job."""
    
    def __init__(self, metadata: ScheduledJobMetadata):
        """Initialize a scheduled job.
        
        Args:
            metadata: Scheduled job metadata
        """
        self.metadata = metadata
        self._next_run: Optional[datetime] = None
        self._last_run: Optional[datetime] = None
        self._run_count = 0
        
        # Initialize cron iterator if using cron
        if metadata.cron:
            if croniter is None:
                raise ImportError(
                    "croniter is required for cron scheduling. "
                    "Install with: pip install croniter"
                )
            self._cron = croniter(metadata.cron, datetime.now(timezone.utc))
        else:
            self._cron = None
        
        # Calculate initial next run time
        self._calculate_next_run()
    
    def _calculate_next_run(self) -> None:
        """Calculate the next run time."""
        now = datetime.now(timezone.utc)
        
        # Check date constraints
        if self.metadata.start_date and now < self.metadata.start_date:
            # Job hasn't started yet
            if self.metadata.interval:
                self._next_run = self.metadata.start_date
            else:
                # For cron, find first run after start date
                self._cron.set_current(self.metadata.start_date)
                self._next_run = self._cron.get_next(datetime)
            return
        
        if self.metadata.end_date and now > self.metadata.end_date:
            # Job has ended
            self._next_run = None
            return
        
        # Calculate based on schedule type
        if self.metadata.interval:
            # Interval-based scheduling
            if self._last_run:
                self._next_run = self._last_run + timedelta(seconds=self.metadata.interval)
            else:
                self._next_run = now
        else:
            # Cron-based scheduling
            self._next_run = self._cron.get_next(datetime)
    
    def should_run(self) -> bool:
        """Check if the job should run now."""
        if self._next_run is None:
            return False
        
        now = datetime.now(timezone.utc)
        
        # Check end date
        if self.metadata.end_date and now > self.metadata.end_date:
            return False
        
        return now >= self._next_run
    
    def create_job_instance(self) -> Job:
        """Create a Job instance for execution."""
        return Job(self.metadata)
    
    def mark_run(self) -> None:
        """Mark that the job has been run."""
        self._last_run = datetime.now(timezone.utc)
        self._run_count += 1
        self._calculate_next_run()
    
    def __repr__(self) -> str:
        """String representation."""
        schedule_type = "cron" if self.metadata.cron else "interval"
        schedule_value = self.metadata.cron or f"{self.metadata.interval}s"
        return (
            f"ScheduledJob(name={self.metadata.name}, "
            f"{schedule_type}={schedule_value}, "
            f"next_run={self._next_run})"
        )


class JobScheduler:
    """Schedules jobs for execution."""
    
    def __init__(self, queues: MultiQueue):
        """Initialize the scheduler.
        
        Args:
            queues: MultiQueue instance
        """
        self.queues = queues
        self._scheduled_jobs: Dict[str, ScheduledJob] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._check_interval = 1.0  # seconds
    
    def add_scheduled_job(self, metadata: ScheduledJobMetadata) -> None:
        """Add a scheduled job.
        
        Args:
            metadata: Scheduled job metadata
        """
        scheduled_job = ScheduledJob(metadata)
        self._scheduled_jobs[metadata.name] = scheduled_job
        logger.info(f"Added scheduled job: {scheduled_job}")
    
    def remove_scheduled_job(self, name: str) -> bool:
        """Remove a scheduled job.
        
        Args:
            name: Job name
            
        Returns:
            True if removed, False if not found
        """
        if name in self._scheduled_jobs:
            del self._scheduled_jobs[name]
            logger.info(f"Removed scheduled job: {name}")
            return True
        return False
    
    async def start(self) -> None:
        """Start the scheduler."""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._run_scheduler())
        logger.info("Job scheduler started")
    
    async def stop(self) -> None:
        """Stop the scheduler."""
        if not self._running:
            return
        
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info("Job scheduler stopped")
    
    async def _run_scheduler(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                await self._check_scheduled_jobs()
                await asyncio.sleep(self._check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in scheduler: {e}")
                await asyncio.sleep(self._check_interval)
    
    async def _check_scheduled_jobs(self) -> None:
        """Check and queue jobs that should run."""
        for scheduled_job in self._scheduled_jobs.values():
            try:
                if scheduled_job.should_run():
                    # Create and queue job
                    job = scheduled_job.create_job_instance()
                    await self.queues.push(job)
                    
                    # Mark as run
                    scheduled_job.mark_run()
                    
                    logger.info(
                        f"Queued scheduled job {job.job_id} ({job.name}) "
                        f"to queue '{job.queue}'"
                    )
                    
            except Exception as e:
                logger.error(
                    f"Error checking scheduled job {scheduled_job.metadata.name}: {e}"
                )
    
    def list_jobs(self) -> List[Dict[str, Any]]:
        """List all scheduled jobs.
        
        Returns:
            List of job information
        """
        jobs = []
        for name, scheduled_job in self._scheduled_jobs.items():
            jobs.append({
                "name": name,
                "schedule": (
                    scheduled_job.metadata.cron or 
                    f"every {scheduled_job.metadata.interval}s"
                ),
                "next_run": scheduled_job._next_run,
                "last_run": scheduled_job._last_run,
                "run_count": scheduled_job._run_count,
                "queue": scheduled_job.metadata.queue,
                "active": scheduled_job._next_run is not None,
            })
        return jobs
    
    def get_stats(self) -> Dict[str, Any]:
        """Get scheduler statistics.
        
        Returns:
            Scheduler statistics
        """
        active_jobs = sum(
            1 for job in self._scheduled_jobs.values() 
            if job._next_run is not None
        )
        
        return {
            "running": self._running,
            "total_jobs": len(self._scheduled_jobs),
            "active_jobs": active_jobs,
            "check_interval": self._check_interval,
        }