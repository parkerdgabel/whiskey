"""PostgreSQL backend using asyncpg."""

from __future__ import annotations

import asyncio
from dataclasses import asdict, is_dataclass
from typing import Any, AsyncIterator, Type, TypeVar

try:
    import asyncpg
except ImportError:
    raise ImportError(
        "asyncpg is required for PostgreSQL support. "
        "Install with: pip install whiskey-sql[postgresql]"
    )

from whiskey_sql.core import Database, SQL, Transaction, ConnectionContext
from whiskey_sql.exceptions import ConnectionError, QueryError

T = TypeVar("T")


async def create_pool(**config) -> asyncpg.Pool:
    """Create asyncpg connection pool.
    
    Args:
        **config: Database configuration
        
    Returns:
        asyncpg connection pool
    """
    url = config["url"]
    pool_size = config.get("pool_size", 20)
    pool_timeout = config.get("pool_timeout", 30.0)
    server_settings = config.get("server_settings", {})
    
    try:
        pool = await asyncpg.create_pool(
            url,
            min_size=1,
            max_size=pool_size,
            command_timeout=pool_timeout,
            server_settings=server_settings,
        )
        return pool
    except Exception as e:
        raise ConnectionError(f"Failed to create PostgreSQL pool: {e}")


class PostgreSQLDatabase(Database):
    """PostgreSQL-specific database implementation."""
    
    def __init__(self, pool: asyncpg.Pool):
        """Initialize PostgreSQL database.
        
        Args:
            pool: asyncpg connection pool
        """
        super().__init__(pool, dialect="postgresql")
        self._type_codecs_set = False
    
    async def _ensure_type_codecs(self) -> None:
        """Set up type codecs for common PostgreSQL types."""
        if self._type_codecs_set:
            return
            
        async with self.pool.acquire() as conn:
            # Set up JSON codec
            await conn.set_type_codec(
                "json",
                encoder=lambda v: v,
                decoder=lambda v: v,
                schema="pg_catalog"
            )
            await conn.set_type_codec(
                "jsonb", 
                encoder=lambda v: v,
                decoder=lambda v: v,
                schema="pg_catalog"
            )
        
        self._type_codecs_set = True
    
    def _convert_params(self, query: SQL, params: dict[str, Any] | None) -> tuple[str, list[Any]]:
        """Convert named parameters to positional for asyncpg.
        
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
        pattern = r':([a-zA-Z_][a-zA-Z0-9_]*)\b'
        param_names = []
        
        def replacer(match):
            param_name = match.group(1)
            if param_name not in param_names:
                param_names.append(param_name)
            return f"${param_names.index(param_name) + 1}"
        
        converted_query = re.sub(pattern, replacer, str(query))
        param_values = [params.get(name) for name in param_names]
        
        return converted_query, param_values
    
    def _map_result(self, record: asyncpg.Record | None, result_type: Type[T] | None) -> T | dict | None:
        """Map database record to result type.
        
        Args:
            record: Database record
            result_type: Target type for mapping
            
        Returns:
            Mapped result or None
        """
        if record is None:
            return None
        
        # Convert to dict first
        row_dict = dict(record)
        
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
        self,
        query: SQL,
        params: dict[str, Any] | None = None,
        result_type: Type[T] | None = None
    ) -> T | dict[str, Any] | None:
        """Fetch a single row."""
        await self._ensure_type_codecs()
        
        converted_query, param_values = self._convert_params(query, params)
        
        try:
            async with self.pool.acquire() as conn:
                record = await conn.fetchrow(converted_query, *param_values)
                return self._map_result(record, result_type)
        except Exception as e:
            raise QueryError(f"Query failed: {e}", str(query), params)
    
    async def fetch_all(
        self,
        query: SQL,
        params: dict[str, Any] | None = None,
        result_type: Type[T] | None = None
    ) -> list[T] | list[dict[str, Any]]:
        """Fetch all rows."""
        await self._ensure_type_codecs()
        
        converted_query, param_values = self._convert_params(query, params)
        
        try:
            async with self.pool.acquire() as conn:
                records = await conn.fetch(converted_query, *param_values)
                return [self._map_result(record, result_type) for record in records]
        except Exception as e:
            raise QueryError(f"Query failed: {e}", str(query), params)
    
    async def fetch_val(
        self,
        query: SQL,
        params: dict[str, Any] | None = None,
        column: int = 0
    ) -> Any:
        """Fetch a single value."""
        await self._ensure_type_codecs()
        
        converted_query, param_values = self._convert_params(query, params)
        
        try:
            async with self.pool.acquire() as conn:
                return await conn.fetchval(converted_query, *param_values, column=column)
        except Exception as e:
            raise QueryError(f"Query failed: {e}", str(query), params)
    
    async def fetch_row(
        self,
        query: SQL,
        params: dict[str, Any] | None = None
    ) -> tuple[Any, ...] | None:
        """Fetch a single row as tuple."""
        await self._ensure_type_codecs()
        
        converted_query, param_values = self._convert_params(query, params)
        
        try:
            async with self.pool.acquire() as conn:
                record = await conn.fetchrow(converted_query, *param_values)
                return tuple(record.values()) if record else None
        except Exception as e:
            raise QueryError(f"Query failed: {e}", str(query), params)
    
    async def execute(
        self,
        query: SQL,
        params: dict[str, Any] | None = None
    ) -> str:
        """Execute a query without results."""
        await self._ensure_type_codecs()
        
        converted_query, param_values = self._convert_params(query, params)
        
        try:
            async with self.pool.acquire() as conn:
                return await conn.execute(converted_query, *param_values)
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
        
        await self._ensure_type_codecs()
        
        # Convert all parameter sets
        converted_query = None
        all_params = []
        
        for params in params_list:
            query_str, param_values = self._convert_params(query, params)
            if converted_query is None:
                converted_query = query_str
            all_params.append(param_values)
        
        try:
            async with self.pool.acquire() as conn:
                await conn.executemany(converted_query, all_params)
        except Exception as e:
            raise QueryError(f"Batch query failed: {e}", str(query), None)
    
    async def stream(
        self,
        query: SQL,
        params: dict[str, Any] | None = None,
        fetch_size: int = 100
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream query results."""
        await self._ensure_type_codecs()
        
        converted_query, param_values = self._convert_params(query, params)
        
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                cursor = await conn.cursor(converted_query, *param_values)
                
                while True:
                    records = await cursor.fetch(fetch_size)
                    if not records:
                        break
                    
                    for record in records:
                        yield dict(record)


# Create factory function
async def create_database(pool: asyncpg.Pool) -> PostgreSQLDatabase:
    """Create PostgreSQL database instance.
    
    Args:
        pool: asyncpg connection pool
        
    Returns:
        PostgreSQL database instance
    """
    return PostgreSQLDatabase(pool)