"""Tests for pipeline execution."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from whiskey import Whiskey, Container

from whiskey_etl import etl_extension
from whiskey_etl.pipeline import (
    Pipeline,
    PipelineContext,
    PipelineManager,
    PipelineRegistry,
    PipelineResult,
    PipelineState,
    Stage,
    StageType,
)
from whiskey_etl.sources import MemorySource, SourceRegistry
from whiskey_etl.sinks import MemorySink, SinkRegistry
from whiskey_etl.transforms import TransformRegistry
from whiskey_etl.errors import PipelineError


@pytest.fixture
def app():
    """Create app with ETL extension."""
    app = Whiskey()
    app.use(etl_extension)
    return app


@pytest.fixture
def pipeline_manager(app):
    """Get pipeline manager from app."""
    return app.container[PipelineManager]


@pytest.mark.asyncio
async def test_pipeline_context():
    """Test pipeline context functionality."""
    container = Container()
    context = PipelineContext(
        pipeline_name="test_pipeline",
        run_id="test_run_123",
        container=container,
        config={"param": "value"},
    )
    
    # Check initial state
    assert context.pipeline_name == "test_pipeline"
    assert context.run_id == "test_run_123"
    assert context.config["param"] == "value"
    assert context.state == PipelineState.IDLE
    assert context.metrics["records_processed"] == 0
    
    # Test logging
    await context.log("Test message")  # Should not raise
    
    # Test checkpoint
    context.checkpoint("stage1", {"offset": 100})
    assert context.get_checkpoint("stage1") == {"offset": 100}
    assert context.get_checkpoint("stage2") is None


@pytest.mark.asyncio
async def test_simple_pipeline_execution(app):
    """Test executing a simple pipeline."""
    # Setup test data
    test_data = [
        {"id": 1, "name": "Alice"},
        {"id": 2, "name": "Bob"},
        {"id": 3, "name": "Charlie"},
    ]
    
    # Register source
    @app.source("memory")
    class TestMemorySource(MemorySource):
        def __init__(self):
            super().__init__(test_data)
    
    # Register sink
    memory_sink = MemorySink()
    app.container[MemorySink] = memory_sink
    
    @app.sink("memory")
    class TestMemorySink(MemorySink):
        pass
    
    # Register transform
    @app.transform
    async def add_processed(record):
        record["processed"] = True
        return record
    
    # Define pipeline
    @app.pipeline("test_pipeline")
    class TestPipeline(Pipeline):
        source = "memory"
        transforms = [add_processed]
        sink = "memory"
        batch_size = 2
    
    # Run pipeline
    async with app:
        result = await app.pipelines.run("test_pipeline")
    
    # Check result
    assert result.is_success
    assert result.pipeline_name == "test_pipeline"
    assert result.records_processed == 3
    assert result.records_failed == 0
    
    # Check sink data
    output_data = memory_sink.get_data()
    assert len(output_data) == 3
    for record in output_data:
        assert record["processed"] is True


@pytest.mark.asyncio
async def test_pipeline_with_error_handling(app):
    """Test pipeline error handling."""
    test_data = [
        {"id": 1, "value": 10},
        {"id": 2, "value": 0},  # Will cause error
        {"id": 3, "value": 20},
    ]
    
    @app.source("memory")
    class TestSource(MemorySource):
        def __init__(self):
            super().__init__(test_data)
    
    memory_sink = MemorySink()
    app.container[MemorySink] = memory_sink
    
    @app.sink("memory")
    class TestSink(MemorySink):
        pass
    
    # Transform that can fail
    @app.transform
    async def divide_by_value(record):
        result = 100 / record["value"]  # Will fail for value=0
        record["result"] = result
        return record
    
    errors_caught = []
    
    @app.pipeline("error_pipeline")
    class ErrorPipeline(Pipeline):
        source = "memory"
        transforms = [divide_by_value]
        sink = "memory"
        max_retries = 1  # Low retry count for testing
        
        async def on_error(self, error, record=None):
            errors_caught.append((error, record))
    
    # Run pipeline
    async with app:
        result = await app.pipelines.run("error_pipeline")
    
    # Check that we caught the error
    assert len(errors_caught) > 0
    assert result.records_failed == 1  # One record failed


@pytest.mark.asyncio
async def test_pipeline_lifecycle_hooks(app):
    """Test pipeline lifecycle hooks are called."""
    hooks_called = {
        "on_start": False,
        "on_complete": False,
        "on_batch_complete": [],
    }
    
    @app.source("memory")
    class TestSource(MemorySource):
        def __init__(self):
            super().__init__([{"i": i} for i in range(5)])
    
    @app.sink("memory")
    class TestSink(MemorySink):
        pass
    
    @app.pipeline("lifecycle_pipeline")
    class LifecyclePipeline(Pipeline):
        source = "memory"
        sink = "memory"
        batch_size = 2
        
        async def on_start(self, context):
            hooks_called["on_start"] = True
        
        async def on_complete(self, context):
            hooks_called["on_complete"] = True
        
        async def on_batch_complete(self, batch_num, records_processed):
            hooks_called["on_batch_complete"].append((batch_num, records_processed))
    
    # Run pipeline
    async with app:
        result = await app.pipelines.run("lifecycle_pipeline")
    
    # Check hooks were called
    assert hooks_called["on_start"] is True
    assert hooks_called["on_complete"] is True
    assert len(hooks_called["on_batch_complete"]) == 3  # 5 records in 2-record batches


@pytest.mark.asyncio
async def test_pipeline_not_found(app):
    """Test error when pipeline not found."""
    with pytest.raises(PipelineError) as exc_info:
        await app.pipelines.run("nonexistent_pipeline")
    
    assert "Pipeline 'nonexistent_pipeline' not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_custom_stages(app):
    """Test pipeline with custom stages."""
    @app.source("memory")
    class TestSource(MemorySource):
        def __init__(self):
            super().__init__([{"i": i} for i in range(3)])
    
    @app.sink("memory")
    class TestSink(MemorySink):
        pass
    
    @app.transform
    async def double_value(record):
        record["doubled"] = record["i"] * 2
        return record
    
    @app.pipeline("custom_stages")
    class CustomStagesPipeline(Pipeline):
        def get_stages(self):
            return [
                Stage("extract", StageType.EXTRACT, "memory"),
                Stage("double", StageType.TRANSFORM, double_value),
                Stage("load", StageType.LOAD, "memory"),
            ]
    
    # Run pipeline
    sink = MemorySink()
    app.container[MemorySink] = sink
    
    async with app:
        result = await app.pipelines.run("custom_stages")
    
    # Check output
    data = sink.get_data()
    assert len(data) == 3
    for i, record in enumerate(data):
        assert record["doubled"] == i * 2