"""Tests for ML pipeline functionality."""

from unittest.mock import AsyncMock, Mock

import numpy as np
import pytest
from whiskey import Whiskey

from whiskey_ml import Dataset, MLPipeline, Model, ModelOutput, ml_extension
from whiskey_ml.core.dataset import ArrayDataLoader
from whiskey_ml.core.pipeline import PipelineConfig, PipelineState
from whiskey_ml.core.trainer import TrainingResult


class MockDataset(Dataset):
    """Mock dataset for testing."""

    def __init__(self, config=None):
        super().__init__(config)
        self.loaded = False

    async def load(self):
        self.loaded = True
        self.data = np.random.randn(100, 10)
        self.labels = np.random.randint(0, 2, 100)

    def get_splits(self):
        if not self.loaded:
            raise ValueError("Dataset not loaded")

        train_loader = ArrayDataLoader(self.data[:70], self.labels[:70], batch_size=16)
        val_loader = ArrayDataLoader(self.data[70:85], self.labels[70:85], batch_size=16)
        test_loader = ArrayDataLoader(self.data[85:], self.labels[85:], batch_size=16)
        return train_loader, val_loader, test_loader

    def __len__(self):
        return 100 if self.loaded else 0


class MockModel(Model):
    """Mock model for testing."""

    def __init__(self, config=None):
        super().__init__(config)
        self.training_steps = 0
        self.saved_path = None
        self.loaded_path = None

    async def forward(self, inputs):
        self.training_steps += 1
        batch_size = inputs["batch_size"]

        predictions = np.random.randn(batch_size, 2)
        loss = max(0.5 - (self.training_steps * 0.01), 0.1)

        if "labels" in inputs:
            pred_classes = np.argmax(predictions, axis=1)
            accuracy = np.mean(pred_classes == inputs["labels"])
            return ModelOutput(predictions=predictions, loss=loss, metrics={"accuracy": accuracy})

        return ModelOutput(predictions=predictions, loss=loss)

    def get_parameters(self):
        return {"weight": np.array([1, 2, 3])}

    def set_parameters(self, params):
        pass

    async def save(self, path):
        self.saved_path = str(path)

    async def load(self, path):
        self.loaded_path = str(path)

    def to_device(self, device):
        pass

    def compile(self):
        pass


class TestPipelineStates:
    """Test pipeline state management."""

    def test_pipeline_states(self):
        """Test pipeline state enum."""
        assert PipelineState.IDLE.value == "idle"
        assert PipelineState.LOADING_DATA.value == "loading_data"
        assert PipelineState.PREPROCESSING.value == "preprocessing"
        assert PipelineState.TRAINING.value == "training"
        assert PipelineState.EVALUATING.value == "evaluating"
        assert PipelineState.SAVING.value == "saving"
        assert PipelineState.COMPLETED.value == "completed"
        assert PipelineState.FAILED.value == "failed"


class TestPipelineConfig:
    """Test pipeline configuration."""

    def test_pipeline_config_creation(self):
        """Test creating pipeline config."""
        config = PipelineConfig(
            name="test_pipeline",
            dataset="test_dataset",
            model="test_model",
            version="1.0.0",
            description="Test pipeline",
        )

        assert config.name == "test_pipeline"
        assert config.dataset == "test_dataset"
        assert config.model == "test_model"
        assert config.version == "1.0.0"
        assert config.description == "Test pipeline"
        assert config.trainer == "default"
        assert config.seed == 42
        assert config.deterministic is True


