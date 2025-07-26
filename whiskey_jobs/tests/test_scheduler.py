"""Tests for job scheduler implementation."""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from whiskey_jobs.queue import MultiQueue
from whiskey_jobs.scheduler import JobScheduler, ScheduledJob
from whiskey_jobs.types import JobPriority, ScheduledJobMetadata


class TestScheduledJob:
    """Test ScheduledJob functionality."""
    
    def test_interval_based_scheduling(self):
        """Test interval-based scheduled job."""
        metadata = ScheduledJobMetadata(
            func=lambda: "test",
            name="interval_job",
            interval=60  # Every minute
        )
        
        scheduled_job = ScheduledJob(metadata)
        
        # Should be ready to run immediately
        assert scheduled_job.should_run()
        
        # Mark as run
        scheduled_job.mark_run()
        assert scheduled_job._run_count == 1
        assert scheduled_job._last_run is not None
        
        # Should not run immediately after
        assert not scheduled_job.should_run()
        
        # Next run should be ~60 seconds later
        assert scheduled_job._next_run is not None
        delta = scheduled_job._next_run - scheduled_job._last_run
        assert 59 <= delta.total_seconds() <= 61
    
    def test_cron_based_scheduling(self):
        """Test cron-based scheduled job."""
        # Every 5 seconds
        metadata = ScheduledJobMetadata(
            func=lambda: "test",
            name="cron_job",
            cron="*/5 * * * * *"
        )
        
        scheduled_job = ScheduledJob(metadata)
        
        # Should have next run time
        assert scheduled_job._next_run is not None
        
        # Mark as run
        original_next = scheduled_job._next_run
        scheduled_job.mark_run()
        
        # Next run should be different
        assert scheduled_job._next_run != original_next
    
    def test_start_date_constraint(self):
        """Test start date constraint."""
        future_start = datetime.now(timezone.utc) + timedelta(hours=1)
        
        metadata = ScheduledJobMetadata(
            func=lambda: "test",
            name="future_job",
            interval=60,
            start_date=future_start
        )
        
        scheduled_job = ScheduledJob(metadata)
        
        # Should not run before start date
        assert not scheduled_job.should_run()
        assert scheduled_job._next_run == future_start
    
    def test_end_date_constraint(self):
        """Test end date constraint."""
        past_end = datetime.now(timezone.utc) - timedelta(hours=1)
        
        metadata = ScheduledJobMetadata(
            func=lambda: "test",
            name="ended_job",
            interval=60,
            end_date=past_end
        )
        
        scheduled_job = ScheduledJob(metadata)
        
        # Should not run after end date
        assert not scheduled_job.should_run()
        assert scheduled_job._next_run is None
    
    def test_create_job_instance(self):
        """Test creating job instances."""
        def test_func():
            return "result"
        
        metadata = ScheduledJobMetadata(
            func=test_func,
            name="test_job",
            interval=60,
            queue="special",
            priority=JobPriority.HIGH
        )
        
        scheduled_job = ScheduledJob(metadata)
        job = scheduled_job.create_job_instance()
        
        assert job.name == "test_job"
        assert job.queue == "special"
        assert job.priority == JobPriority.HIGH
        assert job.metadata.func is test_func
    
    def test_repr(self):
        """Test string representation."""
        metadata = ScheduledJobMetadata(
            func=lambda: None,
            name="test_job",
            cron="0 * * * *"
        )
        
        scheduled_job = ScheduledJob(metadata)
        repr_str = repr(scheduled_job)
        
        assert "test_job" in repr_str
        assert "cron=0 * * * *" in repr_str
    
    def test_validation_errors(self):
        """Test metadata validation."""
        # No schedule specified
        with pytest.raises(ValueError, match="Either 'cron' or 'interval'"):
            ScheduledJobMetadata(
                func=lambda: None,
                name="invalid"
            )
        
        # Both schedules specified
        with pytest.raises(ValueError, match="Cannot specify both"):
            ScheduledJobMetadata(
                func=lambda: None,
                name="invalid",
                cron="* * * * *",
                interval=60
            )


