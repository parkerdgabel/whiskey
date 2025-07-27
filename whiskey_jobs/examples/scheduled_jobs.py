"""Scheduled and periodic jobs example for whiskey_jobs."""

import asyncio
from datetime import datetime, timedelta

from whiskey import Whiskey

from whiskey_jobs import jobs_extension

# Create application
app = Whiskey()
app.use(jobs_extension)


# Mock services
@app.singleton
class MetricsCollector:
    def __init__(self):
        self.metrics = {
            "cpu_usage": 0,
            "memory_usage": 0,
            "request_count": 0,
            "error_count": 0,
        }

    async def collect(self) -> dict:
        # Simulate metric collection
        import random

        self.metrics["cpu_usage"] = random.randint(20, 80)
        self.metrics["memory_usage"] = random.randint(30, 70)
        self.metrics["request_count"] += random.randint(10, 100)
        self.metrics["error_count"] += random.randint(0, 5)
        return self.metrics.copy()


@app.singleton
class DatabaseCleaner:
    async def cleanup_sessions(self) -> int:
        print("🧹 Cleaning up expired sessions...")
        # Simulate cleanup
        cleaned = 42
        await asyncio.sleep(1)
        print(f"   Cleaned {cleaned} expired sessions")
        return cleaned

    async def optimize_tables(self) -> None:
        print("🔧 Optimizing database tables...")
        await asyncio.sleep(2)
        print("   Database optimization complete")


@app.singleton
class ReportGenerator:
    async def generate_hourly_report(self, metrics: dict) -> str:
        report = f"""
📊 Hourly Report - {datetime.now().strftime("%Y-%m-%d %H:%M")}
{"=" * 50}
CPU Usage: {metrics.get("cpu_usage", 0)}%
Memory Usage: {metrics.get("memory_usage", 0)}%
Requests: {metrics.get("request_count", 0)}
Errors: {metrics.get("error_count", 0)}
"""
        return report


# Periodic jobs
@app.periodic_job(interval=5)  # Every 5 seconds
async def collect_metrics(collector: MetricsCollector):
    """Collect system metrics periodically."""
    metrics = await collector.collect()
    print(
        f"📈 Metrics collected: CPU={metrics['cpu_usage']}%, "
        f"Mem={metrics['memory_usage']}%, "
        f"Requests={metrics['request_count']}"
    )
    return metrics


@app.periodic_job(interval=10)  # Every 10 seconds
async def health_check():
    """Simple health check."""
    print(f"💚 Health check OK at {datetime.now().strftime('%H:%M:%S')}")
    return {"status": "healthy", "timestamp": datetime.now()}


# Scheduled jobs (using cron expressions)
@app.scheduled_job(cron="*/30 * * * * *")  # Every 30 seconds
async def cleanup_sessions(db_cleaner: DatabaseCleaner):
    """Clean up expired database sessions."""
    cleaned = await db_cleaner.cleanup_sessions()
    return {"cleaned_sessions": cleaned}


@app.scheduled_job(cron="0 * * * * *")  # Every minute at :00
async def generate_report(collector: MetricsCollector, generator: ReportGenerator):
    """Generate hourly report."""
    metrics = await collector.collect()
    report = await generator.generate_hourly_report(metrics)
    print(report)
    return {"report_generated": True}


# Scheduled job with date constraints
@app.scheduled_job(
    cron="*/15 * * * * *",  # Every 15 seconds
    start_date=datetime.now() + timedelta(seconds=10),
    end_date=datetime.now() + timedelta(seconds=60),
)
async def limited_time_task():
    """This task only runs for 50 seconds (between 10s and 60s from start)."""
    print(f"⏰ Limited time task executed at {datetime.now().strftime('%H:%M:%S')}")
    return {"executed_at": datetime.now()}


# Job with dependencies
@app.job()
async def process_report(report_data: dict):
    """Process a generated report."""
    print(f"📋 Processing report: {report_data}")
    await asyncio.sleep(1)
    return {"processed": True}


# Main application
async def main():
    print("🚀 Whiskey Jobs - Scheduled Jobs Example")
    print("=" * 50)

    # Show scheduled jobs
    scheduled = app.jobs.list_scheduled_jobs()
    print("\n📅 Scheduled Jobs:")
    for job in scheduled:
        print(f"  - {job['name']}: {job['schedule']}")
        if job["next_run"]:
            print(f"    Next run: {job['next_run']}")

    # The scheduler is already running (auto_start=True)
    print("\n⏰ Scheduler is running. Watch the output...")
    print("   (Press Ctrl+C to stop)\n")

    # Manually trigger some jobs too
    print("🎯 Manually triggering some jobs...")

    # Chain a report generation with processing
    await app.jobs.enqueue("collect_metrics")
    await asyncio.sleep(2)

    # Create a job chain
    chain = app.jobs.create_job_chain()
    report_job = (
        await chain.add("generate_report")
        .add("process_report", report_data={"type": "hourly"})
        .enqueue()
    )

    print(f"   Created job chain starting with: {report_job.job_id}")

    # Run for 90 seconds to see everything in action
    print("\n⏱️  Running for 90 seconds...")
    await asyncio.sleep(90)

    # Show final statistics
    stats = app.jobs.get_stats()
    scheduler_stats = stats["scheduler"]
    print("\n📊 Final Statistics:")
    print(f"   Scheduler: {scheduler_stats['active_jobs']} active jobs")
    print(f"   Total processed: {stats['worker_pool']['total_processed']}")

    # Show detailed scheduled job info
    print("\n📅 Scheduled Job Details:")
    for job in app.jobs.list_scheduled_jobs():
        print(f"   {job['name']}:")
        print(f"     - Schedule: {job['schedule']}")
        print(f"     - Run count: {job['run_count']}")
        print(f"     - Active: {job['active']}")
        if job["last_run"]:
            print(f"     - Last run: {job['last_run']}")


# Run the application
if __name__ == "__main__":
    app.run(main)
