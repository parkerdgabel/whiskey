"""Whiskey SQL exception types."""


class DatabaseError(Exception):
    """Base exception for all database-related errors."""

    pass


class ConfigurationError(DatabaseError):
    """Raised when database configuration is invalid."""

    pass


class DatabaseConnectionError(DatabaseError):
    """Raised when database connection fails."""

    pass


class QueryError(DatabaseError):
    """Raised when query execution fails."""

    def __init__(self, message: str, query: str | None = None, params: dict | None = None):
        """Initialize query error.

        Args:
            message: Error message
            query: The SQL query that failed
            params: Query parameters
        """
        super().__init__(message)
        self.query = query
        self.params = params


class TransactionError(DatabaseError):
    """Raised when transaction operations fail."""

    pass


class MigrationError(DatabaseError):
    """Raised when database migration fails."""

    def __init__(self, message: str, migration_file: str | None = None):
        """Initialize migration error.

        Args:
            message: Error message
            migration_file: The migration file that failed
        """
        super().__init__(message)
        self.migration_file = migration_file
