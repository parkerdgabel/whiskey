"""SQLite backend using aiosqlite."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import is_dataclass
from pathlib import Path
from typing import Any, TypeVar

import aiosqlite

from whiskey_sql.core import SQL, Database, Transaction
from whiskey_sql.exceptions import QueryError

T = TypeVar("T")


async def create_pool(**config) -> SQLiteDatabase:
    """Create SQLite database with connection pool.

    Note: SQLite doesn't have true connection pooling, but we simulate it
    for API consistency.

    Args:
        **config: Database configuration

    Returns:
        SQLite database instance
    """
    url = config["url"]

    # Parse SQLite URL formats
    if url.startswith("sqlite:///"):
        # Absolute path: sqlite:///path/to/db.sqlite
        db_path = url[10:]
    elif url.startswith("sqlite://"):
        # Relative path: sqlite://db.sqlite
        db_path = url[9:]
    else:
        db_path = url

    # Special case for in-memory database
    if db_path == ":memory:":
        # For in-memory, we need a single connection
        pool = SQLitePool(":memory:", shared_cache=True)
    else:
        # For file-based, ensure directory exists
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        pool = SQLitePool(str(path))

    await pool.initialize()
    return SQLiteDatabase(pool)


class SQLitePool:
    """Simulated connection pool for SQLite.

    SQLite doesn't support true connection pooling, but we provide
    a compatible interface.
    """

    def __init__(self, database: str, shared_cache: bool = False):
        """Initialize SQLite pool.

        Args:
            database: Path to database file or ":memory:"
            shared_cache: Enable shared cache for in-memory databases
        """
        self.database = database
        self.shared_cache = shared_cache
        self._connection = None

    async def initialize(self) -> None:
        """Initialize the pool."""
        # For in-memory databases with shared cache, create initial connection
        if self.database == ":memory:" and self.shared_cache:
            self._connection = await aiosqlite.connect("file::memory:?cache=shared", uri=True)
            # Enable foreign keys
            await self._connection.execute("PRAGMA foreign_keys = ON")

    async def acquire(self) -> aiosqlite.Connection:
        """Acquire a connection."""
        if self._connection:
            # Return shared connection for in-memory
            return self._connection

        # Create new connection for file-based
        conn = await aiosqlite.connect(self.database)
        await conn.execute("PRAGMA foreign_keys = ON")
        return conn

    async def release(self, conn: aiosqlite.Connection) -> None:
        """Release a connection."""
        if conn != self._connection:
            await conn.close()

    async def close(self) -> None:
        """Close the pool."""
        if self._connection:
            await self._connection.close()
            self._connection = None


class SQLiteDatabase(Database):
    """SQLite-specific database implementation."""

    def __init__(self, pool: SQLitePool):
        """Initialize SQLite database.

        Args:
            pool: SQLite connection pool
        """
        super().__init__(pool, dialect="sqlite")

    def _convert_params(
        self, query: SQL, params: dict[str, Any] | None
    ) -> tuple[str, dict[str, Any]]:
        """Convert parameters for SQLite.

        SQLite uses :name syntax natively, so we just validate.

        Args:
            query: SQL query with :name parameters
            params: Parameter dictionary

        Returns:
            Query string and parameters
        """
        if not params:
            return str(query), {}

        # SQLite supports :name syntax directly
        return str(query), params

    def _map_result(
        self, row: aiosqlite.Row | None, result_type: type[T] | None
    ) -> T | dict | None:
        """Map database row to result type.

        Args:
            row: Database row
            result_type: Target type for mapping

        Returns:
            Mapped result or None
        """
        if row is None:
            return None

        # Convert Row to dict
        row_dict = dict(zip(row.keys(), row)) if hasattr(row, "keys") else dict(row)

        if result_type is None:
            return row_dict

        # Map to dataclass
        if is_dataclass(result_type):
            # Filter only fields that exist in the dataclass
            field_names = {f.name for f in result_type.__dataclass_fields__.values()}
            filtered_data = {k: v for k, v in row_dict.items() if k in field_names}
            return result_type(**filtered_data)

        # Try to instantiate the type
        try:
            return result_type(**row_dict)
        except Exception:
            # Fallback to dict if instantiation fails
            return row_dict

    async def fetch_one(
        self, query: SQL, params: dict[str, Any] | None = None, result_type: type[T] | None = None
    ) -> T | dict[str, Any] | None:
        """Fetch a single row."""
        conn = await self.pool.acquire()
        try:
            query_str, query_params = self._convert_params(query, params)

            cursor = await conn.execute(query_str, query_params)
            row = await cursor.fetchone()

            if row is None:
                return None

            # Set row factory for dict-like access
            cursor.row_factory = aiosqlite.Row
            await cursor.close()

            # Re-execute with row factory
            cursor = await conn.execute(query_str, query_params)
            row = await cursor.fetchone()
            await cursor.close()

            return self._map_result(row, result_type)

        except Exception as e:
            raise QueryError(f"Query failed: {e}", str(query), params) from e
        finally:
            await self.pool.release(conn)

    async def fetch_all(
        self, query: SQL, params: dict[str, Any] | None = None, result_type: type[T] | None = None
    ) -> list[T] | list[dict[str, Any]]:
        """Fetch all rows."""
        conn = await self.pool.acquire()
        try:
            query_str, query_params = self._convert_params(query, params)

            # Set row factory for dict-like access
            conn.row_factory = aiosqlite.Row

            cursor = await conn.execute(query_str, query_params)
            rows = await cursor.fetchall()
            await cursor.close()

            return [self._map_result(row, result_type) for row in rows]

        except Exception as e:
            raise QueryError(f"Query failed: {e}", str(query), params) from e
        finally:
            await self.pool.release(conn)

    async def fetch_val(
        self, query: SQL, params: dict[str, Any] | None = None, column: int = 0
    ) -> Any:
        """Fetch a single value."""
        conn = await self.pool.acquire()
        try:
            query_str, query_params = self._convert_params(query, params)

            cursor = await conn.execute(query_str, query_params)
            row = await cursor.fetchone()
            await cursor.close()

            if row is None:
                return None

            return row[column]

        except Exception as e:
            raise QueryError(f"Query failed: {e}", str(query), params) from e
        finally:
            await self.pool.release(conn)

    async def fetch_row(
        self, query: SQL, params: dict[str, Any] | None = None
    ) -> tuple[Any, ...] | None:
        """Fetch a single row as tuple."""
        conn = await self.pool.acquire()
        try:
            query_str, query_params = self._convert_params(query, params)

            cursor = await conn.execute(query_str, query_params)
            row = await cursor.fetchone()
            await cursor.close()

            return tuple(row) if row else None

        except Exception as e:
            raise QueryError(f"Query failed: {e}", str(query), params) from e
        finally:
            await self.pool.release(conn)

    async def execute(self, query: SQL, params: dict[str, Any] | None = None) -> str:
        """Execute a query without results."""
        conn = await self.pool.acquire()
        try:
            query_str, query_params = self._convert_params(query, params)

            cursor = await conn.execute(query_str, query_params)
            await conn.commit()

            # Get row count for status
            rowcount = cursor.rowcount
            await cursor.close()

            # Return status similar to PostgreSQL
            if query_str.strip().upper().startswith("INSERT"):
                return f"INSERT {rowcount}"
            elif query_str.strip().upper().startswith("UPDATE"):
                return f"UPDATE {rowcount}"
            elif query_str.strip().upper().startswith("DELETE"):
                return f"DELETE {rowcount}"
            else:
                return f"OK {rowcount}"

        except Exception as e:
            raise QueryError(f"Query failed: {e}", str(query), params) from e
        finally:
            await self.pool.release(conn)

    async def execute_many(self, query: SQL, params_list: list[dict[str, Any]]) -> None:
        """Execute query multiple times."""
        if not params_list:
            return

        conn = await self.pool.acquire()
        try:
            query_str, _ = self._convert_params(query, {})

            # Use executemany for efficiency
            await conn.executemany(query_str, params_list)
            await conn.commit()

        except Exception as e:
            raise QueryError(f"Batch query failed: {e}", str(query), None) from e
        finally:
            await self.pool.release(conn)

    def transaction(self) -> SQLiteTransaction:
        """Create a new transaction context."""
        return SQLiteTransaction(self)

    async def stream(
        self, query: SQL, params: dict[str, Any] | None = None, fetch_size: int = 100
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream query results."""
        conn = await self.pool.acquire()
        try:
            query_str, query_params = self._convert_params(query, params)

            # Set row factory
            conn.row_factory = aiosqlite.Row

            cursor = await conn.execute(query_str, query_params)

            while True:
                rows = await cursor.fetchmany(fetch_size)
                if not rows:
                    break

                for row in rows:
                    yield dict(zip(row.keys(), row))

            await cursor.close()

        except Exception as e:
            raise QueryError(f"Stream query failed: {e}", str(query), params) from e
        finally:
            await self.pool.release(conn)

    async def migrate(self, path: str | Path) -> None:
        """Run database migrations.

        Args:
            path: Path to migrations directory
        """
        import re
        from pathlib import Path

        migrations_dir = Path(path)
        if not migrations_dir.exists():
            raise ValueError(f"Migrations directory not found: {path}")

        # Create migrations table
        await self.execute(
            SQL("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version VARCHAR(255) PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        )

        # Get applied migrations
        applied = await self.fetch_all(SQL("SELECT version FROM schema_migrations"))
        applied_versions = {row["version"] for row in applied}

        # Find migration files
        migration_files = sorted(migrations_dir.glob("*.sql"))

        for migration_file in migration_files:
            version = migration_file.stem

            if version in applied_versions:
                continue

            print(f"📄 Applying migration: {version}")

            # Read migration
            content = migration_file.read_text()

            # Extract up migration
            up_match = re.search(
                r"-- migrate:up\s*\n(.*?)(?=-- migrate:down|$)", content, re.DOTALL | re.IGNORECASE
            )

            if not up_match:
                raise ValueError(f"No 'migrate:up' section found in {migration_file}")

            up_sql = up_match.group(1).strip()

            # Execute migration
            conn = await self.pool.acquire()
            try:
                # Execute each statement separately (SQLite limitation)
                statements = up_sql.split(";")
                for stmt in statements:
                    if stmt.strip():
                        await conn.execute(stmt)

                # Record migration
                await conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))
                await conn.commit()

                print(f"✅ Applied migration: {version}")

            except Exception:
                await conn.rollback()
                raise
            finally:
                await self.pool.release(conn)


