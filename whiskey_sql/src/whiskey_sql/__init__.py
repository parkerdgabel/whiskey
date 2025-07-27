"""Whiskey SQL Extension - Pure SQL templating for Whiskey applications."""

from whiskey_sql.core import SQL, Database, transaction
from whiskey_sql.extension import sql_extension
from whiskey_sql.exceptions import DatabaseError, QueryError, TransactionError
from whiskey_sql.types import Row, ResultType

__version__ = "0.1.0"

__all__ = [
    # Core
    "SQL",
    "Database",
    "transaction",
    # Extension
    "sql_extension",
    # Exceptions
    "DatabaseError",
    "QueryError", 
    "TransactionError",
    # Types
    "Row",
    "ResultType",
]