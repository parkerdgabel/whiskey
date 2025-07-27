#!/usr/bin/env python
"""Advanced ASGI patterns and mixed usage.

This example demonstrates:
- Background tasks and scheduling
- Event-driven architecture
- Mixed CLI and ASGI in the same application
- Custom error handlers
- Lifecycle hooks with ASGI
- Integration with async services

Usage:
    # Run as web server (default)
    python 03_advanced_patterns.py

    # Run batch processing
    python 03_advanced_patterns.py --batch

    # Run health check
    python 03_advanced_patterns.py --check
"""

import asyncio
import sys
from datetime import datetime

from whiskey import Whiskey, component, inject, singleton
from whiskey_asgi import Request, asgi_extension
from whiskey_cli import cli_extension


# Domain models and services
@singleton
class TaskQueue:
    """Background task queue."""

    def __init__(self):
        self.tasks: list[dict] = []
        self.processed = 0

    async def add(self, task_type: str, data: dict):
        """Add a task to the queue."""
        task = {
            "id": len(self.tasks) + 1,
            "type": task_type,
            "data": data,
            "created": datetime.now().isoformat(),
            "status": "pending",
        }
        self.tasks.append(task)

        # Emit event
        await app.emit("task.created", task)

        return task

    async def process_next(self):
        """Process the next pending task."""
        for task in self.tasks:
            if task["status"] == "pending":
                task["status"] = "processing"

                # Simulate processing
                await asyncio.sleep(1)

                task["status"] = "completed"
                task["completed"] = datetime.now().isoformat()
                self.processed += 1

                # Emit event
                await app.emit("task.completed", task)

                return task
        return None


@component
class HealthChecker:
    """Service health checker."""

    async def check_database(self) -> bool:
        """Simulate database check."""
        await asyncio.sleep(0.1)
        return True

    async def check_external_api(self) -> bool:
        """Simulate API check."""
        await asyncio.sleep(0.2)
        return True

    async def get_health_status(self):
        """Get overall health status."""
        db_ok = await self.check_database()
        api_ok = await self.check_external_api()

        return {
            "status": "healthy" if (db_ok and api_ok) else "unhealthy",
            "checks": {
                "database": "ok" if db_ok else "failed",
                "external_api": "ok" if api_ok else "failed",
            },
            "timestamp": datetime.now().isoformat(),
        }


@singleton
class MetricsCollector:
    """Collect application metrics."""

    def __init__(self):
        self.requests = 0
        self.errors = 0
        self.task_events = 0

    def record_request(self):
        self.requests += 1

    def record_error(self):
        self.errors += 1

    def record_task_event(self):
        self.task_events += 1

    def get_metrics(self):
        return {"requests": self.requests, "errors": self.errors, "task_events": self.task_events}


# Create application with both extensions
app = Whiskey()
app.use(asgi_extension)
app.use(cli_extension)


# Lifecycle hooks
@app.on_startup
async def startup():
    """Initialize application."""
    print("🚀 Application starting...")
    print(f"   Mode: {'ASGI' if '--batch' not in sys.argv else 'Batch'}")


@app.on_shutdown
@inject
async def shutdown(queue: TaskQueue, metrics: MetricsCollector):
    """Cleanup on shutdown."""
    print("\n📊 Shutdown statistics:")
    print(f"   Tasks processed: {queue.processed}")
    print(f"   Metrics: {metrics.get_metrics()}")


# Event handlers
@app.on("task.created")
@inject
def on_task_created(task: dict, metrics: MetricsCollector):
    """Handle task creation."""
    metrics.record_task_event()
    print(f"📝 Task created: {task['type']} #{task['id']}")


@app.on("task.completed")
@inject
def on_task_completed(task: dict, metrics: MetricsCollector):
    """Handle task completion."""
    metrics.record_task_event()
    print(f"✅ Task completed: {task['type']} #{task['id']}")


# Background task processor
@app.task
@inject
async def process_tasks(queue: TaskQueue):
    """Process tasks in the background (runs if started as server)."""
    while True:
        task = await queue.process_next()
        if not task:
            await asyncio.sleep(5)  # Wait before checking again


