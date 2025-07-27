"""Tests for ML extension integration."""

import pytest
from whiskey import Whiskey
from whiskey_ml import ml_extension


class TestMLExtension:
    """Test ML extension functionality."""
    
    @pytest.fixture
    async def app(self):
        """Create test app with ML extension."""
        app = Whiskey()
        app.use(ml_extension)
        return app
    
    async def test_extension_registration(self, app):
        """Test that ML extension is properly registered."""
        # Check extension namespace is registered
        assert hasattr(app, 'ml')
        assert app.ml is not None
        
        # Check decorators are available
        assert hasattr(app, 'ml_pipeline')
        assert hasattr(app, 'ml_dataset')
        assert hasattr(app, 'ml_model')
        assert hasattr(app, 'ml_trainer')
        assert hasattr(app, 'ml_metric')
    
    async def test_extension_container_registration(self, app):
        """Test extension components in container."""
        async with app:
            # Context should be available
            from whiskey_ml.integrations.base import MLContext
            context = await app.container.resolve(MLContext)
            assert context is not None
    
    async def test_default_components_registered(self, app):
        """Test that default components are registered."""
        async with app:
            # Default metrics should be available
            accuracy = await app.container.resolve("accuracy")
            assert accuracy is not None
            
            loss = await app.container.resolve("loss")
            assert loss is not None
            
            # Default trainer should be available
            trainer = await app.container.resolve("default")
            assert trainer is not None
    
    async def test_pipeline_decorator_registration(self, app):
        """Test pipeline decorator functionality."""
        from whiskey_ml import MLPipeline
        
        @app.ml_pipeline("test_pipeline")
        class TestPipeline(MLPipeline):
            dataset = "test_dataset"
            model = "test_model"
            epochs = 1
        
        # Check pipeline is registered in extension
        assert app.ml.get_pipeline("test_pipeline") == TestPipeline
        
        # Check it's in the pipelines list
        pipelines = app.ml.list_pipelines()
        assert "test_pipeline" in pipelines
        assert pipelines["test_pipeline"] == TestPipeline
    
    async def test_dataset_decorator_registration(self, app):
        """Test dataset decorator functionality."""
        from whiskey_ml import Dataset
        
        @app.ml_dataset("test_dataset")
        class TestDataset(Dataset):
            async def load(self):
                pass
            
            def get_splits(self):
                return None, None, None
            
            def __len__(self):
                return 0
        
        async with app:
            # Should be able to resolve the dataset
            dataset = await app.container.resolve("test_dataset")
            assert isinstance(dataset, TestDataset)
    
    async def test_model_decorator_registration(self, app):
        """Test model decorator functionality."""
        from whiskey_ml import Model, ModelOutput
        
        @app.ml_model("test_model")
        class TestModel(Model):
            async def forward(self, inputs):
                return ModelOutput(predictions=None)
            
            def get_parameters(self):
                return {}
            
            def set_parameters(self, params):
                pass
            
            async def save(self, path):
                pass
            
            async def load(self, path):
                pass
        
        async with app:
            # Should be able to resolve the model
            model = await app.container.resolve("test_model")
            assert isinstance(model, TestModel)
    
    async def test_trainer_decorator_registration(self, app):
        """Test trainer decorator functionality."""
        from whiskey_ml import Trainer
        
        @app.ml_trainer("test_trainer")
        class TestTrainer(Trainer):
            async def train_step(self, batch, step):
                return {"loss": 0.5}
            
            async def validation_step(self, batch, step):
                return {"val_loss": 0.4}
        
        async with app:
            # Should be able to resolve the trainer
            trainer = await app.container.resolve("test_trainer")
            assert isinstance(trainer, TestTrainer)
    
    async def test_metric_decorator_registration(self, app):
        """Test metric decorator functionality."""
        from whiskey_ml import Metric
        
        @app.ml_metric("test_metric")
        class TestMetric(Metric):
            def update(self, *args, **kwargs):
                pass
            
            def compute(self):
                return 0.5
            
            def reset(self):
                pass
        
        async with app:
            # Should be able to resolve the metric
            metric = await app.container.resolve("test_metric")
            assert isinstance(metric, TestMetric)


class TestExtensionIntegration:
    """Test extension integration detection."""
    
    def test_extension_detection(self):
        """Test extension detection functionality."""
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
    
    def test_extension_detection_methods(self):
        """Test has_extension method."""
        from whiskey_ml.integrations.base import ExtensionIntegration
        from whiskey import Container
        
        container = Container()
        integration = ExtensionIntegration(container)
        context = integration.create_context()
        
        # Test has_extension method
        # These should return False since extensions aren't installed
        assert not context.has_extension("etl")
        assert not context.has_extension("sql")
        assert not context.has_extension("jobs")
        assert not context.has_extension("nonexistent")


@pytest.mark.asyncio
async def test_ml_extension_startup():
    """Test ML extension startup hooks."""
    app = Whiskey()
    app.use(ml_extension)
    
    # Test startup completes without errors
    async with app:
        # Extension should be available
        assert hasattr(app, 'ml')
        assert app.ml is not None


@pytest.mark.asyncio
async def test_ml_extension_framework_adapters():
    """Test framework adapter initialization."""
    app = Whiskey()
    app.use(ml_extension)
    
    async with app:
        # Framework adapters should initialize without errors
        # (they will fail to import but shouldn't crash)
        extension = app.ml
        
        # The _initialize_framework_adapters method should complete
        await extension._initialize_framework_adapters()