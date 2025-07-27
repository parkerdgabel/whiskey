"""Tests for data sinks."""

import json
import csv
import pytest
from pathlib import Path
from tempfile import NamedTemporaryFile

from whiskey_etl.sinks import (
    CsvSink,
    JsonSink,
    JsonLinesSink,
    MemorySink,
    ConsoleSink,
    SinkRegistry,
)


@pytest.mark.asyncio
async def test_sink_registry():
    """Test sink registry functionality."""
    registry = SinkRegistry()
    
    # Register sink
    registry.register("test", MemorySink)
    
    # Get sink
    assert registry.get("test") == MemorySink
    assert registry.get("nonexistent") is None
    
    # List sinks
    registry.register("another", CsvSink)
    sinks = registry.list_sinks()
    assert "test" in sinks
    assert "another" in sinks


@pytest.mark.asyncio
async def test_memory_sink():
    """Test memory sink."""
    sink = MemorySink()
    
    # Load data
    data1 = [{"id": 1}, {"id": 2}]
    await sink.load(data1)
    
    # Load more data
    data2 = [{"id": 3}]
    await sink.load(data2)
    
    # Check accumulated data
    all_data = sink.get_data()
    assert len(all_data) == 3
    assert all_data[0]["id"] == 1
    assert all_data[2]["id"] == 3
    
    # Clear data
    sink.clear()
    assert len(sink.get_data()) == 0


@pytest.mark.asyncio
async def test_csv_sink():
    """Test CSV sink."""
    with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        csv_path = f.name
    
    try:
        sink = CsvSink()
        
        # Write records
        records = [
            {"id": 1, "name": "Alice", "age": 30},
            {"id": 2, "name": "Bob", "age": 25},
        ]
        await sink.load(records, csv_path)
        
        # Read back and verify
        with open(csv_path, "r") as f:
            reader = csv.DictReader(f)
            loaded = list(reader)
        
        assert len(loaded) == 2
        assert loaded[0]["name"] == "Alice"
        assert loaded[0]["age"] == "30"  # CSV stores as strings
        
    finally:
        Path(csv_path).unlink()


@pytest.mark.asyncio
async def test_csv_sink_append_mode():
    """Test CSV sink in append mode."""
    with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        csv_path = f.name
    
    try:
        sink = CsvSink(mode="a")
        
        # Write first batch
        await sink.load([{"id": 1, "name": "Alice"}], csv_path)
        
        # Write second batch
        await sink.load([{"id": 2, "name": "Bob"}], csv_path)
        
        # Read back and verify
        with open(csv_path, "r") as f:
            reader = csv.DictReader(f)
            loaded = list(reader)
        
        assert len(loaded) == 2
        assert loaded[0]["name"] == "Alice"
        assert loaded[1]["name"] == "Bob"
        
    finally:
        Path(csv_path).unlink()


@pytest.mark.asyncio
async def test_csv_sink_custom_delimiter():
    """Test CSV sink with custom delimiter."""
    with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        csv_path = f.name
    
    try:
        sink = CsvSink(delimiter="|")
        
        records = [{"id": 1, "name": "Alice"}]
        await sink.load(records, csv_path)
        
        # Verify delimiter
        content = Path(csv_path).read_text()
        assert "|" in content
        assert "," not in content
        
    finally:
        Path(csv_path).unlink()


@pytest.mark.asyncio
async def test_json_sink():
    """Test JSON sink."""
    with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json_path = f.name
    
    try:
        sink = JsonSink(indent=2)
        
        # Write records
        records = [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
        ]
        await sink.load(records, json_path)
        
        # Read back and verify
        with open(json_path, "r") as f:
            loaded = json.load(f)
        
        assert len(loaded) == 2
        assert loaded[0]["name"] == "Alice"
        
        # Check formatting
        content = Path(json_path).read_text()
        assert "  " in content  # Indented
        
    finally:
        Path(json_path).unlink()


@pytest.mark.asyncio
async def test_json_sink_append_mode():
    """Test JSON sink in append mode."""
    with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json_path = f.name
    
    try:
        sink = JsonSink(mode="a")
        
        # Write first batch
        await sink.load([{"id": 1}], json_path)
        
        # Write second batch
        await sink.load([{"id": 2}], json_path)
        
        # Read back and verify
        with open(json_path, "r") as f:
            loaded = json.load(f)
        
        assert len(loaded) == 2
        assert loaded[0]["id"] == 1
        assert loaded[1]["id"] == 2
        
    finally:
        Path(json_path).unlink()


@pytest.mark.asyncio
async def test_jsonl_sink():
    """Test JSON Lines sink."""
    with NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        jsonl_path = f.name
    
    try:
        sink = JsonLinesSink()
        
        # Write records
        records = [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
        ]
        await sink.load(records, jsonl_path)
        
        # Write more records (append mode by default)
        await sink.load([{"id": 3, "name": "Charlie"}], jsonl_path)
        
        # Read back and verify
        loaded = []
        with open(jsonl_path, "r") as f:
            for line in f:
                loaded.append(json.loads(line))
        
        assert len(loaded) == 3
        assert loaded[0]["name"] == "Alice"
        assert loaded[2]["name"] == "Charlie"
        
    finally:
        Path(jsonl_path).unlink()


@pytest.mark.asyncio
async def test_console_sink(capsys):
    """Test console sink."""
    sink = ConsoleSink(format="json", prefix="DEBUG")
    
    records = [{"id": 1, "name": "Alice"}]
    await sink.load(records)
    
    # Check output
    captured = capsys.readouterr()
    assert "DEBUG" in captured.out
    assert "Alice" in captured.out
    assert "{" in captured.out  # JSON format


@pytest.mark.asyncio
async def test_sink_empty_records():
    """Test sinks handle empty records gracefully."""
    # CSV
    csv_sink = CsvSink()
    with NamedTemporaryFile(suffix=".csv", delete=False) as f:
        await csv_sink.load([], f.name)
        assert Path(f.name).stat().st_size == 0
        Path(f.name).unlink()
    
    # JSON
    json_sink = JsonSink()
    with NamedTemporaryFile(suffix=".json", delete=False) as f:
        await json_sink.load([], f.name)
        Path(f.name).unlink()
    
    # Memory
    memory_sink = MemorySink()
    await memory_sink.load([])
    assert len(memory_sink.get_data()) == 0