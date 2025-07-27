#!/usr/bin/env python3
"""Task Manager CLI Whiskey - A complex example using Whiskey with CLI extension."""

import asyncio
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass, field
from enum import Enum

from whiskey import Whiskey, inject, singleton, component
from whiskey_cli import cli_extension


# Domain Models
class TaskStatus(Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    ARCHIVED = "archived"


class Priority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class Task:
    id: Optional[int] = None
    title: str = ""
    description: str = ""
    status: TaskStatus = TaskStatus.TODO
    priority: Priority = Priority.MEDIUM
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    due_date: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    assignee: Optional[str] = None


# Services
@singleton
class DatabaseService:
    """Manages SQLite database connection and operations."""
    
    def __init__(self):
        self.db_path = Path.home() / ".taskmanager" / "tasks.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL,
                priority INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                due_date TEXT,
                tags TEXT,
                assignee TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                details TEXT,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (task_id) REFERENCES tasks(id)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn


@component
class TaskRepository:
    """Repository for task persistence."""
    
    def __init__(self, db: DatabaseService):
        self.db = db
    
    def create(self, task: Task) -> Task:
        """Create a new task."""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO tasks (title, description, status, priority, created_at, updated_at, due_date, tags, assignee)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task.title,
            task.description,
            task.status.value,
            task.priority.value,
            task.created_at.isoformat(),
            task.updated_at.isoformat(),
            task.due_date.isoformat() if task.due_date else None,
            json.dumps(task.tags),
            task.assignee
        ))
        
        task.id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return task
    
    def get(self, task_id: int) -> Optional[Task]:
        """Get a task by ID."""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return self._row_to_task(row)
        return None
    
    def list_all(self, status: Optional[TaskStatus] = None) -> List[Task]:
        """List all tasks, optionally filtered by status."""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        if status:
            cursor.execute("SELECT * FROM tasks WHERE status = ? ORDER BY priority DESC, created_at DESC", 
                         (status.value,))
        else:
            cursor.execute("SELECT * FROM tasks ORDER BY priority DESC, created_at DESC")
        
        rows = cursor.fetchall()
        conn.close()
        
        return [self._row_to_task(row) for row in rows]
    
    def update(self, task: Task) -> Task:
        """Update an existing task."""
        task.updated_at = datetime.now()
        
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE tasks 
            SET title = ?, description = ?, status = ?, priority = ?, 
                updated_at = ?, due_date = ?, tags = ?, assignee = ?
            WHERE id = ?
        """, (
            task.title,
            task.description,
            task.status.value,
            task.priority.value,
            task.updated_at.isoformat(),
            task.due_date.isoformat() if task.due_date else None,
            json.dumps(task.tags),
            task.assignee,
            task.id
        ))
        
        conn.commit()
        conn.close()
        
        return task
    
    def delete(self, task_id: int) -> bool:
        """Delete a task."""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        deleted = cursor.rowcount > 0
        
        conn.commit()
        conn.close()
        
        return deleted
    
    def _row_to_task(self, row: sqlite3.Row) -> Task:
        """Convert a database row to a Task object."""
        return Task(
            id=row['id'],
            title=row['title'],
            description=row['description'] or '',
            status=TaskStatus(row['status']),
            priority=Priority(row['priority']),
            created_at=datetime.fromisoformat(row['created_at']),
            updated_at=datetime.fromisoformat(row['updated_at']),
            due_date=datetime.fromisoformat(row['due_date']) if row['due_date'] else None,
            tags=json.loads(row['tags']) if row['tags'] else [],
            assignee=row['assignee']
        )


@component
class TaskHistoryService:
    """Service for tracking task history."""
    
    def __init__(self, db: DatabaseService):
        self.db = db
    
    async def log_action(self, task_id: int, action: str, details: Optional[str] = None):
        """Log an action on a task."""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO task_history (task_id, action, details, timestamp)
            VALUES (?, ?, ?, ?)
        """, (task_id, action, details, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()


@component
class NotificationService:
    """Service for sending notifications."""
    
    async def notify(self, message: str, level: str = "info"):
        """Send a notification (simulated)."""
        emoji = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "❌"}.get(level, "📢")
        print(f"{emoji}  {message}")
        # In a real app, this might send emails, push notifications, etc.


