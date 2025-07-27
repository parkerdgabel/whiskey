"""ML Pipeline abstractions."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type, Union

from whiskey import Container

from whiskey_ml.core.dataset import Dataset, DatasetConfig, DataLoader
from whiskey_ml.core.metrics import MetricCollection
from whiskey_ml.core.model import Model, ModelConfig
from whiskey_ml.core.trainer import Trainer, TrainerConfig, TrainingResult


class PipelineState(Enum):
    """ML Pipeline execution states."""
    
    IDLE = "idle"
    LOADING_DATA = "loading_data"
    PREPROCESSING = "preprocessing"
    TRAINING = "training"
    EVALUATING = "evaluating"
    SAVING = "saving"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class PipelineConfig:
    """Configuration for ML pipelines."""
    
    # Pipeline identification
    name: str
    version: str = "1.0.0"
    description: str = ""
    
    # Data configuration
    dataset: str | Dataset | None = None
    dataset_config: DatasetConfig = field(default_factory=DatasetConfig)
    
    # Model configuration
    model: str | Model | None = None
    model_config: ModelConfig = field(default_factory=ModelConfig)
    
    # Training configuration
    trainer: str | Trainer = "default"
    trainer_config: TrainerConfig = field(default_factory=TrainerConfig)
    
    # Metrics
    metrics: list[str] = field(default_factory=lambda: ["loss", "accuracy"])
    
    # Optional ETL integration
    data_source: str | None = None  # ETL source name
    preprocessing: list[str] | None = None  # ETL transforms
    prediction_sink: str | None = None  # ETL sink for predictions
    
    # Experiment tracking
    experiment_name: str | None = None
    tags: dict[str, str] = field(default_factory=dict)
    
    # Reproducibility
    seed: int = 42
    deterministic: bool = True


class MLPipeline:
    """Base ML pipeline."""
    
    # Declarative configuration (override in subclasses)
    dataset: str | Dataset | None = None
    model: str | Model | None = None
    trainer: str | Trainer = "default"
    
    # Training configuration
    epochs: int = 10
    batch_size: int = 32
    learning_rate: float = 0.001
    
    # Metrics
    metrics: list[str] = ["loss", "accuracy"]
    
    # Optional ETL integration
    data_source: str | None = None
    preprocessing: list[str] | None = None
    prediction_sink: str | None = None
    
    def __init__(self, context: MLContext):
        """Initialize pipeline.
        
        Args:
            context: ML context with container and integrations
        """
        self.context = context
        self.container = context.container
        self.state = PipelineState.IDLE
        
        # Build config from class attributes
        self.config = self._build_config()
        
        # Components (resolved lazily)
        self._dataset: Dataset | None = None
        self._model: Model | None = None
        self._trainer: Trainer | None = None
        self._metrics: MetricCollection | None = None
    
    def _build_config(self) -> PipelineConfig:
        """Build configuration from class attributes."""
        return PipelineConfig(
            name=self.__class__.__name__,
            dataset=self.dataset,
            model=self.model,
            trainer=self.trainer,
            dataset_config=DatasetConfig(
                batch_size=self.batch_size,
            ),
            model_config=ModelConfig(
                learning_rate=self.learning_rate,
            ),
            trainer_config=TrainerConfig(
                epochs=self.epochs,
            ),
            metrics=self.metrics,
            data_source=self.data_source,
            preprocessing=self.preprocessing,
            prediction_sink=self.prediction_sink,
        )
    
    async def run(self) -> TrainingResult:
        """Run the ML pipeline."""
        try:
            await self.on_start()
            
            # Run entire pipeline within experiment scope using app.container.scope()
            async with self.container.scope("experiment"):
                return await self._run_with_scopes()
                
        except Exception as e:
            self.state = PipelineState.FAILED
            await self._emit_state_change()
            
            # Emit pipeline failed
            if hasattr(self.context, "app"):
                await self.context.app.emit("ml.pipeline.failed", {
                    "name": self.config.name,
                    "error": str(e),
                    "state": self.state.value
                })
            
            await self.on_error(e)
            raise
    
    async def _run_with_scopes(self) -> TrainingResult:
        """Run pipeline with ML scopes for proper resource management."""
        # Emit pipeline started
        if hasattr(self.context, "app"):
            await self.context.app.emit("ml.pipeline.started", {
                "name": self.config.name,
                "state": self.state.value,
                "config": {
                    "model": str(self.config.model),
                    "dataset": str(self.config.dataset),
                    "epochs": self.config.trainer_config.epochs,
                    "batch_size": self.config.dataset_config.batch_size
                }
            })
        
        # Load data (within experiment scope)
        self.state = PipelineState.LOADING_DATA
        await self._emit_state_change()
        await self._load_data()
        
        # Preprocessing  
        if self.preprocessing:
            self.state = PipelineState.PREPROCESSING
            await self._emit_state_change()
            await self._preprocess_data()
        
        # Initialize model and trainer within training scope
        async with self.container.scope("training"):
            # Initialize model
            await self._initialize_model()
            
            # Initialize trainer
            await self._initialize_trainer()
            
            # Training
            self.state = PipelineState.TRAINING
            await self._emit_state_change()
            result = await self._train_with_scopes()
        
        # Evaluation within evaluation scope
        self.state = PipelineState.EVALUATING
        await self._emit_state_change()
        async with self.container.scope("evaluation"):
            await self._evaluate(result)
        
        # Save model
        self.state = PipelineState.SAVING
        await self._emit_state_change()
        await self._save_model()
        
        self.state = PipelineState.COMPLETED
        await self._emit_state_change()
        
        # Emit pipeline completed
        if hasattr(self.context, "app"):
            await self.context.app.emit("ml.pipeline.completed", {
                "name": self.config.name,
                "result": {
                    "epochs_trained": result.epochs_trained,
                    "training_time": result.training_time,
                    "final_metrics": result.training_history[-1] if result.training_history else {},
                    "test_metrics": result.test_metrics
                }
            })
        
        await self.on_complete(result)
        return result
    
    async def _run_without_scopes(self) -> TrainingResult:
        """Fallback method to run without scopes (for backward compatibility)."""
        # Emit pipeline started
        if hasattr(self.context, "app"):
            await self.context.app.emit("ml.pipeline.started", {
                "name": self.config.name,
                "state": self.state.value,
                "config": {
                    "model": str(self.config.model),
                    "dataset": str(self.config.dataset),
                    "epochs": self.config.trainer_config.epochs,
                    "batch_size": self.config.dataset_config.batch_size
                }
            })
        
        # Load data
        self.state = PipelineState.LOADING_DATA
        await self._emit_state_change()
        await self._load_data()
        
        # Preprocessing
        if self.preprocessing:
            self.state = PipelineState.PREPROCESSING
            await self._emit_state_change()
            await self._preprocess_data()
        
        # Initialize model
        await self._initialize_model()
        
        # Initialize trainer
        await self._initialize_trainer()
        
        # Training
        self.state = PipelineState.TRAINING
        await self._emit_state_change()
        result = await self._train()
        
        # Evaluation
        self.state = PipelineState.EVALUATING
        await self._emit_state_change()
        await self._evaluate(result)
        
        # Save model
        self.state = PipelineState.SAVING
        await self._emit_state_change()
        await self._save_model()
        
        self.state = PipelineState.COMPLETED
        await self._emit_state_change()
        
        # Emit pipeline completed
        if hasattr(self.context, "app"):
            await self.context.app.emit("ml.pipeline.completed", {
                "name": self.config.name,
                "result": {
                    "epochs_trained": result.epochs_trained,
                    "training_time": result.training_time,
                    "final_metrics": result.training_history[-1] if result.training_history else {},
                    "test_metrics": result.test_metrics
                }
            })
        
        await self.on_complete(result)
        return result
    
    async def _load_data(self) -> None:
        """Load dataset."""
        # Resolve dataset
        if isinstance(self.config.dataset, str):
            # Try to resolve from container
            dataset_class = await self.container.resolve(self.config.dataset)
            self._dataset = dataset_class(self.config.dataset_config)
        else:
            self._dataset = self.config.dataset
        
        # If ETL integration available, enhance dataset
        if self.context.has_extension("etl") and self.data_source:
            from whiskey_etl import get_source
            etl_source = get_source(self.data_source)
            self._dataset.set_etl_source(etl_source)
        
        # Load data
        await self._dataset.load()
    
    async def _preprocess_data(self) -> None:
        """Apply preprocessing transforms."""
        if not self.context.has_extension("etl"):
            return
        
        # Apply ETL transforms
        from whiskey_etl import get_transform
        
        for transform_name in self.preprocessing:
            transform = get_transform(transform_name)
            # Apply transform to dataset
            # This would need dataset to support transforms
    
    async def _initialize_model(self) -> None:
        """Initialize model."""
        if isinstance(self.config.model, str):
            # Resolve from container
            model_class = await self.container.resolve(self.config.model)
            self._model = model_class(self.config.model_config)
        else:
            self._model = self.config.model
        
        # Move to device
        device = self.config.model_config.device
        if device == "auto":
            device = self._detect_device()
        self._model.to_device(device)
        
        # Compile if requested
        if self.config.model_config.compile_model:
            self._model.compile()
    
    async def _initialize_trainer(self) -> None:
        """Initialize trainer."""
        # Create metrics
        self._metrics = MetricCollection.from_names(self.config.metrics)
        
        # Resolve trainer
        if isinstance(self.config.trainer, str):
            trainer_class = await self.container.resolve(self.config.trainer)
            self._trainer = trainer_class(
                self._model,
                self.config.trainer_config,
                self._metrics,
            )
        else:
            self._trainer = self.config.trainer
    
    async def _train(self) -> TrainingResult:
        """Train the model."""
        # Get data loaders
        train_loader, val_loader, test_loader = self._dataset.get_splits()
        
        # Hook into trainer's epoch callbacks to emit events
        original_on_epoch_end = None
        if hasattr(self._trainer, "on_epoch_end"):
            original_on_epoch_end = self._trainer.on_epoch_end
        
        async def emit_epoch_metrics(epoch: int, metrics: dict[str, float]):
            # Call original callback if exists
            if original_on_epoch_end:
                await original_on_epoch_end(epoch, metrics)
            
            # Emit metrics event
            await self._emit_metrics(epoch, metrics)
            
            # Call pipeline's epoch end hook
            await self.on_epoch_end(epoch, metrics)
        
        # Replace trainer's callback
        self._trainer.on_epoch_end = emit_epoch_metrics
        
        # Train
        result = await self._trainer.train(
            train_loader,
            val_loader,
            test_loader,
        )
        
        return result
    
    async def _train_with_scopes(self) -> TrainingResult:
        """Train the model with epoch scopes for proper resource management."""
        # Get data loaders
        train_loader, val_loader, test_loader = self._dataset.get_splits()
        
        # Hook into trainer's epoch callbacks to emit events and manage epoch scopes
        original_on_epoch_end = None
        if hasattr(self._trainer, "on_epoch_end"):
            original_on_epoch_end = self._trainer.on_epoch_end
        
        async def emit_epoch_metrics_with_scope(epoch: int, metrics: dict[str, float]):
            # Run epoch end processing within epoch scope
            async with self.container.scope("epoch"):
                # Call original callback if exists
                if original_on_epoch_end:
                    await original_on_epoch_end(epoch, metrics)
                
                # Emit metrics event
                await self._emit_metrics(epoch, metrics)
                
                # Call pipeline's epoch end hook
                await self.on_epoch_end(epoch, metrics)
        
        # Replace trainer's callback
        self._trainer.on_epoch_end = emit_epoch_metrics_with_scope
        
        # Train
        result = await self._trainer.train(
            train_loader,
            val_loader,
            test_loader,
        )
        
        return result
    
    async def _evaluate(self, result: TrainingResult) -> None:
        """Evaluate the model."""
        # Log final metrics
        if result.test_metrics:
            await self.context.log_metrics(result.test_metrics, prefix="test")
    
    async def _save_model(self) -> None:
        """Save the trained model."""
        # Save to checkpoint dir
        checkpoint_dir = Path(self.config.trainer_config.checkpoint_dir)
        model_path = checkpoint_dir / "final_model.ckpt"
        await self._model.save(model_path)
        
        # If model registry available, register model
        if self.context.has_extension("registry"):
            await self._register_model()
    
    async def _register_model(self) -> None:
        """Register model in model registry."""
        # This would integrate with model registry
        pass
    
    def _detect_device(self) -> str:
        """Detect best available device."""
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
            elif torch.backends.mps.is_available():
                return "mps"
        except ImportError:
            pass
        
        return "cpu"
    
    # Lifecycle hooks (optional override)
    async def on_start(self) -> None:
        """Called when pipeline starts."""
        await self.context.log(f"Starting ML pipeline: {self.config.name}")
    
    async def on_complete(self, result: TrainingResult) -> None:
        """Called when pipeline completes."""
        await self.context.log(f"Pipeline completed: {result.summary()}")
    
    async def on_error(self, error: Exception) -> None:
        """Called when pipeline fails."""
        await self.context.log(f"Pipeline failed: {error}", level="ERROR")
    
    async def on_epoch_start(self, epoch: int) -> None:
        """Called at start of each epoch."""
        pass
    
    async def on_epoch_end(self, epoch: int, metrics: dict[str, float]) -> None:
        """Called at end of each epoch."""
        pass
    
    async def _emit_state_change(self) -> None:
        """Emit state change event."""
        if hasattr(self.context, "app"):
            await self.context.app.emit("ml.pipeline.state_changed", {
                "name": self.config.name,
                "state": self.state.value,
                "previous_state": getattr(self, "_previous_state", None)
            })
            self._previous_state = self.state.value
    
    async def _emit_metrics(self, epoch: int, metrics: dict[str, float]) -> None:
        """Emit training metrics event."""
        if hasattr(self.context, "app"):
            await self.context.app.emit("ml.training.metrics", {
                "pipeline": self.config.name,
                "epoch": epoch,
                "metrics": metrics,
                "timestamp": datetime.now().isoformat()
            })


@dataclass
class MLContext:
    """Context for ML pipelines."""
    
    container: Container
    integrations: dict[str, bool] = field(default_factory=dict)
    experiment_tracker: Any | None = None
    
    def has_extension(self, name: str) -> bool:
        """Check if extension is available."""
        return self.integrations.get(name, False)
    
    async def log(self, message: str, level: str = "INFO") -> None:
        """Log a message."""
        timestamp = datetime.now().isoformat()
        print(f"[{timestamp}] [{level}] {message}")
    
    async def log_metrics(self, metrics: dict[str, float], prefix: str = "") -> None:
        """Log metrics."""
        if prefix:
            metrics = {f"{prefix}/{k}": v for k, v in metrics.items()}
        
        metric_str = ", ".join(f"{k}: {v:.4f}" for k, v in metrics.items())
        await self.log(f"Metrics - {metric_str}")
        
        if self.experiment_tracker:
            for name, value in metrics.items():
                await self.experiment_tracker.log_metric(name, value)