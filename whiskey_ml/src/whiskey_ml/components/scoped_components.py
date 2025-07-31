"""Scope-aware ML components that demonstrate proper lifecycle management.

This module provides example components that leverage Whiskey's built-in scopes
to manage resources appropriately during different phases of training.
These components show how to:

1. Use experiment scope for long-lived resources
2. Use training scope for model-specific resources
3. Use epoch scope for per-epoch resources
4. Use evaluation scope for validation resources

Components are registered with @app.scoped(Component, scope_name="scope_name")
and resolved within the appropriate scope context manager.

Classes:
    ExperimentLogger: Long-lived experiment tracking
    ModelCheckpointer: Training-scoped model saving
    EpochMetricsCollector: Per-epoch metrics aggregation
    ValidationRunner: Evaluation-scoped validation
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any

from whiskey import component


@component
class ExperimentLogger:
    """Experiment-scoped logger for tracking experiment-wide metrics.

    This component is designed to be used within experiment scope.
    It persists for the entire experiment and tracks experiment-level
    metadata and aggregated metrics.
    """

    def __init__(self, experiment_id: str | None = None):
        self.experiment_id = experiment_id or f"exp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.start_time = datetime.now()
        self.experiment_metadata = {}
        self.run_history = []
        self._log_file = None

    async def log_experiment_start(self, config: dict[str, Any]) -> None:
        """Log experiment start with configuration."""
        self.experiment_metadata.update(
            {
                "experiment_id": self.experiment_id,
                "start_time": self.start_time.isoformat(),
                "config": config,
            }
        )

        # Initialize log file
        log_dir = Path("./experiment_logs")
        log_dir.mkdir(exist_ok=True)
        self._log_file = log_dir / f"{self.experiment_id}.log"

        with open(self._log_file, "w") as f:
            f.write(f"[{datetime.now().isoformat()}] Experiment started: {self.experiment_id}\n")
            f.write(f"Configuration: {config}\n")

    async def log_run_result(self, pipeline_name: str, result: dict[str, Any]) -> None:
        """Log results from a pipeline run."""
        run_data = {
            "pipeline": pipeline_name,
            "timestamp": datetime.now().isoformat(),
            "result": result,
        }
        self.run_history.append(run_data)

        if self._log_file:
            with open(self._log_file, "a") as f:
                f.write(f"[{run_data['timestamp']}] Pipeline {pipeline_name} completed\n")
                f.write(f"Result: {result}\n")

    async def finalize_experiment(self) -> None:
        """Called when experiment scope ends."""
        end_time = datetime.now()
        duration = end_time - self.start_time

        if self._log_file:
            with open(self._log_file, "a") as f:
                f.write(f"[{end_time.isoformat()}] Experiment completed\n")
                f.write(f"Duration: {duration.total_seconds():.2f}s\n")
                f.write(f"Total runs: {len(self.run_history)}\n")

        print(f"🔬 Experiment {self.experiment_id} completed in {duration.total_seconds():.2f}s")
        print(f"   Total runs: {len(self.run_history)}")


@component
class ModelCheckpointer:
    """Training-scoped component for saving model checkpoints.

    This component lives within the training scope and handles
    model checkpointing during training. It's cleaned up when
    training ends.
    """

    def __init__(self, checkpoint_dir: str = "./checkpoints"):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.best_metric = float("inf")
        self.best_checkpoint_path = None
        self.checkpoint_count = 0

    async def save_checkpoint(self, model: Any, epoch: int, metrics: dict[str, float]) -> str:
        """Save a model checkpoint."""
        checkpoint_name = f"checkpoint_epoch_{epoch:04d}.ckpt"
        checkpoint_path = self.checkpoint_dir / checkpoint_name

        # Save model (mock implementation)
        if hasattr(model, "save"):
            await model.save(checkpoint_path)
        else:
            # Mock save for testing
            checkpoint_path.write_text(f"Model checkpoint at epoch {epoch}")

        self.checkpoint_count += 1

        # Check if this is the best checkpoint
        current_metric = metrics.get("loss", float("inf"))
        if current_metric < self.best_metric:
            self.best_metric = current_metric
            self.best_checkpoint_path = checkpoint_path

            # Save as best model
            best_path = self.checkpoint_dir / "best_model.ckpt"
            if hasattr(model, "save"):
                await model.save(best_path)
            else:
                best_path.write_text(f"Best model at epoch {epoch}")

        return str(checkpoint_path)

    async def finalize_training(self) -> None:
        """Called when training scope ends."""
        print(f"💾 Training completed with {self.checkpoint_count} checkpoints")
        if self.best_checkpoint_path:
            print(f"   Best model: {self.best_checkpoint_path} (loss: {self.best_metric:.4f})")


@component
class EpochMetricsCollector:
    """Epoch-scoped component for collecting metrics during an epoch.

    This component is recreated for each epoch and collects
    batch-level metrics, aggregating them at the end of the epoch.
    """

    def __init__(self):
        self.batch_metrics = []
        self.epoch_start_time = datetime.now()
        self.batch_count = 0

    def collect_batch_metrics(self, batch_idx: int, metrics: dict[str, float]) -> None:
        """Collect metrics from a batch."""
        self.batch_metrics.append(
            {"batch": batch_idx, "metrics": metrics, "timestamp": datetime.now().isoformat()}
        )
        self.batch_count += 1

    def get_epoch_summary(self) -> dict[str, float]:
        """Get aggregated metrics for the epoch."""
        if not self.batch_metrics:
            return {}

        # Aggregate metrics
        all_metric_names = set()
        for batch_data in self.batch_metrics:
            all_metric_names.update(batch_data["metrics"].keys())

        aggregated = {}
        for metric_name in all_metric_names:
            values = [
                batch_data["metrics"][metric_name]
                for batch_data in self.batch_metrics
                if metric_name in batch_data["metrics"]
            ]
            aggregated[f"avg_{metric_name}"] = sum(values) / len(values)
            aggregated[f"min_{metric_name}"] = min(values)
            aggregated[f"max_{metric_name}"] = max(values)

        # Add timing info
        epoch_duration = datetime.now() - self.epoch_start_time
        aggregated["epoch_time"] = epoch_duration.total_seconds()
        aggregated["batches_processed"] = self.batch_count

        return aggregated

    async def finalize_epoch(self) -> None:
        """Called when epoch scope ends."""
        summary = self.get_epoch_summary()
        print(
            f"📊 Epoch completed: {self.batch_count} batches in {summary.get('epoch_time', 0):.2f}s"
        )


@component
class ValidationRunner:
    """Evaluation-scoped component for running validation.

    This component is used within evaluation scope to run
    validation procedures isolated from training.
    """

    def __init__(self):
        self.validation_start_time = datetime.now()
        self.validation_results = {}
        self.samples_processed = 0

    async def run_validation(self, model: Any, val_loader: Any) -> dict[str, float]:
        """Run validation on the model."""
        print("🔍 Starting validation...")

        # Mock validation process
        validation_metrics = {}
        batch_count = 0

        # Simulate validation batches
        if hasattr(val_loader, "__iter__"):
            for batch in val_loader:
                await self._process_validation_batch(model, batch)
                batch_count += 1
        else:
            # Mock validation for testing
            for i in range(5):  # Simulate 5 validation batches
                await self._process_validation_batch(model, {"data": f"batch_{i}"})
                batch_count += 1

        # Compute final validation metrics
        validation_metrics = {
            "val_loss": 0.25 + 0.1 * (batch_count % 3),  # Mock loss
            "val_accuracy": 0.85 + 0.05 * (batch_count % 2),  # Mock accuracy
            "samples_processed": self.samples_processed,
            "validation_time": (datetime.now() - self.validation_start_time).total_seconds(),
        }

        self.validation_results = validation_metrics
        return validation_metrics

    async def _process_validation_batch(self, model: Any, batch: Any) -> None:
        """Process a single validation batch."""
        # Mock batch processing
        await asyncio.sleep(0.01)  # Simulate processing time
        self.samples_processed += 32  # Mock batch size

    async def finalize_evaluation(self) -> None:
        """Called when evaluation scope ends."""
        duration = (datetime.now() - self.validation_start_time).total_seconds()
        print(f"✅ Validation completed in {duration:.2f}s")
        if self.validation_results:
            print(f"   Results: {self.validation_results}")


@component
class BatchProcessor:
    """Batch-scoped component for processing individual batches.

    This component is recreated for each batch and handles
    batch-specific processing and cleanup.

    Note: Use batch scope sparingly as it can impact performance.
    """

    def __init__(self):
        self.batch_start_time = datetime.now()
        self.processed_samples = 0
        self.batch_metadata = {}

    async def process_batch(self, batch_data: Any, batch_idx: int) -> dict[str, Any]:
        """Process a single batch."""
        self.batch_metadata = {
            "batch_idx": batch_idx,
            "start_time": self.batch_start_time.isoformat(),
            "batch_size": getattr(batch_data, "size", 32),  # Mock batch size
        }

        # Mock processing
        await asyncio.sleep(0.005)  # Simulate processing time
        self.processed_samples = self.batch_metadata["batch_size"]

        processing_time = (datetime.now() - self.batch_start_time).total_seconds()

        return {
            "batch_idx": batch_idx,
            "samples_processed": self.processed_samples,
            "processing_time": processing_time,
            "throughput": self.processed_samples / processing_time if processing_time > 0 else 0,
        }

    def __del__(self):
        """Cleanup when batch processing is done."""
        # This would be called when the batch scope ends
        # In practice, you'd use dispose() method instead
        pass


# Utility functions for registering scoped components


def register_experiment_components(app) -> None:
    """Register experiment-scoped components."""
    app.scoped(ExperimentLogger, scope_name="experiment")


def register_training_components(app) -> None:
    """Register training-scoped components."""
    app.scoped(ModelCheckpointer, scope_name="training")


def register_epoch_components(app) -> None:
    """Register epoch-scoped components."""
    app.scoped(EpochMetricsCollector, scope_name="epoch")


def register_evaluation_components(app) -> None:
    """Register evaluation-scoped components."""
    app.scoped(ValidationRunner, scope_name="evaluation")


def register_all_scoped_components(app) -> None:
    """Register all scoped ML components."""
    register_experiment_components(app)
    register_training_components(app)
    register_epoch_components(app)
    register_evaluation_components(app)
