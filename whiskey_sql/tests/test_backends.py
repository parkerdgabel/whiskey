"""Tests for SQL backends."""

import os
from dataclasses import dataclass

import pytest

from whiskey import Whiskey
from whiskey_sql import SQL, Database, sql_extension


@dataclass
class TestUser:
    id: int
    name: str
    email: str


@pytest.fixture
async def sqlite_db():
    """Create SQLite in-memory database."""
    app = Whiskey()
    app.use(sql_extension)
    app.configure_database(url="sqlite://:memory:")

    db = await app.container.resolve(Database)

    # Create test table
    await db.execute(
        SQL("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL
        )
    """)
    )

    yield db


@pytest.mark.asyncio
async def test_sqlite_basic_operations(sqlite_db):
    """Test basic SQLite operations."""
    db = sqlite_db

    # Insert
    await db.execute(
        SQL("INSERT INTO users (name, email) VALUES (:name, :email)"),
        {"name": "Alice", "email": "alice@example.com"},
    )

    # Fetch one
    user = await db.fetch_one(
        SQL("SELECT * FROM users WHERE email = :email"), {"email": "alice@example.com"}, TestUser
    )
    assert user.name == "Alice"
    assert user.email == "alice@example.com"

    # Fetch all
    users = await db.fetch_all(SQL("SELECT * FROM users"))
    assert len(users) == 1

    # Fetch value
    count = await db.fetch_val(SQL("SELECT COUNT(*) FROM users"))
    assert count == 1

    # Update
    status = await db.execute(
        SQL("UPDATE users SET name = :name WHERE id = :id"), {"name": "Alice Smith", "id": user.id}
    )
    assert "UPDATE 1" in status

    # Delete
    status = await db.execute(SQL("DELETE FROM users WHERE id = :id"), {"id": user.id})
    assert "DELETE 1" in status


@pytest.mark.asyncio
async def test_sqlite_transactions(sqlite_db):
    """Test SQLite transactions."""
    db = sqlite_db

    # Successful transaction
    async with db.transaction():
        await db.execute(
            SQL("INSERT INTO users (name, email) VALUES (:name, :email)"),
            {"name": "Bob", "email": "bob@example.com"},
        )

    count = await db.fetch_val(SQL("SELECT COUNT(*) FROM users"))
    assert count == 1

    # Failed transaction
    try:
        async with db.transaction():
            await db.execute(
                SQL("INSERT INTO users (name, email) VALUES (:name, :email)"),
                {"name": "Charlie", "email": "charlie@example.com"},
            )
            raise ValueError("Test rollback")
    except ValueError:
        pass

    count = await db.fetch_val(SQL("SELECT COUNT(*) FROM users"))
    assert count == 1  # Should still be 1, not 2


@pytest.mark.asyncio
async def test_sqlite_execute_many(sqlite_db):
    """Test batch operations."""
    db = sqlite_db

    users = [
        {"name": "User1", "email": "user1@example.com"},
        {"name": "User2", "email": "user2@example.com"},
        {"name": "User3", "email": "user3@example.com"},
    ]

    await db.execute_many(SQL("INSERT INTO users (name, email) VALUES (:name, :email)"), users)

    count = await db.fetch_val(SQL("SELECT COUNT(*) FROM users"))
    assert count == 3


@pytest.mark.asyncio
async def test_sqlite_streaming(sqlite_db):
    """Test streaming results."""
    db = sqlite_db

    # Insert test data
    for i in range(10):
        await db.execute(
            SQL("INSERT INTO users (name, email) VALUES (:name, :email)"),
            {"name": f"User{i}", "email": f"user{i}@example.com"},
        )

    # Stream results
    streamed_count = 0
    async with db.stream(SQL("SELECT * FROM users"), fetch_size=3) as cursor:
        async for row in cursor:
            streamed_count += 1
            assert "name" in row
            assert "email" in row

    assert streamed_count == 10


@pytest.fixture
async def mysql_db():
    """Create MySQL test database (requires running MySQL server)."""
    import os

    # Skip if MySQL is not available
    mysql_url = os.getenv("MYSQL_TEST_URL", "mysql://root:password@localhost/test_whiskey")

    app = Whiskey()
    app.use(sql_extension)

    try:
        app.configure_database(url=mysql_url)
        db = await app.container.resolve(Database)

        # Create test table
        await db.execute(
            SQL("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL
            )
        """)
        )

        # Clean up before test
        await db.execute(SQL("TRUNCATE TABLE users"))

        yield db

        # Clean up after test
        await db.execute(SQL("DROP TABLE IF EXISTS users"))
    except Exception as e:
        pytest.skip(f"MySQL not available: {e}")


@pytest.mark.asyncio
@pytest.mark.skipif(os.getenv("MYSQL_TEST_URL") is None, reason="MySQL test URL not provided")
async def test_mysql_basic_operations(mysql_db):
    """Test basic MySQL operations."""
    db = mysql_db

    # Insert
    await db.execute(
        SQL("INSERT INTO users (name, email) VALUES (:name, :email)"),
        {"name": "Alice", "email": "alice@example.com"},
    )

    # Fetch one
    user = await db.fetch_one(
        SQL("SELECT * FROM users WHERE email = :email"), {"email": "alice@example.com"}, TestUser
    )
    assert user.name == "Alice"
    assert user.email == "alice@example.com"

    # Fetch all
    users = await db.fetch_all(SQL("SELECT * FROM users"))
    assert len(users) == 1

    # Fetch value
    count = await db.fetch_val(SQL("SELECT COUNT(*) FROM users"))
    assert count == 1

    # Update
    status = await db.execute(
        SQL("UPDATE users SET name = :name WHERE id = :id"), {"name": "Alice Smith", "id": user.id}
    )
    assert "UPDATE 1" in status

    # Delete
    status = await db.execute(SQL("DELETE FROM users WHERE id = :id"), {"id": user.id})
    assert "DELETE 1" in status


@pytest.mark.asyncio
@pytest.mark.skipif(os.getenv("MYSQL_TEST_URL") is None, reason="MySQL test URL not provided")
async def test_mysql_transactions(mysql_db):
    """Test MySQL transactions."""
    db = mysql_db

    # Successful transaction
    async with db.transaction():
        await db.execute(
            SQL("INSERT INTO users (name, email) VALUES (:name, :email)"),
            {"name": "Bob", "email": "bob@example.com"},
        )

    count = await db.fetch_val(SQL("SELECT COUNT(*) FROM users"))
    assert count == 1

    # Failed transaction
    try:
        async with db.transaction():
            await db.execute(
                SQL("INSERT INTO users (name, email) VALUES (:name, :email)"),
                {"name": "Charlie", "email": "charlie@example.com"},
            )
            raise ValueError("Test rollback")
    except ValueError:
        pass

    count = await db.fetch_val(SQL("SELECT COUNT(*) FROM users"))
    assert count == 1  # Should still be 1, not 2
