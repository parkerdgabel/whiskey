"""DuckDB backend with async support via asyncio.to_thread."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import is_dataclass
from pathlib import Path
from typing import Any, TypeVar

try:
    import duckdb
except ImportError as e:
    raise ImportError(
        "duckdb is required for DuckDB support. Install with: pip install whiskey-sql[duckdb]"
    ) from e

from whiskey_sql.core import SQL, Database, Transaction
from whiskey_sql.exceptions import DatabaseConnectionError, QueryError

T = TypeVar("T")


async def create_pool(**config) -> DuckDBDatabase:
    """Create DuckDB database with connection management.

    Note: DuckDB doesn't have true connection pooling, but we provide
    a compatible interface.

    Args:
        **config: Database configuration

    Returns:
        DuckDB database instance
    """
    url = config["url"]
    read_only = config.get("read_only", False)

    # Parse DuckDB URL formats
    db_path = url[9:] if url.startswith("duckdb://") else url

    # Special handling for in-memory databases
    if db_path in (":memory:", ""):
        # For named in-memory databases, use format ":memory:name"
        db_path = f":memory:{config['database_name']}" if "database_name" in config else ":memory:"

    pool = DuckDBPool(db_path, read_only=read_only, config=config)
    await pool.initialize()
    return DuckDBDatabase(pool)


class DuckDBPool:
    """Connection management for DuckDB.

    DuckDB uses a single-writer model, so we manage a primary connection
    for writes and create read-only connections as needed.
    """

    def __init__(
        self, database: str, read_only: bool = False, config: dict[str, Any] | None = None
    ):
        """Initialize DuckDB pool.

        Args:
            database: Path to database file or ":memory:"
            read_only: Whether to open in read-only mode
            config: Additional DuckDB configuration
        """
        self.database = database
        self.read_only = read_only
        self.config = config or {}
        self._primary_conn = None
        self._closed = False

    async def initialize(self) -> None:
        """Initialize the pool."""
        # Create primary connection
        await asyncio.to_thread(self._create_primary_connection)

    def _create_primary_connection(self) -> None:
        """Create the primary connection (sync)."""
        try:
            self._primary_conn = duckdb.connect(
                database=self.database,
                read_only=self.read_only,
                config=self.config.get("duckdb_config", {}),
            )

            # Set any pragmas
            if "pragmas" in self.config:
                for pragma, value in self.config["pragmas"].items():
                    self._primary_conn.execute(f"PRAGMA {pragma} = {value}")

        except Exception as e:
            raise DatabaseConnectionError(f"Failed to create DuckDB connection: {e}") from e

    @asynccontextmanager
    async def acquire(self):
        """Acquire a connection context."""
        if self._closed:
            raise RuntimeError("Pool is closed")

        # For read-only operations, we could create additional connections
        # For now, we'll use the primary connection with thread safety
        try:
            # DuckDB connections are thread-safe for reads
            yield self._primary_conn
        except Exception:
            raise

    async def close(self) -> None:
        """Close the pool."""
        if self._primary_conn and not self._closed:
            await asyncio.to_thread(self._primary_conn.close)
            self._primary_conn = None
            self._closed = True


class DuckDBDatabase(Database):
    """DuckDB-specific database implementation."""

    def __init__(self, pool: DuckDBPool):
        """Initialize DuckDB database.

        Args:
            pool: DuckDB connection pool
        """
        super().__init__(pool, dialect="duckdb")

    def _convert_params(self, query: SQL, params: dict[str, Any] | None) -> tuple[str, list[Any]]:
        """Convert named parameters to positional for DuckDB.

        DuckDB uses $1, $2 syntax for parameters.

        Args:
            query: SQL query with :name parameters
            params: Parameter dictionary

        Returns:
            Query with $1, $2 placeholders and parameter list
        """
        if not params:
            return str(query), []

        # Extract parameter names in order of appearance
        import re

        pattern = r":([a-zA-Z_][a-zA-Z0-9_]*)\b"
        param_names = []

        def replacer(match):
            param_name = match.group(1)
            if param_name not in param_names:
                param_names.append(param_name)
            # DuckDB uses $1, $2, etc.
            return f"${param_names.index(param_name) + 1}"

        query_str = re.sub(pattern, replacer, str(query))

        # Build parameter list
        param_list = [params.get(name) for name in param_names]

        return query_str, param_list

    def _map_result(
        self, row: tuple | None, columns: list[str], result_type: type[T] | None
    ) -> T | dict | None:
        """Map database row to result type.

        Args:
            row: Database row tuple
            columns: Column names
            result_type: Target type for mapping

        Returns:
            Mapped result or None
        """
        if row is None:
            return None

        # Convert row to dict
        row_dict = dict(zip(columns, row))

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
        async with self.pool.acquire() as conn:
            try:
                query_str, query_params = self._convert_params(query, params)

                # Execute in thread pool
                result = await asyncio.to_thread(conn.execute, query_str, query_params)

                # Get column names
                columns = [desc[0] for desc in result.description]

                # Fetch one row
                row = result.fetchone()

                return self._map_result(row, columns, result_type)

            except Exception as e:
                raise QueryError(f"Query failed: {e}", str(query), params) from e

    async def fetch_all(
        self, query: SQL, params: dict[str, Any] | None = None, result_type: type[T] | None = None
    ) -> list[T] | list[dict[str, Any]]:
        """Fetch all rows."""
        async with self.pool.acquire() as conn:
            try:
                query_str, query_params = self._convert_params(query, params)

                # Execute in thread pool
                result = await asyncio.to_thread(conn.execute, query_str, query_params)

                # Get column names
                columns = [desc[0] for desc in result.description]

                # Fetch all rows
                rows = result.fetchall()

                return [self._map_result(row, columns, result_type) for row in rows]

            except Exception as e:
                raise QueryError(f"Query failed: {e}", str(query), params) from e

    async def fetch_val(
        self, query: SQL, params: dict[str, Any] | None = None, column: int = 0
    ) -> Any:
        """Fetch a single value."""
        async with self.pool.acquire() as conn:
            try:
                query_str, query_params = self._convert_params(query, params)

                # Execute in thread pool
                result = await asyncio.to_thread(conn.execute, query_str, query_params)

                # Fetch one row
                row = result.fetchone()

                if row is None:
                    return None

                return row[column]

            except Exception as e:
                raise QueryError(f"Query failed: {e}", str(query), params) from e

    async def fetch_row(
        self, query: SQL, params: dict[str, Any] | None = None
    ) -> tuple[Any, ...] | None:
        """Fetch a single row as tuple."""
        async with self.pool.acquire() as conn:
            try:
                query_str, query_params = self._convert_params(query, params)

                # Execute in thread pool
                result = await asyncio.to_thread(conn.execute, query_str, query_params)

                # Fetch one row
                row = result.fetchone()

                return row

            except Exception as e:
                raise QueryError(f"Query failed: {e}", str(query), params) from e

    async def execute(self, query: SQL, params: dict[str, Any] | None = None) -> str:
        """Execute a query without results."""
        async with self.pool.acquire() as conn:
            try:
                query_str, query_params = self._convert_params(query, params)

                # Execute in thread pool
                result = await asyncio.to_thread(conn.execute, query_str, query_params)

                # Get row count
                rowcount = (
                    result.fetchone()[0] if query_str.strip().upper().startswith("SELECT") else -1
                )

                # Try to get affected rows for DML
                if rowcount == -1:
                    try:
                        # DuckDB doesn't provide rowcount directly, but we can try
                        count_result = await asyncio.to_thread(
                            conn.execute, "SELECT COUNT(*) FROM last_query_profiling()"
                        )
                        rowcount = count_result.fetchone()[0]
                    except Exception:
                        rowcount = 0

                # Return status similar to PostgreSQL
                if query_str.strip().upper().startswith("INSERT"):
                    return f"INSERT {rowcount}"
                elif query_str.strip().upper().startswith("UPDATE"):
                    return f"UPDATE {rowcount}"
                elif query_str.strip().upper().startswith("DELETE"):
                    return f"DELETE {rowcount}"
                else:
                    return "OK"

            except Exception as e:
                raise QueryError(f"Query failed: {e}", str(query), params) from e

    async def execute_many(self, query: SQL, params_list: list[dict[str, Any]]) -> None:
        """Execute query multiple times."""
        if not params_list:
            return

        async with self.pool.acquire() as conn:
            try:
                query_str, _ = self._convert_params(query, {})

                # DuckDB doesn't have executemany, so we prepare and execute multiple times
                async def execute_batch():
                    prepared = conn.prepare(query_str)
                    for params in params_list:
                        _, param_values = self._convert_params(query, params)
                        prepared.execute(param_values)

                await asyncio.to_thread(execute_batch)

            except Exception as e:
                raise QueryError(f"Batch query failed: {e}", str(query), None) from e

    def transaction(self) -> DuckDBTransaction:
        """Create a new transaction context."""
        return DuckDBTransaction(self)

    async def stream(
        self, query: SQL, params: dict[str, Any] | None = None, fetch_size: int = 1000
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream query results."""
        async with self.pool.acquire() as conn:
            try:
                query_str, query_params = self._convert_params(query, params)

                # Execute query
                result = await asyncio.to_thread(conn.execute, query_str, query_params)

                # Get column names
                columns = [desc[0] for desc in result.description]

                while True:
                    # Fetch batch
                    rows = await asyncio.to_thread(result.fetchmany, fetch_size)

                    if not rows:
                        break

                    for row in rows:
                        yield dict(zip(columns, row))

            except Exception as e:
                raise QueryError(f"Stream query failed: {e}", str(query), params) from e

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
                version VARCHAR PRIMARY KEY,
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

            # Execute migration in transaction
            async with self.transaction() as tx:
                try:
                    # DuckDB can handle multiple statements
                    await tx.execute(SQL(up_sql))

                    # Record migration
                    await tx.execute(
                        SQL("INSERT INTO schema_migrations (version) VALUES (:version)"),
                        {"version": version},
                    )

                    await tx.commit()
                    print(f"✅ Applied migration: {version}")

                except Exception as e:
                    print(f"❌ Failed to apply migration {version}: {e}")
                    await tx.rollback()
                    raise

    # DuckDB-specific features
    async def export_parquet(
        self, query: SQL, path: str, params: dict[str, Any] | None = None
    ) -> None:
        """Export query results to Parquet file.

        Args:
            query: SQL query to export
            path: Output file path
            params: Query parameters
        """
        async with self.pool.acquire() as conn:
            try:
                query_str, query_params = self._convert_params(query, params)

                # Create export query
                export_query = f"COPY ({query_str}) TO '{path}' (FORMAT PARQUET)"

                await asyncio.to_thread(conn.execute, export_query, query_params)

            except Exception as e:
                raise QueryError(f"Parquet export failed: {e}", str(query), params) from e

    async def read_parquet(self, path: str, table_name: str | None = None) -> None:
        """Read Parquet file into DuckDB.

        Args:
            path: Path to Parquet file
            table_name: Optional table name to create
        """
        async with self.pool.acquire() as conn:
            try:
                if table_name:
                    query = f"CREATE TABLE {table_name} AS SELECT * FROM read_parquet('{path}')"
                else:
                    query = f"SELECT * FROM read_parquet('{path}')"

                await asyncio.to_thread(conn.execute, query)

            except Exception as e:
                raise QueryError(f"Parquet read failed: {e}", query, None) from e

    async def export_csv(self, query: SQL, path: str, params: dict[str, Any] | None = None) -> None:
        """Export query results to CSV file.

        Args:
            query: SQL query to export
            path: Output file path
            params: Query parameters
        """
        async with self.pool.acquire() as conn:
            try:
                query_str, query_params = self._convert_params(query, params)

                # Create export query
                export_query = f"COPY ({query_str}) TO '{path}' (FORMAT CSV, HEADER)"

                await asyncio.to_thread(conn.execute, export_query, query_params)

            except Exception as e:
                raise QueryError(f"CSV export failed: {e}", str(query), params) from e


