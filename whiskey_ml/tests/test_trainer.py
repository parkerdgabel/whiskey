"""Tests for ML trainer functionality."""

import numpy as np
import pytest

from whiskey_ml.core.dataset import ArrayDataLoader
from whiskey_ml.core.metrics import Accuracy, Loss, MetricCollection
from whiskey_ml.core.model import Model, ModelOutput
from whiskey_ml.core.trainer import Trainer, TrainerConfig, TrainingResult


class MockModel(Model):
    """Mock model for testing."""

    def __init__(self):
        self.training_steps = 0
        self.params = {"weight": np.random.randn(10, 2)}

    async def forward(self, inputs):
        self.training_steps += 1
        batch_size = inputs["batch_size"]

        # Mock predictions
        predictions = np.random.randn(batch_size, 2)
        loss = 0.5 - (self.training_steps * 0.01)  # Decreasing loss

        # Mock accuracy based on predictions
        if "labels" in inputs:
            pred_classes = np.argmax(predictions, axis=1)
            accuracy = np.mean(pred_classes == inputs["labels"])
            return ModelOutput(
                predictions=predictions,
                loss=max(loss, 0.1),  # Minimum loss
                metrics={"accuracy": accuracy},
            )

        return ModelOutput(predictions=predictions, loss=max(loss, 0.1))

    def get_parameters(self):
        return self.params.copy()

    def set_parameters(self, params):
        self.params = params

    async def save(self, path):
        np.savez(path, **self.params)

    async def load(self, path):
        data = np.load(path)
        self.params = {k: data[k] for k in data.files}


