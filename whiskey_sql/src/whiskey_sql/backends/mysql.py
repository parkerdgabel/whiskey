"""MySQL backend using aiomysql."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import asdict, is_dataclass
from typing import Any, AsyncIterator, Type, TypeVar

try:
    import aiomysql
except ImportError:
    raise ImportError(
        "aiomysql is required for MySQL support. "
        "Install with: pip install whiskey-sql[mysql]"
    )

from whiskey_sql.core import Database, SQL, Transaction, ConnectionContext
from whiskey_sql.exceptions import ConnectionError, QueryError

T = TypeVar("T")


async def create_pool(**config) -> MySQLDatabase:
    """Create MySQL database with connection pool.
    
    Args:
        **config: Database configuration
        
    Returns:
        MySQL database instance
    """
    url = config["url"]
    pool_size = config.get("pool_size", 20)
    pool_timeout = config.get("pool_timeout", 30.0)
    
    # Parse MySQL URL
    from urllib.parse import urlparse
    parsed = urlparse(url)
    
    if parsed.hostname is None:
        raise ConnectionError(f"Invalid MySQL URL: {url}")
    
    try:
        pool = await aiomysql.create_pool(
            host=parsed.hostname,
            port=parsed.port or 3306,
            user=parsed.username or "root",
            password=parsed.password or "",
            db=parsed.path.lstrip("/") if parsed.path else None,
            minsize=1,
            maxsize=pool_size,
            pool_recycle=3600,  # Recycle connections after 1 hour
            autocommit=False,
            cursorclass=aiomysql.DictCursor,
        )
        return MySQLDatabase(pool)
    except Exception as e:
        raise ConnectionError(f"Failed to create MySQL pool: {e}")


class MySQLDatabase(Database):
    """MySQL-specific database implementation."""
    
    def __init__(self, pool: aiomysql.Pool):
        """Initialize MySQL database.
        
        Args:
            pool: aiomysql connection pool
        """
        super().__init__(pool, dialect="mysql")
    
    def _convert_params(self, query: SQL, params: dict[str, Any] | None) -> tuple[str, dict[str, Any]]:
        """Convert parameters for MySQL.
        
        MySQL uses %(name)s format for named parameters.
        
        Args:
            query: SQL query with :name parameters
            params: Parameter dictionary
            
        Returns:
            Query with %(name)s placeholders and parameters
        """
        if not params:
            return str(query), {}
        
        # Convert :name to %(name)s for aiomysql
        import re
        pattern = r':([a-zA-Z_][a-zA-Z0-9_]*)\b'
        
        def replacer(match):
            param_name = match.group(1)
            return f"%({param_name})s"
        
        converted_query = re.sub(pattern, replacer, str(query))
        
        return converted_query, params
    
    def _map_result(self, row: dict | None, result_type: Type[T] | None) -> T | dict | None:
        """Map database row to result type.
        
        Args:
            row: Database row as dict
            result_type: Target type for mapping
            
        Returns:
            Mapped result or None
        """
        if row is None:
            return None
        
        if result_type is None:
            return row
        
        # Map to dataclass
        if is_dataclass(result_type):
            # Filter only fields that exist in the dataclass
            field_names = {f.name for f in result_type.__dataclass_fields__.values()}
            filtered_data = {k: v for k, v in row.items() if k in field_names}
            return result_type(**filtered_data)
        
        # Try to instantiate the type
        try:
            return result_type(**row)
        except Exception:
            # Fallback to dict if instantiation fails
            return row
    
    async def fetch_one(
        self,
        query: SQL,
        params: dict[str, Any] | None = None,
        result_type: Type[T] | None = None
    ) -> T | dict[str, Any] | None:
        """Fetch a single row."""
        converted_query, converted_params = self._convert_params(query, params)
        
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(converted_query, converted_params)
                    row = await cursor.fetchone()
                    return self._map_result(row, result_type)
        except Exception as e:
            raise QueryError(f"Query failed: {e}", str(query), params)
    
    async def fetch_all(
        self,
        query: SQL,
        params: dict[str, Any] | None = None,
        result_type: Type[T] | None = None
    ) -> list[T] | list[dict[str, Any]]:
        """Fetch all rows."""
        converted_query, converted_params = self._convert_params(query, params)
        
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(converted_query, converted_params)
                    rows = await cursor.fetchall()
                    return [self._map_result(row, result_type) for row in rows]
        except Exception as e:
            raise QueryError(f"Query failed: {e}", str(query), params)
    
    async def fetch_val(
        self,
        query: SQL,
        params: dict[str, Any] | None = None,
        column: int = 0
    ) -> Any:
        """Fetch a single value."""
        converted_query, converted_params = self._convert_params(query, params)
        
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(converted_query, converted_params)
                    row = await cursor.fetchone()
                    return row[column] if row else None
        except Exception as e:
            raise QueryError(f"Query failed: {e}", str(query), params)
    
    async def fetch_row(
        self,
        query: SQL,
        params: dict[str, Any] | None = None
    ) -> tuple[Any, ...] | None:
        """Fetch a single row as tuple."""
        converted_query, converted_params = self._convert_params(query, params)
        
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(converted_query, converted_params)
                    return await cursor.fetchone()
        except Exception as e:
            raise QueryError(f"Query failed: {e}", str(query), params)
    
    async def execute(
        self,
        query: SQL,
        params: dict[str, Any] | None = None
    ) -> str:
        """Execute a query without results."""
        converted_query, converted_params = self._convert_params(query, params)
        
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(converted_query, converted_params)
                    await conn.commit()
                    
                    # Return status string similar to PostgreSQL
                    if cursor.rowcount >= 0:
                        if "INSERT" in str(query).upper():
                            return f"INSERT {cursor.rowcount}"
                        elif "UPDATE" in str(query).upper():
                            return f"UPDATE {cursor.rowcount}"
                        elif "DELETE" in str(query).upper():
                            return f"DELETE {cursor.rowcount}"
                    
                    return "OK"
        except Exception as e:
            raise QueryError(f"Query failed: {e}", str(query), params)
    
    async def execute_many(
        self,
        query: SQL,
        params_list: list[dict[str, Any]]
    ) -> None:
        """Execute query multiple times."""
        if not params_list:
            return
        
        converted_query, _ = self._convert_params(query, params_list[0])
        
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.executemany(converted_query, params_list)
                    await conn.commit()
        except Exception as e:
            raise QueryError(f"Batch query failed: {e}", str(query), None)
    
    @asynccontextmanager
    async def stream(
        self,
        query: SQL,
        params: dict[str, Any] | None = None,
        fetch_size: int = 100
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream query results."""
        converted_query, converted_params = self._convert_params(query, params)
        
        async with self.pool.acquire() as conn:
            # Use SSCursor for streaming
            async with conn.cursor(aiomysql.cursors.SSDictCursor) as cursor:
                await cursor.execute(converted_query, converted_params)
                
                async def cursor_iterator():
                    while True:
                        rows = await cursor.fetchmany(fetch_size)
                        if not rows:
                            break
                        for row in rows:
                            yield row
                
                yield cursor_iterator()
    
    async def health_check(self) -> bool:
        """Check database connectivity."""
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("SELECT 1")
                    result = await cursor.fetchone()
                    return result == (1,)
        except Exception:
            return False
    
    def transaction(self) -> MySQLTransaction:
        """Begin a transaction."""
        return MySQLTransaction(self)
    
    def acquire(self) -> MySQLConnection:
        """Acquire a connection from pool."""
        return MySQLConnection(self)


