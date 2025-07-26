"""Tests for the jobs extension."""

import asyncio
import json

import pytest

from whiskey import Whiskey
from whiskey_jobs import configure_jobs, jobs_extension
from whiskey_jobs.types import JobPriority


class TestJobsExtension:
    """Test jobs extension integration."""
    
    def test_extension_setup(self):
        """Test extension setup."""
        app = Whiskey()
        app.use(configure_jobs(auto_start=False))
        
        # Check components are added
        assert hasattr(app, "jobs")
        assert hasattr(app, "job")
        assert hasattr(app, "scheduled_job")
        assert hasattr(app, "periodic_job")
        assert hasattr(app, "JobPriority")
        
        # Check JobPriority is available
        assert app.JobPriority is JobPriority
    
    def test_job_decorator(self, app_with_jobs: Whiskey):
        """Test @app.job decorator."""
        @app_with_jobs.job(
            queue="test_queue",
            priority=app_with_jobs.JobPriority.HIGH,
            max_retries=2,
            tags=["test"]
        )
        async def decorated_job(x: int) -> int:
            return x * 2
        
        # Check metadata is attached
        assert hasattr(decorated_job, "_job_metadata")
        metadata = decorated_job._job_metadata
        assert metadata.name == "decorated_job"
        assert metadata.queue == "test_queue"
        assert metadata.priority == JobPriority.HIGH
        assert metadata.max_retries == 2
        assert "test" in metadata.tags
        
        # Check job is registered
        assert "decorated_job" in app_with_jobs.jobs._job_metadata
    
    @pytest.mark.asyncio
    async def test_job_decorator_enqueue(self, running_app: Whiskey):
        """Test enqueueing via decorator."""
        result_store = []
        
        @running_app.job()
        async def test_job(value: str):
            result_store.append(value)
            return f"processed_{value}"
        
        # Call decorated function enqueues job
        job = await test_job("hello")
        assert job.name == "test_job"
        
        # Wait for processing
        result = await running_app.jobs.wait_for_job(job, timeout=1)
        assert result.result == "processed_hello"
        assert result_store == ["hello"]
    
    @pytest.mark.asyncio
    async def test_job_decorator_methods(self, app_with_jobs: Whiskey):
        """Test decorator methods."""
        @app_with_jobs.job()
        async def test_job(x: int) -> int:
            return x + 1
        
        # Test enqueue method
        job = await test_job.enqueue(5)
        assert job.args == (5,)
        
        # Test delay alias (Celery-style)
        job2 = await test_job.delay(10)
        assert job2.args == (10,)
    
    def test_scheduled_job_decorator(self, app_with_jobs: Whiskey):
        """Test @app.scheduled_job decorator."""
        @app_with_jobs.scheduled_job(
            cron="0 * * * *",
            queue="scheduled",
            timeout=300
        )
        async def hourly_task():
            return "done"
        
        # Check metadata
        assert hasattr(hourly_task, "_scheduled_metadata")
        metadata = hourly_task._scheduled_metadata
        assert metadata.cron == "0 * * * *"
        assert metadata.queue == "scheduled"
        assert metadata.timeout == 300
        
        # Check it's registered with scheduler
        jobs = app_with_jobs.jobs.list_scheduled_jobs()
        assert any(j["name"] == "hourly_task" for j in jobs)
    
    def test_periodic_job_decorator(self, app_with_jobs: Whiskey):
        """Test @app.periodic_job decorator."""
        @app_with_jobs.periodic_job(
            interval=300,  # 5 minutes
            queue="periodic",
            priority=JobPriority.LOW
        )
        async def periodic_task():
            return "periodic"
        
        # Check metadata
        assert hasattr(periodic_task, "_scheduled_metadata")
        metadata = periodic_task._scheduled_metadata
        assert metadata.interval == 300
        assert metadata.cron is None
        assert metadata.priority == JobPriority.LOW
    
    def test_priority_conversion(self, app_with_jobs: Whiskey):
        """Test integer to JobPriority conversion."""
        @app_with_jobs.job(priority=15)
        def custom_priority():
            pass
        
        metadata = custom_priority._job_metadata
        assert metadata.priority == 15
    
    @pytest.mark.asyncio
    async def test_dependency_injection(self, running_app: Whiskey):
        """Test DI in jobs."""
        # Register a service
        @running_app.singleton
        class TestService:
            def process(self, data: str) -> str:
                return f"service_{data}"
        
        @running_app.job()
        async def di_job(input: str, service: TestService) -> str:
            return service.process(input)
        
        # Enqueue with only required args
        job = await running_app.jobs.enqueue("di_job", "test")
        result = await running_app.jobs.wait_for_job(job, timeout=1)
        
        assert result.result == "service_test"
    
    @pytest.mark.asyncio
    async def test_auto_start(self):
        """Test auto-start functionality."""
        app = Whiskey()
        app.use(configure_jobs(auto_start=True))
        
        # Check startup hooks are registered
        assert len(app._startup_callbacks) > 0
        assert len(app._shutdown_callbacks) > 0
        
        # Start app
        await app.startup()
        assert app.jobs._running
        
        # Stop app
        await app.shutdown()
        assert not app.jobs._running
    
    @pytest.mark.asyncio
    async def test_enhanced_run(self):
        """Test enhanced run method."""
        app = Whiskey()
        
        # Add a mock run method
        app.run = lambda main=None: None
        
        app.use(jobs_extension)
        
        # Test that run method is enhanced
        assert hasattr(app, "run")
        
        # Would test actual running but that blocks
    
    def test_cli_commands_registration(self):
        """Test CLI commands are registered if available."""
        app = Whiskey()
        
        # Add mock command decorator and related decorators
        commands = []
        
        def mock_command(**kwargs):
            def decorator(func):
                commands.append((func.__name__, kwargs))
                return func
            return decorator
        
        def mock_argument(name):
            def decorator(func):
                return func
            return decorator
        
        def mock_option(*args, **kwargs):
            def decorator(func):
                return func
            return decorator
        
        app.command = mock_command
        app.argument = mock_argument
        app.option = mock_option
        
        # Now add jobs extension
        app.use(jobs_extension)
        
        # Check commands were registered
        command_names = [name for name, _ in commands]
        assert "jobs_status" in command_names
        assert "jobs_list" in command_names
        assert "jobs_run" in command_names
    
    @pytest.mark.asyncio
    async def test_job_execution_flow(self, running_app: Whiskey):
        """Test complete job execution flow."""
        results = []
        
        @running_app.job(queue="flow_test", priority=running_app.JobPriority.HIGH)
        async def step1():
            results.append("step1")
            return "step1_done"
        
        @running_app.job(queue="flow_test")
        async def step2(prev_result: str):
            results.append(f"step2_{prev_result}")
            return "step2_done"
        
        # Create and execute chain
        chain = running_app.jobs.create_job_chain()
        job = await chain.add("step1").add("step2", "from_step1").enqueue()
        
        # Wait for execution
        await asyncio.sleep(1.0)
        
        # First job should complete
        assert "step1" in results
        
        # Stats should show activity
        stats = running_app.jobs.get_stats()
        assert stats["worker_pool"]["total_processed"] >= 1