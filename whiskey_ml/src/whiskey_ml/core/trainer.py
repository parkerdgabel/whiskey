"""Trainer abstractions for ML pipelines."""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from whiskey_ml.core.dataset import DataLoader
from whiskey_ml.core.metrics import MetricCollection, MetricResult
from whiskey_ml.core.model import Model, ModelOutput


class TrainerState(Enum):
    """Training states."""
    
    IDLE = "idle"
    TRAINING = "training"
    VALIDATING = "validating"
    TESTING = "testing"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


@dataclass
class TrainerConfig:
    """Configuration for trainers."""
    
    # Training configuration
    epochs: int = 10
    max_steps: int | None = None
    gradient_accumulation_steps: int = 1
    
    # Validation
    val_check_interval: float = 1.0  # Check every epoch
    val_check_steps: int | None = None  # Or check every N steps
    
    # Early stopping
    early_stopping: bool = True
    early_stopping_patience: int = 3
    early_stopping_metric: str = "val_loss"
    early_stopping_mode: str = "min"  # min or max
    early_stopping_threshold: float = 0.0001
    
    # Checkpointing
    save_checkpoint: bool = True
    checkpoint_dir: str | Path = "./checkpoints"
    save_top_k: int = 3
    save_last: bool = True
    
    # Logging
    log_interval: int = 10
    log_metrics: bool = True
    log_gradients: bool = False
    
    # Device
    device: str = "auto"
    distributed: bool = False
    
    # Memory optimization
    gradient_checkpointing: bool = False
    mixed_precision: bool = False
    
    # Callbacks
    callbacks: list[str] = field(default_factory=list)


@dataclass
class TrainingResult:
    """Result of training."""
    
    # Training info
    trainer_state: TrainerState
    epochs_trained: int
    steps_trained: int
    training_time: float
    
    # Metrics
    train_metrics: dict[str, list[float]]
    val_metrics: dict[str, list[float]] | None = None
    test_metrics: dict[str, float] | None = None
    
    # Best model info
    best_epoch: int | None = None
    best_metric: float | None = None
    best_checkpoint: str | None = None
    
    # History
    loss_history: list[float] = field(default_factory=list)
    learning_rate_history: list[float] = field(default_factory=list)
    
    def summary(self) -> str:
        """Get training summary."""
        lines = [
            f"Training Result:",
            f"  State: {self.trainer_state.value}",
            f"  Epochs: {self.epochs_trained}",
            f"  Steps: {self.steps_trained}",
            f"  Time: {self.training_time:.2f}s",
        ]
        
        if self.best_metric is not None:
            lines.append(f"  Best metric: {self.best_metric:.4f} (epoch {self.best_epoch})")
        
        if self.test_metrics:
            lines.append("  Test metrics:")
            for name, value in self.test_metrics.items():
                lines.append(f"    {name}: {value:.4f}")
        
        return "\n".join(lines)


