# Whiskey Jobs

Background job execution extension for Whiskey with support for queues, scheduling, retries, and full dependency injection.

## Features

- **Background Job Execution**: Run async/sync functions asynchronously with multiple workers
- **Job Queues**: Priority-based or FIFO queues with multiple named queues
- **Job Scheduling**: Cron expressions and periodic intervals
- **Retry Logic**: Automatic retries with exponential backoff
- **Job Chaining**: Chain jobs with success/failure dependencies
- **Full DI Support**: Jobs can use Whiskey's dependency injection
- **Monitoring**: Track job status, results, and statistics
- **CLI Integration**: Manage jobs from the command line

## Installation

```bash
pip install whiskey[jobs]
```

## Quick Start

```python
from whiskey import Whiskey
from whiskey_jobs import jobs_extension

app = Whiskey()
app.use(jobs_extension)

# Define a job
@app.job(queue="emails", priority=app.JobPriority.HIGH)
async def send_email(to: str, subject: str, email_service: EmailService):
    await email_service.send(to, subject)

# Schedule a job
@app.scheduled_job(cron="0 * * * *")  # Every hour
async def cleanup_old_data(db: Database):
    await db.cleanup_expired_sessions()

# Periodic job
@app.periodic_job(interval=300)  # Every 5 minutes
async def health_check(monitoring: MonitoringService):
    await monitoring.check_all_services()

# Run the app
async def main():
    # Enqueue a job
    job = await app.jobs.enqueue("send_email", "user@example.com", "Welcome!")
    
    # Wait for completion
    result = await app.jobs.wait_for_job(job)
    print(f"Job {job.job_id} completed: {result.is_success}")

app.run(main)
```

## Job Definition

### Basic Jobs

```python
@app.job()
async def process_data(data: dict, processor: DataProcessor):
    return await processor.process(data)

# With options
@app.job(
    queue="processing",
    priority=app.JobPriority.HIGH,
    max_retries=5,
    retry_delay=120,  # 2 minutes
    timeout=300,      # 5 minutes
)
async def important_task(task_id: int, service: ImportantService):
    await service.execute(task_id)
```

### Scheduled Jobs

```python
# Cron syntax
@app.scheduled_job(cron="0 0 * * *")  # Daily at midnight
async def daily_backup(backup_service: BackupService):
    await backup_service.backup_all()

# With date constraints
@app.scheduled_job(
    cron="0 */6 * * *",  # Every 6 hours
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 12, 31),
    timezone="America/New_York"
)
async def limited_time_job():
    print("This job runs only in 2024")
```

### Periodic Jobs

```python
@app.periodic_job(60)  # Every minute
async def sync_data(sync_service: SyncService):
    await sync_service.sync()

# With options
@app.periodic_job(
    interval=3600,  # Every hour
    queue="maintenance",
    start_date=datetime.now() + timedelta(hours=1)
)
async def deferred_maintenance():
    print("Maintenance task")
```

## Job Execution

### Enqueuing Jobs

```python
# Enqueue registered job
job = await app.jobs.enqueue("process_data", {"key": "value"})

# Enqueue with custom args/kwargs
job = await app.jobs.enqueue(
    "send_email",
    "user@example.com",  # positional arg
    subject="Welcome!",   # keyword arg
)

# Ad-hoc function execution
job = await app.jobs.enqueue_func(
    lambda: print("Quick task"),
    queue="quick",
    priority=app.JobPriority.LOW
)
```

### Job Chaining

```python
# Create a job chain
chain = app.jobs.create_job_chain()
job = await chain.add("upload_file", file_path="/tmp/data.csv") \
                 .add("parse_csv") \
                 .add("import_to_db") \
                 .add("send_notification", message="Import complete") \
                 .enqueue()

# Manual chaining
job1 = Job(metadata1)
job2 = Job(metadata2)
job3 = Job(metadata3)

job1.on_success(job2)
job1.on_failure(job3)
```

### Waiting for Results

```python
# Wait for completion
result = await app.jobs.wait_for_job(job, timeout=60)

if result.is_success:
    print(f"Result: {result.result}")
else:
    print(f"Error: {result.error}")

# Check status without waiting
result = app.jobs.get_job_result(job.job_id)
if result:
    print(f"Job completed with status: {result.status}")
```

## Configuration

### Extension Options

```python
app.use(
    jobs_extension,
    worker_pool_size=8,        # Number of workers
    worker_concurrency=20,     # Jobs per worker
    use_priority_queues=True,  # Priority vs FIFO
    auto_start=True,          # Auto-start on app startup
)
```

### Multiple Queues

```python
# Jobs automatically create their queues
@app.job(queue="emails")
async def email_job(): pass

@app.job(queue="uploads")
async def upload_job(): pass

@app.job(queue="analytics")
async def analytics_job(): pass

# Workers process all queues by default
# Or configure specific workers for specific queues (advanced)
```

