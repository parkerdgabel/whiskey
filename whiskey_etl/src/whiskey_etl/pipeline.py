"""Core pipeline abstractions for ETL."""

from __future__ import annotations

import asyncio
from datetime import datetime
from enum import Enum
from typing import (
    Any,
    AsyncIterator,
    Callable,
)

from whiskey import Container

from .errors import PipelineError, TransformError
from .validation import RecordValidator, ValidationMode
from .validation_reporting import ValidationReport, ValidationReporter


class PipelineState(Enum):
    """Pipeline execution states."""

    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"
    COMPLETED = "completed"


class StageType(Enum):
    """Types of pipeline stages."""

    EXTRACT = "extract"
    TRANSFORM = "transform"
    LOAD = "load"


class PipelineContext:
    """Runtime context for pipeline execution."""

    def __init__(
        self,
        pipeline_name: str,
        run_id: str,
        container: Container,
        config: dict[str, Any] | None = None,
    ):
        self.pipeline_name = pipeline_name
        self.run_id = run_id
        self.container = container
        self.config = config or {}
        self.start_time = datetime.now()
        self.end_time: datetime | None = None
        self.state = PipelineState.IDLE
        self.metrics: dict[str, Any] = {
            "records_processed": 0,
            "records_failed": 0,
            "stages_completed": 0,
        }
        self.checkpoints: dict[str, Any] = {}
        self.errors: list[Exception] = []

    async def log(self, message: str, level: str = "INFO") -> None:
        """Log a message."""
        # TODO: Integrate with logging system
        timestamp = datetime.now().isoformat()
        print(f"[{timestamp}] [{level}] {self.pipeline_name}: {message}")

    async def emit_metrics(self) -> None:
        """Emit pipeline metrics."""
        # TODO: Integrate with monitoring system
        duration = (self.end_time or datetime.now()) - self.start_time
        await self.log(
            f"Pipeline metrics - Duration: {duration}, "
            f"Records: {self.metrics['records_processed']}, "
            f"Failed: {self.metrics['records_failed']}"
        )

    def checkpoint(self, stage: str, data: Any) -> None:
        """Save a checkpoint."""
        self.checkpoints[stage] = {
            "timestamp": datetime.now(),
            "data": data,
        }

    def get_checkpoint(self, stage: str) -> Any | None:
        """Retrieve a checkpoint."""
        checkpoint = self.checkpoints.get(stage)
        return checkpoint["data"] if checkpoint else None


class Stage:
    """Pipeline stage definition."""

    def __init__(
        self,
        name: str,
        stage_type: StageType,
        handler: str | Callable | None = None,
        parallel: bool = False,
        workers: int = 1,
        config: dict[str, Any] | None = None,
    ):
        self.name = name
        self.stage_type = stage_type
        self.handler = handler
        self.parallel = parallel
        self.workers = workers
        self.config = config or {}


class Pipeline:
    """Base class for ETL pipelines."""

    # Required attributes (to be defined by subclasses)
    source: str | None = None
    sink: str | None = None
    transforms: list[str | Callable] = []

    # Optional configuration
    batch_size: int = 1000
    max_retries: int = 3
    retry_delay: float = 1.0
    error_handler: str | None = None
    enable_checkpointing: bool = False

    # Validation configuration
    validators: RecordValidator | None = None
    validation_mode: ValidationMode = ValidationMode.FAIL
    enable_validation_reporting: bool = True
    quarantine_sink: str | None = None

    def __init__(self, context: PipelineContext):
        self.context = context
        self._validation_report: ValidationReport | None = None
        self._validation_reporter: ValidationReporter | None = None

    # Lifecycle hooks (optional)
    async def on_start(self, context: PipelineContext) -> None:
        """Called when pipeline starts."""
        pass

    async def on_complete(self, context: PipelineContext) -> None:
        """Called when pipeline completes successfully."""
        pass

    async def on_error(self, error: Exception, record: Any | None = None) -> None:
        """Called when an error occurs."""
        pass

    async def on_batch_complete(self, batch_num: int, records_processed: int) -> None:
        """Called after each batch is processed."""
        pass

    # Optional custom stages method
    def get_stages(self) -> list[Stage]:
        """Get custom pipeline stages.

        Override this to define complex multi-stage pipelines.
        """
        stages = []

        # Extract stage
        if self.source:
            stages.append(
                Stage(
                    name="extract",
                    stage_type=StageType.EXTRACT,
                    handler=self.source,
                )
            )

        # Transform stages
        for i, transform in enumerate(self.transforms):
            stages.append(
                Stage(
                    name=f"transform_{i}",
                    stage_type=StageType.TRANSFORM,
                    handler=transform,
                )
            )

        # Load stage
        if self.sink:
            stages.append(
                Stage(
                    name="load",
                    stage_type=StageType.LOAD,
                    handler=self.sink,
                )
            )

        return stages


