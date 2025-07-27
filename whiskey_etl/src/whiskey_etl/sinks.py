"""Data sink implementations for ETL pipelines."""

from __future__ import annotations

import csv
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, Union

from .errors import SinkError


class DataSink(ABC):
    """Abstract base class for data sinks."""
    
    @abstractmethod
    async def load(self, records: List[Any], **kwargs) -> None:
        """Load records to the sink.
        
        Args:
            records: Batch of records to load
            **kwargs: Additional options
        """
        pass


class SinkRegistry:
    """Registry for data sinks."""
    
    def __init__(self):
        self._sinks: Dict[str, Type[DataSink]] = {}
    
    def register(self, name: str, sink_class: Type[DataSink]) -> None:
        """Register a data sink."""
        self._sinks[name] = sink_class
    
    def get(self, name: str) -> Optional[Type[DataSink]]:
        """Get sink class by name."""
        return self._sinks.get(name)
    
    def list_sinks(self) -> List[str]:
        """List all registered sinks."""
        return list(self._sinks.keys())


class FileSink(DataSink):
    """Base class for file-based sinks."""
    
    def __init__(self, mode: str = "w", encoding: str = "utf-8"):
        self.mode = mode
        self.encoding = encoding
    
    async def ensure_directory(self, file_path: str) -> Path:
        """Ensure directory exists for file."""
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path


class CsvSink(FileSink):
    """CSV file data sink."""
    
    def __init__(
        self,
        delimiter: str = ",",
        encoding: str = "utf-8",
        mode: str = "w",
        write_header: bool = True,
        fieldnames: Optional[List[str]] = None,
    ):
        super().__init__(mode, encoding)
        self.delimiter = delimiter
        self.write_header = write_header
        self.fieldnames = fieldnames
        self._headers_written: Dict[str, bool] = {}
    
    async def load(
        self,
        records: List[Dict[str, Any]],
        file_path: str,
        **kwargs
    ) -> None:
        """Load records to CSV file.
        
        Args:
            records: List of dictionaries to write
            file_path: Path to output CSV file
            **kwargs: Additional options
        """
        if not records:
            return
            
        path = await self.ensure_directory(file_path)
        
        try:
            # Determine fieldnames
            if not self.fieldnames:
                # Get all unique keys from records
                all_keys = set()
                for record in records:
                    if isinstance(record, dict):
                        # Skip metadata fields
                        keys = {k for k in record.keys() if not k.startswith("_")}
                        all_keys.update(keys)
                fieldnames = sorted(all_keys)
            else:
                fieldnames = self.fieldnames
            
            # Write mode handling
            mode = self.mode
            write_header = self.write_header
            
            # For append mode, check if we need to write header
            if mode == "a" and str(path) not in self._headers_written:
                if path.exists() and path.stat().st_size > 0:
                    write_header = False
                self._headers_written[str(path)] = True
            
            # Write records
            with open(path, mode, encoding=self.encoding, newline="") as file:
                writer = csv.DictWriter(
                    file,
                    fieldnames=fieldnames,
                    delimiter=self.delimiter,
                    extrasaction="ignore",  # Ignore extra fields
                )
                
                # Write header if needed
                if write_header and (mode == "w" or path.stat().st_size == 0):
                    writer.writeheader()
                
                # Write records
                for record in records:
                    if isinstance(record, dict):
                        # Remove metadata fields
                        clean_record = {
                            k: v for k, v in record.items()
                            if not k.startswith("_")
                        }
                        writer.writerow(clean_record)
                    else:
                        # Handle non-dict records
                        writer.writerow({"value": record})
                        
        except Exception as e:
            raise SinkError(
                self.__class__.__name__,
                f"Failed to write CSV file: {e}",
                details={"file": str(path), "records": len(records)}
            )


