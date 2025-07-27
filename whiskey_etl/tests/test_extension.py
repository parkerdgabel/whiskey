"""Tests for ETL extension configuration."""

import pytest
from whiskey import Whiskey

from whiskey_etl import etl_extension
from whiskey_etl.pipeline import Pipeline, PipelineManager, PipelineRegistry
from whiskey_etl.sources import SourceRegistry
from whiskey_etl.sinks import SinkRegistry
from whiskey_etl.transforms import TransformRegistry


@pytest.mark.asyncio
async def test_extension_setup():
    """Test that extension sets up all components correctly."""
    app = Whiskey()
    app.use(etl_extension)
    
    # Check registries are created
    assert app.container[PipelineRegistry] is not None
    assert app.container[SourceRegistry] is not None
    assert app.container[SinkRegistry] is not None
    assert app.container[TransformRegistry] is not None
    
    # Check manager is created
    assert app.container[PipelineManager] is not None
    assert hasattr(app, "pipelines")
    assert app.pipelines is app.container[PipelineManager]
    
    # Check decorators are added
    assert hasattr(app, "pipeline")
    assert hasattr(app, "source")
    assert hasattr(app, "sink")
    assert hasattr(app, "transform")
    assert hasattr(app, "scheduled_pipeline")


@pytest.mark.asyncio
async def test_pipeline_decorator():
    """Test pipeline decorator registration."""
    app = Whiskey()
    app.use(etl_extension)
    
    @app.pipeline("test_pipeline")
    class TestPipeline(Pipeline):
        source = "test_source"
        sink = "test_sink"
        batch_size = 100
    
    # Check pipeline is registered
    registry = app.container[PipelineRegistry]
    assert registry.get("test_pipeline") == TestPipeline
    
    # Check metadata
    metadata = registry.get_metadata("test_pipeline")
    assert metadata["batch_size"] == 100


@pytest.mark.asyncio
async def test_source_decorator():
    """Test source decorator registration."""
    app = Whiskey()
    app.use(etl_extension)
    
    @app.source("test_source")
    class TestSource:
        async def extract(self, **kwargs):
            yield {"test": "data"}
    
    # Check source is registered
    registry = app.container[SourceRegistry]
    assert registry.get("test_source") == TestSource


@pytest.mark.asyncio
async def test_sink_decorator():
    """Test sink decorator registration."""
    app = Whiskey()
    app.use(etl_extension)
    
    @app.sink("test_sink")
    class TestSink:
        async def load(self, records, **kwargs):
            pass
    
    # Check sink is registered
    registry = app.container[SinkRegistry]
    assert registry.get("test_sink") == TestSink


@pytest.mark.asyncio
async def test_transform_decorator():
    """Test transform decorator registration."""
    app = Whiskey()
    app.use(etl_extension)
    
    @app.transform
    async def test_transform(record):
        return record
    
    @app.transform(name="named_transform")
    async def another_transform(record):
        return record
    
    # Check transforms are registered
    registry = app.container[TransformRegistry]
    assert registry.get("test_transform") is test_transform
    assert registry.get("named_transform") is another_transform


@pytest.mark.asyncio
async def test_extension_with_config():
    """Test extension with custom configuration."""
    app = Whiskey()
    app.use(
        etl_extension,
        default_batch_size=500,
        enable_checkpointing=True,
        enable_monitoring=False,
        max_retries=5,
        retry_delay=2.0,
    )
    
    manager = app.container[PipelineManager]
    assert manager.default_batch_size == 500
    assert manager.enable_checkpointing is True
    assert manager.enable_monitoring is False
    assert manager.max_retries == 5
    assert manager.retry_delay == 2.0


@pytest.mark.asyncio
async def test_lifecycle_hooks():
    """Test that lifecycle hooks are registered."""
    app = Whiskey()
    app.use(etl_extension)
    
    # Check startup/shutdown hooks
    assert len(app._startup_callbacks) > 0
    assert len(app._shutdown_callbacks) > 0
    
    # Initialize and shutdown should work
    async with app:
        manager = app.container[PipelineManager]
        # Manager should be initialized
        pass