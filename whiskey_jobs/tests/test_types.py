"""Tests for type definitions."""

from datetime import datetime

import pytest

from whiskey_jobs.types import (
    JobMetadata,
    JobPriority,
    JobResult,
    JobStatus,
    ScheduledJobMetadata,
)


class TestJobStatus:
    """Test JobStatus enum."""

    def test_status_values(self):
        """Test status enum values."""
        assert JobStatus.PENDING.value == "pending"
        assert JobStatus.RUNNING.value == "running"
        assert JobStatus.COMPLETED.value == "completed"
        assert JobStatus.FAILED.value == "failed"
        assert JobStatus.CANCELLED.value == "cancelled"
        assert JobStatus.RETRYING.value == "retrying"


class TestJobPriority:
    """Test JobPriority enum."""

    def test_priority_values(self):
        """Test priority enum values."""
        assert JobPriority.LOW.value == 1
        assert JobPriority.NORMAL.value == 5
        assert JobPriority.HIGH.value == 10
        assert JobPriority.CRITICAL.value == 20

    def test_priority_ordering(self):
        """Test priority ordering."""
        assert JobPriority.LOW.value < JobPriority.NORMAL.value
        assert JobPriority.NORMAL.value < JobPriority.HIGH.value
        assert JobPriority.HIGH.value < JobPriority.CRITICAL.value


class TestJobMetadata:
    """Test JobMetadata dataclass."""

    def test_default_values(self):
        """Test default metadata values."""

        def test_func():
            pass

        metadata = JobMetadata(func=test_func, name="test")

        assert metadata.func is test_func
        assert metadata.name == "test"
        assert metadata.queue == "default"
        assert metadata.priority == JobPriority.NORMAL
        assert metadata.max_retries == 3
        assert metadata.retry_delay == 60.0
        assert metadata.timeout is None
        assert metadata.tags == []
        assert metadata.description is None

    def test_custom_values(self):
        """Test custom metadata values."""

        def test_func():
            pass

        metadata = JobMetadata(
            func=test_func,
            name="custom",
            queue="special",
            priority=JobPriority.HIGH,
            max_retries=5,
            retry_delay=120.0,
            timeout=300.0,
            tags=["important", "batch"],
            description="Custom job",
        )

        assert metadata.queue == "special"
        assert metadata.priority == JobPriority.HIGH
        assert metadata.max_retries == 5
        assert metadata.retry_delay == 120.0
        assert metadata.timeout == 300.0
        assert "important" in metadata.tags
        assert metadata.description == "Custom job"


class TestScheduledJobMetadata:
    """Test ScheduledJobMetadata dataclass."""

    def test_cron_scheduling(self):
        """Test cron-based scheduling."""
        metadata = ScheduledJobMetadata(func=lambda: None, name="cron_job", cron="0 * * * *")

        assert metadata.cron == "0 * * * *"
        assert metadata.interval is None

    def test_interval_scheduling(self):
        """Test interval-based scheduling."""
        metadata = ScheduledJobMetadata(func=lambda: None, name="interval_job", interval=3600.0)

        assert metadata.interval == 3600.0
        assert metadata.cron is None

    def test_date_constraints(self):
        """Test date constraints."""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 12, 31)

        metadata = ScheduledJobMetadata(
            func=lambda: None,
            name="limited_job",
            interval=60,
            start_date=start,
            end_date=end,
            timezone="US/Pacific",
        )

        assert metadata.start_date == start
        assert metadata.end_date == end
        assert metadata.timezone == "US/Pacific"

    def test_validation_no_schedule(self):
        """Test validation when no schedule is provided."""
        with pytest.raises(ValueError, match="Either 'cron' or 'interval'"):
            ScheduledJobMetadata(func=lambda: None, name="invalid")

    def test_validation_both_schedules(self):
        """Test validation when both schedules are provided."""
        with pytest.raises(ValueError, match="Cannot specify both"):
            ScheduledJobMetadata(func=lambda: None, name="invalid", cron="* * * * *", interval=60)

    def test_inherits_job_metadata(self):
        """Test that ScheduledJobMetadata inherits from JobMetadata."""
        metadata = ScheduledJobMetadata(
            func=lambda: None,
            name="scheduled",
            interval=60,
            queue="scheduled",
            priority=JobPriority.LOW,
        )

        # Should have all JobMetadata fields
        assert metadata.queue == "scheduled"
        assert metadata.priority == JobPriority.LOW
        assert metadata.max_retries == 3


class TestJobResult:
    """Test JobResult dataclass."""

    def test_success_result(self):
        """Test successful job result."""
        result = JobResult(
            job_id="123",
            status=JobStatus.COMPLETED,
            result="success_data",
            started_at=datetime(2024, 1, 1, 10, 0),
            completed_at=datetime(2024, 1, 1, 10, 5),
        )

        assert result.is_success
        assert not result.is_failure
        assert result.result == "success_data"
        assert result.error is None
        assert result.duration == 300.0  # 5 minutes

    def test_failure_result(self):
        """Test failed job result."""
        result = JobResult(
            job_id="456", status=JobStatus.FAILED, error="Something went wrong", retry_count=2
        )

        assert not result.is_success
        assert result.is_failure
        assert result.error == "Something went wrong"
        assert result.result is None
        assert result.retry_count == 2

    def test_cancelled_result(self):
        """Test cancelled job result."""
        result = JobResult(job_id="789", status=JobStatus.CANCELLED)

        assert not result.is_success
        assert result.is_failure  # Cancelled is considered failure

    def test_duration_calculation(self):
        """Test duration calculation."""
        # No times set
        result1 = JobResult(job_id="1", status=JobStatus.PENDING)
        assert result1.duration is None

        # Only start time
        result2 = JobResult(job_id="2", status=JobStatus.RUNNING, started_at=datetime.now())
        assert result2.duration is None

        # Both times set
        start = datetime(2024, 1, 1, 10, 0, 0)
        end = datetime(2024, 1, 1, 10, 0, 30)
        result3 = JobResult(
            job_id="3", status=JobStatus.COMPLETED, started_at=start, completed_at=end
        )
        assert result3.duration == 30.0  # 30 seconds
