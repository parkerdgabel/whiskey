"""Database sink implementation using whiskey_sql."""

from __future__ import annotations

from typing import Any

from whiskey_sql import SQL, Database

from .errors import SinkError
from .sinks import DataSink


class DatabaseSink(DataSink):
    """SQL database sink using whiskey_sql Database.

    This sink leverages the whiskey_sql extension for database connectivity,
    providing automatic connection pooling, transactions, and proper resource management.
    """

    def __init__(
        self,
        database: Database,
        use_transaction: bool = True,
        on_conflict: str | None = None,
    ):
        """Initialize database sink.

        Args:
            database: Whiskey SQL Database instance (auto-injected)
            use_transaction: Whether to wrap batch inserts in a transaction
            on_conflict: SQL clause for handling conflicts (e.g., "DO NOTHING", "DO UPDATE SET ...")
        """
        self.database = database
        self.use_transaction = use_transaction
        self.on_conflict = on_conflict

    async def load(self, records: list[Any], **kwargs) -> None:
        """Load records to database.

        This base implementation expects subclasses to implement the actual
        loading logic for specific table structures.

        Args:
            records: Batch of records to load
            **kwargs: Additional options
        """
        raise NotImplementedError("Subclasses must implement load()")


class TableSink(DatabaseSink):
    """Sink for inserting records into a specific table."""

    def __init__(
        self,
        database: Database,
        table_name: str,
        columns: list[str] | None = None,
        use_transaction: bool = True,
        on_conflict: str | None = None,
        returning: list[str] | None = None,
    ):
        """Initialize table sink.

        Args:
            database: Whiskey SQL Database instance
            table_name: Target table name
            columns: Columns to insert (if None, uses all record keys)
            use_transaction: Whether to use a transaction
            on_conflict: Conflict handling clause
            returning: Columns to return after insert
        """
        super().__init__(database, use_transaction, on_conflict)
        self.table_name = table_name
        self.columns = columns
        self.returning = returning

    async def load(self, records: list[dict[str, Any]], **kwargs) -> None:
        """Insert records into table.

        Args:
            records: List of dictionaries to insert
            **kwargs: Additional options
        """
        if not records:
            return

        try:
            # Determine columns from first record if not specified
            if self.columns is None:
                # Get columns from first record, excluding metadata fields
                first_record = records[0]
                self.columns = [k for k in first_record.keys() if not k.startswith("_")]

            # Build INSERT query
            columns_str = ", ".join(self.columns)
            values_placeholders = ", ".join(f":{col}" for col in self.columns)

            query = f"INSERT INTO {self.table_name} ({columns_str}) VALUES ({values_placeholders})"

            # Add conflict handling
            if self.on_conflict:
                query += f" ON CONFLICT {self.on_conflict}"

            # Add returning clause
            if self.returning:
                query += f" RETURNING {', '.join(self.returning)}"

            sql_query = SQL(query)

            # Execute with or without transaction
            if self.use_transaction:
                async with self.database.transaction():
                    await self._execute_batch(sql_query, records)
            else:
                await self._execute_batch(sql_query, records)

        except Exception as e:
            raise SinkError(
                self.__class__.__name__,
                f"Failed to insert into table {self.table_name}: {e}",
                details={
                    "table": self.table_name,
                    "records": len(records),
                    "columns": self.columns,
                },
            ) from e

    async def _execute_batch(self, query: SQL, records: list[dict[str, Any]]) -> None:
        """Execute batch insert."""
        # Prepare records - only include specified columns
        params_list = []
        for record in records:
            params = {col: record.get(col) for col in self.columns}
            params_list.append(params)

        # Execute batch insert
        await self.database.execute_many(query, params_list)