class SQLiteTransaction(Transaction):
    """SQLite transaction context manager."""

    def __init__(self, db: SQLiteDatabase):
        """Initialize transaction.

        Args:
            db: SQLite database instance
        """
        super().__init__(db)
        self._conn = None

    async def __aenter__(self) -> SQLiteTransaction:
        """Begin transaction."""
        self._conn = await self.db.pool.acquire()
        # SQLite auto-begins transactions
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Commit or rollback transaction."""
        if self._conn:
            try:
                if exc_type:
                    await self._conn.rollback()
                else:
                    await self._conn.commit()
            finally:
                await self.db.pool.release(self._conn)
                self._conn = None

    async def commit(self) -> None:
        """Commit the transaction."""
        if self._conn:
            await self._conn.commit()

    async def rollback(self) -> None:
        """Rollback the transaction."""
        if self._conn:
            await self._conn.rollback()

    # Proxy methods using transaction connection
    async def fetch_one(self, query: SQL, params: dict | None = None, result_type=None):
        """Fetch one row within transaction."""
        if not self._conn:
            raise RuntimeError("Transaction not active")

        query_str, query_params = self.db._convert_params(query, params)

        self._conn.row_factory = aiosqlite.Row
        cursor = await self._conn.execute(query_str, query_params)
        row = await cursor.fetchone()
        await cursor.close()

        return self.db._map_result(row, result_type)

    async def execute(self, query: SQL, params: dict | None = None) -> str:
        """Execute query within transaction."""
        if not self._conn:
            raise RuntimeError("Transaction not active")

        query_str, query_params = self.db._convert_params(query, params)

        cursor = await self._conn.execute(query_str, query_params)
        rowcount = cursor.rowcount
        await cursor.close()

        # Don't commit - let transaction manager handle it
        return f"OK {rowcount}"


# Create factory function
async def create_database(pool: SQLitePool) -> SQLiteDatabase:
    """Create SQLite database instance.

    Args:
        pool: SQLite connection pool

    Returns:
        SQLite database instance
    """
    return SQLiteDatabase(pool)