# HTTP Routes
@app.get("/")
async def index():
    """API overview."""
    return {
        "name": "Whiskey Advanced Patterns Demo",
        "endpoints": {
            "GET /": "This overview",
            "GET /health": "Health check",
            "GET /metrics": "Application metrics",
            "POST /tasks": "Create a background task",
            "GET /tasks": "List all tasks",
        },
    }


@app.get("/health")
@inject
async def health_check(checker: HealthChecker):
    """Health check endpoint."""
    status = await checker.get_health_status()
    return status, 200 if status["status"] == "healthy" else 503


@app.get("/metrics")
@inject
async def get_metrics(metrics: MetricsCollector, queue: TaskQueue):
    """Get application metrics."""
    return {
        **metrics.get_metrics(),
        "tasks": {
            "total": len(queue.tasks),
            "processed": queue.processed,
            "pending": sum(1 for t in queue.tasks if t["status"] == "pending"),
        },
    }


@app.post("/tasks")
@inject
async def create_task(request: Request, queue: TaskQueue):
    """Create a background task."""
    data = await request.json()

    if "type" not in data:
        return {"error": "Task type is required"}, 400

    task = await queue.add(data["type"], data.get("data", {}))
    return task, 201


@app.get("/tasks")
@inject
async def list_tasks(queue: TaskQueue):
    """List all tasks."""
    return {"tasks": queue.tasks, "total": len(queue.tasks), "processed": queue.processed}


# Custom error handler
@app.on_error
@inject
async def handle_error(error: Exception, metrics: MetricsCollector):
    """Log errors and update metrics."""
    metrics.record_error()
    print(f"❌ Error: {error}")


# Middleware for metrics
@app.middleware(priority=90)
@inject
async def metrics_middleware(request: Request, call_next, metrics: MetricsCollector):
    """Record request metrics."""
    metrics.record_request()
    return await call_next(request)


# CLI Commands for mixed usage
@app.command(name="batch")
@inject
async def run_batch(queue: TaskQueue):
    """Run batch processing."""
    print("🔄 Running batch processor...")

    # Add some tasks
    for i in range(5):
        await queue.add("batch_job", {"index": i})

    # Process all tasks
    while True:
        task = await queue.process_next()
        if not task:
            break

    print(f"✅ Batch complete: {queue.processed} tasks processed")


@app.command(name="check")
@inject
async def check_health(checker: HealthChecker):
    """Check system health."""
    print("🏥 Checking system health...")

    status = await checker.get_health_status()

    print(f"\nStatus: {status['status'].upper()}")
    for check, result in status["checks"].items():
        emoji = "✅" if result == "ok" else "❌"
        print(f"  {emoji} {check}: {result}")


# Custom main for programmatic usage
@inject
async def custom_main(queue: TaskQueue, metrics: MetricsCollector):
    """Custom main for non-server usage."""
    print("🎯 Running custom main...")

    # Create some tasks
    for i in range(3):
        await queue.add("custom_task", {"value": i * 10})

    # Process them
    while await queue.process_next():
        pass

    # Show metrics
    print(f"\n📊 Final metrics: {metrics.get_metrics()}")

    return "Custom processing complete"


# Main entry point with mode detection
if __name__ == "__main__":
    if "--batch" in sys.argv:
        # Run batch processing
        app.run()  # CLI runner will handle the batch command

    elif "--check" in sys.argv:
        # Run health check
        app.run()  # CLI runner will handle the check command

    elif "--custom" in sys.argv:
        # Run custom main
        result = app.run(custom_main)
        print(f"\nResult: {result}")

    else:
        # Default: Run as ASGI server
        print("🌐 Starting ASGI server...")
        print("📡 API available at: http://localhost:8000/")
        print("\nOther modes:")
        print("  --batch  : Run batch processor")
        print("  --check  : Run health check")
        print("  --custom : Run custom main")
        print("\nPress Ctrl+C to stop\n")

        app.run()  # ASGI runner will be used
