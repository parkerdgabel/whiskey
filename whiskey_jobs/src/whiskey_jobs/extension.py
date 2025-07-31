"""Jobs extension for Whiskey applications."""

from __future__ import annotations

import asyncio
import functools
from collections.abc import Callable
from datetime import datetime
from typing import Any

from .manager import JobManager
from .types import JobPriority


def configure_jobs(**kwargs) -> Callable[[Any], None]:
    """Configure the jobs extension with custom settings.

    .. deprecated:: 0.2.0
        Use app.use(jobs_extension, **kwargs) instead.

    Args:
        worker_pool_size: Number of workers in the pool (default: 4)
        worker_concurrency: Concurrent jobs per worker (default: 10)
        use_priority_queues: Use priority queues instead of FIFO (default: True)
        auto_start: Automatically start job manager on app startup (default: True)

    Returns:
        Configured extension function

    Example:
        # Old way (deprecated):
        app.use(configure_jobs(worker_pool_size=8, auto_start=False))

        # New way:
        app.use(jobs_extension, worker_pool_size=8, auto_start=False)
    """

    def configured_extension(app: Any, **inner_kwargs) -> None:
        # Merge kwargs
        config = {**kwargs, **inner_kwargs}
        # Apply extension
        jobs_extension(app, **config)

    return configured_extension


