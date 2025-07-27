"""TensorBoard integration for ML metrics visualization."""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from whiskey_ml.visualization.metrics_tracker import MetricsHandler, MetricSnapshot


class TensorBoardHandler(MetricsHandler):
    """Handler that writes metrics to TensorBoard format."""
    
    def __init__(self, log_dir: str | Path = "./tensorboard_logs"):
        self.log_dir = Path(log_dir)
        self.writers = {}
        self.has_tensorboard = False
        
        try:
            from torch.utils.tensorboard import SummaryWriter
            self.SummaryWriter = SummaryWriter
            self.has_tensorboard = True
        except ImportError:
            print("TensorBoard not available. Install with: pip install tensorboard")
    
    def _get_writer(self, pipeline: str):
        """Get or create writer for pipeline."""
        if not self.has_tensorboard:
            return None
        
        if pipeline not in self.writers:
            log_path = self.log_dir / pipeline / datetime.now().strftime("%Y%m%d-%H%M%S")
            self.writers[pipeline] = self.SummaryWriter(str(log_path))
        
        return self.writers[pipeline]
    
    async def handle_metrics(self, snapshot: MetricSnapshot) -> None:
        """Write metrics to TensorBoard."""
        writer = self._get_writer(snapshot.pipeline)
        if writer is None:
            return
        
        # Write each metric
        for metric_name, value in snapshot.metrics.items():
            tag = f"{snapshot.phase}/{metric_name}"
            writer.add_scalar(tag, value, snapshot.epoch)
        
        # Write learning rate if available
        if "learning_rate" in snapshot.metrics:
            writer.add_scalar("train/learning_rate", snapshot.metrics["learning_rate"], snapshot.epoch)
        
        # Flush to ensure data is written
        writer.flush()
    
    async def handle_state_change(self, pipeline: str, state: str) -> None:
        """Log state changes."""
        writer = self._get_writer(pipeline)
        if writer is None:
            return
        
        # Add text summary for important state changes
        if state == "training":
            writer.add_text("status", "Training started", 0)
        elif state == "completed":
            writer.add_text("status", "Training completed successfully", 1)
        elif state == "failed":
            writer.add_text("status", "Training failed", 1)
    
    async def finalize(self, pipeline: str) -> None:
        """Close TensorBoard writer."""
        if pipeline in self.writers:
            self.writers[pipeline].close()
            del self.writers[pipeline]
            
            print(f"\n📊 TensorBoard logs saved to: {self.log_dir / pipeline}")
            print(f"   Run: tensorboard --logdir {self.log_dir / pipeline}")


class WandBHandler(MetricsHandler):
    """Weights & Biases integration for metrics tracking."""
    
    def __init__(self, project: str = "whiskey-ml", entity: str | None = None):
        self.project = project
        self.entity = entity
        self.runs = {}
        self.has_wandb = False
        
        try:
            import wandb
            self.wandb = wandb
            self.has_wandb = True
        except ImportError:
            print("Weights & Biases not available. Install with: pip install wandb")
    
    def _get_run(self, pipeline: str):
        """Get or create W&B run."""
        if not self.has_wandb:
            return None
        
        if pipeline not in self.runs:
            run = self.wandb.init(
                project=self.project,
                entity=self.entity,
                name=pipeline,
                reinit=True
            )
            self.runs[pipeline] = run
        
        return self.runs[pipeline]
    
    async def handle_metrics(self, snapshot: MetricSnapshot) -> None:
        """Log metrics to W&B."""
        run = self._get_run(snapshot.pipeline)
        if run is None:
            return
        
        # Prepare metrics with phase prefix
        metrics = {
            f"{snapshot.phase}/{k}": v 
            for k, v in snapshot.metrics.items()
        }
        metrics["epoch"] = snapshot.epoch
        
        # Log to W&B
        run.log(metrics)
    
    async def handle_state_change(self, pipeline: str, state: str) -> None:
        """Log state changes to W&B."""
        run = self._get_run(pipeline)
        if run is None:
            return
        
        # Log state as a custom metric
        run.log({"state": state})
    
    async def finalize(self, pipeline: str) -> None:
        """Finish W&B run."""
        if pipeline in self.runs:
            run = self.runs[pipeline]
            run.finish()
            del self.runs[pipeline]
            
            print(f"\n🌐 W&B run finished: {run.url}")


class MLFlowHandler(MetricsHandler):
    """MLflow integration for experiment tracking."""
    
    def __init__(self, tracking_uri: str | None = None, experiment_name: str = "whiskey-ml"):
        self.tracking_uri = tracking_uri
        self.experiment_name = experiment_name
        self.runs = {}
        self.has_mlflow = False
        
        try:
            import mlflow
            self.mlflow = mlflow
            self.has_mlflow = True
            
            if tracking_uri:
                mlflow.set_tracking_uri(tracking_uri)
            
            # Set or create experiment
            mlflow.set_experiment(experiment_name)
        except ImportError:
            print("MLflow not available. Install with: pip install mlflow")
    
    def _get_run(self, pipeline: str):
        """Get or create MLflow run."""
        if not self.has_mlflow:
            return None
        
        if pipeline not in self.runs:
            run = self.mlflow.start_run(run_name=pipeline)
            self.runs[pipeline] = run
        
        return self.runs[pipeline]
    
    async def handle_metrics(self, snapshot: MetricSnapshot) -> None:
        """Log metrics to MLflow."""
        if not self.has_mlflow:
            return
        
        run = self._get_run(snapshot.pipeline)
        
        # Log metrics with phase prefix
        for metric_name, value in snapshot.metrics.items():
            self.mlflow.log_metric(
                f"{snapshot.phase}_{metric_name}",
                value,
                step=snapshot.epoch
            )
    
    async def handle_state_change(self, pipeline: str, state: str) -> None:
        """Log state changes."""
        if not self.has_mlflow:
            return
        
        if state == "training":
            # Log pipeline parameters
            self.mlflow.log_param("pipeline_name", pipeline)
            self.mlflow.log_param("start_time", datetime.now().isoformat())
        elif state in ("completed", "failed"):
            self.mlflow.log_param("end_state", state)
            self.mlflow.log_param("end_time", datetime.now().isoformat())
    
    async def finalize(self, pipeline: str) -> None:
        """End MLflow run."""
        if pipeline in self.runs:
            self.mlflow.end_run()
            del self.runs[pipeline]
            
            print(f"\n🔬 MLflow run completed for {pipeline}")