class PipelineResult:
    """Result of pipeline execution."""

    def __init__(
        self,
        pipeline_name: str,
        run_id: str,
        state: PipelineState,
        records_processed: int,
        records_failed: int,
        start_time: datetime,
        end_time: datetime,
        errors: list[Exception] | None = None,
    ):
        self.pipeline_name = pipeline_name
        self.run_id = run_id
        self.state = state
        self.records_processed = records_processed
        self.records_failed = records_failed
        self.start_time = start_time
        self.end_time = end_time
        self.duration = end_time - start_time
        self.errors = errors or []

    @property
    def is_success(self) -> bool:
        """Check if pipeline succeeded."""
        return self.state == PipelineState.COMPLETED

    @property
    def error_rate(self) -> float:
        """Calculate error rate."""
        total = self.records_processed + self.records_failed
        return self.records_failed / total if total > 0 else 0.0


class PipelineRegistry:
    """Registry for pipeline definitions."""

    def __init__(self):
        self._pipelines: dict[str, dict[str, Any]] = {}

    def register(self, name: str, pipeline_class: type[Pipeline], **metadata) -> None:
        """Register a pipeline."""
        self._pipelines[name] = {
            "class": pipeline_class,
            "metadata": metadata,
        }

    def get(self, name: str) -> type[Pipeline] | None:
        """Get pipeline class by name."""
        entry = self._pipelines.get(name)
        return entry["class"] if entry else None

    def get_metadata(self, name: str) -> dict[str, Any] | None:
        """Get pipeline metadata."""
        entry = self._pipelines.get(name)
        return entry["metadata"] if entry else None

    def list_pipelines(self) -> dict[str, dict[str, Any]]:
        """List all registered pipelines."""
        return {
            name: {
                "source": getattr(entry["class"], "source", None),
                "sink": getattr(entry["class"], "sink", None),
                "transforms": getattr(entry["class"], "transforms", []),
                **entry["metadata"],
            }
            for name, entry in self._pipelines.items()
        }


