"""Basic tests that focus on core functionality without complex startup."""

import numpy as np
import pytest
from whiskey import Container

from whiskey_ml.core.dataset import ArrayDataLoader, DatasetConfig
from whiskey_ml.core.metrics import Accuracy, F1Score, Loss, MeanSquaredError, MetricCollection
from whiskey_ml.core.model import ModelConfig, ModelOutput
from whiskey_ml.core.trainer import TrainerConfig, TrainingResult
from whiskey_ml.integrations.base import ExtensionIntegration


class TestDatasetComponents:
    """Test dataset functionality without app startup."""

    def test_dataset_config(self):
        """Test dataset configuration."""
        config = DatasetConfig(batch_size=64, shuffle=True, num_workers=4, pin_memory=True)

        assert config.batch_size == 64
        assert config.shuffle is True
        assert config.num_workers == 4
        assert config.pin_memory is True

    async def test_array_dataloader(self):
        """Test array data loader functionality."""
        data = np.random.randn(100, 10)
        labels = np.random.randint(0, 2, 100)

        loader = ArrayDataLoader(data, labels, batch_size=16, shuffle=False)

        # Test basic properties
        assert len(loader) == 7  # ceil(100/16)
        assert loader.batch_size == 16
        assert loader.shuffle is False

        # Test iteration
        batches = []
        async for batch in loader:
            batches.append(batch)
            assert "data" in batch
            assert "labels" in batch
            assert "batch_size" in batch
            assert batch["batch_size"] <= 16

        assert len(batches) == len(loader)

        # Verify all data is covered
        total_samples = sum(batch["batch_size"] for batch in batches)
        assert total_samples == 100

    async def test_array_dataloader_shuffled(self):
        """Test array data loader with shuffling."""
        data = np.arange(50).reshape(50, 1).astype(float)
        labels = np.arange(50)

        loader = ArrayDataLoader(data, labels, batch_size=10, shuffle=True)

        # Get first batch
        first_batch = None
        async for batch in loader:
            first_batch = batch
            break

        # Data should be shuffled (very unlikely to be in order)
        batch_data = first_batch["data"].flatten()
        assert not np.array_equal(batch_data, np.arange(10))


class TestMetricsComponents:
    """Test metrics functionality."""

    def test_accuracy_metric(self):
        """Test accuracy metric computation."""
        metric = Accuracy()

        # Binary classification test
        predictions = np.array([0.8, 0.3, 0.9, 0.2])
        targets = np.array([1, 0, 1, 0])

        metric.update(predictions, targets)
        accuracy = metric.compute()
        assert accuracy == 1.0  # All predictions correct

        # Test reset
        metric.reset()
        assert metric.compute() == 0.0

        # Multi-class classification test
        predictions = np.array([[0.2, 0.8], [0.9, 0.1], [0.3, 0.7], [0.6, 0.4]])
        targets = np.array([1, 0, 1, 0])

        metric.update(predictions, targets)
        accuracy = metric.compute()
        assert accuracy == 1.0  # All predictions correct

    def test_loss_metric(self):
        """Test loss metric computation."""
        metric = Loss()

        # Add some losses
        metric.update(0.5)
        metric.update(0.3)
        metric.update(0.7)

        # Should compute average
        avg_loss = metric.compute()
        assert avg_loss == pytest.approx(0.5, rel=1e-3)

        # Test reset
        metric.reset()
        assert metric.compute() == 0.0

    def test_f1_score_metric(self):
        """Test F1 score metric computation."""
        metric = F1Score()

        # Perfect predictions
        predictions = np.array([0.9, 0.1, 0.8, 0.2])
        targets = np.array([1, 0, 1, 0])

        metric.update(predictions, targets)
        f1 = metric.compute()
        assert f1 == pytest.approx(1.0, rel=1e-6)  # Perfect F1 score

        # Test with some incorrect predictions
        metric.reset()
        predictions = np.array([0.9, 0.9, 0.8, 0.2])  # Second prediction wrong
        metric.update(predictions, targets)
        f1 = metric.compute()
        assert 0 < f1 < 1  # Should be between 0 and 1

    def test_mse_metric(self):
        """Test mean squared error metric computation."""
        metric = MeanSquaredError()

        # Test with perfect predictions
        predictions = np.array([1.0, 2.0, 3.0])
        targets = np.array([1.0, 2.0, 3.0])

        metric.update(predictions, targets)
        mse = metric.compute()
        assert mse == 0.0

        # Test with some error
        metric.reset()
        predictions = np.array([1.0, 2.0, 3.0])
        targets = np.array([1.1, 2.1, 3.1])

        metric.update(predictions, targets)
        mse = metric.compute()
        assert mse == pytest.approx(0.01, rel=1e-3)  # (0.1^2 + 0.1^2 + 0.1^2) / 3

    def test_metric_collection(self):
        """Test metric collection functionality."""
        metrics = MetricCollection([Accuracy(), Loss()])

        # Test update
        predictions = np.array([[0.2, 0.8], [0.9, 0.1]])
        targets = np.array([1, 0])
        loss = 0.25

        results = metrics.update(predictions, targets, loss)

        assert "accuracy" in results
        assert "loss" in results
        assert results["accuracy"] == 1.0  # Perfect predictions
        assert results["loss"] == 0.25

        # Test compute
        computed = metrics.compute()
        assert "accuracy" in computed
        assert "loss" in computed

        # Test reset
        metrics.reset()
        computed_after_reset = metrics.compute()
        assert computed_after_reset["accuracy"] == 0.0
        assert computed_after_reset["loss"] == 0.0

    def test_metric_collection_from_names(self):
        """Test creating metric collection from names."""
        collection = MetricCollection.from_names(["accuracy", "loss", "f1", "mse"])

        assert len(collection.metrics) == 4
        assert any(isinstance(m, Accuracy) for m in collection.metrics.values())
        assert any(isinstance(m, Loss) for m in collection.metrics.values())
        assert any(isinstance(m, F1Score) for m in collection.metrics.values())
        assert any(isinstance(m, MeanSquaredError) for m in collection.metrics.values())


