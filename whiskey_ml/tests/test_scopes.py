"""Tests for ML scope-aware components."""

import numpy as np
import pytest
from whiskey import Whiskey
from whiskey.core.errors import ScopeError

from whiskey_ml import ml_extension
from whiskey_ml.components.scoped_components import (
    EpochMetricsCollector,
    ExperimentLogger,
    ModelCheckpointer,
    ValidationRunner,
    register_all_scoped_components,
)


class TestScopedComponents:
    """Test scope-aware ML components."""

    @pytest.fixture
    async def app(self):
        """Create test app with ML extension and scoped components."""
        app = Whiskey()
        app.use(ml_extension)
        register_all_scoped_components(app)
        return app

    async def test_experiment_logger_scoped(self, app):
        """Test ExperimentLogger in experiment scope."""
        async with app:
            # Use experiment scope
            async with app.container.scope("experiment"):
                # Resolve experiment logger
                logger1 = await app.container.resolve(ExperimentLogger)
                logger2 = await app.container.resolve(ExperimentLogger)

                # Should be the same instance within scope
                assert logger1 is logger2

                # Test logging functionality
                await logger1.log_experiment_start({"test": True})
                assert logger1.experiment_metadata["config"]["test"] is True

                # Test run result logging
                await logger1.log_run_result("test_pipeline", {"accuracy": 0.85})
                assert len(logger1.run_history) == 1
                assert logger1.run_history[0]["pipeline"] == "test_pipeline"

    async def test_model_checkpointer_scoped(self, app, tmp_path):
        """Test ModelCheckpointer in training scope."""
        async with app:
            # Use training scope
            async with app.container.scope("training"):
                # Resolve checkpointer
                checkpointer1 = await app.container.resolve(ModelCheckpointer)
                checkpointer2 = await app.container.resolve(ModelCheckpointer)

                # Should be the same instance within scope
                assert checkpointer1 is checkpointer2

                # Set checkpoint directory
                checkpointer1.checkpoint_dir = tmp_path

                # Test checkpoint saving
                mock_model = MockModel()
                checkpoint_path = await checkpointer1.save_checkpoint(
                    mock_model, epoch=1, metrics={"loss": 0.5}
                )

                assert checkpoint_path.endswith("checkpoint_epoch_0001.ckpt")
                assert checkpointer1.checkpoint_count == 1
                assert checkpointer1.best_metric == 0.5

    async def test_epoch_metrics_collector_scoped(self, app):
        """Test EpochMetricsCollector in epoch scope."""
        async with app:
            # Use epoch scope
            async with app.container.scope("epoch"):
                # Resolve metrics collector
                collector1 = await app.container.resolve(EpochMetricsCollector)
                collector2 = await app.container.resolve(EpochMetricsCollector)

                # Should be the same instance within scope
                assert collector1 is collector2

                # Test metrics collection
                collector1.collect_batch_metrics(0, {"loss": 0.6, "accuracy": 0.8})
                collector1.collect_batch_metrics(1, {"loss": 0.4, "accuracy": 0.9})

                # Test epoch summary
                summary = collector1.get_epoch_summary()
                assert "avg_loss" in summary
                assert "avg_accuracy" in summary
                assert summary["avg_loss"] == 0.5  # (0.6 + 0.4) / 2
                assert summary["avg_accuracy"] == 0.85  # (0.8 + 0.9) / 2
                assert summary["batches_processed"] == 2

    async def test_validation_runner_scoped(self, app):
        """Test ValidationRunner in evaluation scope."""
        async with app:
            # Use evaluation scope
            async with app.container.scope("evaluation"):
                # Resolve validation runner
                runner1 = await app.container.resolve(ValidationRunner)
                runner2 = await app.container.resolve(ValidationRunner)

                # Should be the same instance within scope
                assert runner1 is runner2

                # Test validation
                mock_model = MockModel()
                mock_loader = MockDataLoader()

                results = await runner1.run_validation(mock_model, mock_loader)

                assert "val_loss" in results
                assert "val_accuracy" in results
                assert "samples_processed" in results
                assert results["samples_processed"] > 0

    async def test_scope_isolation(self, app):
        """Test that components are isolated between different scopes."""
        async with app:
            logger1 = None
            logger2 = None

            # First experiment scope
            async with app.container.scope("experiment"):
                logger1 = await app.container.resolve(ExperimentLogger)
                logger1.experiment_metadata["test"] = "scope1"

            # Second experiment scope (should be different instance)
            async with app.container.scope("experiment"):
                logger2 = await app.container.resolve(ExperimentLogger)
                logger2.experiment_metadata["test"] = "scope2"

            # Should be different instances
            assert logger1 is not logger2
            assert logger1.experiment_metadata["test"] == "scope1"
            assert logger2.experiment_metadata["test"] == "scope2"

    async def test_nested_scopes(self, app):
        """Test nested scope behavior."""
        async with app:
            # Nested scopes: experiment -> training -> epoch
            async with app.container.scope("experiment"):
                exp_logger = await app.container.resolve(ExperimentLogger)

                async with app.container.scope("training"):
                    checkpointer = await app.container.resolve(ModelCheckpointer)

                    async with app.container.scope("epoch"):
                        collector = await app.container.resolve(EpochMetricsCollector)

                        # All components should be accessible
                        assert exp_logger is not None
                        assert checkpointer is not None
                        assert collector is not None

                        # Experiment logger should still be the same instance
                        exp_logger2 = await app.container.resolve(ExperimentLogger)
                        assert exp_logger is exp_logger2