class TestTrainer:
    """Test trainer functionality."""

    @pytest.fixture
    def model(self):
        """Create test model."""
        return MockModel()

    @pytest.fixture
    def metrics(self):
        """Create test metrics."""
        return MetricCollection([Accuracy(), Loss()])

    @pytest.fixture
    def config(self):
        """Create test trainer config."""
        return TrainerConfig(
            epochs=3,
            learning_rate=0.01,
            batch_size=16,
            validation_frequency=1,
            checkpoint_frequency=2,
            early_stopping_patience=5,
            early_stopping_threshold=0.001,
        )

    @pytest.fixture
    def data_loaders(self):
        """Create test data loaders."""
        # Training data
        train_data = np.random.randn(100, 10)
        train_labels = np.random.randint(0, 2, 100)
        train_loader = ArrayDataLoader(train_data, train_labels, batch_size=16)

        # Validation data
        val_data = np.random.randn(50, 10)
        val_labels = np.random.randint(0, 2, 50)
        val_loader = ArrayDataLoader(val_data, val_labels, batch_size=16)

        # Test data
        test_data = np.random.randn(30, 10)
        test_labels = np.random.randint(0, 2, 30)
        test_loader = ArrayDataLoader(test_data, test_labels, batch_size=16)

        return train_loader, val_loader, test_loader

    def test_trainer_config(self, config):
        """Test trainer configuration."""
        assert config.epochs == 3
        assert config.learning_rate == 0.01
        assert config.batch_size == 16
        assert config.validation_frequency == 1
        assert config.checkpoint_frequency == 2
        assert config.early_stopping_patience == 5
        assert config.early_stopping_threshold == 0.001

    def test_trainer_creation(self, model, config, metrics):
        """Test trainer creation."""
        trainer = Trainer(model, config, metrics)

        assert trainer.model is model
        assert trainer.config is config
        assert trainer.metrics is metrics
        assert trainer.training_history == []
        assert trainer.validation_history == []
        assert trainer.best_metric is None
        assert trainer.patience_counter == 0

    async def test_train_step(self, model, config, metrics):
        """Test training step."""
        trainer = Trainer(model, config, metrics)

        # Create a mock batch
        batch = {
            "data": np.random.randn(16, 10),
            "labels": np.random.randint(0, 2, 16),
            "batch_size": 16,
        }

        # Run training step
        step_metrics = await trainer.train_step(batch, step=0)

        assert "loss" in step_metrics
        assert "accuracy" in step_metrics
        assert isinstance(step_metrics["loss"], int | float)
        assert isinstance(step_metrics["accuracy"], int | float)

    async def test_validation_step(self, model, config, metrics):
        """Test validation step."""
        trainer = Trainer(model, config, metrics)

        # Create a mock batch
        batch = {
            "data": np.random.randn(16, 10),
            "labels": np.random.randint(0, 2, 16),
            "batch_size": 16,
        }

        # Run validation step
        step_metrics = await trainer.validation_step(batch, step=0)

        assert "loss" in step_metrics
        assert "accuracy" in step_metrics
        assert isinstance(step_metrics["loss"], int | float)
        assert isinstance(step_metrics["accuracy"], int | float)

    async def test_train_epoch(self, model, config, metrics, data_loaders):
        """Test training epoch."""
        trainer = Trainer(model, config, metrics)
        train_loader, val_loader, test_loader = data_loaders

        # Run training epoch
        epoch_metrics = await trainer.train_epoch(train_loader, epoch=0)

        assert "avg_loss" in epoch_metrics
        assert "avg_accuracy" in epoch_metrics
        assert epoch_metrics["samples_processed"] > 0
        assert epoch_metrics["batches_processed"] > 0

    async def test_validate_epoch(self, model, config, metrics, data_loaders):
        """Test validation epoch."""
        trainer = Trainer(model, config, metrics)
        train_loader, val_loader, test_loader = data_loaders

        # Run validation epoch
        val_metrics = await trainer.validate_epoch(val_loader, epoch=0)

        assert "avg_loss" in val_metrics
        assert "avg_accuracy" in val_metrics
        assert val_metrics["samples_processed"] > 0
        assert val_metrics["batches_processed"] > 0

    async def test_full_training(self, model, config, metrics, data_loaders):
        """Test full training process."""
        trainer = Trainer(model, config, metrics)
        train_loader, val_loader, test_loader = data_loaders

        # Set up callbacks to track calls
        epoch_calls = []

        async def mock_epoch_callback(epoch, epoch_metrics):
            epoch_calls.append((epoch, epoch_metrics))

        trainer.on_epoch_end = mock_epoch_callback

        # Run training
        result = await trainer.train(train_loader, val_loader, test_loader)

        # Check result
        assert isinstance(result, TrainingResult)
        assert result.epochs_trained == config.epochs
        assert result.training_time > 0
        assert len(result.training_history) == config.epochs
        assert len(result.validation_history) == config.epochs

        # Check callbacks were called
        assert len(epoch_calls) == config.epochs

        # Check best metrics
        assert result.best_metrics is not None
        assert "loss" in result.best_metrics

    async def test_early_stopping(self, model, metrics, data_loaders):
        """Test early stopping functionality."""
        # Config with aggressive early stopping
        config = TrainerConfig(
            epochs=10,
            early_stopping_patience=2,
            early_stopping_threshold=0.001,
        )

        trainer = Trainer(model, config, metrics)
        train_loader, val_loader, test_loader = data_loaders

        # Mock the model to have non-improving loss
        original_forward = model.forward

        async def mock_forward_non_improving(inputs):
            result = await original_forward(inputs)
            # Return constant loss (no improvement)
            result.loss = 0.5
            return result

        model.forward = mock_forward_non_improving

        # Run training (should stop early)
        result = await trainer.train(train_loader, val_loader, test_loader)

        # Should stop before max epochs due to early stopping
        assert result.epochs_trained < config.epochs
        assert result.early_stopped is True

    async def test_checkpointing(self, model, config, metrics, data_loaders, tmp_path):
        """Test model checkpointing."""
        config.checkpoint_dir = str(tmp_path)
        config.save_best_model = True

        trainer = Trainer(model, config, metrics)
        train_loader, val_loader, test_loader = data_loaders

        # Run training
        await trainer.train(train_loader, val_loader, test_loader)

        # Check that checkpoints were created
        checkpoints = list(tmp_path.glob("checkpoint_*.npz"))
        assert len(checkpoints) > 0

        # Check best model was saved
        best_model_path = tmp_path / "best_model.npz"
        assert best_model_path.exists()

    def test_should_validate(self, model, config, metrics):
        """Test validation frequency logic."""
        trainer = Trainer(model, config, metrics)

        # Should validate on epoch 0 and every validation_frequency epochs
        assert trainer.should_validate(0) is True
        assert trainer.should_validate(1) is True
        assert trainer.should_validate(2) is True

        # Test with different frequency
        config.validation_frequency = 2
        trainer = Trainer(model, config, metrics)

        assert trainer.should_validate(0) is True
        assert trainer.should_validate(1) is False
        assert trainer.should_validate(2) is True
        assert trainer.should_validate(3) is False

    def test_should_checkpoint(self, model, config, metrics):
        """Test checkpoint frequency logic."""
        trainer = Trainer(model, config, metrics)

        # Should checkpoint every checkpoint_frequency epochs
        assert trainer.should_checkpoint(0) is False
        assert trainer.should_checkpoint(1) is False
        assert trainer.should_checkpoint(2) is True
        assert trainer.should_checkpoint(3) is False
        assert trainer.should_checkpoint(4) is True

    def test_check_early_stopping_improvement(self, model, config, metrics):
        """Test early stopping improvement detection."""
        trainer = Trainer(model, config, metrics)

        # First validation (no previous best)
        improved = trainer.check_early_stopping(0.5, 0)
        assert improved is True
        assert trainer.best_metric == 0.5
        assert trainer.patience_counter == 0

        # Better metric (improvement)
        improved = trainer.check_early_stopping(0.3, 1)
        assert improved is True
        assert trainer.best_metric == 0.3
        assert trainer.patience_counter == 0

        # Worse metric (no improvement)
        improved = trainer.check_early_stopping(0.4, 2)
        assert improved is False
        assert trainer.best_metric == 0.3
        assert trainer.patience_counter == 1

    def test_check_early_stopping_patience(self, model, config, metrics):
        """Test early stopping patience."""
        trainer = Trainer(model, config, metrics)

        # Set up initial best metric
        trainer.best_metric = 0.3
        trainer.patience_counter = config.early_stopping_patience - 1

        # One more non-improvement should trigger early stopping
        improved = trainer.check_early_stopping(0.4, 5)
        assert improved is False
        assert trainer.patience_counter == config.early_stopping_patience

        # Check if should stop
        should_stop = trainer.should_early_stop()
        assert should_stop is True


