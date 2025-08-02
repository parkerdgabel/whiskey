"""Tests for DuckDB backend."""

import tempfile
from pathlib import Path

import pytest

from whiskey_sql import SQL
from whiskey_sql.backends.duckdb import create_pool


@pytest.fixture
async def db():
    """Create a test database."""
    # Use in-memory database for tests
    db = await create_pool(url=":memory:")

    # Create test table
    await db.execute(
        SQL("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name VARCHAR NOT NULL,
            email VARCHAR UNIQUE NOT NULL,
            age INTEGER,
            active BOOLEAN DEFAULT true,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    )

    yield db

    await db.pool.close()


@pytest.fixture
async def populated_db(db):
    """Database with test data."""
    await db.execute_many(
        SQL("INSERT INTO users (id, name, email, age) VALUES (:id, :name, :email, :age)"),
        [
            {"id": 1, "name": "Alice", "email": "alice@example.com", "age": 30},
            {"id": 2, "name": "Bob", "email": "bob@example.com", "age": 25},
            {"id": 3, "name": "Charlie", "email": "charlie@example.com", "age": 35},
        ],
    )
    return db


class TestDuckDBConnection:
    """Test DuckDB connection handling."""

    async def test_connect_memory(self):
        """Test connecting to in-memory database."""
        db = await create_pool(url=":memory:")
        assert db is not None
        assert db.dialect == "duckdb"
        await db.pool.close()

    async def test_connect_file(self):
        """Test connecting to file database."""
        with tempfile.NamedTemporaryFile(suffix=".duckdb") as tmp:
            db = await create_pool(url=tmp.name)
            assert db is not None

            # Create a table
            await db.execute(SQL("CREATE TABLE test (id INTEGER)"))

            # Verify table exists
            result = await db.fetch_val(
                SQL("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'test'")
            )
            assert result == 1

            await db.pool.close()

    async def test_named_memory_database(self):
        """Test named in-memory databases share data."""
        db1 = await create_pool(url=":memory:test", database_name="test")
        db2 = await create_pool(url=":memory:test", database_name="test")

        # Create table in first connection
        await db1.execute(SQL("CREATE TABLE shared (id INTEGER)"))
        await db1.execute(SQL("INSERT INTO shared VALUES (1)"))

        # Verify data is visible in second connection
        result = await db2.fetch_val(SQL("SELECT id FROM shared"))
        assert result == 1

        await db1.pool.close()
        await db2.pool.close()


class TestDuckDBQueries:
    """Test DuckDB query execution."""

    async def test_fetch_one(self, populated_db):
        """Test fetching a single row."""
        result = await populated_db.fetch_one(
            SQL("SELECT * FROM users WHERE email = :email"), {"email": "alice@example.com"}
        )

        assert result is not None
        assert result["name"] == "Alice"
        assert result["age"] == 30

    async def test_fetch_all(self, populated_db):
        """Test fetching all rows."""
        results = await populated_db.fetch_all(SQL("SELECT * FROM users ORDER BY id"))

        assert len(results) == 3
        assert results[0]["name"] == "Alice"
        assert results[1]["name"] == "Bob"
        assert results[2]["name"] == "Charlie"

    async def test_fetch_val(self, populated_db):
        """Test fetching a single value."""
        count = await populated_db.fetch_val(SQL("SELECT COUNT(*) FROM users"))
        assert count == 3

        # Test with parameters
        age = await populated_db.fetch_val(
            SQL("SELECT age FROM users WHERE name = :name"), {"name": "Bob"}
        )
        assert age == 25

    async def test_fetch_row(self, populated_db):
        """Test fetching a row as tuple."""
        row = await populated_db.fetch_row(
            SQL("SELECT id, name FROM users WHERE id = :id"), {"id": 1}
        )

        assert row == (1, "Alice")

    async def test_execute_insert(self, db):
        """Test INSERT execution."""
        status = await db.execute(
            SQL("INSERT INTO users (id, name, email) VALUES (:id, :name, :email)"),
            {"id": 1, "name": "Test", "email": "test@example.com"},
        )

        # DuckDB doesn't provide rowcount easily
        assert "INSERT" in status

        # Verify insert
        count = await db.fetch_val(SQL("SELECT COUNT(*) FROM users"))
        assert count == 1

    async def test_execute_update(self, populated_db):
        """Test UPDATE execution."""
        status = await populated_db.execute(
            SQL("UPDATE users SET age = :age WHERE name = :name"), {"age": 31, "name": "Alice"}
        )

        assert "UPDATE" in status

        # Verify update
        age = await populated_db.fetch_val(SQL("SELECT age FROM users WHERE name = 'Alice'"))
        assert age == 31

    async def test_execute_delete(self, populated_db):
        """Test DELETE execution."""
        status = await populated_db.execute(SQL("DELETE FROM users WHERE age < :age"), {"age": 30})

        assert "DELETE" in status

        # Verify delete
        count = await populated_db.fetch_val(SQL("SELECT COUNT(*) FROM users"))
        assert count == 2


class TestDuckDBTransactions:
    """Test DuckDB transaction handling."""

    async def test_transaction_commit(self, db):
        """Test committing a transaction."""
        async with db.transaction() as tx:
            await tx.execute(
                SQL("INSERT INTO users (id, name, email) VALUES (1, 'Test', 'test@example.com')")
            )
            await tx.commit()

        # Verify data was committed
        count = await db.fetch_val(SQL("SELECT COUNT(*) FROM users"))
        assert count == 1

    async def test_transaction_rollback(self, db):
        """Test rolling back a transaction."""
        async with db.transaction() as tx:
            await tx.execute(
                SQL("INSERT INTO users (id, name, email) VALUES (1, 'Test', 'test@example.com')")
            )
            await tx.rollback()

        # Verify data was not committed
        count = await db.fetch_val(SQL("SELECT COUNT(*) FROM users"))
        assert count == 0

    async def test_transaction_auto_rollback(self, db):
        """Test automatic rollback on exception."""
        with pytest.raises(Exception, match="Test error"):
            async with db.transaction() as tx:
                await tx.execute(
                    SQL(
                        "INSERT INTO users (id, name, email) VALUES (1, 'Test', 'test@example.com')"
                    )
                )
                raise Exception("Test error")

        # Verify data was rolled back
        count = await db.fetch_val(SQL("SELECT COUNT(*) FROM users"))
        assert count == 0


class TestDuckDBStreaming:
    """Test DuckDB streaming functionality."""

    async def test_stream_results(self, db):
        """Test streaming query results."""
        # Insert more data
        for i in range(100):
            await db.execute(
                SQL("INSERT INTO users (id, name, email) VALUES (:id, :name, :email)"),
                {"id": i, "name": f"User{i}", "email": f"user{i}@example.com"},
            )

        # Stream results
        count = 0
        async for row in db.stream(SQL("SELECT * FROM users"), fetch_size=10):
            count += 1
            assert "name" in row
            assert "email" in row

        assert count == 100


class TestDuckDBSpecificFeatures:
    """Test DuckDB-specific features."""

    async def test_export_parquet(self, populated_db):
        """Test exporting to Parquet."""
        with tempfile.NamedTemporaryFile(suffix=".parquet") as tmp:
            await populated_db.export_parquet(SQL("SELECT * FROM users"), tmp.name)

            # Verify file exists
            assert Path(tmp.name).exists()

            # Read back and verify
            result = await populated_db.fetch_val(
                SQL(f"SELECT COUNT(*) FROM read_parquet('{tmp.name}')")
            )
            assert result == 3

    async def test_export_csv(self, populated_db):
        """Test exporting to CSV."""
        with tempfile.NamedTemporaryFile(suffix=".csv") as tmp:
            await populated_db.export_csv(SQL("SELECT * FROM users"), tmp.name)

            # Verify file exists
            assert Path(tmp.name).exists()

            # Read back and verify
            result = await populated_db.fetch_val(
                SQL(f"SELECT COUNT(*) FROM read_csv_auto('{tmp.name}')")
            )
            assert result == 3

    async def test_read_parquet(self, db):
        """Test reading from Parquet file."""
        with tempfile.NamedTemporaryFile(suffix=".parquet") as tmp:
            # First create a parquet file
            await db.execute(SQL("CREATE TABLE temp (id INTEGER, value VARCHAR)"))
            await db.execute(SQL("INSERT INTO temp VALUES (1, 'test')"))
            await db.export_parquet(SQL("SELECT * FROM temp"), tmp.name)

            # Read it into a new table
            await db.read_parquet(tmp.name, "imported")

            # Verify
            result = await db.fetch_one(SQL("SELECT * FROM imported"))
            assert result["id"] == 1
            assert result["value"] == "test"

    async def test_analytical_queries(self, populated_db):
        """Test DuckDB analytical capabilities."""
        # Window functions
        result = await populated_db.fetch_all(
            SQL("""
                SELECT 
                    name,
                    age,
                    AVG(age) OVER () as avg_age,
                    RANK() OVER (ORDER BY age DESC) as age_rank
                FROM users
                ORDER BY age_rank
            """)
        )

        assert len(result) == 3
        assert result[0]["name"] == "Charlie"  # Oldest
        assert result[0]["age_rank"] == 1
        assert result[0]["avg_age"] == 30  # (30 + 25 + 35) / 3

    async def test_with_clause(self, populated_db):
        """Test WITH clause (CTE)."""
        result = await populated_db.fetch_all(
            SQL("""
                WITH age_groups AS (
                    SELECT 
                        CASE 
                            WHEN age < 30 THEN 'Young'
                            ELSE 'Adult'
                        END as age_group,
                        COUNT(*) as count
                    FROM users
                    GROUP BY 1
                )
                SELECT * FROM age_groups ORDER BY age_group
            """)
        )

        assert len(result) == 2
        assert result[0]["age_group"] == "Adult"
        assert result[0]["count"] == 2
        assert result[1]["age_group"] == "Young"
        assert result[1]["count"] == 1


@pytest.mark.asyncio
async def test_duckdb_migration(tmp_path):
    """Test DuckDB migration functionality."""
    # Create migrations directory
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()

    # Create migration file
    migration_file = migrations_dir / "001_create_tables.sql"
    migration_file.write_text("""
-- migrate:up
CREATE TABLE products (
    id INTEGER PRIMARY KEY,
    name VARCHAR NOT NULL,
    price DECIMAL(10, 2)
);

INSERT INTO products VALUES (1, 'Widget', 9.99);

-- migrate:down
DROP TABLE products;
""")

    # Create database and run migrations
    db = await create_pool(url=":memory:")
    await db.migrate(migrations_dir)

    # Verify migration was applied
    result = await db.fetch_val(SQL("SELECT COUNT(*) FROM products"))
    assert result == 1

    # Verify migration was recorded
    migrations = await db.fetch_all(SQL("SELECT version FROM schema_migrations"))
    assert len(migrations) == 1
    assert migrations[0]["version"] == "001_create_tables"

    await db.pool.close()