def jobs_extension(
    app: Any,
    worker_pool_size: int = 4,
    worker_concurrency: int = 10,
    use_priority_queues: bool = True,
    auto_start: bool = True,
    **kwargs,
) -> None:
    """Add background job execution capabilities to Whiskey applications.

    This extension provides comprehensive job management including background
    execution with queues and priorities, scheduling (cron and periodic),
    retries and error handling, job chaining, full dependency injection
    support, and monitoring statistics.

    Args:
        app: Whiskey instance.
        worker_pool_size: Number of workers in the pool. Defaults to 4.
        worker_concurrency: Concurrent jobs per worker. Defaults to 10.
        use_priority_queues: Use priority queues instead of FIFO. Defaults to True.
        auto_start: Automatically start job manager on app startup. Defaults to True.
        **kwargs: Additional configuration options.

    Examples:
        Basic usage::

            app = Whiskey()
            app.use(jobs_extension, worker_pool_size=8, auto_start=False)

            @app.job(queue="emails", priority=JobPriority.HIGH)
            async def send_email(to: str, subject: str, email_service: EmailService):
                await email_service.send(to, subject)

            @app.scheduled_job(cron="0 * * * *")  # Every hour
            async def cleanup_old_data(db: Database):
                await db.cleanup_expired_sessions()

            # Enqueue jobs
            await app.jobs.enqueue("send_email", "user@example.com", "Welcome!")

    """

    # Create job manager
    manager = JobManager(
        app.container,
        worker_pool_size=worker_pool_size,
        worker_concurrency=worker_concurrency,
        use_priority_queues=use_priority_queues,
    )

    # Store manager in app
    app.jobs = manager

    # Register manager as singleton in container
    app.container[JobManager] = manager

    # Job decorator
    def job(
        name: str | None = None,
        queue: str = "default",
        priority: JobPriority | int = JobPriority.NORMAL,
        max_retries: int = 3,
        retry_delay: float = 60.0,
        timeout: float | None = None,
        tags: list[str] | None = None,
    ):
        """Register a function as a background job.

        Args:
            name: Job name. Defaults to function name.
            queue: Queue name. Defaults to "default".
            priority: Job priority (JobPriority enum or int). Defaults to NORMAL.
            max_retries: Maximum retry attempts. Defaults to 3.
            retry_delay: Delay between retries in seconds. Defaults to 60.0.
            timeout: Job timeout in seconds. Defaults to None.
            tags: Job tags for categorization. Defaults to None.

        Returns:
            Decorated function that can be enqueued as a job.

        Examples:
            Basic job registration::

                @app.job(queue="emails", priority=JobPriority.HIGH)
                async def send_welcome_email(user_id: int, user_service: UserService):
                    user = await user_service.get_user(user_id)
                    await email_service.send_welcome(user)

        """
        # Keep priority as-is (JobPriority enum or int)

        def decorator(func: Callable) -> Callable:
            # Register job
            metadata = manager.register_job(
                func=func,
                name=name or func.__name__,
                queue=queue,
                priority=priority,
                max_retries=max_retries,
                retry_delay=retry_delay,
                timeout=timeout,
                tags=tags,
            )

            # Create wrapper that enqueues the job
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                # If called directly, enqueue the job
                job = await manager.enqueue(metadata.name, *args, **kwargs)
                return job

            # Add metadata to wrapper
            wrapper._job_metadata = metadata
            wrapper.delay = wrapper  # Celery-style alias

            # Add enqueue method
            async def enqueue(*args, **kwargs):
                return await manager.enqueue(metadata.name, *args, **kwargs)

            wrapper.enqueue = enqueue

            return wrapper

        return decorator

    # Scheduled job decorator
    def scheduled_job(
        name: str | None = None,
        cron: str | None = None,
        interval: float | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        timezone: str = "UTC",
        queue: str = "default",
        priority: JobPriority | int = JobPriority.NORMAL,
        max_retries: int = 3,
        retry_delay: float = 60.0,
        timeout: float | None = None,
        tags: list[str] | None = None,
    ):
        """Register a function as a scheduled job.

        Args:
            name: Job name. Defaults to function name.
            cron: Cron expression (e.g., "0 * * * *" for hourly). Defaults to None.
            interval: Interval in seconds (alternative to cron). Defaults to None.
            start_date: When to start scheduling. Defaults to None.
            end_date: When to stop scheduling. Defaults to None.
            timezone: Timezone for cron expressions. Defaults to "UTC".
            queue: Queue name. Defaults to "default".
            priority: Job priority. Defaults to NORMAL.
            max_retries: Maximum retry attempts. Defaults to 3.
            retry_delay: Delay between retries in seconds. Defaults to 60.0.
            timeout: Job timeout in seconds. Defaults to None.
            tags: Job tags. Defaults to None.

        Returns:
            Original function with scheduling metadata attached.

        Examples:
            Daily scheduled job::

                @app.scheduled_job(cron="0 0 * * *")  # Daily at midnight
                async def daily_report(reporting_service: ReportingService):
                    await reporting_service.generate_daily_report()

        """
        # Keep priority as-is (JobPriority enum or int)

        def decorator(func: Callable) -> Callable:
            # Register scheduled job
            metadata = manager.register_scheduled_job(
                func=func,
                name=name or func.__name__,
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
                tags=tags,
            )

            # Return original function (scheduled jobs aren't called directly)
            func._scheduled_metadata = metadata
            return func

        return decorator

    # Periodic job decorator (convenience for interval-based)
    def periodic_job(
        interval: float,
        name: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        queue: str = "default",
        priority: JobPriority | int = JobPriority.NORMAL,
        max_retries: int = 3,
        retry_delay: float = 60.0,
        timeout: float | None = None,
        tags: list[str] | None = None,
    ):
        """Register a function as a periodic job.

        Convenience decorator for interval-based scheduled jobs.

        Args:
            interval: Interval in seconds between executions.
            name: Job name. Defaults to function name.
            start_date: When to start scheduling. Defaults to None.
            end_date: When to stop scheduling. Defaults to None.
            queue: Queue name. Defaults to "default".
            priority: Job priority. Defaults to NORMAL.
            max_retries: Maximum retry attempts. Defaults to 3.
            retry_delay: Delay between retries in seconds. Defaults to 60.0.
            timeout: Job timeout in seconds. Defaults to None.
            tags: Job tags. Defaults to None.

        Returns:
            Original function with scheduling metadata attached.

        Examples:
            Periodic data sync::

                @app.periodic_job(300)  # Every 5 minutes
                async def sync_data(sync_service: SyncService):
                    await sync_service.sync_all()

        """
        return scheduled_job(
            name=name,
            interval=interval,
            start_date=start_date,
            end_date=end_date,
            queue=queue,
            priority=priority,
            max_retries=max_retries,
            retry_delay=retry_delay,
            timeout=timeout,
            tags=tags,
        )

    # Add decorators to app
    app.add_decorator("job", job)
    app.add_decorator("scheduled_job", scheduled_job)
    app.add_decorator("periodic_job", periodic_job)

    # Also add as attributes for direct access
    app.job = job
    app.scheduled_job = scheduled_job
    app.periodic_job = periodic_job

    # Add JobPriority to app for convenience
    app.JobPriority = JobPriority

    # Startup/shutdown hooks
    if auto_start:

        @app.on_startup
        async def start_job_manager():
            """Start the job manager on application startup."""
            await manager.start()

        @app.on_shutdown
        async def stop_job_manager():
            """Stop the job manager on application shutdown."""
            await manager.stop()

    # CLI commands if CLI extension is available
    if hasattr(app, "command"):

        @app.command(group="jobs")
        def jobs_status():
            """Show job system status."""
            stats = manager.get_stats()

            print("Job System Status")
            print("=" * 50)
            print(f"Running: {stats['running']}")
            print(f"Registered jobs: {stats['registered_jobs']}")
            print(f"Scheduled jobs: {stats['scheduled_jobs']}")
            print()

            print("Queues:")
            print(f"  Active queues: {', '.join(stats['queues']['names'])}")
            print(f"  Total pending jobs: {stats['queues']['total_jobs']}")
            print()

            print("Worker Pool:")
            pool_stats = stats["worker_pool"]
            print(f"  Workers: {pool_stats['size']}")
            print(f"  Total processed: {pool_stats['total_processed']}")
            print(f"  Total failed: {pool_stats['total_failed']}")
            print(f"  Currently processing: {pool_stats['total_current_jobs']}")

        @app.command(group="jobs")
        def jobs_list():
            """List all registered jobs."""
            jobs = manager.list_jobs()
            scheduled = manager.list_scheduled_jobs()

            print("Registered Jobs")
            print("=" * 50)
            if jobs:
                for job_name in sorted(jobs):
                    print(f"  - {job_name}")
            else:
                print("  No jobs registered")

            print()
            print("Scheduled Jobs")
            print("=" * 50)
            if scheduled:
                for job in scheduled:
                    print(f"  - {job['name']}: {job['schedule']}")
                    if job["next_run"]:
                        print(f"    Next run: {job['next_run']}")
                    print(f"    Active: {job['active']}")
            else:
                print("  No scheduled jobs")

        @app.command(group="jobs")
        @app.argument("job_name")
        @app.option("--args", help="JSON-encoded args")
        @app.option("--kwargs", help="JSON-encoded kwargs")
        async def jobs_run(job_name: str, args: str | None = None, kwargs: str | None = None):
            """Run a job immediately."""
            import json

            # Parse arguments
            job_args = json.loads(args) if args else []
            job_kwargs = json.loads(kwargs) if kwargs else {}

            # Enqueue and wait
            async with app:
                job = await manager.enqueue(job_name, *job_args, **job_kwargs)
                print(f"Running job {job.job_id}...")

                try:
                    result = await manager.wait_for_job(job, timeout=300)
                    if result.is_success:
                        print("Job completed successfully")
                        if result.result:
                            print(f"Result: {result.result}")
                    else:
                        print(f"Job failed: {result.error}")
                except TimeoutError:
                    print("Job timed out")

    # Enhanced run method (only if app has run)
    if hasattr(app, "run"):
        original_run = app.run

        def enhanced_run(main: Callable | None = None) -> None:
            """Run the application with job manager support."""
            if main is None and hasattr(app, "_main_func"):
                original_run()
            else:
                # Wrap main to start/stop job manager
                async def wrapped_main():
                    async with app:
                        if main:
                            if asyncio.iscoroutinefunction(main):
                                await main()
                            else:
                                main()
                        else:
                            # Keep running for job processing
                            print("Job system running. Press Ctrl+C to stop.")
                            try:
                                await asyncio.Event().wait()
                            except KeyboardInterrupt:
                                print("\nShutting down...")

                asyncio.run(wrapped_main())

        app.run = enhanced_run
