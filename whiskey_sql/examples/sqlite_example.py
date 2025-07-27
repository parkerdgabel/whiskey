"""SQLite example for Whiskey SQL extension."""

from dataclasses import dataclass

from whiskey import Whiskey, inject, singleton
from whiskey_sql import SQL, Database, sql_extension


# Define your data models
@dataclass
class Todo:
    id: int
    title: str
    completed: bool
    created_at: str  # SQLite stores timestamps as strings


# Create application with SQL extension
app = Whiskey()
app.use(sql_extension)

# Configure SQLite database
app.configure_database(
    url="sqlite:///example_todos.db",  # Use a file
    # url="sqlite://:memory:",  # Or use in-memory for testing
    echo_queries=True,
)


# Define SQL queries
@app.sql("todos")
class TodoQueries:
    """SQL queries for todo operations."""

    create_table = SQL("""
        CREATE TABLE IF NOT EXISTS todos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            completed BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    get_by_id = SQL("""
        SELECT id, title, completed, created_at
        FROM todos
        WHERE id = :id
    """)

    list_all = SQL("""
        SELECT id, title, completed, created_at
        FROM todos
        ORDER BY created_at DESC
    """)

    list_pending = SQL("""
        SELECT id, title, completed, created_at
        FROM todos
        WHERE completed = 0
        ORDER BY created_at ASC
    """)

    create = SQL("""
        INSERT INTO todos (title, completed)
        VALUES (:title, :completed)
    """)

    toggle = SQL("""
        UPDATE todos
        SET completed = NOT completed
        WHERE id = :id
    """)

    delete = SQL("""
        DELETE FROM todos
        WHERE id = :id
    """)

    # SQLite-specific: Using JSON functions (SQLite 3.38+)
    stats = SQL("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) as completed,
            SUM(CASE WHEN completed = 0 THEN 1 ELSE 0 END) as pending
        FROM todos
    """)


@singleton
class TodoService:
    """Service for todo operations."""

    def __init__(self, db: Database, queries: TodoQueries):
        self.db = db
        self.queries = queries

    async def create_todo(self, title: str, completed: bool = False) -> int:
        """Create a new todo and return its ID."""
        await self.db.execute(self.queries.create, {"title": title, "completed": completed})

        # Get the last inserted ID (SQLite specific)
        todo_id = await self.db.fetch_val(SQL("SELECT last_insert_rowid()"))
        return todo_id

    async def get_todo(self, todo_id: int) -> Todo | None:
        """Get todo by ID."""
        return await self.db.fetch_one(self.queries.get_by_id, {"id": todo_id}, Todo)

    async def list_todos(self, pending_only: bool = False) -> list[Todo]:
        """List todos."""
        query = self.queries.list_pending if pending_only else self.queries.list_all
        return await self.db.fetch_all(query, result_type=Todo)

    async def toggle_todo(self, todo_id: int) -> bool:
        """Toggle todo completion status."""
        status = await self.db.execute(self.queries.toggle, {"id": todo_id})
        return "UPDATE 1" in status

    async def delete_todo(self, todo_id: int) -> bool:
        """Delete a todo."""
        status = await self.db.execute(self.queries.delete, {"id": todo_id})
        return "DELETE 1" in status

    async def get_stats(self) -> dict:
        """Get todo statistics."""
        row = await self.db.fetch_one(self.queries.stats)
        return row or {"total": 0, "completed": 0, "pending": 0}


# Initialize database
@app.on_startup
async def init_database(db: Database, queries: TodoQueries):
    """Create database tables on startup."""
    print("🗄️  Initializing SQLite database...")

    await db.execute(queries.create_table)

    print("✅ Database ready")


# Demo application
@app.main
@inject
async def main(service: TodoService, db: Database):
    """Demonstrate SQLite usage."""

    print("\n=== Whiskey SQL SQLite Example ===\n")

    # Create some todos
    print("Creating todos...")
    todo1_id = await service.create_todo("Learn Whiskey DI")
    print(f"✅ Created todo ID: {todo1_id}")

    todo2_id = await service.create_todo("Build a project with Whiskey")
    print(f"✅ Created todo ID: {todo2_id}")

    todo3_id = await service.create_todo("Write documentation", completed=True)
    print(f"✅ Created todo ID: {todo3_id}")

    # List all todos
    print("\nAll todos:")
    todos = await service.list_todos()
    for todo in todos:
        status = "✓" if todo.completed else "○"
        print(f"  {status} [{todo.id}] {todo.title}")

    # List pending todos
    print("\nPending todos:")
    pending = await service.list_todos(pending_only=True)
    for todo in pending:
        print(f"  ○ [{todo.id}] {todo.title}")

    # Toggle a todo
    print(f"\nToggling todo {todo1_id}...")
    if await service.toggle_todo(todo1_id):
        print("✅ Toggled successfully")

    # Get stats
    print("\nTodo statistics:")
    stats = await service.get_stats()
    print(f"  Total: {stats['total']}")
    print(f"  Completed: {stats['completed']}")
    print(f"  Pending: {stats['pending']}")

    # Demonstrate transactions
    print("\nDemonstrating transactions...")
    try:
        async with db.transaction():
            # Create a todo
            await db.execute(
                SQL("INSERT INTO todos (title) VALUES (:title)"),
                {"title": "This will be rolled back"},
            )

            # Force an error
            raise ValueError("Simulating error")
    except ValueError:
        print("❌ Transaction rolled back")

    # Verify rollback
    rollback_check = await db.fetch_val(
        SQL("SELECT COUNT(*) FROM todos WHERE title = :title"),
        {"title": "This will be rolled back"},
    )
    print(f"Todo exists after rollback: {rollback_check > 0}")

    # Demonstrate SQLite-specific features
    print("\nSQLite-specific features:")

    # Get SQLite version
    version = await db.fetch_val(SQL("SELECT sqlite_version()"))
    print(f"  SQLite version: {version}")

    # Check compile options
    has_json = await db.fetch_val(SQL("SELECT sqlite_compileoption_used('ENABLE_JSON1')"))
    print(f"  JSON support: {'Yes' if has_json else 'No'}")

    # Use streaming for large results
    print("\nStreaming todos:")
    async with db.stream(SQL("SELECT * FROM todos")) as cursor:
        async for row in cursor:
            print(f"  Stream: {row['title']}")

    print("\n✅ Demo completed!")

    # Cleanup (optional)
    # await db.execute(SQL("DROP TABLE todos"))


if __name__ == "__main__":
    # Run the application
    app.run()
