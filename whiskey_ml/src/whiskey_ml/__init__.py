"""Whiskey ML - Declarative machine learning extension for Whiskey framework."""

from whiskey_ml.core.dataset import DataLoader, Dataset, DatasetConfig
from whiskey_ml.core.metrics import Metric, MetricCollection, MetricResult
from whiskey_ml.core.model import Model, ModelConfig, ModelOutput
from whiskey_ml.core.pipeline import MLPipeline, PipelineConfig, PipelineState

# ML scopes are managed using Whiskey's built-in scope system
# Use app.container.scope("scope_name") context managers
from whiskey_ml.core.trainer import Trainer, TrainerConfig, TrainingResult
from whiskey_ml.extension import ml_extension
from whiskey_ml.integrations.base import MLContext

# Optional visualization imports
try:
    from whiskey_ml.visualization import (
        ConsoleMetricsHandler,
        MetricsTracker,
        ProgressTracker,
        RichProgressHandler,
        TensorBoardHandler,
    )

    _has_visualization = True
except ImportError:
    _has_visualization = False

__version__ = "0.1.0"

__all__ = [
    # Extension
    "ml_extension",
    "MLContext",
    # Core classes
    "MLPipeline",
    "PipelineConfig",
    "PipelineState",
    "Dataset",
    "DataLoader",
    "DatasetConfig",
    "Model",
    "ModelConfig",
    "ModelOutput",
    "Trainer",
    "TrainerConfig",
    "TrainingResult",
    "Metric",
    "MetricCollection",
    "MetricResult",
    # Note: ML scopes use Whiskey's built-in scope system
    # Use app.container.scope("experiment"), app.container.scope("training"), etc.
]

# Add visualization exports if available
if _has_visualization:
    __all__.extend(
        [
            "MetricsTracker",
            "ConsoleMetricsHandler",
            "ProgressTracker",
            "RichProgressHandler",
            "TensorBoardHandler",
        ]
    )
