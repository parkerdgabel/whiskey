"""Data source implementations for ETL pipelines."""

from __future__ import annotations

import csv
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, AsyncIterator, Callable

from .errors import SourceError


class DataSource(ABC):
    """Abstract base class for data sources."""

    @abstractmethod
    async def extract(self, **kwargs) -> AsyncIterator[Any]:
        """Extract data from the source.

        Yields:
            Records from the data source
        """
        pass


class SourceRegistry:
    """Registry for data sources."""

    def __init__(self):
        self._sources: dict[str, type[DataSource]] = {}

    def register(self, name: str, source_class: type[DataSource]) -> None:
        """Register a data source."""
        self._sources[name] = source_class

    def get(self, name: str) -> type[DataSource] | None:
        """Get source class by name."""
        return self._sources.get(name)

    def list_sources(self) -> list[str]:
        """List all registered sources."""
        return list(self._sources.keys())


class FileSource(DataSource):
    """Base class for file-based sources."""

    async def validate_file(self, file_path: str) -> Path:
        """Validate file exists and is readable."""
        path = Path(file_path)
        if not path.exists():
            raise SourceError(self.__class__.__name__, f"File not found: {file_path}")
        if not path.is_file():
            raise SourceError(self.__class__.__name__, f"Not a file: {file_path}")
        return path


class CsvSource(FileSource):
    """CSV file data source."""

    def __init__(
        self,
        delimiter: str = ",",
        encoding: str = "utf-8",
        has_header: bool = True,
        skip_lines: int = 0,
    ):
        self.delimiter = delimiter
        self.encoding = encoding
        self.has_header = has_header
        self.skip_lines = skip_lines

    async def extract(
        self, file_path: str, fieldnames: list[str] | None = None, **kwargs
    ) -> AsyncIterator[dict[str, Any]]:
        """Extract records from CSV file.

        Args:
            file_path: Path to CSV file
            fieldnames: Optional field names if not in header
            **kwargs: Additional options

        Yields:
            Dictionary for each row
        """
        path = await self.validate_file(file_path)

        try:
            with open(path, encoding=self.encoding) as file:
                # Skip lines if needed
                for _ in range(self.skip_lines):
                    next(file, None)

                # Create CSV reader
                if self.has_header and not fieldnames:
                    reader = csv.DictReader(file, delimiter=self.delimiter)
                else:
                    reader = csv.DictReader(file, fieldnames=fieldnames, delimiter=self.delimiter)
                    if self.has_header:
                        next(reader, None)  # Skip header

                # Yield records
                for row_num, row in enumerate(reader, start=1):
                    try:
                        # Convert to regular dict and clean
                        record = dict(row)
                        # Add metadata
                        record["_source_file"] = str(path)
                        record["_row_number"] = row_num + self.skip_lines

                        yield record
                    except Exception as e:
                        raise SourceError(
                            self.__class__.__name__,
                            f"Error reading row {row_num}: {e}",
                            details={"row": row, "file": str(path)},
                        ) from e

        except Exception as e:
            if isinstance(e, SourceError):
                raise
            raise SourceError(
                self.__class__.__name__,
                f"Failed to read CSV file: {e}",
                details={"file": str(path)},
            ) from e


class JsonSource(FileSource):
    """JSON file data source."""

    def __init__(
        self,
        encoding: str = "utf-8",
        json_path: str | None = None,
    ):
        self.encoding = encoding
        self.json_path = json_path  # JSONPath expression for nested data

    async def extract(self, file_path: str, **kwargs) -> AsyncIterator[dict[str, Any]]:
        """Extract records from JSON file.

        Args:
            file_path: Path to JSON file
            **kwargs: Additional options

        Yields:
            Records from JSON file
        """
        path = await self.validate_file(file_path)

        try:
            with open(path, encoding=self.encoding) as file:
                data = json.load(file)

                # Handle different JSON structures
                if isinstance(data, list):
                    # Array of records
                    for i, record in enumerate(data):
                        if isinstance(record, dict):
                            record["_source_file"] = str(path)
                            record["_index"] = i
                            yield record
                        else:
                            yield {
                                "value": record,
                                "_source_file": str(path),
                                "_index": i,
                            }

                elif isinstance(data, dict):
                    # Single record or nested structure
                    if self.json_path:
                        # TODO: Implement JSONPath extraction
                        raise NotImplementedError("JSONPath not yet implemented")
                    else:
                        # Yield single record
                        data["_source_file"] = str(path)
                        yield data

                else:
                    # Primitive value
                    yield {
                        "value": data,
                        "_source_file": str(path),
                    }

        except json.JSONDecodeError as e:
            raise SourceError(
                self.__class__.__name__,
                f"Invalid JSON file: {e}",
                details={"file": str(path), "error": str(e)},
            ) from e
        except Exception as e:
            if isinstance(e, SourceError):
                raise
            raise SourceError(
                self.__class__.__name__,
                f"Failed to read JSON file: {e}",
                details={"file": str(path)},
            ) from e


class JsonLinesSource(FileSource):
    """JSON Lines (JSONL) file data source."""

    def __init__(self, encoding: str = "utf-8"):
        self.encoding = encoding

    async def extract(self, file_path: str, **kwargs) -> AsyncIterator[dict[str, Any]]:
        """Extract records from JSON Lines file.

        Args:
            file_path: Path to JSONL file
            **kwargs: Additional options

        Yields:
            One record per line
        """
        path = await self.validate_file(file_path)

        try:
            with open(path, encoding=self.encoding) as file:
                for line_num, line in enumerate(file, start=1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        record = json.loads(line)
                        if isinstance(record, dict):
                            record["_source_file"] = str(path)
                            record["_line_number"] = line_num
                            yield record
                        else:
                            yield {
                                "value": record,
                                "_source_file": str(path),
                                "_line_number": line_num,
                            }
                    except json.JSONDecodeError as e:
                        raise SourceError(
                            self.__class__.__name__,
                            f"Invalid JSON on line {line_num}: {e}",
                            details={
                                "file": str(path),
                                "line": line_num,
                                "content": line[:100],
                            },
                        ) from e

        except Exception as e:
            if isinstance(e, SourceError):
                raise
            raise SourceError(
                self.__class__.__name__,
                f"Failed to read JSON Lines file: {e}",
                details={"file": str(path)},
            ) from e


class MemorySource(DataSource):
    """In-memory data source for testing."""

    def __init__(self, data: list[Any] | None = None):
        self.data = data or []

    async def extract(self, **kwargs) -> AsyncIterator[Any]:
        """Extract records from memory.

        Yields:
            Records from memory
        """
        for record in self.data:
            yield record


class GeneratorSource(DataSource):
    """Data source from a generator function."""

    def __init__(self, generator_func: Callable[..., AsyncIterator[Any]]):
        self.generator_func = generator_func

    async def extract(self, **kwargs) -> AsyncIterator[Any]:
        """Extract records from generator.

        Yields:
            Records from generator function
        """
        async for record in self.generator_func(**kwargs):
            yield record
