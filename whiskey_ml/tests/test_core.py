"""Tests for core ML abstractions."""

import numpy as np
import pytest

from whiskey import Whiskey
from whiskey_ml import (
    Dataset,
    MLPipeline,
    Model,
    ModelOutput,
    ml_extension,
)
from whiskey_ml.core.dataset import FileDataset
from whiskey_ml.core.dataset import ArrayDataLoader
from whiskey_ml.core.metrics import Accuracy, Loss, MetricCollection


class TestDataset:
    """Test dataset functionality."""
    
    async def test_file_dataset(self, tmp_path):
        """Test file dataset loading."""
        # Create test data
        data = np.random.randn(100, 10)
        data_file = tmp_path / "test_data.npy"
        np.save(data_file, data)
        
        # Create dataset
        dataset = FileDataset(data_file)
        
        # Test loading
        await dataset.load()
        assert dataset.data is not None
        assert len(dataset) == 100
        assert dataset.data.shape == (100, 10)
        
        # Test splits
        train, val, test = dataset.get_splits()
        assert train is not None
        assert len(train) > 0
    
    async def test_array_dataloader(self):
        """Test array data loader."""
        data = np.random.randn(100, 10)
        labels = np.random.randint(0, 2, 100)
        
        loader = ArrayDataLoader(data, labels, batch_size=16)
        
        # Test iteration
        batches = []
        async for batch in loader:
            batches.append(batch)
            assert "data" in batch
            assert "labels" in batch
            assert batch["batch_size"] <= 16
        
        assert len(batches) == len(loader)


class TestModel:
    """Test model functionality."""
    
    async def test_model_forward(self):
        """Test model forward pass."""
        class SimpleModel(Model):
            async def forward(self, inputs):
                predictions = np.random.randn(inputs["batch_size"], 3)
                return ModelOutput(predictions=predictions, loss=0.5)
            
            def get_parameters(self):
                return {"weight": np.array([1, 2, 3])}
            
            def set_parameters(self, params):
                self.weight = params["weight"]
            
            async def save(self, path):
                pass
            
            async def load(self, path):
                pass
        
        model = SimpleModel()
        output = await model.forward({"batch_size": 32})
        
        assert output.predictions.shape == (32, 3)
        assert output.loss == 0.5
    
    def test_model_summary(self):
        """Test model summary."""
        class TestModel(Model):
            def get_parameters(self):
                return {
                    "layer1": np.zeros((100, 50)),
                    "layer2": np.zeros((50, 10))
                }
            
            def set_parameters(self, params):
                pass
            
            async def forward(self, inputs):
                return ModelOutput(predictions=None)
            
            async def save(self, path):
                pass
            
            async def load(self, path):
                pass
        
        model = TestModel()
        summary = model.summary()
        assert "TestModel" in summary
        assert "parameters: 5,500" in summary  # 100*50 + 50*10


class TestMetrics:
    """Test metrics functionality."""
    
    def test_accuracy_metric(self):
        """Test accuracy computation."""
        metric = Accuracy()
        
        # Binary classification
        predictions = np.array([0.8, 0.3, 0.9, 0.2])
        targets = np.array([1, 0, 1, 0])
        
        metric.update(predictions, targets)
        accuracy = metric.compute()
        assert accuracy == 1.0  # All correct
        
        # Reset and test incorrect predictions
        metric.reset()
        predictions = np.array([0.3, 0.8, 0.2, 0.9])  # Opposite
        metric.update(predictions, targets)
        accuracy = metric.compute()
        assert accuracy == 0.0  # All wrong
    
    def test_loss_metric(self):
        """Test loss tracking."""
        metric = Loss()
        
        # Add losses
        metric.update(0.5)
        metric.update(0.3)
        metric.update(0.7)
        
        avg_loss = metric.compute()
        assert avg_loss == pytest.approx(0.5, rel=1e-3)
    
    def test_metric_collection(self):
        """Test metric collection."""
        metrics = MetricCollection([
            Accuracy(),
            Loss()
        ])
        
        # Update metrics
        predictions = np.array([[0.2, 0.8], [0.9, 0.1], [0.3, 0.7]])
        targets = np.array([1, 0, 1])
        loss = 0.25
        
        results = metrics.update(predictions, targets, loss)
        
        assert "accuracy" in results
        assert "loss" in results
        assert results["accuracy"] == 1.0
        assert results["loss"] == 0.25


class TestMLPipeline:
    """Test ML pipeline functionality."""
    
    @pytest.fixture
    async def app(self):
        """Create test app with ML extension."""
        app = Whiskey()
        app.use(ml_extension)
        return app
    
    async def test_pipeline_registration(self, app):
        """Test pipeline registration."""
        @app.ml_pipeline("test_pipeline")
        class TestPipeline(MLPipeline):
            dataset = "test_dataset"
            model = "test_model"
            epochs = 1
        
        # Check registration
        assert app.ml.get_pipeline("test_pipeline") == TestPipeline
        assert "test_pipeline" in app.ml.list_pipelines()
    
    async def test_pipeline_creation_and_config(self, app):
        """Test pipeline creation and configuration."""
        @app.ml_dataset("test_dataset")
        class TestDataset(Dataset):
            async def load(self):
                self.data = np.random.randn(10, 5)
                self.labels = np.random.randint(0, 2, 10)
            
            def get_splits(self):
                loader = ArrayDataLoader(self.data, self.labels, batch_size=5)
                return loader, None, None
            
            def __len__(self):
                return 10
        
        @app.ml_model("test_model")
        class TestModel(Model):
            async def forward(self, inputs):
                return ModelOutput(
                    predictions=np.random.randn(inputs["batch_size"], 2),
                    loss=0.5
                )
            
            def get_parameters(self):
                return {}
            
            def set_parameters(self, params):
                pass
            
            async def save(self, path):
                pass
            
            async def load(self, path):
                pass
        
        @app.ml_pipeline("config_test")
        class ConfigPipeline(MLPipeline):
            dataset = "test_dataset"
            model = "test_model"
            epochs = 2
            batch_size = 16
            learning_rate = 0.01
            metrics = ["loss", "accuracy"]
        
        # Test pipeline configuration
        async with app:
            from whiskey_ml.integrations.base import MLContext
            context = await app.container.resolve(MLContext)
            pipeline = ConfigPipeline(context)
            
            # Test config building
            config = pipeline.config
            assert config.name == "ConfigPipeline"
            assert config.dataset == "test_dataset"
            assert config.model == "test_model"
            assert config.trainer_config.epochs == 2
            assert config.dataset_config.batch_size == 16
            assert config.model_config.learning_rate == 0.01
            assert config.metrics == ["loss", "accuracy"]


@pytest.mark.asyncio
async def test_extension_integration():
    """Test extension integration detection."""
    from whiskey_ml.integrations.base import ExtensionIntegration
    from whiskey import Container
    
    container = Container()
    integration = ExtensionIntegration(container)
    
    # Check extension detection
    extensions = integration.available_extensions
    assert isinstance(extensions, dict)
    
    # Create context
    context = integration.create_context()
    assert context.container == container
    assert context.integrations == extensions