"""Type definitions for Whiskey SQL."""

from typing import Any, Protocol, TypeVar, Union

# Type variable for result mapping
T = TypeVar("T")

# Row type alias
Row = dict[str, Any]

# Result type can be a dataclass, dict, or custom type
ResultType = Union[type[T], None]


class Executable(Protocol):
    """Protocol for objects that can execute SQL queries."""

    async def execute(self, query: str, params: dict | None = None) -> str:
        """Execute a query without returning results."""
        ...

    async def fetch(self, query: str, params: dict | None = None) -> list[Row]:
        """Fetch all rows from a query."""
        ...

    async def fetchone(self, query: str, params: dict | None = None) -> Row | None:
        """Fetch a single row from a query."""
        ...

    async def fetchval(self, query: str, params: dict | None = None, column: int = 0) -> Any:
        """Fetch a single value from a query."""
        ...
