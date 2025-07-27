"""Type definitions for whiskey_jobs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class JobStatus(Enum):
    """Job execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class JobPriority(Enum):
    """Job priority levels."""

    LOW = 1
    NORMAL = 5
    HIGH = 10
    CRITICAL = 20


@dataclass
class JobMetadata:
    """Metadata for a job definition."""

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
    """Metadata for scheduled jobs."""

    cron: str | None = None
    interval: float | None = None  # seconds
    start_date: datetime | None = None
    end_date: datetime | None = None
    timezone: str = "UTC"

    def __post_init__(self):
        """Validate scheduling configuration."""
        if not self.cron and not self.interval:
            raise ValueError("Either 'cron' or 'interval' must be specified")
        if self.cron and self.interval:
            raise ValueError("Cannot specify both 'cron' and 'interval'")


@dataclass
class JobResult:
    """Result of a job execution."""

    job_id: str
    status: JobStatus
    result: Any = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration: float | None = None  # seconds
    retry_count: int = 0

    def __post_init__(self):
        """Calculate duration if not provided."""
        if self.duration is None and self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            self.duration = delta.total_seconds()

    @property
    def is_success(self) -> bool:
        """Check if job completed successfully."""
        return self.status == JobStatus.COMPLETED

    @property
    def is_failure(self) -> bool:
        """Check if job failed."""
        return self.status in (JobStatus.FAILED, JobStatus.CANCELLED)
