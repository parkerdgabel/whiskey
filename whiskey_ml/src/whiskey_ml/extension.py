"""ML extension for Whiskey framework."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from whiskey import Whiskey

from whiskey_ml.core.dataset import Dataset
from whiskey_ml.core.metrics import (
    Accuracy,
    F1Score,
    Loss,
    MeanSquaredError,
    Metric,
)
from whiskey_ml.core.model import Model
from whiskey_ml.core.pipeline import MLContext, MLPipeline
from whiskey_ml.core.trainer import Trainer
from whiskey_ml.integrations.base import ExtensionIntegration


def ml_extension(app: Whiskey) -> None:
    """ML extension that adds machine learning capabilities to Whiskey.

    This extension provides:
    - ML component decorators: @app.ml_model(), @app.ml_dataset(), etc.
    - ML pipeline support with scope management
    - Event-driven metrics tracking
    - Framework adapter integration (PyTorch, TensorFlow, JAX)

    Example:
        app = Whiskey()
        app.use(ml_extension)

        @app.ml_model("my_model")
        class MyModel(Model):
            async def forward(self, inputs):
                return ModelOutput(predictions=predictions)

        @app.ml_pipeline("training")
        class TrainingPipeline(MLPipeline):
            dataset = "my_dataset"
            model = "my_model"
            epochs = 10

    Args:
        app: Whiskey application instance
    """
    # Set up extension integration
    integration = ExtensionIntegration(app.container)
    context = integration.create_context()
    context.app = app

    # Register ML context using dict-like syntax (proper Whiskey pattern)
    app.container[MLContext] = context

    # Registries for ML components
    datasets = {}
    models = {}
    trainers = {}
    pipelines = {}
    metrics = {}

    # Register core components
    _register_core_components(app)

    # Add decorators
    app.add_decorator("ml_pipeline", _create_pipeline_decorator(app, pipelines))
    app.add_decorator("ml_dataset", _create_dataset_decorator(app, datasets))
    app.add_decorator("ml_model", _create_model_decorator(app, models))
    app.add_decorator("ml_trainer", _create_trainer_decorator(app, trainers))
    app.add_decorator("ml_metric", _create_metric_decorator(app, metrics))

    # Add ML-specific methods to app
    class MLNamespace:
        """ML namespace for the app."""

        def __init__(self):
            self._datasets = datasets
            self._models = models
            self._trainers = trainers
            self._pipelines = pipelines
            self._metrics = metrics

        def get_pipeline(self, name: str) -> type[MLPipeline] | None:
            """Get registered pipeline by name."""
            return self._pipelines.get(name)

        def list_pipelines(self) -> dict[str, type[MLPipeline]]:
            """List all registered pipelines."""
            return self._pipelines.copy()

        async def run_pipeline(self, name: str, **kwargs) -> Any:
            """Run a registered pipeline."""
            pipeline_class = self.get_pipeline(name)
            if not pipeline_class:
                raise ValueError(f"Pipeline '{name}' not found")

            # Create pipeline instance
            pipeline = pipeline_class(context)

            # Run pipeline
            return await pipeline.run(**kwargs)

    app.ml = MLNamespace()

    # Register lifecycle hooks
    app.on("startup", _on_startup)
    app.on("shutdown", _on_shutdown)


def _register_core_components(app: Whiskey) -> None:
    """Register core ML components.

    Args:
        app: Whiskey instance
    """
    # Register metrics (these have safe default constructors)
    app.container["accuracy"] = Accuracy
    app.container["f1"] = F1Score
    app.container["loss"] = Loss
    app.container["mse"] = MeanSquaredError

    # Other ML components are registered via decorators only


def _create_pipeline_decorator(app: Whiskey, pipelines: dict) -> Callable:
    """Create ML pipeline decorator."""

    def ml_pipeline(name: str, **kwargs):
        def decorator(cls: type[MLPipeline]) -> type[MLPipeline]:
            # Store metadata
            cls._pipeline_name = name
            cls._pipeline_metadata = kwargs

            # Register pipeline
            pipelines[name] = cls
            app.container[name] = cls

            # Register as component
            app.component(cls)
            return cls

        return decorator

    return ml_pipeline


def _create_dataset_decorator(app: Whiskey, datasets: dict) -> Callable:
    """Create dataset decorator."""

    def ml_dataset(name: str, **kwargs):
        def decorator(cls: type[Dataset]) -> type[Dataset]:
            # Register dataset
            datasets[name] = cls
            app.container[name] = cls

            app.component(cls)
            return cls

        return decorator

    return ml_dataset


def _create_model_decorator(app: Whiskey, models: dict) -> Callable:
    """Create model decorator."""

    def ml_model(name: str, **kwargs):
        def decorator(cls: type[Model]) -> type[Model]:
            # Register model
            models[name] = cls
            app.container[name] = cls

            app.component(cls)
            return cls

        return decorator

    return ml_model


def _create_trainer_decorator(app: Whiskey, trainers: dict) -> Callable:
    """Create trainer decorator."""

    def ml_trainer(name: str, **kwargs):
        def decorator(cls: type[Trainer]) -> type[Trainer]:
            # Register trainer
            trainers[name] = cls
            app.container[name] = cls

            app.component(cls)
            return cls

        return decorator

    return ml_trainer


def _create_metric_decorator(app: Whiskey, metrics: dict) -> Callable:
    """Create metric decorator."""

    def ml_metric(name: str, **kwargs):
        def decorator(cls: type[Metric]) -> type[Metric]:
            # Register metric
            metrics[name] = cls
            app.container[name] = cls

            app.component(cls)
            return cls

        return decorator

    return ml_metric


async def _on_startup() -> None:
    """Called on application startup."""
    # Initialize framework adapters if available
    await _initialize_framework_adapters()


async def _on_shutdown() -> None:
    """Called on application shutdown."""
    # Cleanup resources
    pass


async def _initialize_framework_adapters() -> None:
    """Initialize ML framework adapters."""
    # Try to import and register PyTorch adapter
    try:
        from whiskey_ml.frameworks.pytorch import register_pytorch_adapter  # noqa: F401
        # Note: Will need to pass app/context when implementing
        # register_pytorch_adapter(app)
    except ImportError:
        pass

    # Try to import and register TensorFlow adapter
    try:
        from whiskey_ml.frameworks.tensorflow import register_tensorflow_adapter  # noqa: F401
        # register_tensorflow_adapter(app)
    except ImportError:
        pass

    # Try to import and register JAX adapter
    try:
        from whiskey_ml.frameworks.jax import register_jax_adapter  # noqa: F401
        # register_jax_adapter(app)
    except ImportError:
        pass
