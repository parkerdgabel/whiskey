# Whiskey SQL Extension 🗃️

Pure SQL templating for Whiskey applications. Write real SQL, not ORM abstractions, with full type safety and dependency injection support.

## Why Whiskey SQL?

- **SQL First**: Write and maintain pure SQL queries
- **Type Safe**: Optional dataclass mapping for query results  
- **DI Integrated**: Seamlessly works with Whiskey's injection system
- **Simple**: Minimal API that gets out of your way
- **Fast**: Connection pooling, prepared statements, streaming support
- **Testable**: Built-in test utilities with auto-migrations

## Installation

```bash
pip install whiskey[sql]  # Includes whiskey-sql with asyncpg
# or
pip install whiskey-sql[postgresql]  # PostgreSQL support
pip install whiskey-sql[mysql]       # MySQL support  
pip install whiskey-sql[sqlite]      # SQLite support
pip install whiskey-sql[all]         # All database drivers
```

## Quick Start

```python
from dataclasses import dataclass
from datetime import datetime
from whiskey import Whiskey, inject, singleton
from whiskey_sql import sql_extension, SQL, Database

# Create app with SQL extension
app = Whiskey()
app.use(sql_extension)

# Configure database
app.configure_database(
    url="postgresql://localhost/myapp",
    pool_size=20
)

# Define result types
@dataclass
class User:
    id: int
    name: str
    email: str
    created_at: datetime

# Define SQL queries
@app.sql("users")
class UserQueries:
    get_by_id = SQL("""
        SELECT id, name, email, created_at
        FROM users
        WHERE id = :id
    """)
    
    create = SQL("""
        INSERT INTO users (name, email)
        VALUES (:name, :email)
        RETURNING id, name, email, created_at
    """)

# Create services
@singleton
class UserService:
    def __init__(self, db: Database, queries: UserQueries):
        self.db = db
        self.queries = queries
    
    async def get_user(self, user_id: int) -> User | None:
        return await self.db.fetch_one(
            self.queries.get_by_id,
            {"id": user_id},
            User
        )
    
    async def create_user(self, name: str, email: str) -> User:
        async with self.db.transaction():
            return await self.db.fetch_one(
                self.queries.create,
                {"name": name, "email": email},
                User
            )

# Use in your application
@app.main
@inject
async def main(service: UserService):
    user = await service.create_user("Alice", "alice@example.com")
    print(f"Created user: {user.name}")

if __name__ == "__main__":
    app.run()
```

## Core Features

### 1. SQL Templates

Define SQL queries as reusable templates:

```python
@app.sql("products")
class ProductQueries:
    # Simple query
    get_all = SQL("SELECT * FROM products ORDER BY name")
    
    # Parameterized query
    find_by_category = SQL("""
        SELECT * FROM products 
        WHERE category = :category
        AND price <= :max_price
        ORDER BY price DESC
    """)
    
    # Dynamic query builder
    @staticmethod
    def search(filters: dict) -> SQL:
        conditions = []
        if filters.get('name'):
            conditions.append("name ILIKE :name_pattern")
        if filters.get('min_price'):
            conditions.append("price >= :min_price")
            
        where = " AND ".join(conditions) if conditions else "1=1"
        return SQL(f"SELECT * FROM products WHERE {where}")
```

### 2. Database Operations

Execute queries with different result types:

```python
@inject
async def database_examples(db: Database):
    # Fetch single row as dataclass
    user = await db.fetch_one(
        SQL("SELECT * FROM users WHERE id = :id"),
        {"id": 1},
        User
    )
    
    # Fetch multiple rows
    users = await db.fetch_all(
        SQL("SELECT * FROM users WHERE active = true"),
        result_type=User
    )
    
    # Fetch single value
    count = await db.fetch_val(
        SQL("SELECT COUNT(*) FROM users")
    )
    
    # Fetch row as tuple
    stats = await db.fetch_row(
        SQL("SELECT COUNT(*), AVG(age) FROM users")
    )
    
    # Execute without results
    await db.execute(
        SQL("UPDATE users SET last_login = NOW() WHERE id = :id"),
        {"id": 1}
    )
    
    # Batch operations
    await db.execute_many(
        SQL("INSERT INTO logs (level, message) VALUES (:level, :message)"),
        [
            {"level": "info", "message": "Started"},
            {"level": "error", "message": "Failed"},
        ]
    )
```

### 3. Transactions

Use transactions for data integrity:

```python
@inject
async def transfer_funds(
    db: Database,
    from_account: int,
    to_account: int,
    amount: Decimal
):
    async with db.transaction() as tx:
        # Debit source account
        balance = await tx.fetch_val(
            SQL("SELECT balance FROM accounts WHERE id = :id FOR UPDATE"),
            {"id": from_account}
        )
        
        if balance < amount:
            raise ValueError("Insufficient funds")
            
        await tx.execute(
            SQL("UPDATE accounts SET balance = balance - :amount WHERE id = :id"),
            {"id": from_account, "amount": amount}
        )
        
        # Credit destination account
        await tx.execute(
            SQL("UPDATE accounts SET balance = balance + :amount WHERE id = :id"),
            {"id": to_account, "amount": amount}
        )
        
        # Transaction commits on success, rolls back on exception
```