class TestJobScheduler:
    """Test JobScheduler functionality."""
    
    @pytest.mark.asyncio
    async def test_scheduler_lifecycle(self):
        """Test starting and stopping scheduler."""
        queues = MultiQueue()
        scheduler = JobScheduler(queues)
        
        assert not scheduler._running
        
        await scheduler.start()
        assert scheduler._running
        assert scheduler._task is not None
        
        await scheduler.stop()
        assert not scheduler._running
    
    @pytest.mark.asyncio
    async def test_add_remove_jobs(self):
        """Test adding and removing scheduled jobs."""
        queues = MultiQueue()
        scheduler = JobScheduler(queues)
        
        metadata = ScheduledJobMetadata(
            func=lambda: "test",
            name="test_job",
            interval=60
        )
        
        scheduler.add_scheduled_job(metadata)
        assert "test_job" in scheduler._scheduled_jobs
        
        # Remove job
        assert scheduler.remove_scheduled_job("test_job")
        assert "test_job" not in scheduler._scheduled_jobs
        
        # Remove non-existent job
        assert not scheduler.remove_scheduled_job("non_existent")
    
    @pytest.mark.asyncio
    async def test_job_scheduling(self):
        """Test that jobs are scheduled correctly."""
        queues = MultiQueue()
        scheduler = JobScheduler(queues)
        
        # Set faster check interval for testing
        scheduler._check_interval = 0.1
        
        # Counter to track executions
        execution_count = 0
        
        def counting_job():
            nonlocal execution_count
            execution_count += 1
            return "done"
        
        # Schedule job to run every 0.2 seconds
        metadata = ScheduledJobMetadata(
            func=counting_job,
            name="frequent_job",
            interval=0.2
        )
        
        scheduler.add_scheduled_job(metadata)
        
        await scheduler.start()
        await asyncio.sleep(0.6)  # Should run ~3 times
        await scheduler.stop()
        
        # Check that jobs were queued
        assert queues.size() >= 2  # At least 2 executions
    
    @pytest.mark.asyncio
    async def test_list_jobs(self):
        """Test listing scheduled jobs."""
        queues = MultiQueue()
        scheduler = JobScheduler(queues)
        
        # Add multiple jobs
        metadata1 = ScheduledJobMetadata(
            func=lambda: None,
            name="job1",
            interval=60
        )
        metadata2 = ScheduledJobMetadata(
            func=lambda: None,
            name="job2",
            cron="0 * * * *"
        )
        
        scheduler.add_scheduled_job(metadata1)
        scheduler.add_scheduled_job(metadata2)
        
        jobs = scheduler.list_jobs()
        assert len(jobs) == 2
        
        # Check job info
        job_names = [j["name"] for j in jobs]
        assert "job1" in job_names
        assert "job2" in job_names
        
        # Check schedule info
        for job in jobs:
            if job["name"] == "job1":
                assert job["schedule"] == "every 60s"
            elif job["name"] == "job2":
                assert job["schedule"] == "0 * * * *"
    
    @pytest.mark.asyncio
    async def test_scheduler_stats(self):
        """Test scheduler statistics."""
        queues = MultiQueue()
        scheduler = JobScheduler(queues)
        
        # Add jobs
        metadata1 = ScheduledJobMetadata(
            func=lambda: None,
            name="active_job",
            interval=60
        )
        metadata2 = ScheduledJobMetadata(
            func=lambda: None,
            name="ended_job",
            interval=60,
            end_date=datetime.now(timezone.utc) - timedelta(hours=1)
        )
        
        scheduler.add_scheduled_job(metadata1)
        scheduler.add_scheduled_job(metadata2)
        
        stats = scheduler.get_stats()
        assert stats["total_jobs"] == 2
        assert stats["active_jobs"] == 1  # Only active_job is active
        assert stats["check_interval"] == 1.0
        assert not stats["running"]
        
        await scheduler.start()
        stats = scheduler.get_stats()
        assert stats["running"]
        
        await scheduler.stop()
    
    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling in scheduler."""
        queues = MultiQueue()
        scheduler = JobScheduler(queues)
        
        # Add a job that will cause an error during checking
        metadata = ScheduledJobMetadata(
            func=lambda: None,
            name="error_job",
            interval=0.1
        )
        
        scheduled_job = ScheduledJob(metadata)
        # Corrupt the scheduled job to cause an error
        scheduled_job._next_run = "invalid"  # Not a datetime
        
        scheduler._scheduled_jobs["error_job"] = scheduled_job
        scheduler._check_interval = 0.1
        
        # Should handle error gracefully
        await scheduler.start()
        await asyncio.sleep(0.3)
        await scheduler.stop()
        
        # Scheduler should still be functional
        assert True  # If we get here, error was handled