### Priority Levels

```python
# Built-in priorities
app.JobPriority.CRITICAL  # 20
app.JobPriority.HIGH      # 10
app.JobPriority.NORMAL    # 5
app.JobPriority.LOW       # 1

# Custom priority values
@app.job(priority=15)  # Between HIGH and CRITICAL
async def custom_priority_job(): pass
```

## Monitoring

### Job Statistics

```python
# Get comprehensive stats
stats = app.jobs.get_stats()
print(f"Total processed: {stats['worker_pool']['total_processed']}")
print(f"Total failed: {stats['worker_pool']['total_failed']}")
print(f"Queue sizes: {stats['queues']['total_jobs']}")

# List jobs
print("Registered jobs:", app.jobs.list_jobs())
print("Scheduled jobs:", app.jobs.list_scheduled_jobs())
```

### CLI Commands

```bash
# Show job system status
python app.py jobs-status

# List all jobs
python app.py jobs-list

# Run a job manually
python app.py jobs-run send_email --args '["user@example.com"]' --kwargs '{"subject":"Test"}'
```

## Error Handling

### Retry Configuration

```python
@app.job(
    max_retries=3,
    retry_delay=60,  # Seconds between retries
)
async def flaky_job():
    # Job will retry up to 3 times on failure
    if random.random() < 0.5:
        raise Exception("Random failure")
    return "Success!"
```

### Timeout Handling

```python
@app.job(timeout=30)  # 30 second timeout
async def long_running_job():
    await asyncio.sleep(60)  # Will timeout
```

### Error Callbacks

```python
# Chain error handling
error_handler = await app.jobs.enqueue("handle_error")
main_job = await app.jobs.enqueue("risky_operation")
main_job.on_failure(error_handler)
```

## Advanced Usage

### Custom Job Classes

```python
from whiskey_jobs import Job, JobMetadata

# Create custom job
metadata = JobMetadata(
    func=my_function,
    name="custom_job",
    queue="special",
    priority=app.JobPriority.HIGH,
)

job = Job(metadata, args=(1, 2), kwargs={"key": "value"})
await app.jobs.queues.push(job)
```

### Direct Worker Control

```python
# Access worker pool
pool = app.jobs.worker_pool

# Get worker stats
stats = pool.get_stats()
for worker in stats["workers"]:
    print(f"{worker['name']}: {worker['processed']} processed")

# Access scheduler
scheduler = app.jobs.scheduler
scheduled = scheduler.list_jobs()
```

### Queue Management

```python
# Clear specific queue
await app.jobs.clear_queue("emails")

# Clear all queues
await app.jobs.clear_queue()

# Get queue size
size = app.jobs.queues.size("uploads")
```

## Best Practices

1. **Use Type Hints**: Enable full dependency injection support
   ```python
   @app.job()
   async def process(data: dict, service: MyService):  # service is injected
       return await service.process(data)
   ```

2. **Configure Timeouts**: Prevent jobs from running forever
   ```python
   @app.job(timeout=300)  # 5 minutes max
   ```

3. **Use Appropriate Queues**: Separate different types of work
   ```python
   @app.job(queue="critical")  # For time-sensitive tasks
   @app.job(queue="batch")     # For bulk processing
   ```

4. **Monitor Job Health**: Check statistics regularly
   ```python
   stats = app.jobs.get_stats()
   if stats["worker_pool"]["total_failed"] > 100:
       logger.warning("High failure rate detected")
   ```

5. **Handle Errors Gracefully**: Use retries and error handlers
   ```python
   @app.job(max_retries=3)
   async def resilient_job():
       try:
           # risky operation
       except TemporaryError:
           raise  # Will retry
       except PermanentError:
           return None  # Won't retry
   ```

## Integration with Other Extensions

### With ASGI

```python
app.use(asgi_extension)
app.use(jobs_extension)

@app.post("/upload")
async def upload_file(request: Request):
    # Process upload in background
    file_data = await request.form()
    job = await app.jobs.enqueue("process_upload", file_data["file"])
    return {"job_id": job.job_id}

@app.get("/job/{job_id}")
async def job_status(job_id: str):
    result = app.jobs.get_job_result(job_id)
    if result:
        return {"status": result.status.value, "done": True}
    return {"status": "pending", "done": False}
```

### With CLI

```python
app.use(cli_extension)
app.use(jobs_extension)

@app.command()
@app.argument("email")
async def send_test_email(email: str):
    job = await app.jobs.enqueue("send_email", email, "Test Subject")
    print(f"Email job queued: {job.job_id}")
```

## Roadmap

- [ ] Persistent job storage (Redis, PostgreSQL)
- [ ] Distributed workers across multiple processes/machines
- [ ] Job progress tracking
- [ ] Batch job processing
- [ ] Job priorities with preemption
- [ ] Web UI for job monitoring
- [ ] Webhook notifications
- [ ] Rate limiting and throttling