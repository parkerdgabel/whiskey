"""Example object store ETL pipelines for cloud storage."""

import asyncio
from datetime import datetime, timedelta

from whiskey import Whiskey

from whiskey_etl import etl_extension, json_processor


async def main():
    """Run object store ETL examples."""
    app = Whiskey()
    app.use(etl_extension)

    # Example 1: S3 to S3 data processing pipeline
    @app.pipeline("s3_data_processing")
    class S3ProcessingPipeline:
        """Process JSON files from S3 and write results back."""
        source = "s3"
        transforms = ["validate_record", "enrich_data", "anonymize_pii"]
        sink = "s3"

        # Source configuration
        source_config = {
            "bucket": "raw-data-bucket",
            "prefix": "events/2024/",
            "suffix": ".json",
            "processor": json_processor,
            "modified_after": datetime.now() - timedelta(days=1),
        }

        # Sink configuration
        sink_config = {
            "bucket": "processed-data-bucket",
            "key_template": "processed/{timestamp}/events_{batch_id}.jsonl",
            "format": "jsonl",
            "compression": "gzip",
            "partition_by": ["event_type", "country"],
            "metadata": {
                "pipeline": "s3_data_processing",
                "version": "1.0",
            },
        }

    @app.transform
    async def validate_record(record: dict) -> dict | None:
        """Validate required fields."""
        required_fields = ["event_id", "timestamp", "user_id", "event_type"]

        for field in required_fields:
            if field not in record:
                print(f"Dropping record missing {field}: {record}")
                return None

        # Parse timestamp
        try:
            record["timestamp"] = datetime.fromisoformat(record["timestamp"])
        except ValueError:
            return None

        return record

    @app.transform
    async def enrich_data(record: dict) -> dict:
        """Add derived fields."""
        # Extract date parts
        ts = record["timestamp"]
        record["year"] = ts.year
        record["month"] = ts.month
        record["day"] = ts.day
        record["hour"] = ts.hour
        record["day_of_week"] = ts.strftime("%A")

        # Add processing metadata
        record["processed_at"] = datetime.now().isoformat()
        record["pipeline_version"] = "1.0"

        return record

    @app.transform
    async def anonymize_pii(record: dict) -> dict:
        """Remove or hash PII data."""
        import hashlib

        # Hash user_id
        if "user_id" in record:
            user_hash = hashlib.sha256(str(record["user_id"]).encode()).hexdigest()
            record["user_hash"] = user_hash[:16]  # Use first 16 chars
            del record["user_id"]

        # Remove sensitive fields
        sensitive_fields = ["email", "phone", "ip_address", "credit_card"]
        for field in sensitive_fields:
            if field in record:
                del record[field]

        return record

    # Example 2: Multi-cloud data migration
    @app.pipeline("cloud_migration")
    class CloudMigrationPipeline:
        """Migrate data from Azure Blob to GCS."""
        source = "azure_blob"
        transforms = ["convert_format", "add_metadata"]
        sink = "gcs"
        batch_size = 5000  # Process in larger batches

        source_config = {
            "bucket": "source-container",  # Azure container
            "prefix": "data/exports/",
            "suffix": ".csv",
            "processor": csv_processor,
        }

        sink_config = {
            "bucket": "destination-bucket",  # GCS bucket
            "key_template": "migrated/{timestamp}/data_{batch_id}.parquet",
            "format": "parquet",
            "storage_class": "NEARLINE",  # For archival
            "metadata": {
                "source": "azure_blob",
                "migration_date": datetime.now().isoformat(),
            },
        }

    @app.transform
    async def convert_format(record: dict) -> dict:
        """Convert data types for parquet."""
        # Convert string numbers to proper types
        for field, value in record.items():
            if isinstance(value, str):
                # Try to convert to number
                try:
                    if "." in value:
                        record[field] = float(value)
                    else:
                        record[field] = int(value)
                except ValueError:
                    # Keep as string
                    pass

        return record

    @app.transform
    async def add_metadata(record: dict) -> dict:
        """Add migration metadata."""
        record["_migrated_at"] = datetime.now()
        record["_source_system"] = "azure"
        return record

    # Example 3: Real-time streaming to object store
    @app.pipeline("stream_to_s3")
    class StreamToS3Pipeline:
        """Stream data from API to S3 with time-based partitioning."""
        source = "api_stream"  # Custom streaming source
        transforms = ["parse_event", "aggregate_metrics"]
        sink = "s3"

        sink_config = {
            "bucket": "streaming-data",
            "key_template": "streams/{year}/{month}/{day}/{hour}/events_{batch_id}.json",
            "format": "json",
            "partition_by": ["year", "month", "day", "hour"],
        }

    # Example 4: Data lake ingestion with schema evolution
    @app.pipeline("data_lake_ingestion")
    class DataLakeIngestionPipeline:
        """Ingest various file formats into data lake."""
        source = "s3"
        transforms = ["detect_schema", "standardize_fields", "add_lineage"]
        sink = "s3"

        source_config = {
            "bucket": "landing-zone",
            "recursive": True,
            "max_keys": 1000,  # Process up to 1000 files
        }

        sink_config = {
            "bucket": "data-lake",
            "key_template": "bronze/{source_format}/{year}/{month}/{day}/data_{batch_id}.parquet",
            "format": "parquet",
            "partition_by": ["source_format", "year", "month", "day"],
        }

        async def on_start(self, context):
            """Initialize schema registry."""
            context.schema_registry = {}

        async def on_complete(self, context):
            """Save schema registry."""
            # Could write to a schema registry service
            print(f"Discovered schemas: {list(context.schema_registry.keys())}")

    @app.transform
    async def detect_schema(record: dict, context) -> dict:
        """Detect and register schema."""
        # Simple schema detection based on fields
        schema_key = tuple(sorted(record.keys()))

        if schema_key not in context.schema_registry:
            context.schema_registry[schema_key] = {
                "fields": list(schema_key),
                "first_seen": datetime.now(),
                "record_count": 0,
            }

        context.schema_registry[schema_key]["record_count"] += 1
        record["_schema_version"] = hash(schema_key) % 1000

        return record

    @app.transform
    async def standardize_fields(record: dict) -> dict:
        """Standardize field names and types."""
        # Lowercase all field names
        standardized = {}
        for key, value in record.items():
            standardized[key.lower().replace(" ", "_")] = value

        return standardized

    @app.transform
    async def add_lineage(record: dict) -> dict:
        """Add data lineage information."""
        record["_ingested_at"] = datetime.now()
        record["_pipeline"] = "data_lake_ingestion"
        record["_quality_score"] = 1.0  # Could calculate based on completeness

        return record

    # Example 5: Cross-region replication with filtering
    @app.pipeline("cross_region_replication")
    class CrossRegionReplicationPipeline:
        """Replicate data across regions with filtering."""
        source = "s3"
        transforms = ["filter_by_region", "compress_large_fields"]
        sink = "s3"

        source_config = {
            "bucket": "us-east-1-data",
            "aws_region": "us-east-1",
        }

        # Multiple sinks for different regions
        sinks = [
            {
                "name": "s3",
                "config": {
                    "bucket": "eu-west-1-data",
                    "aws_region": "eu-west-1",
                },
                "filter": lambda r: r.get("region") in ["EU", "UK"],
            },
            {
                "name": "s3",
                "config": {
                    "bucket": "ap-southeast-1-data",
                    "aws_region": "ap-southeast-1",
                },
                "filter": lambda r: r.get("region") in ["APAC", "ANZ"],
            },
        ]

    @app.transform
    async def filter_by_region(record: dict) -> dict | None:
        """Filter records based on compliance rules."""
        # Example: GDPR compliance
        if record.get("region") == "EU" and record.get("consent") != True:
            return None  # Don't replicate without consent

        return record

    @app.transform
    async def compress_large_fields(record: dict) -> dict:
        """Compress large text fields."""
        import base64
        import gzip

        for field, value in record.items():
            if isinstance(value, str) and len(value) > 10000:
                # Compress large strings
                compressed = gzip.compress(value.encode())
                record[field] = {
                    "compressed": True,
                    "encoding": "gzip+base64",
                    "data": base64.b64encode(compressed).decode(),
                    "original_size": len(value),
                    "compressed_size": len(compressed),
                }

        return record

    # Run examples
    async with app:
        print("🚀 Object Store ETL Examples")
        print("=" * 50)

        # Configure AWS credentials (from environment or IAM)
        s3_config = {
            "aws_access_key_id": None,  # Use environment
            "aws_secret_access_key": None,
            "region_name": "us-east-1",
        }

        # Configure Azure credentials
        azure_config = {
            "account_name": "mystorageaccount",
            "account_key": None,  # Use environment
        }

        # Configure GCS credentials
        gcs_config = {
            "project_id": "my-project",
            "credentials_path": None,  # Use default
        }

        # Example: Run S3 processing pipeline
        print("\n📦 Processing S3 data...")
        try:
            result = await app.pipelines.run(
                "s3_data_processing",
                **s3_config,
            )
            print(f"✅ Processed {result.records_processed} records")
        except Exception as e:
            print(f"❌ S3 processing failed: {e}")

        # Example: Run cloud migration
        print("\n☁️  Migrating from Azure to GCS...")
        try:
            # Set up source and sink configs
            app.container[AzureBlobSource] = AzureBlobSource(**azure_config)
            app.container[GCSSink] = GCSSink(**gcs_config)

            result = await app.pipelines.run("cloud_migration")
            print(f"✅ Migrated {result.records_processed} records")
        except Exception as e:
            print(f"❌ Migration failed: {e}")

        print("\n✨ Examples complete!")


if __name__ == "__main__":
    # For the example, we import the components directly
    from whiskey_etl import AzureBlobSource, GCSSink

    asyncio.run(main())
