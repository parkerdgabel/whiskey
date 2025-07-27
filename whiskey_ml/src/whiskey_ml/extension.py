"""ML extension for Whiskey framework."""

from __future__ import annotations

from typing import Any, Callable, Type

from whiskey import component, Container
from whiskey import Whiskey

from whiskey_ml.core.dataset import Dataset, FileDataset
from whiskey_ml.core.metrics import (
    Accuracy,
    F1Score,
    Loss,
    MeanSquaredError,
    Metric,
    MetricCollection,
)
from whiskey_ml.core.model import Model
from whiskey_ml.core.pipeline import MLContext, MLPipeline
# ML-specific scopes are managed using Whiskey's built-in scope system
# No need for custom scope classes - use app.container.scope("scope_name")
from whiskey_ml.core.trainer import Trainer
from whiskey_ml.integrations.base import ExtensionIntegration


class MLExtension:
    """Machine Learning extension for Whiskey."""
    
    def __init__(self):
        """Initialize ML extension."""
        self.integration: ExtensionIntegration | None = None
        self.context: MLContext | None = None
        
        # Registries
        self._datasets = {}
        self._models = {}
        self._trainers = {}
        self._pipelines = {}
        self._metrics = {}
    
    def __call__(self, app: Whiskey) -> None:
        """Register ML extension with Whiskey application.
        
        Args:
            app: Whiskey application instance
        """
        # Set up extension integration
        self.integration = ExtensionIntegration(app.container)
        self.context = self.integration.create_context()
        
        # Store app reference for event emission
        self.app = app
        self.context.app = app
        
        # Register extension in container
        app.container[MLExtension] = self
        app.container[MLContext] = self.context
        
        # Register core components
        self._register_core_components(app)
        
        # Add decorators
        app.ml_pipeline = self._create_pipeline_decorator(app)
        app.ml_dataset = self._create_dataset_decorator(app)
        app.ml_model = self._create_model_decorator(app)
        app.ml_trainer = self._create_trainer_decorator(app)
        app.ml_metric = self._create_metric_decorator(app)
        
        # Add ML-specific methods to app
        app.ml = self
        
        # Register lifecycle hooks
        app.on("startup", self._on_startup)
        app.on("shutdown", self._on_shutdown)
    
    def _register_core_components(self, app: Whiskey) -> None:
        """Register core ML components.
        
        Args:
            app: Whiskey instance
        """
        # Register default implementations
        app.container.register(Dataset, FileDataset)
        
        # Register metrics
        app.container.register("accuracy", Accuracy)
        app.container.register("f1", F1Score)
        app.container.register("loss", Loss)
        app.container.register("mse", MeanSquaredError)
        
        # Register default trainer (framework-specific adapters will override)
        @app.component
        class DefaultTrainer(Trainer):
            """Default trainer implementation."""
            
            async def train_step(self, batch: dict[str, Any], step: int) -> dict[str, float]:
                """Default training step."""
                # Forward pass
                output = await self.model.forward(batch)
                
                # Update metrics
                metrics = {}
                if output.loss is not None:
                    metrics["loss"] = output.loss
                
                if "labels" in batch:
                    metric_results = self.metrics.update(
                        output.predictions,
                        batch["labels"],
                        output.loss,
                    )
                    metrics.update(metric_results)
                
                return metrics
            
            async def validation_step(self, batch: dict[str, Any], step: int) -> dict[str, float]:
                """Default validation step."""
                # Same as training but without gradient updates
                return await self.train_step(batch, step)
        
        app.container.register("default", DefaultTrainer)
    
    def _create_pipeline_decorator(self, app: Whiskey) -> Callable:
        """Create ML pipeline decorator.
        
        Args:
            app: Whiskey instance
            
        Returns:
            Decorator function
        """
        def ml_pipeline(name: str, **kwargs):
            def decorator(cls: Type[MLPipeline]) -> Type[MLPipeline]:
                # Store metadata
                cls._pipeline_name = name
                cls._pipeline_metadata = kwargs
                
                # Register pipeline
                self._pipelines[name] = cls
                app.container.register(name, cls)
                
                # Register as component
                return app.component(cls)
            
            return decorator
        
        return ml_pipeline
    
    def _create_dataset_decorator(self, app: Whiskey) -> Callable:
        """Create dataset decorator.
        
        Args:
            app: Whiskey instance
            
        Returns:
            Decorator function
        """
        def ml_dataset(name: str, **kwargs):
            def decorator(cls: Type[Dataset]) -> Type[Dataset]:
                # Register dataset
                self._datasets[name] = cls
                app.container.register(name, cls)
                
                return app.component(cls)
            
            return decorator
        
        return ml_dataset
    
    def _create_model_decorator(self, app: Whiskey) -> Callable:
        """Create model decorator.
        
        Args:
            app: Whiskey instance
            
        Returns:
            Decorator function
        """
        def ml_model(name: str, **kwargs):
            def decorator(cls: Type[Model]) -> Type[Model]:
                # Register model
                self._models[name] = cls
                app.container.register(name, cls)
                
                return app.component(cls)
            
            return decorator
        
        return ml_model
    
    def _create_trainer_decorator(self, app: Whiskey) -> Callable:
        """Create trainer decorator.
        
        Args:
            app: Whiskey instance
            
        Returns:
            Decorator function
        """
        def ml_trainer(name: str, **kwargs):
            def decorator(cls: Type[Trainer]) -> Type[Trainer]:
                # Register trainer
                self._trainers[name] = cls
                app.container.register(name, cls)
                
                return app.component(cls)
            
            return decorator
        
        return ml_trainer
    
    def _create_metric_decorator(self, app: Whiskey) -> Callable:
        """Create metric decorator.
        
        Args:
            app: Whiskey instance
            
        Returns:
            Decorator function
        """
        def ml_metric(name: str, **kwargs):
            def decorator(cls: Type[Metric]) -> Type[Metric]:
                # Register metric
                self._metrics[name] = cls
                app.container.register(name, cls)
                
                return app.component(cls)
            
            return decorator
        
        return ml_metric
    
    async def _on_startup(self) -> None:
        """Called on application startup."""
        # Initialize framework adapters if available
        await self._initialize_framework_adapters()
    
    async def _on_shutdown(self) -> None:
        """Called on application shutdown."""
        # Cleanup resources
        pass
    
    async def _initialize_framework_adapters(self) -> None:
        """Initialize ML framework adapters."""
        # Try to import and register PyTorch adapter
        try:
            from whiskey_ml.frameworks.pytorch import register_pytorch_adapter
            register_pytorch_adapter(self)
        except ImportError:
            pass
        
        # Try to import and register TensorFlow adapter
        try:
            from whiskey_ml.frameworks.tensorflow import register_tensorflow_adapter
            register_tensorflow_adapter(self)
        except ImportError:
            pass
        
        # Try to import and register JAX adapter
        try:
            from whiskey_ml.frameworks.jax import register_jax_adapter
            register_jax_adapter(self)
        except ImportError:
            pass
    
    def get_pipeline(self, name: str) -> Type[MLPipeline] | None:
        """Get registered pipeline by name.
        
        Args:
            name: Pipeline name
            
        Returns:
            Pipeline class or None
        """
        return self._pipelines.get(name)
    
    def list_pipelines(self) -> dict[str, Type[MLPipeline]]:
        """List all registered pipelines.
        
        Returns:
            Dictionary of pipeline name to class
        """
        return self._pipelines.copy()
    
    async def run_pipeline(self, name: str, **kwargs) -> Any:
        """Run a registered pipeline.
        
        Args:
            name: Pipeline name
            **kwargs: Pipeline arguments
            
        Returns:
            Pipeline result
        """
        pipeline_class = self.get_pipeline(name)
        if not pipeline_class:
            raise ValueError(f"Pipeline '{name}' not found")
        
        # Create pipeline instance
        pipeline = pipeline_class(self.context)
        
        # Run pipeline
        return await pipeline.run(**kwargs)


# Extension instance
ml_extension = MLExtension()