@component
class TaskService:
    """High-level task management service."""
    
    def __init__(self, 
                 repo: TaskRepository, 
                 history: TaskHistoryService,
                 notifier: NotificationService):
        self.repo = repo
        self.history = history
        self.notifier = notifier
    
    async def create_task(self, title: str, description: str = "", 
                         priority: Priority = Priority.MEDIUM,
                         due_date: Optional[datetime] = None,
                         tags: Optional[List[str]] = None,
                         assignee: Optional[str] = None) -> Task:
        """Create a new task with notifications."""
        task = Task(
            title=title,
            description=description,
            priority=priority,
            due_date=due_date,
            tags=tags or [],
            assignee=assignee
        )
        
        task = self.repo.create(task)
        
        await self.history.log_action(task.id, "created", f"Task '{title}' created")
        await self.notifier.notify(f"Task #{task.id} '{title}' created", "success")
        
        return task
    
    async def update_status(self, task_id: int, new_status: TaskStatus) -> Optional[Task]:
        """Update task status with history tracking."""
        task = self.repo.get(task_id)
        if not task:
            await self.notifier.notify(f"Task #{task_id} not found", "error")
            return None
        
        old_status = task.status
        task.status = new_status
        task = self.repo.update(task)
        
        await self.history.log_action(
            task_id, 
            "status_changed", 
            f"{old_status.value} -> {new_status.value}"
        )
        await self.notifier.notify(
            f"Task #{task_id} status changed to {new_status.value}", 
            "success"
        )
        
        return task


# Create the application
app = Whiskey()
app.use(cli_extension)


# CLI Commands
@app.command()
@inject
async def add(title: str, service: TaskService):
    """Add a new task."""
    task = await service.create_task(title)
    print(f"Created task #{task.id}: {task.title}")


@app.command()
@app.option("--description", help="Task description")
@app.option("--priority", default="2", help="Priority (1-4)")
@app.option("--due", help="Due date (YYYY-MM-DD)")
@app.option("--tags", help="Tags for the task (comma-separated)")
@app.option("--assignee", help="Assign to someone")
@inject
async def create(title: str, description: str, priority: str, due: Optional[str], 
                tags: str, assignee: Optional[str], service: TaskService):
    """Create a task with full details."""
    due_date = None
    if due:
        try:
            due_date = datetime.fromisoformat(due)
        except ValueError:
            print("Invalid date format. Use YYYY-MM-DD")
            return
    
    try:
        priority_enum = Priority(int(priority))
    except ValueError:
        print("Invalid priority. Use 1 (low), 2 (medium), 3 (high), or 4 (critical)")
        return
    
    task = await service.create_task(
        title=title,
        description=description,
        priority=priority_enum,
        due_date=due_date,
        tags=[t.strip() for t in tags.split(',')] if tags else [],
        assignee=assignee
    )
    
    print(f"\nCreated task #{task.id}")
    print(f"Title: {task.title}")
    print(f"Priority: {task.priority.name}")
    if task.due_date:
        print(f"Due: {task.due_date.strftime('%Y-%m-%d')}")
    if task.tags:
        print(f"Tags: {', '.join(task.tags)}")
    if task.assignee:
        print(f"Assignee: {task.assignee}")


@app.command()
@app.option("--status", help="Filter by status (todo, in_progress, done, archived)")
@app.option("--assignee", help="Filter by assignee")
@inject
def list(status: Optional[str], assignee: Optional[str], repo: TaskRepository):
    """List all tasks."""
    status_filter = None
    if status:
        try:
            status_filter = TaskStatus(status)
        except ValueError:
            print(f"Invalid status: {status}")
            return
    
    tasks = repo.list_all(status_filter)
    
    if assignee:
        tasks = [t for t in tasks if t.assignee == assignee]
    
    if not tasks:
        print("No tasks found.")
        return
    
    # Group by status
    by_status = {}
    for task in tasks:
        by_status.setdefault(task.status, []).append(task)
    
    # Display tasks
    for status, status_tasks in by_status.items():
        print(f"\n{status.value.upper()} ({len(status_tasks)})")
        print("-" * 40)
        
        for task in status_tasks:
            priority_symbol = ["", "🟢", "🟡", "🟠", "🔴"][task.priority.value]
            due_str = ""
            if task.due_date:
                days_until = (task.due_date - datetime.now()).days
                if days_until < 0:
                    due_str = f" (⚠️  OVERDUE by {-days_until} days)"
                elif days_until == 0:
                    due_str = " (⚠️  DUE TODAY)"
                elif days_until <= 3:
                    due_str = f" (Due in {days_until} days)"
            
            assignee_str = f" @{task.assignee}" if task.assignee else ""
            tags_str = f" [{', '.join(task.tags)}]" if task.tags else ""
            
            print(f"{priority_symbol} #{task.id}: {task.title}{due_str}{assignee_str}{tags_str}")