class JsonSink(FileSink):
    """JSON file data sink."""
    
    def __init__(
        self,
        encoding: str = "utf-8",
        mode: str = "w",
        indent: Optional[int] = 2,
        ensure_ascii: bool = False,
    ):
        super().__init__(mode, encoding)
        self.indent = indent
        self.ensure_ascii = ensure_ascii
        self._existing_data: Dict[str, List[Any]] = {}
    
    async def load(
        self,
        records: List[Any],
        file_path: str,
        **kwargs
    ) -> None:
        """Load records to JSON file.
        
        Args:
            records: List of records to write
            file_path: Path to output JSON file
            **kwargs: Additional options
        """
        if not records:
            return
            
        path = await self.ensure_directory(file_path)
        
        try:
            # Handle append mode
            if self.mode == "a" and path.exists():
                # Load existing data
                if str(path) not in self._existing_data:
                    try:
                        with open(path, "r", encoding=self.encoding) as file:
                            existing = json.load(file)
                            if isinstance(existing, list):
                                self._existing_data[str(path)] = existing
                            else:
                                self._existing_data[str(path)] = [existing]
                    except (json.JSONDecodeError, FileNotFoundError):
                        self._existing_data[str(path)] = []
                
                # Append new records
                all_records = self._existing_data[str(path)] + records
            else:
                all_records = records
            
            # Write all records
            with open(path, "w", encoding=self.encoding) as file:
                json.dump(
                    all_records,
                    file,
                    indent=self.indent,
                    ensure_ascii=self.ensure_ascii,
                )
                
            # Update cache for append mode
            if self.mode == "a":
                self._existing_data[str(path)] = all_records
                
        except Exception as e:
            raise SinkError(
                self.__class__.__name__,
                f"Failed to write JSON file: {e}",
                details={"file": str(path), "records": len(records)}
            )


class JsonLinesSink(FileSink):
    """JSON Lines (JSONL) file data sink."""
    
    def __init__(
        self,
        encoding: str = "utf-8",
        mode: str = "a",  # Default to append for streaming
        ensure_ascii: bool = False,
    ):
        super().__init__(mode, encoding)
        self.ensure_ascii = ensure_ascii
    
    async def load(
        self,
        records: List[Any],
        file_path: str,
        **kwargs
    ) -> None:
        """Load records to JSON Lines file.
        
        Args:
            records: List of records to write
            file_path: Path to output JSONL file
            **kwargs: Additional options
        """
        if not records:
            return
            
        path = await self.ensure_directory(file_path)
        
        try:
            with open(path, self.mode, encoding=self.encoding) as file:
                for record in records:
                    # Write each record as a JSON line
                    json_line = json.dumps(
                        record,
                        ensure_ascii=self.ensure_ascii,
                    )
                    file.write(json_line + "\n")
                    
        except Exception as e:
            raise SinkError(
                self.__class__.__name__,
                f"Failed to write JSON Lines file: {e}",
                details={"file": str(path), "records": len(records)}
            )


class MemorySink(DataSink):
    """In-memory data sink for testing."""
    
    def __init__(self):
        self.data: List[Any] = []
    
    async def load(self, records: List[Any], **kwargs) -> None:
        """Load records to memory.
        
        Args:
            records: Records to store
            **kwargs: Additional options
        """
        self.data.extend(records)
    
    def clear(self) -> None:
        """Clear stored data."""
        self.data.clear()
    
    def get_data(self) -> List[Any]:
        """Get stored data."""
        return self.data.copy()


class ConsoleSink(DataSink):
    """Console output sink for debugging."""
    
    def __init__(
        self,
        format: str = "json",
        prefix: Optional[str] = None,
    ):
        self.format = format
        self.prefix = prefix
    
    async def load(self, records: List[Any], **kwargs) -> None:
        """Print records to console.
        
        Args:
            records: Records to print
            **kwargs: Additional options
        """
        for i, record in enumerate(records):
            if self.prefix:
                print(f"{self.prefix} [{i}]:", end=" ")
            
            if self.format == "json":
                print(json.dumps(record, indent=2))
            elif self.format == "repr":
                print(repr(record))
            else:
                print(record)


class CallbackSink(DataSink):
    """Sink that calls a user-provided callback."""
    
    def __init__(self, callback: Callable[[List[Any]], None]):
        self.callback = callback
    
    async def load(self, records: List[Any], **kwargs) -> None:
        """Pass records to callback.
        
        Args:
            records: Records to process
            **kwargs: Additional options
        """
        if asyncio.iscoroutinefunction(self.callback):
            await self.callback(records, **kwargs)
        else:
            self.callback(records, **kwargs)