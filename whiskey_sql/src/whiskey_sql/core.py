"""Core SQL templating and database functionality."""

from __future__ import annotations

import re
from dataclasses import is_dataclass
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Type, TypeVar, overload

T = TypeVar("T")


class SQL:
    """SQL template that safely handles parameterized queries.
    
    Examples:
        >>> query = SQL("SELECT * FROM users WHERE id = :id")
        >>> query = SQL("INSERT INTO logs (level, message) VALUES (:level, :message)")
        
        >>> # Load from file
        >>> query = SQL.from_file("sql/queries/get_user.sql")
    """
    
    def __init__(self, query: str, *, prepare: bool = False):
        """Initialize SQL template.
        
        Args:
            query: The SQL query string with :param placeholders
            prepare: Whether to prepare this statement (for performance)
        """
        self.query = query.strip()
        self.prepare = prepare
        self._params = self._extract_params()
    
    def _extract_params(self) -> set[str]:
        """Extract parameter names from the query."""
        # Match :param_name but not ::casts or :'literals'
        pattern = r':([a-zA-Z_][a-zA-Z0-9_]*)\b'
        return set(re.findall(pattern, self.query))
    
    @classmethod
    def from_file(cls, path: str | Path) -> SQL:
        """Load SQL from a file.
        
        Args:
            path: Path to the SQL file
            
        Returns:
            SQL template loaded from file
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"SQL file not found: {path}")
        
        return cls(path.read_text())
    
    def __str__(self) -> str:
        """Return the SQL query string."""
        return self.query
    
    def __repr__(self) -> str:
        """Return string representation."""
        preview = self.query[:50] + "..." if len(self.query) > 50 else self.query
        return f"SQL({preview!r})"
    
    def __add__(self, other: SQL | str) -> SQL:
        """Concatenate SQL queries."""
        if isinstance(other, SQL):
            return SQL(f"{self.query}\n{other.query}")
        elif isinstance(other, str):
            return SQL(f"{self.query}\n{other}")
        return NotImplemented


class Database:
    """Database connection manager with query execution methods.
    
    This is the main interface for executing SQL queries. It handles:
    - Connection pooling
    - Query execution
    - Result mapping
    - Transaction management
    """
    
    def __init__(self, pool: Any, dialect: str = "postgresql"):
        """Initialize database wrapper.
        
        Args:
            pool: The underlying database connection pool
            dialect: Database dialect (postgresql, mysql, sqlite)
        """
        self.pool = pool
        self.dialect = dialect
    
    # Fetch methods with multiple overloads for type safety
    
    @overload
    async def fetch_one(
        self, 
        query: SQL, 
        params: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        """Fetch single row as dict."""
        ...
    
    @overload
    async def fetch_one(
        self,
        query: SQL,
        params: dict[str, Any] | None,
        result_type: Type[T]
    ) -> T | None:
        """Fetch single row as typed result."""
        ...
    
    async def fetch_one(
        self,
        query: SQL,
        params: dict[str, Any] | None = None,
        result_type: Type[T] | None = None
    ) -> T | dict[str, Any] | None:
        """Fetch a single row from the database.
        
        Args:
            query: SQL query to execute
            params: Query parameters
            result_type: Optional type to map results to
            
        Returns:
            Single row as dict or mapped type, None if no results
            
        Examples:
            >>> # Get as dict
            >>> user = await db.fetch_one(
            ...     SQL("SELECT * FROM users WHERE id = :id"),
            ...     {"id": 123}
            ... )
            
            >>> # Get as dataclass
            >>> user = await db.fetch_one(
            ...     SQL("SELECT * FROM users WHERE id = :id"),
            ...     {"id": 123},
            ...     User
            ... )
        """
        # Implementation will be in backend-specific subclasses
        raise NotImplementedError
    
    @overload
    async def fetch_all(
        self,
        query: SQL,
        params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Fetch all rows as dicts."""
        ...
    
    @overload
    async def fetch_all(
        self,
        query: SQL,
        params: dict[str, Any] | None,
        result_type: Type[T]
    ) -> list[T]:
        """Fetch all rows as typed results."""
        ...
    
    async def fetch_all(
        self,
        query: SQL,
        params: dict[str, Any] | None = None,
        result_type: Type[T] | None = None
    ) -> list[T] | list[dict[str, Any]]:
        """Fetch all rows from the database.
        
        Args:
            query: SQL query to execute
            params: Query parameters
            result_type: Optional type to map results to
            
        Returns:
            List of rows as dicts or mapped types
        """
        raise NotImplementedError
    
    async def fetch_val(
        self,
        query: SQL,
        params: dict[str, Any] | None = None,
        column: int = 0
    ) -> Any:
        """Fetch a single value from the first row.
        
        Args:
            query: SQL query to execute
            params: Query parameters
            column: Column index to return (default: 0)
            
        Returns:
            Single value from the result
            
        Examples:
            >>> count = await db.fetch_val(
            ...     SQL("SELECT COUNT(*) FROM users")
            ... )
            
            >>> name = await db.fetch_val(
            ...     SQL("SELECT name, email FROM users WHERE id = :id"),
            ...     {"id": 123},
            ...     column=0  # Returns name
            ... )
        """
        raise NotImplementedError
    
    async def fetch_row(
        self,
        query: SQL,
        params: dict[str, Any] | None = None
    ) -> tuple[Any, ...] | None:
        """Fetch a single row as a tuple.
        
        Args:
            query: SQL query to execute
            params: Query parameters
            
        Returns:
            Row as tuple, None if no results
            
        Examples:
            >>> row = await db.fetch_row(
            ...     SQL("SELECT COUNT(*), AVG(age) FROM users")
            ... )
            >>> if row:
            ...     count, avg_age = row
        """
        raise NotImplementedError
    
    async def execute(
        self,
        query: SQL,
        params: dict[str, Any] | None = None
    ) -> str:
        """Execute a query without returning results.
        
        Args:
            query: SQL query to execute
            params: Query parameters
            
        Returns:
            Status string (e.g., "UPDATE 5")
            
        Examples:
            >>> status = await db.execute(
            ...     SQL("UPDATE users SET active = false WHERE last_login < :date"),
            ...     {"date": cutoff_date}
            ... )
        """
        raise NotImplementedError
    
    async def execute_many(
        self,
        query: SQL,
        params_list: list[dict[str, Any]]
    ) -> None:
        """Execute a query multiple times with different parameters.
        
        Args:
            query: SQL query to execute
            params_list: List of parameter dictionaries
            
        Examples:
            >>> await db.execute_many(
            ...     SQL("INSERT INTO logs (level, message) VALUES (:level, :message)"),
            ...     [
            ...         {"level": "INFO", "message": "Started"},
            ...         {"level": "ERROR", "message": "Failed"},
            ...     ]
            ... )
        """
        raise NotImplementedError
    
    def transaction(self) -> Transaction:
        """Create a new transaction context.
        
        Returns:
            Transaction context manager
            
        Examples:
            >>> async with db.transaction():
            ...     await db.execute(SQL("INSERT ..."))
            ...     await db.execute(SQL("UPDATE ..."))
            ...     # Commits on success, rolls back on exception
        """
        return Transaction(self)
    
    async def stream(
        self,
        query: SQL,
        params: dict[str, Any] | None = None,
        fetch_size: int = 100
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream results for large datasets.
        
        Args:
            query: SQL query to execute
            params: Query parameters
            fetch_size: Number of rows to fetch at a time
            
        Yields:
            Individual rows as dicts
            
        Examples:
            >>> async with db.stream(SQL("SELECT * FROM large_table")) as cursor:
            ...     async for row in cursor:
            ...         process_row(row)
        """
        raise NotImplementedError
    
    def acquire(self) -> ConnectionContext:
        """Acquire a dedicated connection from the pool.
        
        Returns:
            Connection context manager
            
        Examples:
            >>> async with db.acquire() as conn:
            ...     # Use conn for session-specific features
            ...     await conn.execute(SQL("SET LOCAL ..."))
        """
        return ConnectionContext(self)
    
    async def migrate(self, path: str | Path) -> None:
        """Run database migrations from a directory.
        
        Args:
            path: Path to migrations directory
            
        The migration files should follow the naming pattern:
        - 001_initial.sql
        - 002_add_users.sql
        - etc.
        
        Each file should contain:
        -- migrate:up
        CREATE TABLE ...
        
        -- migrate:down
        DROP TABLE ...
        """
        # Migration implementation
        raise NotImplementedError
    
    async def health_check(self) -> dict[str, Any]:
        """Check database health and connection pool status.
        
        Returns:
            Health status dictionary
        """
        return {
            "status": "healthy",
            "dialect": self.dialect,
            "pool_size": getattr(self.pool, "_size", "unknown"),
            "pool_free": getattr(self.pool, "_free_size", "unknown")
        }


class Transaction:
    """Database transaction context manager."""
    
    def __init__(self, db: Database):
        """Initialize transaction.
        
        Args:
            db: Database instance
        """
        self.db = db
        self._connection = None
        self._transaction = None
    
    async def __aenter__(self) -> Transaction:
        """Begin transaction."""
        # Implementation depends on database backend
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Commit or rollback transaction."""
        if exc_type:
            await self.rollback()
        else:
            await self.commit()
    
    async def commit(self) -> None:
        """Commit the transaction."""
        raise NotImplementedError
    
    async def rollback(self) -> None:
        """Rollback the transaction."""
        raise NotImplementedError
    
    # Proxy methods to database
    async def fetch_one(self, *args, **kwargs):
        """Fetch one row within transaction."""
        # Uses transaction connection
        raise NotImplementedError
    
    async def execute(self, *args, **kwargs):
        """Execute query within transaction."""
        raise NotImplementedError


class ConnectionContext:
    """Context manager for dedicated database connections."""
    
    def __init__(self, db: Database):
        """Initialize connection context.
        
        Args:
            db: Database instance
        """
        self.db = db
        self._connection = None
    
    async def __aenter__(self) -> Any:
        """Acquire connection from pool."""
        # Implementation depends on database backend
        return self._connection
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Release connection back to pool."""
        # Implementation depends on database backend
        pass


# Convenience function for inline transactions
def transaction(db: Database) -> Transaction:
    """Create a transaction context.
    
    Args:
        db: Database instance
        
    Returns:
        Transaction context manager
        
    Examples:
        >>> async with transaction(db):
        ...     await db.execute(...)
    """
    return db.transaction()