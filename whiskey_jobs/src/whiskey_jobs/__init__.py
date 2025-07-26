"""Whiskey Jobs - Background job execution extension for Whiskey.

This extension provides:
- Background job execution with queues
- Job scheduling (cron and periodic)
- Job persistence and retries
- Full dependency injection support
- Job monitoring and metrics
"""

from .extension import jobs_extension
from .job import Job, JobResult, JobStatus
from .manager import JobManager
from .queue import JobQueue, PriorityQueue
from .scheduler import JobScheduler
from .worker import JobWorker

__all__ = [
    "jobs_extension",
    "Job",
    "JobResult",
    "JobStatus",
    "JobManager",
    "JobQueue",
    "PriorityQueue",
    "JobScheduler",
    "JobWorker",
]

__version__ = "0.1.0"