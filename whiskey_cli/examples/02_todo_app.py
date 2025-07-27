#!/usr/bin/env python
"""Complete TODO app demonstrating advanced CLI features.

This example demonstrates:
- Multiple commands working with shared state (singleton services)
- Async commands with dependency injection
- Command groups for organizing related commands
- Different argument types (string, int)
- List output formatting

Usage:
    python 02_todo_app.py add "Learn Whiskey framework"
    python 02_todo_app.py list
    python 02_todo_app.py complete 1
    python 02_todo_app.py delete 1
    python 02_todo_app.py db:backup
"""

from typing import Optional

from whiskey import Whiskey, inject, singleton
from whiskey_cli import cli_extension


# Domain model
class Task:
    """A task in our todo app."""

    def __init__(self, task_id: int, title: str, completed: bool = False):
        self.id = task_id
        self.title = title
        self.completed = completed


# Services (singletons maintain state across commands)
@singleton
class TaskService:
    """Service for managing tasks."""

    def __init__(self):
        self._tasks: list[Task] = []
        self._next_id = 1
        # Add some sample tasks
        self.add("Learn Whiskey framework")
        self.add("Build a CLI app")
        self.add("Master dependency injection")

    def add(self, title: str) -> Task:
        """Add a new task."""
        task = Task(self._next_id, title)
        self._tasks.append(task)
        self._next_id += 1
        return task

    def list_all(self) -> list[Task]:
        """List all tasks."""
        return self._tasks.copy()

    def get(self, task_id: int) -> Optional[Task]:
        """Get a task by ID."""
        return next((t for t in self._tasks if t.id == task_id), None)

    def complete(self, task_id: int) -> bool:
        """Mark a task as completed."""
        task = self.get(task_id)
        if task:
            task.completed = True
            return True
        return False

    def delete(self, task_id: int) -> bool:
        """Delete a task."""
        self._tasks = [t for t in self._tasks if t.id != task_id]
        return True


# Create the application
app = Whiskey()
app.use(cli_extension)


# Task management commands
@app.command()
@app.argument("title", help="Task description")
@inject
def add(title: str, tasks: TaskService):
    """Add a new task to your list."""
    task = tasks.add(title)
    print(f"✅ Added task #{task.id}: {task.title}")


@app.command(name="list")
@inject
def list_tasks(tasks: TaskService):
    """List all tasks."""
    all_tasks = tasks.list_all()

    if not all_tasks:
        print("No tasks found. Use 'add' to create one!")
        return

    print("\n📋 Your Tasks:\n")

    # Separate pending and completed
    pending = [t for t in all_tasks if not t.completed]
    completed = [t for t in all_tasks if t.completed]

    if pending:
        print("⏳ Pending:")
        for task in pending:
            print(f"  [{task.id}] {task.title}")

    if completed:
        print("\n✅ Completed:")
        for task in completed:
            print(f"  [{task.id}] {task.title} ✓")

    print(f"\nTotal: {len(pending)} pending, {len(completed)} completed")


@app.command()
@app.argument("task_id", type=int, help="ID of the task to complete")
@inject
def complete(task_id: int, tasks: TaskService):
    """Mark a task as completed."""
    task = tasks.get(task_id)
    if task and tasks.complete(task_id):
        print(f"✅ Completed: {task.title}")
    else:
        print(f"❌ Task #{task_id} not found")


@app.command()
@app.argument("task_id", type=int, help="ID of the task to delete")
@inject
def delete(task_id: int, tasks: TaskService):
    """Delete a task from your list."""
    task = tasks.get(task_id)
    if task:
        tasks.delete(task_id)
        print(f"🗑️  Deleted: {task.title}")
    else:
        print(f"❌ Task #{task_id} not found")


# Database command group
@app.command(name="db:backup", group="db")
@inject
async def backup(tasks: TaskService):
    """Backup all tasks (async example)."""
    all_tasks = tasks.list_all()
    print(f"📦 Backing up {len(all_tasks)} tasks...")

    # Simulate async operation
    import asyncio

    await asyncio.sleep(1)

    print("✅ Backup complete!")
    print(f"   Saved to: backup_{len(all_tasks)}_tasks.json")


@app.command(name="db:restore", group="db")
async def restore():
    """Restore tasks from backup."""
    print("📥 Restoring from backup...")

    # Simulate async operation
    import asyncio

    await asyncio.sleep(1)

    print("✅ Restore complete!")


# Main entry point
if __name__ == "__main__":
    # Run the CLI using the standardized run API
    app.run()
