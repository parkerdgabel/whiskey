"""Database source implementation using whiskey_sql."""

from __future__ import annotations

from typing import Any, AsyncIterator

from whiskey_sql import SQL, Database

from .errors import SourceError
from .sources import DataSource


class DatabaseSource(DataSource):
    """SQL database source using whiskey_sql Database.

    This source leverages the whiskey_sql extension for database connectivity,
    providing automatic connection pooling and proper resource management.
    """

    def __init__(
        self,
        database: Database,
        fetch_size: int = 1000,
    ):
        """Initialize database source.

        Args:
            database: Whiskey SQL Database instance (auto-injected)
            fetch_size: Number of rows to fetch at a time for streaming
        """
        self.database = database
        self.fetch_size = fetch_size

    async def extract(
        self,
        query: str | SQL | None = None,
        table: str | None = None,
        columns: list[str] | None = None,
        where: str | None = None,
        order_by: str | None = None,
        limit: int | None = None,
        params: dict[str, Any] | None = None,
        stream: bool = True,
        **kwargs,
    ) -> AsyncIterator[dict[str, Any]]:
        """Extract data from SQL database.

        Args:
            query: Raw SQL query or SQL object (takes precedence)
            table: Table name for simple SELECT
            columns: Columns to select (default: all)
            where: WHERE clause conditions
            order_by: ORDER BY clause
            limit: LIMIT clause
            params: Query parameters for parameterized queries
            stream: Whether to stream results (default: True)
            **kwargs: Additional options

        Yields:
            Records as dictionaries
        """
        # Build query if not provided
        if query is None:
            if table is None:
                raise ValueError("Either 'query' or 'table' must be provided")

            # Build SELECT query
            col_clause = ", ".join(columns) if columns else "*"
            query_str = f"SELECT {col_clause} FROM {table}"

            if where:
                query_str += f" WHERE {where}"
            if order_by:
                query_str += f" ORDER BY {order_by}"
            if limit:
                query_str += f" LIMIT {limit}"

            query = SQL(query_str)
        elif isinstance(query, str):
            query = SQL(query)

        try:
            if stream:
                # Stream results for memory efficiency
                async for row in self.database.stream(
                    query, params=params, fetch_size=self.fetch_size
                ):
                    yield row
            else:
                # Fetch all at once (for smaller datasets)
                rows = await self.database.fetch_all(query, params=params)
                for row in rows:
                    yield row

        except Exception as e:
            raise SourceError(
                self.__class__.__name__,
                f"Database query failed: {e}",
                details={
                    "query": str(query),
                    "params": params,
                    "dialect": self.database.dialect,
                },
            ) from e


class TableSource(DatabaseSource):
    """Specialized source for extracting entire tables with efficient pagination."""

    def __init__(
        self,
        database: Database,
        table_name: str,
        key_column: str = "id",
        batch_size: int = 10000,
    ):
        """Initialize table source.

        Args:
            database: Whiskey SQL Database instance
            table_name: Name of the table to extract
            key_column: Column to use for pagination (should be indexed)
            batch_size: Number of rows per batch
        """
        super().__init__(database, fetch_size=batch_size)
        self.table_name = table_name
        self.key_column = key_column

    async def extract(
        self,
        start_key: Any = None,
        end_key: Any = None,
        columns: list[str] | None = None,
        where: str | None = None,
        **kwargs,
    ) -> AsyncIterator[dict[str, Any]]:
        """Extract table data with efficient key-based pagination.

        Args:
            start_key: Start value for key column (inclusive)
            end_key: End value for key column (inclusive)
            columns: Columns to select
            where: Additional WHERE conditions
            **kwargs: Additional options

        Yields:
            Table records in key order
        """
        # Build WHERE clause with key range
        conditions = []
        params = {}

        if start_key is not None:
            conditions.append(f"{self.key_column} >= :start_key")
            params["start_key"] = start_key

        if end_key is not None:
            conditions.append(f"{self.key_column} <= :end_key")
            params["end_key"] = end_key

        if where:
            conditions.append(f"({where})")

        where_clause = " AND ".join(conditions) if conditions else None

        # Extract with ordering by key for consistent pagination
        async for record in super().extract(
            table=self.table_name,
            columns=columns,
            where=where_clause,
            order_by=self.key_column,
            params=params,
            **kwargs,
        ):
            yield record


class QuerySource(DatabaseSource):
    """Source that executes predefined queries with parameter substitution."""

    def __init__(
        self,
        database: Database,
        query: str | SQL,
        fetch_size: int = 1000,
    ):
        """Initialize query source.

        Args:
            database: Whiskey SQL Database instance
            query: SQL query template
            fetch_size: Number of rows to fetch at a time
        """
        super().__init__(database, fetch_size)
        self.query = SQL(query) if isinstance(query, str) else query

    async def extract(self, **params) -> AsyncIterator[dict[str, Any]]:
        """Execute query with provided parameters.

        Args:
            **params: Parameters to pass to the query

        Yields:
            Query results
        """
        async for record in super().extract(
            query=self.query,
            params=params,
        ):
            yield record


class SQLFileSource(DatabaseSource):
    """Source that loads queries from SQL files."""

    def __init__(
        self,
        database: Database,
        sql_file: str,
        fetch_size: int = 1000,
    ):
        """Initialize SQL file source.

        Args:
            database: Whiskey SQL Database instance
            sql_file: Path to SQL file
            fetch_size: Number of rows to fetch at a time
        """
        super().__init__(database, fetch_size)
        self.query = SQL.from_file(sql_file)

    async def extract(self, **params) -> AsyncIterator[dict[str, Any]]:
        """Execute SQL file query with parameters.

        Args:
            **params: Parameters to pass to the query

        Yields:
            Query results
        """
        async for record in super().extract(
            query=self.query,
            params=params,
        ):
            yield record