class TestMLPipeline:
    """Test ML pipeline functionality."""

    @pytest.fixture
    async def app(self):
        """Create test app with ML extension."""
        app = Whiskey()
        app.use(ml_extension)
        return app

    @pytest.fixture
    async def context(self, app):
        """Create ML context."""
        async with app:
            from whiskey_ml.integrations.base import MLContext

            return await app.container.resolve(MLContext)

    def test_pipeline_creation(self, context):
        """Test creating a pipeline."""

        class TestPipeline(MLPipeline):
            dataset = "test_dataset"
            model = "test_model"
            epochs = 5
            batch_size = 32
            learning_rate = 0.001

        pipeline = TestPipeline(context)

        assert pipeline.context is context
        assert pipeline.container is context.container
        assert pipeline.state == PipelineState.IDLE
        assert pipeline.epochs == 5
        assert pipeline.batch_size == 32
        assert pipeline.learning_rate == 0.001

    def test_pipeline_config_building(self, context):
        """Test pipeline configuration building."""

        class TestPipeline(MLPipeline):
            dataset = "test_dataset"
            model = "test_model"
            epochs = 3
            batch_size = 16
            learning_rate = 0.01
            metrics = ["loss", "accuracy"]

        pipeline = TestPipeline(context)
        config = pipeline.config

        assert config.name == "TestPipeline"
        assert config.dataset == "test_dataset"
        assert config.model == "test_model"
        assert config.trainer_config.epochs == 3
        assert config.dataset_config.batch_size == 16
        assert config.model_config.learning_rate == 0.01
        assert config.metrics == ["loss", "accuracy"]

    def test_pipeline_validation(self, context):
        """Test pipeline validation."""

        # Pipeline without dataset should fail
        class BadPipeline1(MLPipeline):
            model = "test_model"

        with pytest.raises(ValueError, match="must specify a dataset"):
            BadPipeline1(context)

        # Pipeline without model should fail
        class BadPipeline2(MLPipeline):
            dataset = "test_dataset"

        with pytest.raises(ValueError, match="must specify a model"):
            BadPipeline2(context)

    async def test_pipeline_lifecycle_hooks(self, context):
        """Test pipeline lifecycle hooks."""
        hook_calls = []

        class TestPipeline(MLPipeline):
            dataset = "test_dataset"
            model = "test_model"
            epochs = 1

            async def on_start(self):
                hook_calls.append("start")

            async def on_complete(self, result):
                hook_calls.append("complete")

            async def on_error(self, error):
                hook_calls.append("error")

            async def on_epoch_end(self, epoch, metrics):
                hook_calls.append(f"epoch_{epoch}")

        pipeline = TestPipeline(context)

        # Test hooks are called
        await pipeline.on_start()
        await pipeline.on_epoch_end(0, {"loss": 0.5})
        await pipeline.on_complete(None)
        await pipeline.on_error(Exception("test"))

        assert "start" in hook_calls
        assert "epoch_0" in hook_calls
        assert "complete" in hook_calls
        assert "error" in hook_calls

    async def test_pipeline_state_changes(self, context):
        """Test pipeline state change events."""
        events = []

        class TestPipeline(MLPipeline):
            dataset = "test_dataset"
            model = "test_model"

            async def _emit_state_change(self):
                events.append(self.state)

        pipeline = TestPipeline(context)

        # Test state changes
        pipeline.state = PipelineState.LOADING_DATA
        await pipeline._emit_state_change()

        pipeline.state = PipelineState.TRAINING
        await pipeline._emit_state_change()

        pipeline.state = PipelineState.COMPLETED
        await pipeline._emit_state_change()

        assert PipelineState.LOADING_DATA in events
        assert PipelineState.TRAINING in events
        assert PipelineState.COMPLETED in events

    async def test_pipeline_run_with_scopes(self, app):
        """Test pipeline running with scope management."""

        @app.ml_dataset("test_dataset")
        class TestDataset(MockDataset):
            pass

        @app.ml_model("test_model")
        class TestModel(MockModel):
            pass

        class TestPipeline(MLPipeline):
            dataset = "test_dataset"
            model = "test_model"
            epochs = 1

        async with app:
            from whiskey_ml.integrations.base import MLContext

            context = await app.container.resolve(MLContext)
            pipeline = TestPipeline(context)

            # Mock the training process to avoid complex setup
            async def mock_run_with_scopes():
                return TrainingResult(
                    epochs_trained=1,
                    training_time=10.0,
                    training_history=[{"loss": 0.5}],
                    validation_history=[{"val_loss": 0.4}],
                    test_metrics={"test_loss": 0.3},
                    best_metrics={"loss": 0.5},
                )

            pipeline._run_with_scopes = mock_run_with_scopes

            # Run pipeline
            result = await pipeline.run()

            assert isinstance(result, TrainingResult)
            assert result.epochs_trained == 1

    async def test_pipeline_component_resolution(self, app):
        """Test pipeline component resolution."""

        @app.ml_dataset("test_dataset")
        class TestDataset(MockDataset):
            pass

        @app.ml_model("test_model")
        class TestModel(MockModel):
            pass

        class TestPipeline(MLPipeline):
            dataset = "test_dataset"
            model = "test_model"
            epochs = 1

        async with app:
            from whiskey_ml.integrations.base import MLContext

            context = await app.container.resolve(MLContext)
            pipeline = TestPipeline(context)

            # Test component resolution
            await pipeline._load_data()
            assert pipeline._dataset is not None
            assert isinstance(pipeline._dataset, TestDataset)
            assert pipeline._dataset.loaded is True

            await pipeline._initialize_model()
            assert pipeline._model is not None
            assert isinstance(pipeline._model, TestModel)

            await pipeline._initialize_trainer()
            assert pipeline._trainer is not None

    async def test_pipeline_error_handling(self, context):
        """Test pipeline error handling."""

        class FailingPipeline(MLPipeline):
            dataset = "test_dataset"
            model = "test_model"

            async def _load_data(self):
                raise RuntimeError("Failed to load data")

        pipeline = FailingPipeline(context)

        # Mock the scope-aware run method to test error handling
        async def mock_run_with_scopes():
            await pipeline._load_data()  # This will raise

        pipeline._run_with_scopes = mock_run_with_scopes

        # Run should handle the error and set state to FAILED
        with pytest.raises(RuntimeError):
            await pipeline.run()

        assert pipeline.state == PipelineState.FAILED

    async def test_pipeline_metrics_emission(self, context):
        """Test pipeline metrics emission."""
        emitted_events = []

        # Mock the context app to capture events
        context.app = Mock()
        context.app.emit = AsyncMock(
            side_effect=lambda event, data: emitted_events.append((event, data))
        )

        class TestPipeline(MLPipeline):
            dataset = "test_dataset"
            model = "test_model"

        pipeline = TestPipeline(context)

        # Test metrics emission
        await pipeline._emit_metrics(epoch=1, metrics={"loss": 0.5, "accuracy": 0.8})

        # Check event was emitted
        assert len(emitted_events) > 0
        event_name, event_data = emitted_events[-1]
        assert event_name == "ml.metrics"
        assert event_data["epoch"] == 1
        assert event_data["metrics"]["loss"] == 0.5
        assert event_data["metrics"]["accuracy"] == 0.8


