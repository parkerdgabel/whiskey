"""Database backend implementations."""

from typing import Any

from whiskey_sql.exceptions import ConfigurationError


async def create_database_pool(**config) -> Any:
    """Create a database connection pool based on dialect.

    Args:
        **config: Database configuration including 'dialect'

    Returns:
        Database connection pool

    Raises:
        ConfigurationError: If dialect is not supported
    """
    dialect = config.get("dialect", "").lower()

    if dialect in ("postgresql", "postgres"):
        from whiskey_sql.backends.postgresql import create_pool

        return await create_pool(**config)

    elif dialect == "mysql":
        from whiskey_sql.backends.mysql import create_pool

        return await create_pool(**config)

    elif dialect == "sqlite":
        from whiskey_sql.backends.sqlite import create_pool

        return await create_pool(**config)

    elif dialect == "duckdb":
        from whiskey_sql.backends.duckdb import create_pool

        return await create_pool(**config)

    else:
        raise ConfigurationError(
            f"Unsupported database dialect: {dialect}. Supported: postgresql, mysql, sqlite, duckdb"
        )