### 4. Query Organization

Load queries from files for better organization:

```python
@app.sql("reports", path="sql/reports")
class ReportQueries:
    # Automatically loads from sql/reports/daily_revenue.sql
    daily_revenue: SQL
    
    # Loads from sql/reports/user_activity.sql
    user_activity: SQL
    
    # Mix file-based and inline queries
    summary = SQL("SELECT COUNT(*) as total FROM orders WHERE date = :date")
```

### 5. Streaming Large Results

Handle large datasets efficiently:

```python
@inject
async def export_users(db: Database):
    async with db.stream(
        SQL("SELECT * FROM users ORDER BY id"),
        fetch_size=1000
    ) as cursor:
        async for user in cursor:
            # Process one user at a time
            yield f"{user['id']},{user['name']},{user['email']}\n"
```

### 6. Connection Management

Get direct connection access when needed:

```python
@inject
async def use_advisory_lock(db: Database):
    async with db.acquire() as conn:
        # PostgreSQL advisory lock
        await conn.execute(SQL("SELECT pg_advisory_lock(12345)"))
        try:
            # Do work with lock held
            await conn.execute(SQL("UPDATE critical_table SET ..."))
        finally:
            await conn.execute(SQL("SELECT pg_advisory_unlock(12345)"))
```

### 7. Multiple Databases

Work with multiple database connections:

```python
# Configure multiple databases
app.configure_database("postgresql://localhost/main", name="primary")
app.configure_database("postgresql://localhost/analytics", name="analytics")
app.configure_database("sqlite:///cache.db", name="cache")

@singleton
class DataService:
    def __init__(
        self,
        primary_db: Database,  # Default database
        analytics_db: Database = Inject(name="analytics"),
        cache_db: Database = Inject(name="cache")
    ):
        self.primary = primary_db
        self.analytics = analytics_db
        self.cache = cache_db
```

### 8. Migrations

Simple migration support:

```sql
-- migrations/001_initial.sql
-- migrate:up
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);

-- migrate:down
DROP TABLE IF EXISTS users;
```

```python
@app.on_startup
async def run_migrations(db: Database):
    await db.migrate("migrations/")
```

### 9. Testing

Built-in testing utilities:

```python
import pytest
from whiskey_sql.testing import TestDatabase

@pytest.fixture
async def test_db():
    async with TestDatabase.create() as db:
        yield db

async def test_user_service(test_db):
    # Test database is isolated and migrations are auto-run
    container = Container()
    container[Database] = test_db
    
    service = await container.resolve(UserService)
    user = await service.create_user("Test", "test@example.com")
    assert user.name == "Test"
```

### 10. Query Composition

Build complex queries from reusable fragments:

```python
class QueryFragments:
    """Reusable SQL fragments."""
    
    PAGINATION = SQL("LIMIT :limit OFFSET :offset")
    
    AUDIT_FIELDS = SQL("created_at, updated_at, created_by, updated_by")
    
    @staticmethod
    def where_active(table: str = "") -> SQL:
        prefix = f"{table}." if table else ""
        return SQL(f"{prefix}deleted_at IS NULL AND {prefix}status = 'active'")

# Compose queries
users_query = SQL(f"""
    SELECT id, name, email, {QueryFragments.AUDIT_FIELDS}
    FROM users
    WHERE {QueryFragments.where_active()}
    ORDER BY created_at DESC
    {QueryFragments.PAGINATION}
""")
```

## Configuration

### Environment Variables

```bash
DATABASE_URL=postgresql://user:pass@localhost/dbname
DATABASE_POOL_SIZE=20
DATABASE_POOL_TIMEOUT=30
DATABASE_ECHO=false
DATABASE_SSL=true
```

### Programmatic Configuration

```python
app.configure_database(
    url=os.getenv("DATABASE_URL"),
    pool_size=20,
    pool_timeout=30,
    echo_queries=True,  # Log all queries
    ssl_context=ssl_context,
    server_settings={
        "application_name": "myapp",
        "jit": "off"
    }
)
```

## Database Support

### PostgreSQL (asyncpg)
- Full feature support including LISTEN/NOTIFY
- Array types, JSON/JSONB, custom types
- Advisory locks, prepared statements
- Native :param syntax converted to $1, $2

### MySQL (aiomysql)
- Core features supported
- JSON support, prepared statements
- Native :param syntax

### SQLite (aiosqlite)
- Perfect for development and testing
- In-memory database support
- File-based persistence
- Native :param syntax support
- Automatic foreign key enforcement
- JSON1 extension support (SQLite 3.38+)

## Best Practices

1. **Use Type Hints**: Define dataclasses for your results
2. **Parameterize Queries**: Always use `:param` syntax, never string formatting
3. **Organize Queries**: Group related queries in classes
4. **Handle Transactions**: Use explicit transactions for multi-statement operations
5. **Test with Real SQL**: Use test databases, not mocks

## Examples

See the `examples/` directory for complete examples:
- `basic_crud.py` - Simple CRUD operations
- `transactions.py` - Transaction patterns
- `migrations.py` - Migration setup
- `multiple_databases.py` - Multi-database setup
- `streaming.py` - Large dataset handling

## Contributing

We welcome contributions! See the main [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](../LICENSE) for details.