@app.command()
@inject
def show(task_id: int, repo: TaskRepository, db: DatabaseService):
    """Show detailed information about a task."""
    task = repo.get(task_id)
    if not task:
        print(f"Task #{task_id} not found")
        return
    
    print(f"\nTask #{task.id}")
    print("=" * 50)
    print(f"Title: {task.title}")
    print(f"Status: {task.status.value}")
    print(f"Priority: {task.priority.name}")
    print(f"Created: {task.created_at.strftime('%Y-%m-%d %H:%M')}")
    print(f"Updated: {task.updated_at.strftime('%Y-%m-%d %H:%M')}")
    
    if task.description:
        print(f"\nDescription:\n{task.description}")
    
    if task.due_date:
        print(f"\nDue Date: {task.due_date.strftime('%Y-%m-%d')}")
        days_until = (task.due_date - datetime.now()).days
        if days_until < 0:
            print(f"⚠️  OVERDUE by {-days_until} days")
        elif days_until == 0:
            print("⚠️  DUE TODAY")
        else:
            print(f"Due in {days_until} days")
    
    if task.assignee:
        print(f"\nAssignee: {task.assignee}")
    
    if task.tags:
        print(f"\nTags: {', '.join(task.tags)}")
    
    # Show history
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT action, details, timestamp 
        FROM task_history 
        WHERE task_id = ? 
        ORDER BY timestamp DESC 
        LIMIT 10
    """, (task_id,))
    
    history = cursor.fetchall()
    conn.close()
    
    if history:
        print("\nRecent History:")
        for entry in history:
            timestamp = datetime.fromisoformat(entry['timestamp'])
            details = f" - {entry['details']}" if entry['details'] else ""
            print(f"  {timestamp.strftime('%Y-%m-%d %H:%M')} - {entry['action']}{details}")


@app.command()
@inject
async def start(task_id: int, service: TaskService):
    """Start working on a task (set status to in_progress)."""
    task = await service.update_status(task_id, TaskStatus.IN_PROGRESS)
    if task:
        print(f"Started working on task #{task_id}: {task.title}")


@app.command()
@inject  
async def done(task_id: int, service: TaskService):
    """Mark a task as done."""
    task = await service.update_status(task_id, TaskStatus.DONE)
    if task:
        print(f"Completed task #{task_id}: {task.title} ✅")


@app.command()
@inject
async def archive(task_id: int, service: TaskService):
    """Archive a completed task."""
    task = service.repo.get(task_id)
    if not task:
        print(f"Task #{task_id} not found")
        return
    
    if task.status != TaskStatus.DONE:
        print(f"Can only archive completed tasks. Task #{task_id} is {task.status.value}")
        return
    
    task = await service.update_status(task_id, TaskStatus.ARCHIVED)
    if task:
        print(f"Archived task #{task_id}: {task.title}")


@app.command()
@app.option("--force", is_flag=True, help="Skip confirmation")
@inject
def delete(task_id: int, force: bool, repo: TaskRepository):
    """Delete a task."""
    task = repo.get(task_id)
    if not task:
        print(f"Task #{task_id} not found")
        return
    
    if not force:
        confirm = input(f"Delete task #{task_id}: {task.title}? [y/N] ")
        if confirm.lower() != 'y':
            print("Cancelled")
            return
    
    if repo.delete(task_id):
        print(f"Deleted task #{task_id}")
    else:
        print(f"Failed to delete task #{task_id}")


# Task group for bulk operations
task_group = app.group("tasks", description="Bulk task operations")


@task_group.command("cleanup")
@inject
async def cleanup_tasks(repo: TaskRepository, notifier: NotificationService):
    """Archive all completed tasks older than 7 days."""
    tasks = repo.list_all(TaskStatus.DONE)
    archived_count = 0
    
    for task in tasks:
        days_old = (datetime.now() - task.updated_at).days
        if days_old > 7:
            task.status = TaskStatus.ARCHIVED
            repo.update(task)
            archived_count += 1
    
    await notifier.notify(f"Archived {archived_count} old completed tasks", "success")


@task_group.command("export")
@app.option("--format", default="json", help="Export format (json, csv)")
@inject
def export_tasks(format: str, repo: TaskRepository):
    """Export all tasks to a file."""
    tasks = repo.list_all()
    
    if format == "json":
        data = []
        for task in tasks:
            data.append({
                "id": task.id,
                "title": task.title,
                "description": task.description,
                "status": task.status.value,
                "priority": task.priority.value,
                "created_at": task.created_at.isoformat(),
                "updated_at": task.updated_at.isoformat(),
                "due_date": task.due_date.isoformat() if task.due_date else None,
                "tags": task.tags,
                "assignee": task.assignee
            })
        
        filename = f"tasks_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"Exported {len(tasks)} tasks to {filename}")
    
    elif format == "csv":
        import csv
        
        filename = f"tasks_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["ID", "Title", "Status", "Priority", "Created", "Updated", "Due", "Assignee", "Tags"])
            
            for task in tasks:
                writer.writerow([
                    task.id,
                    task.title,
                    task.status.value,
                    task.priority.name,
                    task.created_at.strftime('%Y-%m-%d %H:%M'),
                    task.updated_at.strftime('%Y-%m-%d %H:%M'),
                    task.due_date.strftime('%Y-%m-%d') if task.due_date else "",
                    task.assignee or "",
                    ", ".join(task.tags)
                ])
        
        print(f"Exported {len(tasks)} tasks to {filename}")
    
    else:
        print(f"Unknown format: {format}")


# Stats command
@app.command()
@inject
def stats(repo: TaskRepository):
    """Show task statistics."""
    all_tasks = repo.list_all()
    
    if not all_tasks:
        print("No tasks found.")
        return
    
    # Count by status
    by_status = {}
    by_priority = {}
    by_assignee = {}
    overdue_count = 0
    
    for task in all_tasks:
        by_status[task.status] = by_status.get(task.status, 0) + 1
        by_priority[task.priority] = by_priority.get(task.priority, 0) + 1
        
        if task.assignee:
            by_assignee[task.assignee] = by_assignee.get(task.assignee, 0) + 1
        
        if task.due_date and task.status in (TaskStatus.TODO, TaskStatus.IN_PROGRESS):
            if task.due_date < datetime.now():
                overdue_count += 1
    
    print("\nTask Statistics")
    print("=" * 40)
    print(f"Total tasks: {len(all_tasks)}")
    
    print("\nBy Status:")
    for status in TaskStatus:
        count = by_status.get(status, 0)
        print(f"  {status.value}: {count}")
    
    print("\nBy Priority:")
    for priority in sorted(Priority, key=lambda p: p.value, reverse=True):
        count = by_priority.get(priority, 0)
        symbol = ["", "🟢", "🟡", "🟠", "🔴"][priority.value]
        print(f"  {symbol} {priority.name}: {count}")
    
    if by_assignee:
        print("\nBy Assignee:")
        for assignee, count in sorted(by_assignee.items(), key=lambda x: x[1], reverse=True):
            print(f"  {assignee}: {count}")
    
    if overdue_count:
        print(f"\n⚠️  Overdue tasks: {overdue_count}")


# Interactive mode
@app.command()
@inject
async def interactive(service: TaskService, repo: TaskRepository):
    """Start interactive task management mode."""
    print("Task Manager - Interactive Mode")
    print("Type 'help' for commands, 'quit' to exit")
    
    while True:
        try:
            command = input("\n> ").strip().lower()
            
            if command == "quit" or command == "exit":
                break
            
            elif command == "help":
                print("\nCommands:")
                print("  list - Show all tasks")
                print("  add <title> - Quick add a task")
                print("  start <id> - Start working on a task")
                print("  done <id> - Mark a task as done")
                print("  show <id> - Show task details")
                print("  quit - Exit interactive mode")
            
            elif command.startswith("list"):
                tasks = repo.list_all()
                for task in tasks[:10]:  # Show first 10
                    status_icon = {"todo": "⬜", "in_progress": "🔄", "done": "✅", "archived": "📦"}
                    icon = status_icon.get(task.status.value, "❓")
                    print(f"{icon} #{task.id}: {task.title}")
                if len(tasks) > 10:
                    print(f"... and {len(tasks) - 10} more")
            
            elif command.startswith("add "):
                title = command[4:].strip()
                if title:
                    task = await service.create_task(title)
                    print(f"Created task #{task.id}")
            
            elif command.startswith("start "):
                try:
                    task_id = int(command[6:])
                    await service.update_status(task_id, TaskStatus.IN_PROGRESS)
                except ValueError:
                    print("Invalid task ID")
            
            elif command.startswith("done "):
                try:
                    task_id = int(command[5:])
                    await service.update_status(task_id, TaskStatus.DONE)
                except ValueError:
                    print("Invalid task ID")
            
            elif command.startswith("show "):
                try:
                    task_id = int(command[5:])
                    task = repo.get(task_id)
                    if task:
                        print(f"\n#{task.id}: {task.title}")
                        print(f"Status: {task.status.value}")
                        print(f"Priority: {task.priority.name}")
                        if task.description:
                            print(f"Description: {task.description}")
                    else:
                        print("Task not found")
                except ValueError:
                    print("Invalid task ID")
            
            elif command:
                print(f"Unknown command: {command}")
                
        except KeyboardInterrupt:
            print("\nUse 'quit' to exit")
        except Exception as e:
            print(f"Error: {e}")
    
    print("\nGoodbye!")


if __name__ == "__main__":
    app.run_cli()