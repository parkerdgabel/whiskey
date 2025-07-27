"""Tests for data sources."""

import json
from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest

from whiskey_etl.errors import SourceError
from whiskey_etl.sources import (
    CsvSource,
    JsonLinesSource,
    JsonSource,
    MemorySource,
    SourceRegistry,
)


@pytest.mark.asyncio
async def test_source_registry():
    """Test source registry functionality."""
    registry = SourceRegistry()

    # Register source
    registry.register("test", MemorySource)

    # Get source
    assert registry.get("test") == MemorySource
    assert registry.get("nonexistent") is None

    # List sources
    registry.register("another", CsvSource)
    sources = registry.list_sources()
    assert "test" in sources
    assert "another" in sources


@pytest.mark.asyncio
async def test_memory_source():
    """Test memory source."""
    data = [{"id": 1}, {"id": 2}, {"id": 3}]
    source = MemorySource(data)

    # Extract data
    extracted = []
    async for record in source.extract():
        extracted.append(record)

    assert extracted == data


@pytest.mark.asyncio
async def test_csv_source():
    """Test CSV source."""
    # Create test CSV file
    with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("id,name,age\n")
        f.write("1,Alice,30\n")
        f.write("2,Bob,25\n")
        f.write("3,Charlie,35\n")
        csv_path = f.name

    try:
        source = CsvSource()

        # Extract data
        records = []
        async for record in source.extract(csv_path):
            records.append(record)

        # Check records
        assert len(records) == 3
        assert records[0]["name"] == "Alice"
        assert records[0]["age"] == "30"  # CSV returns strings
        assert "_source_file" in records[0]
        assert "_row_number" in records[0]

    finally:
        Path(csv_path).unlink()


@pytest.mark.asyncio
async def test_csv_source_with_custom_delimiter():
    """Test CSV source with custom delimiter."""
    with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("id|name|age\n")
        f.write("1|Alice|30\n")
        csv_path = f.name

    try:
        source = CsvSource(delimiter="|")

        records = []
        async for record in source.extract(csv_path):
            records.append(record)

        assert len(records) == 1
        assert records[0]["name"] == "Alice"

    finally:
        Path(csv_path).unlink()


@pytest.mark.asyncio
async def test_csv_source_without_header():
    """Test CSV source without header."""
    with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("1,Alice,30\n")
        f.write("2,Bob,25\n")
        csv_path = f.name

    try:
        source = CsvSource(has_header=False)

        records = []
        async for record in source.extract(csv_path, fieldnames=["id", "name", "age"]):
            records.append(record)

        assert len(records) == 2
        assert records[0]["name"] == "Alice"

    finally:
        Path(csv_path).unlink()


@pytest.mark.asyncio
async def test_json_source_array():
    """Test JSON source with array of records."""
    data = [
        {"id": 1, "name": "Alice"},
        {"id": 2, "name": "Bob"},
    ]

    with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        json_path = f.name

    try:
        source = JsonSource()

        records = []
        async for record in source.extract(json_path):
            records.append(record)

        assert len(records) == 2
        assert records[0]["name"] == "Alice"
        assert "_source_file" in records[0]
        assert "_index" in records[0]

    finally:
        Path(json_path).unlink()


@pytest.mark.asyncio
async def test_json_source_object():
    """Test JSON source with single object."""
    data = {"id": 1, "name": "Alice", "nested": {"age": 30}}

    with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        json_path = f.name

    try:
        source = JsonSource()

        records = []
        async for record in source.extract(json_path):
            records.append(record)

        assert len(records) == 1
        assert records[0]["name"] == "Alice"
        assert records[0]["nested"]["age"] == 30

    finally:
        Path(json_path).unlink()


@pytest.mark.asyncio
async def test_jsonl_source():
    """Test JSON Lines source."""
    with NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        f.write('{"id": 1, "name": "Alice"}\n')
        f.write('{"id": 2, "name": "Bob"}\n')
        f.write("\n")  # Empty line should be skipped
        f.write('{"id": 3, "name": "Charlie"}\n')
        jsonl_path = f.name

    try:
        source = JsonLinesSource()

        records = []
        async for record in source.extract(jsonl_path):
            records.append(record)

        assert len(records) == 3
        assert records[0]["name"] == "Alice"
        assert "_line_number" in records[0]

    finally:
        Path(jsonl_path).unlink()


@pytest.mark.asyncio
async def test_source_file_not_found():
    """Test error when source file not found."""
    source = CsvSource()

    with pytest.raises(SourceError) as exc_info:
        async for _ in source.extract("nonexistent.csv"):
            pass

    assert "File not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_json_source_invalid_json():
    """Test error with invalid JSON."""
    with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("{ invalid json }")
        json_path = f.name

    try:
        source = JsonSource()

        with pytest.raises(SourceError) as exc_info:
            async for _ in source.extract(json_path):
                pass

        assert "Invalid JSON" in str(exc_info.value)

    finally:
        Path(json_path).unlink()