class DuckDBTransaction(Transaction):
    """DuckDB transaction context manager."""

    def __init__(self, db: DuckDBDatabase):
        """Initialize transaction.

        Args:
            db: DuckDB database instance
        """
        super().__init__(db)
        self._conn = None
        self._tx_conn = None

    async def __aenter__(self) -> DuckDBTransaction:
        """Begin transaction."""
        self._conn = await self.db.pool.acquire().__aenter__()
        # Begin transaction
        await asyncio.to_thread(self._conn.execute, "BEGIN TRANSACTION")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Commit or rollback transaction."""
        if self._conn:
            try:
                if exc_type:
                    await asyncio.to_thread(self._conn.execute, "ROLLBACK")
                else:
                    await asyncio.to_thread(self._conn.execute, "COMMIT")
            finally:
                await self.db.pool.acquire().__aexit__(None, None, None)
                self._conn = None

    async def commit(self) -> None:
        """Commit the transaction."""
        if self._conn:
            await asyncio.to_thread(self._conn.execute, "COMMIT")

    async def rollback(self) -> None:
        """Rollback the transaction."""
        if self._conn:
            await asyncio.to_thread(self._conn.execute, "ROLLBACK")

    # Proxy methods using transaction connection
    async def fetch_one(self, query: SQL, params: dict | None = None, result_type=None):
        """Fetch one row within transaction."""
        if not self._conn:
            raise RuntimeError("Transaction not active")

        query_str, query_params = self.db._convert_params(query, params)

        result = await asyncio.to_thread(self._conn.execute, query_str, query_params)

        columns = [desc[0] for desc in result.description]
        row = result.fetchone()

        return self.db._map_result(row, columns, result_type)

    async def execute(self, query: SQL, params: dict | None = None) -> str:
        """Execute query within transaction."""
        if not self._conn:
            raise RuntimeError("Transaction not active")

        query_str, query_params = self.db._convert_params(query, params)

        await asyncio.to_thread(self._conn.execute, query_str, query_params)

        return "OK"