class PipelineManager:
    """Manages pipeline execution."""

    def __init__(
        self,
        container: Container,
        pipeline_registry: PipelineRegistry,
        source_registry: Any,  # Avoid circular import
        sink_registry: Any,
        transform_registry: Any,
        default_batch_size: int = 1000,
        enable_checkpointing: bool = False,
        enable_monitoring: bool = True,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        self.container = container
        self.pipeline_registry = pipeline_registry
        self.source_registry = source_registry
        self.sink_registry = sink_registry
        self.transform_registry = transform_registry
        self.default_batch_size = default_batch_size
        self.enable_checkpointing = enable_checkpointing
        self.enable_monitoring = enable_monitoring
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._running_pipelines: dict[str, PipelineContext] = {}
        self._run_counter = 0

    async def initialize(self) -> None:
        """Initialize the pipeline manager."""
        # TODO: Setup monitoring, checkpointing, etc.
        pass

    async def shutdown(self) -> None:
        """Shutdown the pipeline manager."""
        # Stop all running pipelines
        for context in list(self._running_pipelines.values()):
            await self._stop_pipeline(context)

    async def run(self, pipeline_name: str, **kwargs) -> PipelineResult:
        """Run a pipeline.

        Args:
            pipeline_name: Name of registered pipeline
            **kwargs: Runtime arguments passed to source/sink/transforms

        Returns:
            PipelineResult with execution details
        """
        # Get pipeline class
        pipeline_class = self.pipeline_registry.get(pipeline_name)
        if not pipeline_class:
            raise PipelineError(pipeline_name, f"Pipeline '{pipeline_name}' not found")

        # Generate run ID
        self._run_counter += 1
        run_id = f"{pipeline_name}_{self._run_counter}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Create context
        context = PipelineContext(
            pipeline_name=pipeline_name,
            run_id=run_id,
            container=self.container,
            config=kwargs,
        )

        # Store running pipeline
        self._running_pipelines[run_id] = context

        try:
            # Create pipeline instance
            pipeline = pipeline_class(context)

            # Run pipeline
            await self._execute_pipeline(pipeline, context)

            # Create result
            result = PipelineResult(
                pipeline_name=pipeline_name,
                run_id=run_id,
                state=context.state,
                records_processed=context.metrics["records_processed"],
                records_failed=context.metrics["records_failed"],
                start_time=context.start_time,
                end_time=context.end_time or datetime.now(),
                errors=context.errors,
            )

            return result

        finally:
            # Remove from running
            self._running_pipelines.pop(run_id, None)

    async def _execute_pipeline(
        self,
        pipeline: Pipeline,
        context: PipelineContext,
    ) -> None:
        """Execute a pipeline."""
        try:
            # Update state
            context.state = PipelineState.STARTING
            await context.log(f"Starting pipeline run: {context.run_id}")

            # Call on_start hook
            await pipeline.on_start(context)

            # Get stages
            stages = pipeline.get_stages()
            if not stages:
                raise PipelineError(context.pipeline_name, "Pipeline has no stages defined")

            # Update state
            context.state = PipelineState.RUNNING

            # Execute stages
            data_stream: AsyncIterator[Any] | None = None

            for stage in stages:
                await context.log(f"Executing stage: {stage.name}")

                if stage.stage_type == StageType.EXTRACT:
                    data_stream = await self._execute_extract(stage, pipeline, context)
                elif stage.stage_type == StageType.TRANSFORM:
                    data_stream = await self._execute_transform(
                        stage, data_stream, pipeline, context
                    )
                elif stage.stage_type == StageType.LOAD:
                    await self._execute_load(stage, data_stream, pipeline, context)

                context.metrics["stages_completed"] += 1

            # Update state
            context.state = PipelineState.COMPLETED
            context.end_time = datetime.now()

            # Call on_complete hook
            await pipeline.on_complete(context)
            await context.emit_metrics()

        except Exception as e:
            # Update state
            context.state = PipelineState.FAILED
            context.end_time = datetime.now()
            context.errors.append(e)

            # Call error handler
            await pipeline.on_error(e)

            # Re-raise
            raise

    async def _execute_extract(
        self,
        stage: Stage,
        pipeline: Pipeline,
        context: PipelineContext,
    ) -> AsyncIterator[Any]:
        """Execute extract stage."""
        # Get source
        source_name = stage.handler
        source_class = self.source_registry.get(source_name)
        if not source_class:
            raise PipelineError(
                context.pipeline_name,
                f"Source '{source_name}' not found",
                stage=stage.name,
            )

        # Resolve source instance
        source = await self.container.resolve(source_class)

        # Extract data
        async def extract_generator():
            try:
                # Call extract method with config
                async for record in source.extract(**context.config):
                    yield record
            except Exception as e:
                raise PipelineError(
                    context.pipeline_name,
                    f"Extract failed: {e}",
                    stage=stage.name,
                ) from e

        return extract_generator()

    async def _execute_transform(
        self,
        stage: Stage,
        data_stream: AsyncIterator[Any],
        pipeline: Pipeline,
        context: PipelineContext,
    ) -> AsyncIterator[Any]:
        """Execute transform stage."""
        if not data_stream:
            raise PipelineError(
                context.pipeline_name,
                "No data stream for transform stage",
                stage=stage.name,
            )

        # Get transform function
        transform = stage.handler
        if isinstance(transform, str):
            transform = self.transform_registry.get(transform)
            if not transform:
                raise PipelineError(
                    context.pipeline_name,
                    f"Transform '{stage.handler}' not found",
                    stage=stage.name,
                )

        # Apply transform
        async def transform_generator():
            async for record in data_stream:
                try:
                    # Apply transform - check if it needs DI resolution
                    import inspect

                    sig = inspect.signature(transform)
                    params = list(sig.parameters.values())

                    # If transform only takes record parameter, call directly
                    if len(params) == 1 and params[0].name == "record":
                        result = await transform(record)
                    else:
                        # Otherwise, use DI resolution
                        from whiskey.core.decorators import inject

                        injected_transform = inject(transform)
                        result = await injected_transform(record)

                    if result is not None:
                        yield result
                except Exception as e:
                    # Handle transform error
                    context.metrics["records_failed"] += 1
                    await pipeline.on_error(e, record)

                    # Retry logic
                    for retry in range(pipeline.max_retries):
                        await asyncio.sleep(pipeline.retry_delay * (retry + 1))
                        try:
                            # Apply transform again with same logic
                            if len(params) == 1 and params[0].name == "record":
                                result = await transform(record)
                            else:
                                from whiskey.core.decorators import inject

                                injected_transform = inject(transform)
                                result = await injected_transform(record)

                            if result is not None:
                                yield result
                                break
                        except Exception as e:
                            if retry == pipeline.max_retries - 1:
                                raise TransformError(
                                    (
                                        stage.handler
                                        if isinstance(stage.handler, str)
                                        else stage.handler.__name__
                                    ),
                                    f"Transform failed after {pipeline.max_retries} retries",
                                    record=record,
                                ) from e

        return transform_generator()

    async def _execute_load(
        self,
        stage: Stage,
        data_stream: AsyncIterator[Any],
        pipeline: Pipeline,
        context: PipelineContext,
    ) -> None:
        """Execute load stage."""
        if not data_stream:
            raise PipelineError(
                context.pipeline_name,
                "No data stream for load stage",
                stage=stage.name,
            )

        # Get sink
        sink_name = stage.handler
        sink_class = self.sink_registry.get(sink_name)
        if not sink_class:
            raise PipelineError(
                context.pipeline_name,
                f"Sink '{sink_name}' not found",
                stage=stage.name,
            )

        # Resolve sink instance
        sink = await self.container.resolve(sink_class)

        # Process in batches
        batch: list[Any] = []
        batch_num = 0

        async for record in data_stream:
            batch.append(record)
            context.metrics["records_processed"] += 1

            if len(batch) >= pipeline.batch_size:
                # Load batch with config kwargs
                await sink.load(batch, **context.config)

                # Call batch complete hook
                batch_num += 1
                await pipeline.on_batch_complete(batch_num, len(batch))

                # Clear batch
                batch = []

        # Load remaining records
        if batch:
            await sink.load(batch, **context.config)
            batch_num += 1
            await pipeline.on_batch_complete(batch_num, len(batch))

    async def _stop_pipeline(self, context: PipelineContext) -> None:
        """Stop a running pipeline."""
        context.state = PipelineState.STOPPING
        await context.log("Stopping pipeline...")
        # TODO: Implement graceful shutdown
        context.state = PipelineState.STOPPED
