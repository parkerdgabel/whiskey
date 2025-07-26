"""Whiskey SQL extension for dependency injection integration."""

from __future__ import annotations

import os
from typing import Any, Callable, Type
from urllib.parse import urlparse

from whiskey import Whiskey, singleton
from whiskey.core.decorators import component

from whiskey_sql.core import Database, SQL
from whiskey_sql.backends import create_database_pool
from whiskey_sql.exceptions import ConfigurationError


def sql_extension(app: Whiskey) -> None:
    """Configure Whiskey application with SQL support.
    
    This extension adds:
    - Database configuration methods
    - SQL query registration decorator
    - Automatic Database injection
    - Migration support
    
    Args:
        app: Whiskey application instance
        
    Examples:
        >>> app = Whiskey()
        >>> app.use(sql_extension)
        >>> app.configure_database("postgresql://localhost/myapp")
    """
    # Add configuration method
    app.configure_database = lambda **kwargs: _configure_database(app, **kwargs)
    
    # Add SQL registration decorator
    app.sql = lambda name: _create_sql_decorator(app, name)
    
    # Register default database if DATABASE_URL is set
    if database_url := os.getenv("DATABASE_URL"):
        _configure_database(app, url=database_url)


def _configure_database(
    app: Whiskey,
    url: str | None = None,
    *,
    name: str | None = None,
    pool_size: int = 20,
    pool_timeout: float = 30.0,
    echo_queries: bool = False,
    ssl_context: Any = None,
    server_settings: dict[str, str] | None = None,
    **kwargs
) -> None:
    """Configure a database connection.
    
    Args:
        app: Whiskey application instance
        url: Database URL (e.g., postgresql://user:pass@host/db)
        name: Optional name for multiple databases
        pool_size: Maximum number of connections in pool
        pool_timeout: Timeout for acquiring connection from pool
        echo_queries: Whether to log all queries
        ssl_context: SSL context for secure connections
        server_settings: Database-specific server settings
        **kwargs: Additional backend-specific options
    """
    if not url:
        url = os.getenv("DATABASE_URL")
        if not url:
            raise ConfigurationError("Database URL not provided")
    
    # Parse database URL to determine backend
    parsed = urlparse(url)
    dialect = parsed.scheme.split("+")[0]  # Handle postgresql+asyncpg
    
    # Create configuration
    config = {
        "url": url,
        "dialect": dialect,
        "pool_size": pool_size,
        "pool_timeout": pool_timeout,
        "echo_queries": echo_queries,
        "ssl_context": ssl_context,
        "server_settings": server_settings or {},
        **kwargs
    }
    
    # Create database factory
    async def database_factory() -> Database:
        """Factory function to create database instance."""
        pool = await create_database_pool(**config)
        return Database(pool, dialect=dialect)
    
    # Register as singleton
    if name:
        # Named database registration
        app.container.singleton((Database, name), database_factory)
    else:
        # Default database registration
        app.container.singleton(Database, database_factory)
    
    # Add startup hook to initialize pool
    @app.on_startup
    async def initialize_database():
        """Initialize database connection pool on startup."""
        if name:
            db = await app.container.resolve(Database, name=name)
        else:
            db = await app.container.resolve(Database)
        
        # Verify connection
        health = await db.health_check()
        if echo_queries:
            print(f"🗄️  Database connected: {dialect} (pool_size={pool_size})")
    
    # Add shutdown hook to close pool
    @app.on_shutdown
    async def close_database():
        """Close database connection pool on shutdown."""
        if name:
            db = await app.container.resolve(Database, name=name)
        else:
            db = await app.container.resolve(Database)
        
        if hasattr(db.pool, "close"):
            await db.pool.close()
            if echo_queries:
                print(f"🗄️  Database connection closed: {dialect}")


def _create_sql_decorator(app: Whiskey, name: str, path: str | None = None) -> Callable:
    """Create SQL query registration decorator.
    
    Args:
        app: Whiskey application instance
        name: Name for the query group
        path: Optional path to SQL files directory
        
    Returns:
        Decorator function for registering SQL queries
    """
    def decorator(cls: Type) -> Type:
        """Register a class containing SQL queries.
        
        The class can contain:
        - SQL instances as class attributes
        - Methods that return SQL instances
        - References to .sql files (when path is provided)
        
        Args:
            cls: Class containing SQL queries
            
        Returns:
            The registered class
        """
        # Process class attributes
        if path:
            _load_sql_files(cls, path)
        
        # Register as singleton component
        app.container.singleton(cls, cls)
        
        # Store metadata for introspection
        if not hasattr(cls, "_sql_metadata"):
            cls._sql_metadata = {
                "name": name,
                "path": path
            }
        
        return cls
    
    return decorator


def _load_sql_files(cls: Type, base_path: str) -> None:
    """Load SQL files referenced by class attributes.
    
    Args:
        cls: Class to populate with SQL queries
        base_path: Base directory for SQL files
    """
    from pathlib import Path
    
    base = Path(base_path)
    if not base.exists():
        raise ConfigurationError(f"SQL directory not found: {base_path}")
    
    # Look for None attributes that should be loaded from files
    for attr_name in dir(cls):
        if attr_name.startswith("_"):
            continue
            
        attr_value = getattr(cls, attr_name, None)
        if attr_value is None:
            # Try to load from file
            sql_file = base / f"{attr_name}.sql"
            if sql_file.exists():
                setattr(cls, attr_name, SQL.from_file(sql_file))
            else:
                # Check for type annotation
                annotations = getattr(cls, "__annotations__", {})
                if attr_name in annotations and annotations[attr_name] == SQL:
                    raise ConfigurationError(
                        f"SQL file not found for {cls.__name__}.{attr_name}: {sql_file}"
                    )