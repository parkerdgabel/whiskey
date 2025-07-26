"""Type definitions for whiskey_jobs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union


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
    priority: JobPriority = JobPriority.NORMAL
    max_retries: int = 3
    retry_delay: float = 60.0  # seconds
    timeout: Optional[float] = None  # seconds
    tags: List[str] = field(default_factory=list)
    description: Optional[str] = None


@dataclass
class ScheduledJobMetadata(JobMetadata):
    """Metadata for scheduled jobs."""
    
    cron: Optional[str] = None
    interval: Optional[float] = None  # seconds
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
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
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration: Optional[float] = None  # seconds
    retry_count: int = 0
    
    @property
    def is_success(self) -> bool:
        """Check if job completed successfully."""
        return self.status == JobStatus.COMPLETED
    
    @property
    def is_failure(self) -> bool:
        """Check if job failed."""
        return self.status in (JobStatus.FAILED, JobStatus.CANCELLED)