class UpsertSink(TableSink):
    """Sink that performs UPSERT operations (INSERT ... ON CONFLICT DO UPDATE)."""

    def __init__(
        self,
        database: Database,
        table_name: str,
        key_columns: list[str],
        update_columns: list[str] | None = None,
        columns: list[str] | None = None,
        use_transaction: bool = True,
    ):
        """Initialize upsert sink.

        Args:
            database: Whiskey SQL Database instance
            table_name: Target table name
            key_columns: Columns that form the unique constraint
            update_columns: Columns to update on conflict (if None, updates all non-key columns)
            columns: All columns to insert
            use_transaction: Whether to use a transaction
        """
        # Build ON CONFLICT clause
        key_cols_str = ", ".join(key_columns)
        on_conflict = f"({key_cols_str}) DO UPDATE SET "

        # Determine update columns
        if update_columns is None and columns is not None:
            # Update all non-key columns
            update_columns = [col for col in columns if col not in key_columns]

        if update_columns:
            # Build UPDATE SET clause
            update_parts = [f"{col} = EXCLUDED.{col}" for col in update_columns]
            on_conflict += ", ".join(update_parts)
        else:
            # If no columns to update, just do nothing on conflict
            on_conflict = f"({key_cols_str}) DO NOTHING"

        super().__init__(
            database=database,
            table_name=table_name,
            columns=columns,
            use_transaction=use_transaction,
            on_conflict=on_conflict,
        )
        self.key_columns = key_columns
        self.update_columns = update_columns


class BulkUpdateSink(DatabaseSink):
    """Sink for bulk UPDATE operations."""

    def __init__(
        self,
        database: Database,
        table_name: str,
        key_columns: list[str],
        update_columns: list[str],
        use_transaction: bool = True,
    ):
        """Initialize bulk update sink.

        Args:
            database: Whiskey SQL Database instance
            table_name: Target table name
            key_columns: Columns to match for updates
            update_columns: Columns to update
            use_transaction: Whether to use a transaction
        """
        super().__init__(database, use_transaction)
        self.table_name = table_name
        self.key_columns = key_columns
        self.update_columns = update_columns

    async def load(self, records: list[dict[str, Any]], **kwargs) -> None:
        """Perform bulk updates.

        Args:
            records: Records containing key columns and update values
            **kwargs: Additional options
        """
        if not records:
            return

        try:
            # Build UPDATE query
            set_clause = ", ".join(f"{col} = :{col}" for col in self.update_columns)
            where_clause = " AND ".join(f"{col} = :key_{col}" for col in self.key_columns)

            query = SQL(f"UPDATE {self.table_name} SET {set_clause} WHERE {where_clause}")

            # Prepare parameters
            params_list = []
            for record in records:
                params = {}
                # Add update column values
                for col in self.update_columns:
                    params[col] = record.get(col)
                # Add key column values with prefix to avoid conflicts
                for col in self.key_columns:
                    params[f"key_{col}"] = record.get(col)
                params_list.append(params)

            # Execute updates
            if self.use_transaction:
                async with self.database.transaction():
                    await self.database.execute_many(query, params_list)
            else:
                await self.database.execute_many(query, params_list)

        except Exception as e:
            raise SinkError(
                self.__class__.__name__,
                f"Failed to update table {self.table_name}: {e}",
                details={
                    "table": self.table_name,
                    "records": len(records),
                    "key_columns": self.key_columns,
                    "update_columns": self.update_columns,
                },
            ) from e


class SQLExecuteSink(DatabaseSink):
    """Sink that executes arbitrary SQL for each record."""

    def __init__(
        self,
        database: Database,
        query: str | SQL,
        use_transaction: bool = True,
    ):
        """Initialize SQL execute sink.

        Args:
            database: Whiskey SQL Database instance
            query: SQL query template with parameter placeholders
            use_transaction: Whether to use a transaction
        """
        super().__init__(database, use_transaction)
        self.query = SQL(query) if isinstance(query, str) else query

    async def load(self, records: list[dict[str, Any]], **kwargs) -> None:
        """Execute SQL for each record.

        Args:
            records: Records to process (each record's values are passed as query parameters)
            **kwargs: Additional options
        """
        if not records:
            return

        try:
            if self.use_transaction:
                async with self.database.transaction():
                    await self.database.execute_many(self.query, records)
            else:
                await self.database.execute_many(self.query, records)

        except Exception as e:
            raise SinkError(
                self.__class__.__name__,
                f"Failed to execute SQL: {e}",
                details={
                    "query": str(self.query),
                    "records": len(records),
                },
            ) from e
