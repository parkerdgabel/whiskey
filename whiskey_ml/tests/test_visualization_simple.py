"""Simple tests for ML visualization components."""

import pytest
from unittest.mock import Mock, AsyncMock
from whiskey import Whiskey
from whiskey_ml import ml_extension


class TestVisualizationImports:
    """Test that visualization components can be imported."""
    
    def test_metrics_tracker_import(self):
        """Test importing MetricsTracker."""
        try:
            from whiskey_ml.visualization.metrics_tracker import MetricsTracker
            tracker = MetricsTracker()
            assert tracker is not None
            assert hasattr(tracker, 'handlers')
        except ImportError:
            pytest.skip("Visualization module not available")
    
    def test_console_handler_import(self):
        """Test importing ConsoleMetricsHandler."""
        try:
            from whiskey_ml.visualization.metrics_tracker import ConsoleMetricsHandler
            handler = ConsoleMetricsHandler()
            assert handler is not None
        except ImportError:
            pytest.skip("Visualization module not available")
    
    def test_metric_snapshot_import(self):
        """Test importing MetricSnapshot."""
        try:
            from whiskey_ml.visualization.metrics_tracker import MetricSnapshot
            snapshot = MetricSnapshot(
                pipeline="test",
                epoch=1,
                phase="training",
                metrics={"loss": 0.5},
                timestamp=123.456
            )
            assert snapshot.pipeline == "test"
            assert snapshot.epoch == 1
            assert snapshot.phase == "training"
        except ImportError:
            pytest.skip("Visualization module not available")


class TestVisualizationBasic:
    """Basic tests for visualization functionality."""
    
    def test_metrics_tracker_creation(self):
        """Test creating a metrics tracker."""
        try:
            from whiskey_ml.visualization.metrics_tracker import MetricsTracker
            tracker = MetricsTracker()
            assert hasattr(tracker, 'handlers')
        except ImportError:
            pytest.skip("Visualization module not available")
    
    def test_console_handler_creation(self):
        """Test creating console handler.""" 
        try:
            from whiskey_ml.visualization.metrics_tracker import ConsoleMetricsHandler
            handler = ConsoleMetricsHandler()
            assert handler is not None
        except ImportError:
            pytest.skip("Visualization module not available")


class TestVisualizationIntegration:
    """Test integration with ML extension."""
    
    @pytest.fixture
    async def app(self):
        """Create test app with ML extension."""
        app = Whiskey()
        app.use(ml_extension)
        return app
    
    async def test_visualization_with_ml_extension(self, app):
        """Test that visualization works with ML extension."""
        try:
            from whiskey_ml.visualization.metrics_tracker import MetricsTracker
            
            async with app:
                # Should be able to create tracker
                tracker = MetricsTracker()
                assert tracker is not None
                
        except ImportError:
            pytest.skip("Visualization module not available")


@pytest.mark.asyncio
async def test_optional_visualization_dependencies():
    """Test handling of optional visualization dependencies."""
    # Test that missing dependencies don't break the extension
    app = Whiskey()
    app.use(ml_extension)
    
    async with app:
        # Extension should work even if visualization deps are missing
        assert hasattr(app, 'ml')
        assert app.ml is not None