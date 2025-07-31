"""Type definitions for whiskey_jobs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class JobStatus(Enum):
    """Represent the execution status of a job.

    Tracks the lifecycle of a job from pending through
    completion or failure.
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class JobPriority(Enum):
    """Define priority levels for job execution.

    Higher numeric values indicate higher priority, with
    CRITICAL being the highest priority.
    """

    LOW = 1
    NORMAL = 5
    HIGH = 10
    CRITICAL = 20


@dataclass
class JobMetadata:
    """Store metadata for a job definition.

    Contains all configuration needed to execute a job,
    including the function, queue assignment, retry policy,
    and other execution parameters.
    """

    func: Callable
    name: str
    queue: str = "default"
    priority: JobPriority | int = JobPriority.NORMAL
    max_retries: int = 3
    retry_delay: float = 60.0  # seconds
    timeout: float | None = None  # seconds
    tags: list[str] = field(default_factory=list)
    description: str | None = None


@dataclass
class ScheduledJobMetadata(JobMetadata):
    """Store metadata for scheduled job definitions.

    Extends JobMetadata with scheduling-specific configuration,
    supporting both cron expressions and interval-based scheduling.
    """

    cron: str | None = None
    interval: float | None = None  # seconds
    start_date: datetime | None = None
    end_date: datetime | None = None
    timezone: str = "UTC"

    def __post_init__(self):
        """Validate that scheduling configuration is properly specified.

        Raises:
            ValueError: If scheduling configuration is invalid.
        """
        if not self.cron and not self.interval:
            raise ValueError("Either 'cron' or 'interval' must be specified")
        if self.cron and self.interval:
            raise ValueError("Cannot specify both 'cron' and 'interval'")


@dataclass
class JobResult:
    """Store the result of a job execution.

    Contains execution status, timing information, results or errors,
    and retry count for a completed job execution.
    """

    job_id: str
    status: JobStatus
    result: Any = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration: float | None = None  # seconds
    retry_count: int = 0

    def __post_init__(self):
        """Calculate duration from start and completion times if not provided."""
        if self.duration is None and self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            self.duration = delta.total_seconds()

    @property
    def is_success(self) -> bool:
        """Check if the job completed successfully.

        Returns:
            True if status is COMPLETED, False otherwise.
        """
        return self.status == JobStatus.COMPLETED

    @property
    def is_failure(self) -> bool:
        """Check if the job failed or was cancelled.

        Returns:
            True if status is FAILED or CANCELLED, False otherwise.
        """
        return self.status in (JobStatus.FAILED, JobStatus.CANCELLED)
