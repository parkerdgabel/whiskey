"""Basic job execution example for whiskey_jobs."""

import asyncio
import random
from datetime import datetime

from whiskey import Whiskey

from whiskey_jobs import jobs_extension

# Create application
app = Whiskey()
app.use(jobs_extension)


# Simple services for demonstration
@app.singleton
class EmailService:
    async def send(self, to: str, subject: str, body: str) -> bool:
        print(f"📧 Sending email to {to}")
        print(f"   Subject: {subject}")
        print(f"   Body: {body}")
        await asyncio.sleep(1)  # Simulate email sending
        return True


@app.singleton
class DataProcessor:
    async def process(self, data: dict) -> dict:
        print(f"🔄 Processing data: {data}")
        await asyncio.sleep(2)  # Simulate processing
        return {"processed": True, "items": len(data), "timestamp": datetime.now()}


# Define jobs
@app.job(queue="emails", priority=app.JobPriority.HIGH)
async def send_welcome_email(user_id: int, email: str, service: EmailService):
    """Send a welcome email to a new user."""
    subject = "Welcome to Our Service!"
    body = f"Hello User {user_id}, welcome aboard!"
    result = await service.send(email, subject, body)
    return {"sent": result, "user_id": user_id}


@app.job(queue="processing")
async def process_user_data(user_id: int, data: dict, processor: DataProcessor):
    """Process user data in the background."""
    print(f"👤 Processing data for user {user_id}")
    result = await processor.process(data)
    return {"user_id": user_id, **result}


@app.job(max_retries=3, retry_delay=2)
async def flaky_job(success_rate: float = 0.5):
    """A job that randomly fails to demonstrate retry logic."""
    if random.random() < success_rate:
        print("✅ Flaky job succeeded!")
        return "Success"
    else:
        print("❌ Flaky job failed!")
        raise Exception("Random failure occurred")


@app.job(timeout=3)
async def slow_job(duration: int = 5):
    """A job that might timeout."""
    print(f"🐌 Starting slow job (will take {duration}s)...")
    await asyncio.sleep(duration)
    return "Completed"


# Main application
async def main():
    print("🚀 Whiskey Jobs - Basic Example")
    print("=" * 50)

    # Enqueue some jobs
    print("\n📋 Enqueuing jobs...")

    # Email job
    email_job = await app.jobs.enqueue("send_welcome_email", user_id=123, email="user@example.com")
    print(f"  - Email job: {email_job.job_id}")

    # Data processing job
    data_job = await app.jobs.enqueue(
        "process_user_data",
        user_id=123,
        data={"name": "John", "age": 30, "interests": ["coding", "music"]},
    )
    print(f"  - Data job: {data_job.job_id}")

    # Flaky job (will retry on failure)
    flaky = await app.jobs.enqueue("flaky_job", success_rate=0.3)
    print(f"  - Flaky job: {flaky.job_id}")

    # Slow job (might timeout)
    slow = await app.jobs.enqueue("slow_job", duration=2)  # Won't timeout
    timeout = await app.jobs.enqueue("slow_job", duration=5)  # Will timeout
    print(f"  - Slow job (ok): {slow.job_id}")
    print(f"  - Slow job (timeout): {timeout.job_id}")

    # Ad-hoc job
    adhoc = await app.jobs.enqueue_func(lambda: print("🎯 Ad-hoc job executed!"), queue="quick")
    print(f"  - Ad-hoc job: {adhoc.job_id}")

    # Wait for some jobs to complete
    print("\n⏳ Waiting for jobs to complete...")

    # Wait for email job
    email_result = await app.jobs.wait_for_job(email_job, timeout=10)
    print(f"\n📧 Email job result: {email_result.status.value}")
    if email_result.is_success:
        print(f"   Result: {email_result.result}")

    # Check data job status
    await asyncio.sleep(3)
    data_result = app.jobs.get_job_result(data_job.job_id)
    if data_result:
        print(f"\n🔄 Data job result: {data_result.status.value}")
        if data_result.is_success:
            print(f"   Result: {data_result.result}")

    # Show statistics
    await asyncio.sleep(5)  # Let more jobs complete
    stats = app.jobs.get_stats()
    print("\n📊 Job Statistics:")
    print(f"   Registered jobs: {stats['registered_jobs']}")
    print("   Worker pool:")
    print(f"     - Processed: {stats['worker_pool']['total_processed']}")
    print(f"     - Failed: {stats['worker_pool']['total_failed']}")
    print(f"     - Current: {stats['worker_pool']['total_current_jobs']}")

    # Keep running for a bit to see retries
    print("\n⏰ Running for 10 more seconds to see retries...")
    await asyncio.sleep(10)

    # Final stats
    final_stats = app.jobs.get_stats()
    print("\n📊 Final Statistics:")
    print(f"   Total processed: {final_stats['worker_pool']['total_processed']}")
    print(f"   Total failed: {final_stats['worker_pool']['total_failed']}")


# Run the application
if __name__ == "__main__":
    app.run(main)