class TestScopeRegistration:
    """Test scope registration utilities."""

    async def test_register_all_scoped_components(self):
        """Test registering all scoped components."""
        app = Whiskey()
        app.use(ml_extension)

        # Register all scoped components
        register_all_scoped_components(app)

        async with app:
            # All components should be resolvable in their respective scopes
            async with app.container.scope("experiment"):
                logger = await app.container.resolve(ExperimentLogger)
                assert logger is not None

            async with app.container.scope("training"):
                checkpointer = await app.container.resolve(ModelCheckpointer)
                assert checkpointer is not None

            async with app.container.scope("epoch"):
                collector = await app.container.resolve(EpochMetricsCollector)
                assert collector is not None

            async with app.container.scope("evaluation"):
                runner = await app.container.resolve(ValidationRunner)
                assert runner is not None


# Mock classes for testing
class MockModel:
    """Mock model for testing."""

    async def save(self, path):
        """Mock save method."""
        with open(path, "w") as f:
            f.write("mock model")


class MockDataLoader:
    """Mock data loader for testing."""

    def __iter__(self):
        return iter(
            [
                {"data": np.random.randn(32, 10), "labels": np.random.randint(0, 2, 32)}
                for _ in range(5)
            ]
        )


@pytest.mark.asyncio
async def test_scope_component_lifecycle():
    """Test component lifecycle management in scopes."""
    app = Whiskey()
    app.use(ml_extension)
    register_all_scoped_components(app)

    async with app:
        # Test that components are properly cleaned up when scopes exit
        async with app.container.scope("experiment"):
            logger = await app.container.resolve(ExperimentLogger)
            logger.experiment_metadata["test"] = "cleanup_test"

        # After scope exit, new resolution should give new instance
        async with app.container.scope("experiment"):
            new_logger = await app.container.resolve(ExperimentLogger)
            assert (
                "test" not in new_logger.experiment_metadata
                or new_logger.experiment_metadata.get("test") != "cleanup_test"
            )


@pytest.mark.asyncio
async def test_scope_error_handling():
    """Test error handling in scoped components."""
    app = Whiskey()
    app.use(ml_extension)
    register_all_scoped_components(app)

    async with app:
        # Test accessing scoped component outside of scope
        with pytest.raises(ScopeError):
            # This should fail since we're not in the right scope
            await app.container.resolve(ExperimentLogger)
