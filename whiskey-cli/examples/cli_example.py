"""CLI application example using Whiskey's IoC system."""

import asyncio
from typing import List, Optional

import click
from whiskey import Application, inject, singleton
from whiskey_cli import cli_extension


# Domain models
class Task:
    """A task in our todo app."""
    def __init__(self, id: int, title: str, completed: bool = False):
        self.id = id
        self.title = title
        self.completed = completed


# Services
@singleton
class TaskService:
    """Service for managing tasks."""
    
    def __init__(self):
        self._tasks: List[Task] = []
        self._next_id = 1
        # Add some sample tasks
        self.add("Learn Whiskey framework")
        self.add("Build a CLI app", completed=True)
    
    def add(self, title: str, completed: bool = False) -> Task:
        """Add a new task."""
        task = Task(self._next_id, title, completed)
        self._tasks.append(task)
        self._next_id += 1
        return task
    
    def list_all(self) -> List[Task]:
        """List all tasks."""
        return self._tasks.copy()
    
    def get(self, task_id: int) -> Optional[Task]:
        """Get a task by ID."""
        for task in self._tasks:
            if task.id == task_id:
                return task
        return None
    
    def complete(self, task_id: int) -> bool:
        """Mark a task as completed."""
        task = self.get(task_id)
        if task:
            task.completed = True
            return True
        return False
    
    def delete(self, task_id: int) -> bool:
        """Delete a task."""
        for i, task in enumerate(self._tasks):
            if task.id == task_id:
                del self._tasks[i]
                return True
        return False


@singleton
class ConfigService:
    """Application configuration."""
    
    def __init__(self):
        self.app_name = "Whiskey Todo CLI"
        self.version = "1.0.0"
        self.show_completed = True


# Create the application
app = Application()
app.use(cli_extension)

# Register services
app.component(TaskService)
app.component(ConfigService)


# CLI Commands
@app.command()
@click.argument("title")
@inject
async def add(title: str, task_service: TaskService):
    """Add a new task."""
    task = task_service.add(title)
    click.echo(f"✅ Added task #{task.id}: {task.title}")
    
    # Emit event
    await app.emit("task.created", {"id": task.id, "title": task.title})


@app.command(name="list")
@inject
def list_tasks(task_service: TaskService, config: ConfigService):
    """List all tasks."""
    tasks = task_service.list_all()
    
    if not tasks:
        click.echo("No tasks found. Use 'add' to create one!")
        return
    
    click.echo(f"\n{config.app_name} - Tasks:\n")
    
    pending = [t for t in tasks if not t.completed]
    completed = [t for t in tasks if t.completed]
    
    if pending:
        click.echo("📋 Pending:")
        for task in pending:
            click.echo(f"  [{task.id}] {task.title}")
    
    if completed and config.show_completed:
        click.echo("\n✅ Completed:")
        for task in completed:
            click.echo(f"  [{task.id}] {task.title}")
    
    click.echo(f"\nTotal: {len(pending)} pending, {len(completed)} completed")


@app.command()
@click.argument("task_id", type=int)
@inject
async def complete(task_id: int, task_service: TaskService):
    """Mark a task as completed."""
    if task_service.complete(task_id):
        task = task_service.get(task_id)
        click.echo(f"✅ Completed task #{task_id}: {task.title}")
        await app.emit("task.completed", {"id": task_id})
    else:
        click.echo(f"❌ Task #{task_id} not found", err=True)


@app.command()
@click.argument("task_id", type=int)
@inject
async def delete(task_id: int, task_service: TaskService):
    """Delete a task."""
    task = task_service.get(task_id)
    if task and task_service.delete(task_id):
        click.echo(f"🗑️  Deleted task #{task_id}: {task.title}")
        await app.emit("task.deleted", {"id": task_id})
    else:
        click.echo(f"❌ Task #{task_id} not found", err=True)


@app.command()
@inject
def config(config_service: ConfigService):
    """Show configuration."""
    click.echo(f"App Name: {config_service.app_name}")
    click.echo(f"Version: {config_service.version}")
    click.echo(f"Show Completed: {config_service.show_completed}")


# Command groups example
db_group = app.group("db")


@db_group.command()
async def migrate():
    """Run database migrations."""
    click.echo("Running migrations...")
    await asyncio.sleep(1)
    click.echo("✅ Migrations complete!")


@db_group.command()
@inject
async def backup(task_service: TaskService):
    """Backup the database."""
    tasks = task_service.list_all()
    click.echo(f"Backing up {len(tasks)} tasks...")
    await asyncio.sleep(0.5)
    click.echo("✅ Backup complete!")


# Event handlers (these run during CLI commands)
@app.on("task.*")
async def log_task_events(data: dict):
    """Log all task events."""
    # In a real app, this might write to a log file
    print(f"[Event] Task event: {data}")


# Background task (won't run in CLI mode, but shows the pattern)
@app.task
@inject
async def cleanup_old_tasks(task_service: TaskService):
    """This would run if app.run() was called instead of app.run_cli()."""
    # This is just an example - background tasks don't run in CLI mode
    pass


# Main entry point
if __name__ == "__main__":
    # Run as CLI
    app.run_cli()
    
    # Alternative: Run with a main function
    # @app.main
    # @inject
    # async def main(task_service: TaskService):
    #     tasks = task_service.list_all()
    #     print(f"Running with {len(tasks)} tasks")
    # 
    # app.run()