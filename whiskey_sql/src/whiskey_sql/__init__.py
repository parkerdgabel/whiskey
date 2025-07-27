"""Whiskey SQL Extension - Pure SQL templating for Whiskey applications."""

from whiskey_sql.core import SQL, Database, transaction
from whiskey_sql.exceptions import (
    DatabaseConnectionError,
    DatabaseError,
    QueryError,
    TransactionError,
)
from whiskey_sql.extension import sql_extension
from whiskey_sql.types import ResultType, Row

__version__ = "0.1.0"

__all__ = [
    "SQL",
    # Core
    "Database",
    # Exceptions
    "DatabaseConnectionError",
    "DatabaseError",
    "QueryError",
    # Types
    "ResultType",
    "Row",
    "TransactionError",
    # Extension
    "sql_extension",
    "transaction",
]
