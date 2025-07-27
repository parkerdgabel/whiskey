"""Metrics tracking and visualization components."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from whiskey import Component, Whiskey


@dataclass
class MetricSnapshot:
    """Snapshot of metrics at a point in time."""
    
    pipeline: str
    epoch: int
    metrics: dict[str, float]
    timestamp: datetime
    phase: str = "train"  # train, val, test


class MetricsHandler(ABC):
    """Base class for metrics visualization handlers."""
    
    @abstractmethod
    async def handle_metrics(self, snapshot: MetricSnapshot) -> None:
        """Handle a metrics snapshot."""
        pass
    
    @abstractmethod
    async def handle_state_change(self, pipeline: str, state: str) -> None:
        """Handle pipeline state change."""
        pass
    
    @abstractmethod
    async def finalize(self, pipeline: str) -> None:
        """Finalize visualization for a pipeline."""
        pass


class ConsoleMetricsHandler(MetricsHandler):
    """Simple console output for metrics."""
    
    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.start_times = {}
        self.last_metrics = {}
    
    async def handle_metrics(self, snapshot: MetricSnapshot) -> None:
        """Print metrics to console."""
        if not self.verbose and snapshot.phase == "train":
            return
        
        # Format metrics
        metrics_str = ", ".join(
            f"{name}: {value:.4f}" for name, value in snapshot.metrics.items()
        )
        
        # Calculate improvement
        key = f"{snapshot.pipeline}_{snapshot.phase}"
        improvement_str = ""
        if key in self.last_metrics:
            last = self.last_metrics[key]
            if "loss" in snapshot.metrics and "loss" in last:
                diff = last["loss"] - snapshot.metrics["loss"]
                improvement_str = f" (Δ{diff:+.4f})"
        
        self.last_metrics[key] = snapshot.metrics
        
        # Print with emoji based on phase
        emoji = {"train": "🏋️", "val": "📊", "test": "🎯"}.get(snapshot.phase, "📈")
        print(
            f"{emoji} [{snapshot.phase.upper()}] "
            f"Epoch {snapshot.epoch}: {metrics_str}{improvement_str}"
        )
    
    async def handle_state_change(self, pipeline: str, state: str) -> None:
        """Print state changes."""
        if state == "training":
            self.start_times[pipeline] = datetime.now()
            print(f"\n🚀 Training started for {pipeline}")
        elif state == "completed":
            if pipeline in self.start_times:
                duration = datetime.now() - self.start_times[pipeline]
                print(f"\n✅ Training completed in {duration.total_seconds():.1f}s")
        elif state == "failed":
            print(f"\n❌ Training failed for {pipeline}")
    
    async def finalize(self, pipeline: str) -> None:
        """Print final summary."""
        if pipeline in self.last_metrics:
            print(f"\n📋 Final metrics for {pipeline}:")
            for phase_key, metrics in self.last_metrics.items():
                if phase_key.startswith(pipeline):
                    phase = phase_key.split("_")[1]
                    metrics_str = ", ".join(
                        f"{name}: {value:.4f}" for name, value in metrics.items()
                    )
                    print(f"   {phase}: {metrics_str}")


@Component
class MetricsTracker:
    """Central metrics tracking component that aggregates and distributes metrics."""
    
    def __init__(self):
        self.handlers: list[MetricsHandler] = []
        self.metrics_history: dict[str, list[MetricSnapshot]] = defaultdict(list)
        self.active_pipelines: set[str] = set()
    
    def add_handler(self, handler: MetricsHandler) -> None:
        """Add a visualization handler."""
        self.handlers.append(handler)
    
    def remove_handler(self, handler: MetricsHandler) -> None:
        """Remove a visualization handler."""
        if handler in self.handlers:
            self.handlers.remove(handler)
    
    async def register_with_app(self, app: Whiskey) -> None:
        """Register event handlers with the application."""
        @app.on("ml.training.metrics")
        async def on_metrics(data: dict[str, Any]):
            snapshot = MetricSnapshot(
                pipeline=data["pipeline"],
                epoch=data["epoch"],
                metrics=data["metrics"],
                timestamp=datetime.fromisoformat(data["timestamp"]),
                phase="train"
            )
            await self.handle_metrics(snapshot)
        
        @app.on("ml.validation.metrics")
        async def on_val_metrics(data: dict[str, Any]):
            snapshot = MetricSnapshot(
                pipeline=data["pipeline"],
                epoch=data["epoch"],
                metrics=data["metrics"],
                timestamp=datetime.fromisoformat(data["timestamp"]),
                phase="val"
            )
            await self.handle_metrics(snapshot)
        
        @app.on("ml.pipeline.state_changed")
        async def on_state_change(data: dict[str, Any]):
            await self.handle_state_change(data["name"], data["state"])
        
        @app.on("ml.pipeline.completed")
        async def on_complete(data: dict[str, Any]):
            await self.finalize_pipeline(data["name"])
        
        @app.on("ml.pipeline.failed")
        async def on_failed(data: dict[str, Any]):
            await self.finalize_pipeline(data["name"])
    
    async def handle_metrics(self, snapshot: MetricSnapshot) -> None:
        """Process and distribute metrics snapshot."""
        # Store in history
        self.metrics_history[snapshot.pipeline].append(snapshot)
        
        # Distribute to all handlers
        await asyncio.gather(
            *[handler.handle_metrics(snapshot) for handler in self.handlers],
            return_exceptions=True
        )
    
    async def handle_state_change(self, pipeline: str, state: str) -> None:
        """Process state change."""
        if state == "training":
            self.active_pipelines.add(pipeline)
        elif state in ("completed", "failed"):
            self.active_pipelines.discard(pipeline)
        
        # Distribute to all handlers
        await asyncio.gather(
            *[handler.handle_state_change(pipeline, state) for handler in self.handlers],
            return_exceptions=True
        )
    
    async def finalize_pipeline(self, pipeline: str) -> None:
        """Finalize tracking for a pipeline."""
        # Distribute to all handlers
        await asyncio.gather(
            *[handler.finalize(pipeline) for handler in self.handlers],
            return_exceptions=True
        )
        
        # Clean up if needed (keep history for analysis)
        self.active_pipelines.discard(pipeline)
    
    def get_history(self, pipeline: str) -> list[MetricSnapshot]:
        """Get metrics history for a pipeline."""
        return self.metrics_history.get(pipeline, [])
    
    def get_latest_metrics(self, pipeline: str) -> dict[str, float] | None:
        """Get latest metrics for a pipeline."""
        history = self.get_history(pipeline)
        if history:
            return history[-1].metrics
        return None
    
    def plot_metrics(self, pipeline: str, metric_names: list[str] | None = None) -> None:
        """Generate a simple plot of metrics (requires matplotlib)."""
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            print("matplotlib not installed. Install with: pip install matplotlib")
            return
        
        history = self.get_history(pipeline)
        if not history:
            print(f"No metrics history for pipeline: {pipeline}")
            return
        
        # Group by phase
        phases = defaultdict(list)
        for snapshot in history:
            phases[snapshot.phase].append(snapshot)
        
        # Determine metrics to plot
        if metric_names is None:
            metric_names = list(history[0].metrics.keys())
        
        # Create subplots
        fig, axes = plt.subplots(len(metric_names), 1, figsize=(10, 4 * len(metric_names)))
        if len(metric_names) == 1:
            axes = [axes]
        
        # Plot each metric
        for idx, metric_name in enumerate(metric_names):
            ax = axes[idx]
            
            for phase, snapshots in phases.items():
                epochs = [s.epoch for s in snapshots if metric_name in s.metrics]
                values = [s.metrics[metric_name] for s in snapshots if metric_name in s.metrics]
                
                if epochs:
                    ax.plot(epochs, values, marker='o', label=phase)
            
            ax.set_xlabel('Epoch')
            ax.set_ylabel(metric_name)
            ax.set_title(f'{metric_name} over training')
            ax.legend()
            ax.grid(True)
        
        plt.suptitle(f'Training Metrics for {pipeline}')
        plt.tight_layout()
        plt.show()