class MySQLTransaction(Transaction):
    """MySQL transaction context manager."""
    
    def __init__(self, db: MySQLDatabase):
        """Initialize transaction.
        
        Args:
            db: MySQL database instance
        """
        self.db = db
        self._connection = None
        self._transaction = None
    
    async def __aenter__(self):
        """Begin transaction."""
        self._connection = await self.db.pool.acquire()
        await self._connection.begin()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Commit or rollback transaction."""
        if self._connection:
            try:
                if exc_type is None:
                    await self._connection.commit()
                else:
                    await self._connection.rollback()
            finally:
                self.db.pool.release(self._connection)
                self._connection = None
    
    async def execute(self, query: SQL, params: dict[str, Any] | None = None) -> str:
        """Execute within transaction."""
        if not self._connection:
            raise RuntimeError("Transaction not active")
        
        converted_query, converted_params = self.db._convert_params(query, params)
        
        async with self._connection.cursor() as cursor:
            await cursor.execute(converted_query, converted_params)
            
            if cursor.rowcount >= 0:
                if "INSERT" in str(query).upper():
                    return f"INSERT {cursor.rowcount}"
                elif "UPDATE" in str(query).upper():
                    return f"UPDATE {cursor.rowcount}"
                elif "DELETE" in str(query).upper():
                    return f"DELETE {cursor.rowcount}"
            
            return "OK"
    
    async def fetch_one(self, query: SQL, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """Fetch one row within transaction."""
        if not self._connection:
            raise RuntimeError("Transaction not active")
        
        converted_query, converted_params = self.db._convert_params(query, params)
        
        async with self._connection.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute(converted_query, converted_params)
            return await cursor.fetchone()
    
    async def fetch_val(self, query: SQL, params: dict[str, Any] | None = None, column: int = 0) -> Any:
        """Fetch single value within transaction."""
        if not self._connection:
            raise RuntimeError("Transaction not active")
        
        converted_query, converted_params = self.db._convert_params(query, params)
        
        async with self._connection.cursor() as cursor:
            await cursor.execute(converted_query, converted_params)
            row = await cursor.fetchone()
            return row[column] if row else None


class MySQLConnection(ConnectionContext):
    """MySQL connection context manager."""
    
    def __init__(self, db: MySQLDatabase):
        """Initialize connection context.
        
        Args:
            db: MySQL database instance
        """
        self.db = db
        self._connection = None
    
    async def __aenter__(self):
        """Acquire connection."""
        self._connection = await self.db.pool.acquire()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Release connection."""
        if self._connection:
            self.db.pool.release(self._connection)
            self._connection = None
    
    async def execute(self, query: SQL, params: dict[str, Any] | None = None) -> str:
        """Execute using connection."""
        if not self._connection:
            raise RuntimeError("Connection not active")
        
        converted_query, converted_params = self.db._convert_params(query, params)
        
        async with self._connection.cursor() as cursor:
            await cursor.execute(converted_query, converted_params)
            await self._connection.commit()
            
            if cursor.rowcount >= 0:
                if "INSERT" in str(query).upper():
                    return f"INSERT {cursor.rowcount}"
                elif "UPDATE" in str(query).upper():
                    return f"UPDATE {cursor.rowcount}"
                elif "DELETE" in str(query).upper():
                    return f"DELETE {cursor.rowcount}"
            
            return "OK"