class TestModelComponents:
    """Test model configuration and output."""

    def test_model_config(self):
        """Test model configuration."""
        config = ModelConfig(
            learning_rate=0.01, weight_decay=0.001, device="cuda", compile_model=True
        )

        assert config.learning_rate == 0.01
        assert config.weight_decay == 0.001
        assert config.device == "cuda"
        assert config.compile_model is True

    def test_model_output(self):
        """Test model output structure."""
        predictions = np.array([[0.2, 0.8], [0.9, 0.1]])
        loss = 0.5
        metrics = {"accuracy": 0.85}

        output = ModelOutput(predictions=predictions, loss=loss, metrics=metrics)

        assert np.array_equal(output.predictions, predictions)
        assert output.loss == 0.5
        assert output.metrics["accuracy"] == 0.85

    def test_model_output_optional_fields(self):
        """Test model output with optional fields."""
        predictions = np.array([1, 0, 1])

        output = ModelOutput(predictions=predictions)

        assert np.array_equal(output.predictions, predictions)
        assert output.loss is None
        assert output.metrics is None


class TestTrainerComponents:
    """Test trainer configuration and results."""

    def test_trainer_config(self):
        """Test trainer configuration."""
        config = TrainerConfig(
            epochs=10,
            early_stopping_patience=3,
            early_stopping_threshold=0.01,
            checkpoint_dir="./checkpoints",
            save_checkpoint=True,
            device="cuda",
        )

        assert config.epochs == 10
        assert config.early_stopping_patience == 3
        assert config.early_stopping_threshold == 0.01
        assert config.checkpoint_dir == "./checkpoints"
        assert config.save_checkpoint is True
        assert config.device == "cuda"

    def test_training_result(self):
        """Test training result structure."""
        from whiskey_ml.core.trainer import TrainerState

        result = TrainingResult(
            trainer_state=TrainerState.COMPLETED,
            epochs_trained=5,
            steps_trained=100,
            training_time=120.5,
            train_metrics={"loss": [0.5, 0.3], "accuracy": [0.8, 0.9]},
            val_metrics={"val_loss": [0.4, 0.2]},
            test_metrics={"test_loss": 0.1, "test_accuracy": 0.9},
            best_epoch=1,
            best_metric=0.2,
        )

        assert result.trainer_state == TrainerState.COMPLETED
        assert result.epochs_trained == 5
        assert result.steps_trained == 100
        assert result.training_time == 120.5
        assert result.train_metrics["loss"] == [0.5, 0.3]
        assert result.val_metrics["val_loss"] == [0.4, 0.2]
        assert result.test_metrics["test_accuracy"] == 0.9
        assert result.best_epoch == 1
        assert result.best_metric == 0.2


class TestExtensionIntegration:
    """Test extension integration without app startup."""

    def test_extension_integration_creation(self):
        """Test creating extension integration."""
        container = Container()
        integration = ExtensionIntegration(container)

        assert integration.container is container
        assert isinstance(integration.available_extensions, dict)

    def test_extension_context_creation(self):
        """Test creating ML context."""
        container = Container()
        integration = ExtensionIntegration(container)

        context = integration.create_context()

        assert context.container is container
        assert context.integrations == integration.available_extensions

    def test_has_extension_method(self):
        """Test has_extension method."""
        container = Container()
        integration = ExtensionIntegration(container)
        context = integration.create_context()

        # Test with non-existent extensions
        assert context.has_extension("nonexistent") is False
        assert context.has_extension("totally_fake_extension") is False

        # ETL and SQL extensions might be available in workspace
        # Just test that the method returns a boolean
        etl_available = context.has_extension("etl")
        sql_available = context.has_extension("sql")
        assert isinstance(etl_available, bool)
        assert isinstance(sql_available, bool)

    def test_log_metrics_method(self):
        """Test log_metrics method."""
        container = Container()
        integration = ExtensionIntegration(container)
        context = integration.create_context()

        # Should not raise any errors
        asyncio = pytest.importorskip("asyncio")

        async def test_logging():
            await context.log_metrics({"loss": 0.5, "accuracy": 0.8})
            await context.log_metrics({"val_loss": 0.4}, prefix="validation")

        # Run the test
        import asyncio

        asyncio.run(test_logging())


@pytest.mark.asyncio
async def test_basic_component_integration():
    """Test that basic components work together."""
    # Create data
    data = np.random.randn(32, 10)
    labels = np.random.randint(0, 2, 32)

    # Create data loader
    loader = ArrayDataLoader(data, labels, batch_size=8)

    # Create metrics
    metrics = MetricCollection([Accuracy(), Loss()])

    # Test processing batches
    total_accuracy = 0
    total_loss = 0
    batch_count = 0

    async for batch in loader:
        # Mock predictions (random for testing)
        batch_size = batch["batch_size"]
        mock_predictions = np.random.rand(batch_size, 2)

        # Update metrics
        results = metrics.update(
            mock_predictions,
            batch["labels"],
            np.random.rand(),  # Mock loss
        )

        total_accuracy += results["accuracy"]
        total_loss += results["loss"]
        batch_count += 1

    # Verify we processed all batches
    assert batch_count == len(loader)

    # Compute final metrics
    final_metrics = metrics.compute()
    assert "accuracy" in final_metrics
    assert "loss" in final_metrics
