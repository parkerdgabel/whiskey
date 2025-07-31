"""Progress tracking visualization components."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta

from whiskey_ml.visualization.metrics_tracker import MetricsHandler, MetricSnapshot


@dataclass
class PipelineProgress:
    """Track progress of a pipeline."""

    name: str
    total_epochs: int
    current_epoch: int = 0
    state: str = "idle"
    start_time: datetime | None = None
    metrics: dict[str, float] = None

    @property
    def progress_percent(self) -> float:
        """Get progress as percentage."""
        if self.total_epochs == 0:
            return 0.0
        return (self.current_epoch / self.total_epochs) * 100

    @property
    def elapsed_time(self) -> timedelta:
        """Get elapsed time."""
        if self.start_time is None:
            return timedelta(0)
        return datetime.now() - self.start_time

    @property
    def estimated_remaining(self) -> timedelta | None:
        """Estimate remaining time."""
        if self.current_epoch == 0 or self.start_time is None:
            return None

        time_per_epoch = self.elapsed_time / self.current_epoch
        remaining_epochs = self.total_epochs - self.current_epoch
        return time_per_epoch * remaining_epochs


class ProgressTracker:
    """Track and display training progress."""

    def __init__(self):
        self.pipelines: dict[str, PipelineProgress] = {}
        self._update_task: asyncio.Task | None = None
        self._running = False

    def start_pipeline(self, name: str, total_epochs: int) -> None:
        """Start tracking a pipeline."""
        self.pipelines[name] = PipelineProgress(
            name=name, total_epochs=total_epochs, start_time=datetime.now()
        )

    def update_progress(
        self, name: str, epoch: int, metrics: dict[str, float] | None = None
    ) -> None:
        """Update pipeline progress."""
        if name in self.pipelines:
            pipeline = self.pipelines[name]
            pipeline.current_epoch = epoch
            if metrics:
                pipeline.metrics = metrics

    def complete_pipeline(self, name: str) -> None:
        """Mark pipeline as completed."""
        if name in self.pipelines:
            pipeline = self.pipelines[name]
            pipeline.state = "completed"
            pipeline.current_epoch = pipeline.total_epochs

    def fail_pipeline(self, name: str) -> None:
        """Mark pipeline as failed."""
        if name in self.pipelines:
            self.pipelines[name].state = "failed"

    async def start_display(self, update_interval: float = 1.0) -> None:
        """Start progress display loop."""
        if self._running:
            return

        self._running = True
        self._update_task = asyncio.create_task(self._update_loop(update_interval))

    async def stop_display(self) -> None:
        """Stop progress display."""
        self._running = False
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass

    async def _update_loop(self, interval: float) -> None:
        """Update display loop."""
        while self._running:
            self._display_progress()
            await asyncio.sleep(interval)

    def _display_progress(self) -> None:
        """Display current progress."""
        if not self.pipelines:
            return

        # Clear previous output (simple version)
        print("\033[2J\033[H")  # Clear screen and move to top

        print("=" * 80)
        print("ML Training Progress")
        print("=" * 80)

        for pipeline in self.pipelines.values():
            # Status emoji
            status_emoji = {"idle": "⏸️", "training": "🏃", "completed": "✅", "failed": "❌"}.get(
                pipeline.state, "❓"
            )

            # Progress bar
            bar_length = 40
            filled = int(bar_length * pipeline.progress_percent / 100)
            bar = "█" * filled + "░" * (bar_length - filled)

            print(f"\n{status_emoji} {pipeline.name}")
            print(f"   [{bar}] {pipeline.progress_percent:.1f}%")
            print(f"   Epoch: {pipeline.current_epoch}/{pipeline.total_epochs}")

            # Time info
            if pipeline.start_time:
                print(f"   Elapsed: {str(pipeline.elapsed_time).split('.')[0]}")
                if pipeline.estimated_remaining:
                    print(f"   ETA: {str(pipeline.estimated_remaining).split('.')[0]}")

            # Metrics
            if pipeline.metrics:
                metrics_str = ", ".join(f"{k}: {v:.4f}" for k, v in pipeline.metrics.items())
                print(f"   Metrics: {metrics_str}")


class RichProgressHandler(MetricsHandler):
    """Rich progress display using rich library (optional)."""

    def __init__(self):
        self.progress_tracker = ProgressTracker()
        self.has_rich = False
        self.progress = None
        self.tasks = {}

        try:
            from rich.console import Console
            from rich.progress import BarColumn, Progress, TextColumn, TimeRemainingColumn

            self.has_rich = True
            self.console = Console()
            self.progress = Progress(
                TextColumn("[bold blue]{task.fields[pipeline]}", justify="right"),
                BarColumn(bar_width=None),
                "[progress.percentage]{task.percentage:>3.1f}%",
                "•",
                TextColumn("{task.fields[status]}"),
                "•",
                TimeRemainingColumn(),
                console=self.console,
                refresh_per_second=4,
            )
        except ImportError:
            print("Rich not installed. Using simple progress display.")

    async def handle_metrics(self, snapshot: MetricSnapshot) -> None:
        """Update progress with metrics."""
        if self.has_rich and self.progress and snapshot.pipeline in self.tasks:
            task_id = self.tasks[snapshot.pipeline]

            # Update progress
            self.progress.update(
                task_id,
                completed=snapshot.epoch + 1,
                status=f"Loss: {snapshot.metrics.get('loss', 0):.4f}",
            )
        else:
            # Fallback to simple tracker
            self.progress_tracker.update_progress(
                snapshot.pipeline, snapshot.epoch + 1, snapshot.metrics
            )

    async def handle_state_change(self, pipeline: str, state: str) -> None:
        """Handle pipeline state changes."""
        if state == "training":
            # Extract total epochs from somewhere (would need to be passed)
            total_epochs = 10  # Default

            if self.has_rich and self.progress:
                # Create rich progress task
                task_id = self.progress.add_task(
                    f"Training {pipeline}",
                    total=total_epochs,
                    pipeline=pipeline,
                    status="Starting...",
                )
                self.tasks[pipeline] = task_id

                if not self.progress.live.is_started:
                    self.progress.start()
            else:
                # Use simple tracker
                self.progress_tracker.start_pipeline(pipeline, total_epochs)
                if not self.progress_tracker._running:
                    asyncio.create_task(self.progress_tracker.start_display())

        elif state in ("completed", "failed"):
            if self.has_rich and self.progress and pipeline in self.tasks:
                task_id = self.tasks[pipeline]
                if state == "completed":
                    self.progress.update(task_id, status="✅ Complete")
                else:
                    self.progress.update(task_id, status="❌ Failed")
            else:
                if state == "completed":
                    self.progress_tracker.complete_pipeline(pipeline)
                else:
                    self.progress_tracker.fail_pipeline(pipeline)

    async def finalize(self, pipeline: str) -> None:
        """Finalize progress display."""
        # Keep progress visible for completed pipelines
        pass