class TrainingContext:
    """Context for training lifecycle."""
    
    def __init__(
        self,
        model: Model,
        config: TrainerConfig,
        experiment_tracker: Any | None = None,
    ):
        """Initialize training context.
        
        Args:
            model: Model being trained
            config: Trainer configuration
            experiment_tracker: Optional experiment tracker
        """
        self.model = model
        self.config = config
        self.experiment_tracker = experiment_tracker
        
        # State
        self.current_epoch = 0
        self.current_step = 0
        self.best_metric = float("inf") if config.early_stopping_mode == "min" else float("-inf")
        self.patience_counter = 0
        
        # Metrics
        self.train_metrics = MetricCollection()
        self.val_metrics = MetricCollection()
        
        # History
        self.loss_history = []
        self.metric_history = {}
        
    async def log(self, message: str, level: str = "INFO") -> None:
        """Log a message."""
        timestamp = datetime.now().isoformat()
        print(f"[{timestamp}] [{level}] {message}")
        
        if self.experiment_tracker:
            await self.experiment_tracker.log_text(message, step=self.current_step)
    
    async def log_metrics(self, metrics: dict[str, float], prefix: str = "") -> None:
        """Log metrics."""
        if prefix:
            metrics = {f"{prefix}/{k}": v for k, v in metrics.items()}
        
        # Log to console
        metric_str = ", ".join(f"{k}: {v:.4f}" for k, v in metrics.items())
        await self.log(f"Step {self.current_step} - {metric_str}")
        
        # Log to experiment tracker
        if self.experiment_tracker:
            for name, value in metrics.items():
                await self.experiment_tracker.log_metric(name, value, step=self.current_step)
    
    def should_stop_early(self, metric_value: float) -> bool:
        """Check if should stop early."""
        if not self.config.early_stopping:
            return False
        
        # Check if metric improved
        if self.config.early_stopping_mode == "min":
            improved = metric_value < self.best_metric - self.config.early_stopping_threshold
        else:
            improved = metric_value > self.best_metric + self.config.early_stopping_threshold
        
        if improved:
            self.best_metric = metric_value
            self.patience_counter = 0
        else:
            self.patience_counter += 1
        
        return self.patience_counter >= self.config.early_stopping_patience


