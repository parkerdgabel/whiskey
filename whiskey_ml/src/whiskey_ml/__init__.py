"""Whiskey ML - Declarative machine learning extension for Whiskey framework."""

from whiskey_ml.core.dataset import Dataset, DataLoader, DatasetConfig
from whiskey_ml.core.metrics import Metric, MetricCollection, MetricResult
from whiskey_ml.core.model import Model, ModelConfig, ModelOutput
from whiskey_ml.core.pipeline import MLPipeline, PipelineConfig, PipelineState
from whiskey_ml.core.trainer import Trainer, TrainerConfig, TrainingResult
from whiskey_ml.extension import ml_extension
from whiskey_ml.integrations.base import MLContext

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
]