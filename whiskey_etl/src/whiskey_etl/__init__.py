"""Whiskey ETL - Declarative data pipeline extension for Whiskey DI framework."""

from whiskey_etl.db_sink import BulkUpdateSink, DatabaseSink, SQLExecuteSink, TableSink, UpsertSink
from whiskey_etl.db_source import DatabaseSource, QuerySource, SQLFileSource, TableSource
from whiskey_etl.extension import etl_extension
from whiskey_etl.object_store_sink import AzureBlobSink, GCSSink, ObjectStoreSink, S3Sink
from whiskey_etl.object_store_source import (
    AzureBlobSource,
    GCSSource,
    ObjectStoreSource,
    S3Source,
    csv_processor,
    json_processor,
    jsonl_processor,
)
from whiskey_etl.pipeline import Pipeline, PipelineResult, PipelineState
from whiskey_etl.sinks import DataSink
from whiskey_etl.sources import DataSource
from whiskey_etl.sql_transform import (
    AggregateTransform,
    JoinTransform,
    LookupTransform,
    SQLTransform,
    ValidateTransform,
    create_aggregate_transform,
    create_join_transform,
    create_lookup_transform,
    create_sql_transform,
    create_validate_transform,
)

__version__ = "0.1.0"
__all__ = [
    "etl_extension",
    # Pipeline
    "Pipeline",
    "PipelineResult",
    "PipelineState",
    # Base classes
    "DataSource",
    "DataSink",
    # Database sources
    "DatabaseSource",
    "TableSource",
    "QuerySource",
    "SQLFileSource",
    # Database sinks
    "DatabaseSink",
    "TableSink",
    "UpsertSink",
    "BulkUpdateSink",
    "SQLExecuteSink",
    # Object store sources
    "ObjectStoreSource",
    "S3Source",
    "AzureBlobSource",
    "GCSSource",
    "json_processor",
    "jsonl_processor",
    "csv_processor",
    # Object store sinks
    "ObjectStoreSink",
    "S3Sink",
    "AzureBlobSink",
    "GCSSink",
    # SQL transforms
    "SQLTransform",
    "LookupTransform",
    "JoinTransform",
    "ValidateTransform",
    "AggregateTransform",
    "create_sql_transform",
    "create_lookup_transform",
    "create_join_transform",
    "create_validate_transform",
    "create_aggregate_transform",
]
