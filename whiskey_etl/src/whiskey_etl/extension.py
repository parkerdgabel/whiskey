"""ETL extension for Whiskey applications."""

from __future__ import annotations

from typing import Any, Callable

from whiskey import Whiskey

from .pipeline import Pipeline, PipelineManager, PipelineRegistry
from .sinks import DataSink, SinkRegistry
from .sources import DataSource, SourceRegistry
from .transforms import TransformRegistry


def etl_extension(
    app: Whiskey,
    default_batch_size: int = 1000,
    enable_checkpointing: bool = False,
    enable_monitoring: bool = True,
    max_retries: int = 3,
    retry_delay: float = 1.0,
    **kwargs,
) -> None:
    """ETL extension that adds declarative data pipeline capabilities.

    This extension provides:
    - Declarative pipeline definition with @app.pipeline
    - Data source and sink abstractions
    - Transform functions with dependency injection
    - Error handling and retries
    - Monitoring and progress tracking
    - Schema validation
    - Parallel and streaming support

    Args:
        app: Whiskey instance
        default_batch_size: Default batch size for processing (default: 1000)
        enable_checkpointing: Enable checkpoint/resume support (default: False)
        enable_monitoring: Enable pipeline monitoring (default: True)
        max_retries: Default max retries for failed records (default: 3)
        retry_delay: Delay between retries in seconds (default: 1.0)
        **kwargs: Additional configuration options

    Example:
        app = Whiskey()
        app.use(etl_extension, default_batch_size=500)

        @app.source("csv_file")
        class CsvSource:
            async def extract(self, file_path: str):
                # Read CSV and yield records
                pass

        @app.transform
        async def clean_data(record: dict) -> dict:
            # Clean and validate record
            return record

        @app.pipeline("data_import")
        class DataImportPipeline:
            source = "csv_file"
            transforms = [clean_data]
            sink = "database"

        # Run pipeline
        await app.pipelines.run("data_import", file_path="data.csv")
    """

    # Create registries
    pipeline_registry = PipelineRegistry()
    source_registry = SourceRegistry()
    sink_registry = SinkRegistry()
    transform_registry = TransformRegistry()

    # Register as singletons
    app.container[PipelineRegistry] = pipeline_registry
    app.container[SourceRegistry] = source_registry
    app.container[SinkRegistry] = sink_registry
    app.container[TransformRegistry] = transform_registry

    # Register built-in database sources and sinks if whiskey_sql is available
    try:
        from whiskey_sql import Database

        from .db_sink import BulkUpdateSink, SQLExecuteSink, TableSink, UpsertSink
        from .db_source import DatabaseSource, QuerySource, SQLFileSource, TableSource

        # Register database sources
        source_registry.register("database", DatabaseSource)
        source_registry.register("table", TableSource)
        source_registry.register("query", QuerySource)
        source_registry.register("sql_file", SQLFileSource)

        # Register database sinks
        sink_registry.register("table", TableSink)
        sink_registry.register("upsert", UpsertSink)
        sink_registry.register("bulk_update", BulkUpdateSink)
        sink_registry.register("sql_execute", SQLExecuteSink)

        # Don't register the concrete classes directly - they need Database injection
        # They will be created when needed with proper dependencies

    except ImportError:
        # whiskey_sql not available - database features disabled
        pass

    # Create pipeline manager
    manager = PipelineManager(
        container=app.container,
        pipeline_registry=pipeline_registry,
        source_registry=source_registry,
        sink_registry=sink_registry,
        transform_registry=transform_registry,
        default_batch_size=default_batch_size,
        enable_checkpointing=enable_checkpointing,
        enable_monitoring=enable_monitoring,
        max_retries=max_retries,
        retry_delay=retry_delay,
    )

    # Register manager
    app.container[PipelineManager] = manager
    app.pipelines = manager

    # Pipeline decorator
    def pipeline(
        name: str | None = None,
        batch_size: int | None = None,
        enable_checkpointing: bool | None = None,
        max_retries: int | None = None,
        retry_delay: float | None = None,
        tags: list[str] | None = None,
    ):
        """Decorator to register a data pipeline.

        Args:
            name: Pipeline name (defaults to class name)
            batch_size: Override default batch size
            enable_checkpointing: Enable checkpoint/resume
            max_retries: Max retries for failed records
            retry_delay: Delay between retries
            tags: Pipeline tags for categorization

        Example:
            @app.pipeline("user_import")
            class UserImportPipeline:
                source = "csv_users"
                transforms = [validate_user, enrich_user]
                sink = "user_database"

                async def on_error(self, error: Exception, record: Any):
                    # Handle errors
                    pass
        """

        def decorator(cls: type[Pipeline]) -> type[Pipeline]:
            # Create pipeline metadata
            pipeline_name = name or cls.__name__

            # Register pipeline class
            pipeline_registry.register(
                name=pipeline_name,
                pipeline_class=cls,
                batch_size=batch_size or default_batch_size,
                enable_checkpointing=(
                    enable_checkpointing if enable_checkpointing is not None else False
                ),
                max_retries=max_retries or 3,
                retry_delay=retry_delay or 1.0,
                tags=tags or [],
            )

            # Add metadata to class
            cls._pipeline_name = pipeline_name
            cls._pipeline_metadata = {
                "batch_size": batch_size,
                "enable_checkpointing": enable_checkpointing,
                "max_retries": max_retries,
                "retry_delay": retry_delay,
                "tags": tags,
            }

            return cls

        return decorator

    # Source decorator
    def source(name: str):
        """Decorator to register a data source.

        Args:
            name: Source identifier

        Example:
            @app.source("csv_file")
            class CsvFileSource:
                async def extract(self, file_path: str, file_service: FileService):
                    async for row in file_service.read_csv(file_path):
                        yield row
        """

        def decorator(cls: type[DataSource]) -> type[DataSource]:
            # Register source class
            source_registry.register(name, cls)

            # Register in container if needed
            if hasattr(cls, "__init__"):
                app.container[cls] = cls

            return cls

        return decorator

    # Sink decorator
    def sink(name: str):
        """Decorator to register a data sink.

        Args:
            name: Sink identifier

        Example:
            @app.sink("database")
            class DatabaseSink:
                async def load(self, records: List[dict], db: Database):
                    await db.bulk_insert(records)
        """

        def decorator(cls: type[DataSink]) -> type[DataSink]:
            # Register sink class
            sink_registry.register(name, cls)

            # Register in container if needed
            if hasattr(cls, "__init__"):
                app.container[cls] = cls

            return cls

        return decorator

    # Transform decorator
    def transform(func: Callable | None = None, *, name: str | None = None):
        """Decorator to register a transform function.

        Args:
            func: Transform function (if used without parentheses)
            name: Transform name (defaults to function name)

        Example:
            @app.transform
            async def clean_email(record: dict) -> dict:
                record["email"] = record["email"].lower().strip()
                return record

            @app.transform(name="validate")
            async def validate_record(record: dict, validator: Validator) -> dict:
                return await validator.validate(record)
        """

        def decorator(f: Callable) -> Callable:
            # Create transform wrapper
            transform_name = name or f.__name__

            # Register transform
            transform_registry.register(transform_name, f)

            # Add metadata
            f._transform_name = transform_name

            return f

        # Handle both @transform and @transform()
        if func is None:
            return decorator
        else:
            return decorator(func)

    # SQL transform decorator (only if whiskey_sql is available)
    def sql_transform(transform_type: str, *, name: str | None = None, **config):
        """Decorator to register a SQL-based transform.

        Args:
            transform_type: Type of SQL transform (lookup, join, validate, aggregate)
            name: Transform name (defaults to decorated function name)
            **config: Transform-specific configuration

        Example:
            @app.sql_transform("lookup",
                lookup_query="SELECT name, email FROM users WHERE id = :user_id",
                input_fields=["user_id"],
                output_fields=["user_name", "user_email"])
            async def enrich_with_user_info(record: dict, transform: SQLTransform) -> dict:
                # Can customize behavior if needed
                return await transform.transform(record)

            @app.sql_transform("validate",
                validation_query="SELECT 1 FROM products WHERE sku = :sku",
                validation_fields=["sku"],
                on_invalid="drop")
            async def validate_product_exists(record: dict, transform: SQLTransform) -> dict | None:
                return await transform.transform(record)
        """

        def decorator(func: Callable) -> Callable:
            transform_name = name or func.__name__

            # Create the SQL transform wrapper that will get database injected
            from .sql_transform import create_sql_transform
            
            async def sql_transform_wrapper(record: dict[str, Any], database: Database) -> dict[str, Any] | None:
                # Create transform with injected database
                transform_func = create_sql_transform(transform_type, database, **config)
                return await transform_func(record)

            # Copy metadata
            sql_transform_wrapper.__name__ = func.__name__
            sql_transform_wrapper._transform_name = transform_name
            sql_transform_wrapper._sql_transform_config = {"type": transform_type, **config}

            # Register the wrapper
            transform_registry.register(transform_name, sql_transform_wrapper)

            return func

        return decorator

    # Scheduled pipeline decorator
    def scheduled_pipeline(
        name: str | None = None,
        cron: str | None = None,
        interval: float | None = None,
        **pipeline_kwargs,
    ):
        """Decorator to register a scheduled pipeline.

        Args:
            name: Pipeline name
            cron: Cron expression
            interval: Interval in seconds
            **pipeline_kwargs: Additional pipeline configuration

        Example:
            @app.scheduled_pipeline("daily_sync", cron="0 0 * * *")
            class DailySyncPipeline:
                source = "api_source"
                sink = "warehouse"
        """

        def decorator(cls: type[Pipeline]) -> type[Pipeline]:
            # First register as regular pipeline
            pipeline_decorator = pipeline(name, **pipeline_kwargs)
            cls = pipeline_decorator(cls)

            # Add scheduling metadata
            cls._schedule = {
                "cron": cron,
                "interval": interval,
            }

            # Register with scheduler if available
            if hasattr(app, "jobs") and hasattr(app, "scheduled_job"):
                # Use whiskey_jobs if available
                pipeline_name = name or cls.__name__

                @app.scheduled_job(
                    name=f"pipeline_{pipeline_name}",
                    cron=cron,
                    interval=interval,
                )
                async def run_scheduled_pipeline():
                    await manager.run(pipeline_name)

            return cls

        return decorator

    # Add decorators to app
    app.add_decorator("pipeline", pipeline)
    app.add_decorator("source", source)
    app.add_decorator("sink", sink)
    app.add_decorator("transform", transform)
    app.add_decorator("scheduled_pipeline", scheduled_pipeline)

    # Also add as attributes
    app.pipeline = pipeline
    app.source = source
    app.sink = sink
    app.transform = transform
    app.scheduled_pipeline = scheduled_pipeline

    # Add SQL transform if available
    try:
        from whiskey_sql import Database

        app.add_decorator("sql_transform", sql_transform)
        app.sql_transform = sql_transform
    except ImportError:
        pass

    # Lifecycle hooks
    @app.on_startup
    async def start_etl_system():
        """Initialize ETL system on startup."""
        await manager.initialize()

    @app.on_shutdown
    async def stop_etl_system():
        """Cleanup ETL system on shutdown."""
        await manager.shutdown()

    # CLI commands if available
    if hasattr(app, "command"):

        @app.command(group="etl")
        def pipelines_list():
            """List all registered pipelines."""
            pipelines = pipeline_registry.list_pipelines()

            print("Registered Pipelines")
            print("=" * 50)
            if pipelines:
                for name, info in pipelines.items():
                    print(f"\n{name}:")
                    print(f"  Source: {info.get('source', 'N/A')}")
                    print(f"  Sink: {info.get('sink', 'N/A')}")
                    print(f"  Transforms: {info.get('transforms', [])}")
                    print(f"  Batch size: {info.get('batch_size', default_batch_size)}")
                    if info.get("tags"):
                        print(f"  Tags: {', '.join(info['tags'])}")
            else:
                print("No pipelines registered")

        @app.command(group="etl")
        @app.argument("pipeline_name")
        @app.option("--kwargs", help="JSON-encoded kwargs for pipeline")
        async def pipelines_run(pipeline_name: str, kwargs: str | None = None):
            """Run a pipeline."""
            import json

            # Parse kwargs
            run_kwargs = json.loads(kwargs) if kwargs else {}

            # Run pipeline
            async with app:
                print(f"Running pipeline: {pipeline_name}")
                try:
                    result = await manager.run(pipeline_name, **run_kwargs)
                    print("\nPipeline completed successfully")
                    print(f"Records processed: {result.records_processed}")
                    if result.errors:
                        print(f"Errors: {len(result.errors)}")
                except Exception as e:
                    print(f"Pipeline failed: {e}")
                    raise

        @app.command(group="etl")
        def sources_list():
            """List all registered sources."""
            sources = source_registry.list_sources()

            print("Registered Sources")
            print("=" * 50)
            if sources:
                for name in sorted(sources):
                    print(f"  - {name}")
            else:
                print("No sources registered")

        @app.command(group="etl")
        def sinks_list():
            """List all registered sinks."""
            sinks = sink_registry.list_sinks()

            print("Registered Sinks")
            print("=" * 50)
            if sinks:
                for name in sorted(sinks):
                    print(f"  - {name}")
            else:
                print("No sinks registered")