class TestTrainingResult:
    """Test training result data structure."""

    def test_training_result_creation(self):
        """Test creating training result."""
        result = TrainingResult(
            epochs_trained=5,
            training_time=120.5,
            training_history=[{"loss": 0.5}, {"loss": 0.3}],
            validation_history=[{"val_loss": 0.4}, {"val_loss": 0.2}],
            test_metrics={"test_loss": 0.1, "test_accuracy": 0.9},
            best_metrics={"loss": 0.3},
            early_stopped=False,
        )

        assert result.epochs_trained == 5
        assert result.training_time == 120.5
        assert len(result.training_history) == 2
        assert len(result.validation_history) == 2
        assert result.test_metrics["test_accuracy"] == 0.9
        assert result.best_metrics["loss"] == 0.3
        assert result.early_stopped is False


@pytest.mark.asyncio
async def test_trainer_with_custom_callbacks():
    """Test trainer with custom callbacks."""
    model = MockModel()
    config = TrainerConfig(epochs=2)
    metrics = MetricCollection([Loss()])

    trainer = Trainer(model, config, metrics)

    # Create test data
    train_data = np.random.randn(32, 10)
    train_labels = np.random.randint(0, 2, 32)
    train_loader = ArrayDataLoader(train_data, train_labels, batch_size=16)

    # Track callback calls
    callback_calls = []

    async def custom_epoch_callback(epoch, metrics):
        callback_calls.append(f"epoch_{epoch}")

    async def custom_training_callback(metrics):
        callback_calls.append("training_complete")

    trainer.on_epoch_end = custom_epoch_callback
    trainer.on_training_complete = custom_training_callback

    # Run training
    await trainer.train(train_loader)

    # Check callbacks were called
    assert "epoch_0" in callback_calls
    assert "epoch_1" in callback_calls
    assert "training_complete" in callback_calls