class Trainer(ABC):
    """Base trainer abstraction."""
    
    def __init__(
        self,
        model: Model,
        config: TrainerConfig | None = None,
        metrics: MetricCollection | None = None,
    ):
        """Initialize trainer.
        
        Args:
            model: Model to train
            config: Trainer configuration
            metrics: Metrics to track
        """
        self.model = model
        self.config = config or TrainerConfig()
        self.metrics = metrics or MetricCollection()
        
        self.state = TrainerState.IDLE
        self.context = TrainingContext(model, self.config)
    
    @abstractmethod
    async def train_step(
        self,
        batch: dict[str, Any],
        step: int,
    ) -> dict[str, float]:
        """Single training step.
        
        Args:
            batch: Input batch
            step: Current step
            
        Returns:
            Dictionary of metric name to value
        """
        pass
    
    @abstractmethod
    async def validation_step(
        self,
        batch: dict[str, Any],
        step: int,
    ) -> dict[str, float]:
        """Single validation step.
        
        Args:
            batch: Input batch
            step: Current step within validation
            
        Returns:
            Dictionary of metric name to value
        """
        pass
    
    async def train(
        self,
        train_loader: DataLoader,
        val_loader: DataLoader | None = None,
        test_loader: DataLoader | None = None,
    ) -> TrainingResult:
        """Train the model.
        
        Args:
            train_loader: Training data loader
            val_loader: Optional validation data loader
            test_loader: Optional test data loader
            
        Returns:
            TrainingResult with metrics and history
        """
        start_time = time.time()
        self.state = TrainerState.TRAINING
        
        try:
            # Training loop
            for epoch in range(self.config.epochs):
                self.context.current_epoch = epoch
                
                # Train epoch
                train_metrics = await self._train_epoch(train_loader)
                
                # Validation
                val_metrics = None
                if val_loader and self._should_validate(epoch):
                    val_metrics = await self._validate(val_loader)
                    
                    # Early stopping
                    if self.context.should_stop_early(val_metrics[self.config.early_stopping_metric]):
                        await self.context.log(f"Early stopping at epoch {epoch}")
                        break
                
                # Checkpoint
                if self.config.save_checkpoint:
                    await self._save_checkpoint(epoch, train_metrics, val_metrics)
            
            # Test evaluation
            test_metrics = None
            if test_loader:
                self.state = TrainerState.TESTING
                test_metrics = await self._test(test_loader)
            
            self.state = TrainerState.COMPLETED
            
        except KeyboardInterrupt:
            self.state = TrainerState.INTERRUPTED
            await self.context.log("Training interrupted by user")
        except Exception as e:
            self.state = TrainerState.FAILED
            await self.context.log(f"Training failed: {e}", level="ERROR")
            raise
        
        # Create result
        return TrainingResult(
            trainer_state=self.state,
            epochs_trained=self.context.current_epoch + 1,
            steps_trained=self.context.current_step,
            training_time=time.time() - start_time,
            train_metrics=self.context.metric_history,
            val_metrics=val_metrics,
            test_metrics=test_metrics,
            best_epoch=self.context.best_epoch if hasattr(self.context, "best_epoch") else None,
            best_metric=self.context.best_metric if self.context.best_metric != float("inf") else None,
            loss_history=self.context.loss_history,
        )
    
    async def _train_epoch(self, train_loader: DataLoader) -> dict[str, float]:
        """Train for one epoch."""
        epoch_metrics = {}
        step_count = 0
        
        async for batch in train_loader:
            # Training step
            step_metrics = await self.train_step(batch, self.context.current_step)
            
            # Update metrics
            for name, value in step_metrics.items():
                if name not in epoch_metrics:
                    epoch_metrics[name] = []
                epoch_metrics[name].append(value)
            
            # Log progress
            if self.context.current_step % self.config.log_interval == 0:
                await self.context.log_metrics(step_metrics, prefix="train")
            
            self.context.current_step += 1
            step_count += 1
            
            # Check max steps
            if self.config.max_steps and self.context.current_step >= self.config.max_steps:
                break
        
        # Average epoch metrics
        avg_metrics = {name: sum(values) / len(values) for name, values in epoch_metrics.items()}
        
        # Update history
        for name, value in avg_metrics.items():
            if name not in self.context.metric_history:
                self.context.metric_history[name] = []
            self.context.metric_history[name].append(value)
        
        return avg_metrics
    
    async def _validate(self, val_loader: DataLoader) -> dict[str, float]:
        """Run validation."""
        self.state = TrainerState.VALIDATING
        val_metrics = {}
        
        async for i, batch in enumerate(val_loader):
            step_metrics = await self.validation_step(batch, i)
            
            for name, value in step_metrics.items():
                if name not in val_metrics:
                    val_metrics[name] = []
                val_metrics[name].append(value)
        
        # Average metrics
        avg_metrics = {name: sum(values) / len(values) for name, values in val_metrics.items()}
        
        await self.context.log_metrics(avg_metrics, prefix="val")
        
        self.state = TrainerState.TRAINING
        return avg_metrics
    
    async def _test(self, test_loader: DataLoader) -> dict[str, float]:
        """Run test evaluation."""
        test_metrics = {}
        
        async for i, batch in enumerate(test_loader):
            step_metrics = await self.validation_step(batch, i)  # Reuse validation step
            
            for name, value in step_metrics.items():
                if name not in test_metrics:
                    test_metrics[name] = []
                test_metrics[name].append(value)
        
        # Average metrics
        avg_metrics = {name: sum(values) / len(values) for name, values in test_metrics.items()}
        
        await self.context.log_metrics(avg_metrics, prefix="test")
        
        return avg_metrics
    
    def _should_validate(self, epoch: int) -> bool:
        """Check if should run validation."""
        if self.config.val_check_steps:
            return self.context.current_step % self.config.val_check_steps == 0
        else:
            return (epoch + 1) % self.config.val_check_interval == 0
    
    async def _save_checkpoint(
        self,
        epoch: int,
        train_metrics: dict[str, float],
        val_metrics: dict[str, float] | None,
    ) -> None:
        """Save model checkpoint."""
        checkpoint_dir = Path(self.config.checkpoint_dir)
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        # Save model
        checkpoint_path = checkpoint_dir / f"epoch_{epoch}.ckpt"
        await self.model.save(checkpoint_path)
        
        # Track best model
        if val_metrics and self.config.early_stopping_metric in val_metrics:
            metric_value = val_metrics[self.config.early_stopping_metric]
            if self.context.should_stop_early(metric_value):
                self.context.best_epoch = epoch
                
                # Save as best
                best_path = checkpoint_dir / "best.ckpt"
                await self.model.save(best_path)