class TestPipelineIntegration:
    """Test pipeline integration with other components."""

    async def test_pipeline_with_etl_integration(self):
        """Test pipeline with ETL integration (mocked)."""
        from whiskey import Container

        from whiskey_ml.integrations.base import MLContext

        container = Container()
        context = MLContext(container, {})

        # Mock ETL extension available
        context.integrations["etl"] = {"available": True}

        class ETLPipeline(MLPipeline):
            dataset = "test_dataset"
            model = "test_model"
            data_source = "etl_source"
            preprocessing = ["transform1", "transform2"]

        pipeline = ETLPipeline(context)

        # Check ETL configuration
        assert pipeline.data_source == "etl_source"
        assert pipeline.preprocessing == ["transform1", "transform2"]
        assert context.has_extension("etl") is True

    async def test_pipeline_without_etl_integration(self):
        """Test pipeline without ETL integration."""
        from whiskey import Container

        from whiskey_ml.integrations.base import MLContext

        container = Container()
        context = MLContext(container, {})

        class StandardPipeline(MLPipeline):
            dataset = "test_dataset"
            model = "test_model"

        pipeline = StandardPipeline(context)

        # Check no ETL configuration
        assert pipeline.data_source is None
        assert pipeline.preprocessing is None
        assert context.has_extension("etl") is False


@pytest.mark.asyncio
async def test_pipeline_run_pipeline_method():
    """Test MLExtension.run_pipeline method."""
    app = Whiskey()
    app.use(ml_extension)

    class TestPipeline(MLPipeline):
        dataset = "test_dataset"
        model = "test_model"
        epochs = 1

        async def run(self):
            return TrainingResult(
                epochs_trained=1,
                training_time=5.0,
                training_history=[{"loss": 0.5}],
                validation_history=[{"val_loss": 0.4}],
                test_metrics={"test_loss": 0.3},
                best_metrics={"loss": 0.5},
            )

    # Register pipeline
    app.ml._pipelines["test_pipeline"] = TestPipeline

    async with app:
        # Test run_pipeline method
        result = await app.ml.run_pipeline("test_pipeline")

        assert isinstance(result, TrainingResult)
        assert result.epochs_trained == 1

        # Test non-existent pipeline
        with pytest.raises(ValueError, match="Pipeline 'nonexistent' not found"):
            await app.ml.run_pipeline("nonexistent")
