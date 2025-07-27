# Whiskey ETL

A declarative ETL (Extract, Transform, Load) extension for the Whiskey dependency injection framework.

## Features

- **Declarative Pipeline Definition**: Define data pipelines using decorators and classes
- **Dependency Injection**: Inject services into transforms, sources, and sinks
- **Built-in Components**: CSV, JSON, and JSON Lines sources/sinks
- **Database Integration**: Full SQL database support via whiskey_sql
- **SQL Transforms**: Lookup, join, validate, and aggregate data using SQL
- **Transform Utilities**: Filter, map, validate, and clean data with ease
- **Error Handling**: Retry logic, error callbacks, and detailed error reporting
- **Monitoring**: Track pipeline progress and metrics
- **Flexible Architecture**: Easy to extend with custom sources, sinks, and transforms

## Installation

```bash
# Basic installation
pip install whiskey-etl

# With object store support
pip install whiskey-etl[s3]          # AWS S3 support
pip install whiskey-etl[azure]       # Azure Blob Storage support
pip install whiskey-etl[gcs]         # Google Cloud Storage support
pip install whiskey-etl[cloud]       # All cloud storage providers

# With additional features
pip install whiskey-etl[parquet]     # Parquet file format support
pip install whiskey-etl[compression] # Snappy compression support

# Full installation
pip install whiskey-etl[cloud,parquet,compression]
```

## Quick Start

```python
from whiskey import Whiskey
from whiskey_etl import etl_extension

# Create app with ETL extension
app = Whiskey()
app.use(etl_extension)

# Define a data source
@app.source("csv_users")
class UsersCsvSource:
    async def extract(self, file_path: str):
        # Read CSV and yield records
        pass

# Define transforms
@app.transform
async def clean_email(record: dict) -> dict:
    record["email"] = record["email"].lower().strip()
    return record

@app.transform
async def validate_user(record: dict, validator: UserValidator) -> dict:
    # Validator is injected automatically!
    return await validator.validate(record)

# Define a pipeline
@app.pipeline("import_users")
class ImportUsersPipeline:
    source = "csv_users"
    transforms = [clean_email, validate_user]
    sink = "user_database"
    
    batch_size = 1000
    max_retries = 3

# Run the pipeline
async with app:
    result = await app.pipelines.run("import_users", file_path="users.csv")
    print(f"Processed {result.records_processed} records")
```

## Built-in Sources

### CSV Source
```python
from whiskey_etl.sources import CsvSource

@app.source("csv")
class MyCsvSource(CsvSource):
    def __init__(self):
        super().__init__(
            delimiter=",",
            has_header=True,
            encoding="utf-8"
        )
```

### JSON Source
```python
from whiskey_etl.sources import JsonSource

@app.source("json")
class MyJsonSource(JsonSource):
    pass
```

### JSON Lines Source
```python
from whiskey_etl.sources import JsonLinesSource

@app.source("jsonl")
class MyJsonLinesSource(JsonLinesSource):
    pass
```

## Built-in Sinks

### CSV Sink
```python
from whiskey_etl.sinks import CsvSink

@app.sink("csv_output")
class MyCsvSink(CsvSink):
    def __init__(self):
        super().__init__(
            mode="w",  # or "a" for append
            write_header=True
        )
```

### JSON Sink
```python
from whiskey_etl.sinks import JsonSink

@app.sink("json_output")
class MyJsonSink(JsonSink):
    def __init__(self):
        super().__init__(indent=2)
```

### Console Sink (for debugging)
```python
from whiskey_etl.sinks import ConsoleSink

@app.sink("console")
class DebugSink(ConsoleSink):
    def __init__(self):
        super().__init__(format="json", prefix="Record")
```

## Transform Utilities

```python
from whiskey_etl.transforms import (
    filter_transform,
    map_transform,
    select_fields,
    rename_fields,
    clean_strings,
    validate_required,
    TransformChain
)

# Use transform utilities
@app.transform
async def process_record(record: dict) -> dict:
    # Select specific fields
    record = await select_fields(record, ["id", "name", "email"])
    
    # Rename fields
    record = await rename_fields(record, {"user_id": "id"})
    
    # Clean strings
    record = await clean_strings(record, operations=["strip", "lower"])
    
    return record

# Or use transform chains
chain = TransformChain()
chain.select(["id", "name", "email"]) \
     .rename({"user_id": "id"}) \
     .filter(lambda r: r.get("email") is not None)

@app.transform
async def chained_transform(record: dict) -> dict:
    return await chain.apply(record)
```

## Pipeline Lifecycle

```python
@app.pipeline("my_pipeline")
class MyPipeline(Pipeline):
    source = "my_source"
    sink = "my_sink"
    
    async def on_start(self, context):
        """Called when pipeline starts."""
        await context.log("Pipeline starting...")
    
    async def on_complete(self, context):
        """Called when pipeline completes successfully."""
        await context.emit_metrics()
    
    async def on_error(self, error, record=None):
        """Called when an error occurs."""
        # Handle error, maybe send to dead letter queue
        pass
    
    async def on_batch_complete(self, batch_num, records_processed):
        """Called after each batch is processed."""
        print(f"Batch {batch_num}: {records_processed} records")
```

## Custom Sources and Sinks

```python
from whiskey_etl.sources import DataSource
from whiskey_etl.sinks import DataSink

@app.source("api")
class ApiSource(DataSource):
    def __init__(self, api_client: ApiClient):  # DI works here!
        self.api_client = api_client
    
    async def extract(self, endpoint: str, **kwargs):
        async for item in self.api_client.paginate(endpoint):
            yield item

@app.sink("database")
class DatabaseSink(DataSink):
    def __init__(self, db: Database):  # DI works here too!
        self.db = db
    
    async def load(self, records: List[dict], table: str, **kwargs):
        await self.db.bulk_insert(table, records)
```

## Error Handling

```python
@app.pipeline("robust_pipeline")
class RobustPipeline(Pipeline):
    source = "unreliable_api"
    sink = "database"
    
    # Retry configuration
    max_retries = 3
    retry_delay = 1.0  # seconds
    
    # Error handling
    error_handler = "dead_letter_queue"
    
    async def on_error(self, error, record=None):
        if isinstance(error, NetworkError):
            # Wait longer for network errors
            await asyncio.sleep(5)
        elif isinstance(error, ValidationError):
            # Send to dead letter queue
            await self.context.container.resolve(DeadLetterQueue).send(record)
```

## CLI Integration

If you have the whiskey_cli extension installed:

```bash
# List pipelines
python app.py etl pipelines-list

# Run a pipeline
python app.py etl pipelines-run import_users --kwargs '{"file_path": "users.csv"}'

# List sources and sinks
python app.py etl sources-list
python app.py etl sinks-list
```

## Testing

```python
from whiskey_etl.sources import MemorySource
from whiskey_etl.sinks import MemorySink

# Use memory source/sink for testing
test_data = [
    {"name": "John", "email": "john@example.com"},
    {"name": "Jane", "email": "jane@example.com"},
]

app.container[MemorySource] = MemorySource(test_data)
memory_sink = MemorySink()
app.container[MemorySink] = memory_sink

@app.source("test_source")
class TestSource(MemorySource):
    pass

@app.sink("test_sink")  
class TestSink(MemorySink):
    pass

# Run pipeline and check results
result = await app.pipelines.run("my_pipeline")
assert memory_sink.get_data() == expected_output
```

## Database Integration

When using whiskey_sql, ETL pipelines can leverage powerful database sources, sinks, and transforms.

### Database Sources

```python
# Configure database first
app.use(sql_extension)
app.configure_database("postgresql://localhost/mydb")

# Use built-in database source
@app.pipeline("extract_users")
class ExtractUsersPipeline:
    source = "table"  # Built-in table source
    source_config = {
        "table_name": "users",
        "key_column": "id",
        "batch_size": 1000,
    }
    sink = "csv_output"

# Or use custom query source
@app.source("recent_orders")
class RecentOrdersSource(QuerySource):
    def __init__(self, database: Database):
        super().__init__(
            database,
            query="""
                SELECT * FROM orders 
                WHERE created_at >= :start_date
                ORDER BY created_at
            """
        )
```

### Database Sinks

```python
# Table sink with upsert
@app.pipeline("sync_products")
class SyncProductsPipeline:
    source = "api_products"
    sink = "upsert"  # Built-in upsert sink
    sink_config = {
        "table_name": "products",
        "key_columns": ["sku"],
        "update_columns": ["name", "price", "updated_at"],
    }

# Bulk update sink
@app.sink("bulk_inventory_update")
class InventoryUpdateSink(BulkUpdateSink):
    def __init__(self, database: Database):
        super().__init__(
            database,
            table_name="inventory",
            key_columns=["warehouse_id", "sku"],
            update_columns=["quantity", "last_updated"]
        )
```

### SQL Transforms

```python
# Lookup transform with caching
@app.sql_transform("lookup",
    lookup_query="SELECT name, email FROM customers WHERE id = :customer_id",
    input_fields=["customer_id"],
    output_fields=["customer_name", "customer_email"],
    cache_size=1000
)
async def enrich_customer(record: dict, transform: SQLTransform) -> dict:
    return await transform.transform(record)

# Join transform
@app.sql_transform("join",
    join_table="products",
    join_keys={"product_id": "id"},
    select_fields=["name", "category", "price"]
)
async def join_product_info(record: dict, transform: SQLTransform) -> dict:
    return await transform.transform(record)

# Validation transform
@app.sql_transform("validate",
    validation_query="SELECT 1 FROM valid_skus WHERE sku = :sku",
    validation_fields=["sku"],
    on_invalid="drop"  # or "mark", "error"
)
async def validate_sku(record: dict, transform: SQLTransform) -> dict | None:
    return await transform.transform(record)

# Aggregation transform
@app.sql_transform("aggregate",
    aggregate_query="""
        SELECT COUNT(*) as order_count,
               SUM(amount) as total_spent,
               AVG(amount) as avg_order_value
        FROM orders
        WHERE customer_id = :customer_id
    """,
    group_by_fields=["customer_id"],
    aggregate_fields=["order_count", "total_spent"]
)
async def add_customer_stats(record: dict, transform: SQLTransform) -> dict:
    return await transform.transform(record)

# Use in pipeline
@app.pipeline("enrich_orders")
class EnrichOrdersPipeline:
    source = "table"
    source_config = {"table_name": "orders"}
    transforms = [
        enrich_customer,
        join_product_info,
        validate_sku,
        add_customer_stats
    ]
    sink = "enriched_orders"
```

## Data Validation

Whiskey ETL includes a robust validation framework that integrates seamlessly with pipelines.

### Built-in Validators

```python
from whiskey_etl import validation_transform, ValidationMode

# Create validation with builder API
validator = (
    validation_transform(ValidationMode.FAIL)  # Fail on first error
    .field("email").required().email().end_field()
    .field("age").required().type(int).range(18, 100).end_field()
    .field("status").choices(["active", "inactive"]).end_field()
    .build()
)

# Use as transform in pipeline
@app.pipeline("validated_pipeline")
class ValidatedPipeline:
    source = "api"
    transforms = [validator.transform]
    sink = "database"
```

### Validation Modes

- `FAIL`: Raise exception on validation failure (default)
- `DROP`: Silently drop invalid records
- `MARK`: Mark records with validation info but pass through
- `COLLECT`: Collect all errors before failing
- `QUARANTINE`: Send invalid records to quarantine

### Custom Validators

```python
# Simple custom validator
def validate_phone(value, record):
    """Check if phone number is valid."""
    import re
    pattern = r'^\+?1?\d{9,15}$'
    return bool(re.match(pattern, value))

# Complex validator with ValidationResult
def validate_address(value, record):
    from whiskey_etl.validation import ValidationResult
    
    result = ValidationResult(valid=True)
    
    if not value.get("street"):
        result.add_error("street", "Street is required")
    
    if not value.get("postal_code"):
        result.add_warning("postal_code", "Postal code recommended")
    
    return result

# Use in validation
validator = (
    validation_transform()
    .field("phone").custom(validate_phone, "Invalid phone format").end_field()
    .field("address").custom(validate_address).end_field()
    .build()
)
```

### Validation Reporting

```python
from whiskey_etl import ValidationReporter, ValidationQuarantine

# Create reporter
reporter = ValidationReporter()

# Start report for pipeline run
report = reporter.start_report("my_pipeline")

# In your pipeline or transform
async def validate_with_reporting(record):
    result = await validator.validate_record(record)
    report.add_validation_result(record, result)
    
    if not result.valid:
        # Add to quarantine
        quarantine.add(record, result.errors, "my_pipeline")
    
    return record if result.valid else None

# After pipeline completes
reporter.finalize_report("my_pipeline")

# Get report summary
summary = report.get_summary()
print(f"Validation rate: {summary['validation_rate']}%")
print(f"Top errors: {summary['top_field_errors']}")

# Generate HTML report
html_report = report.to_html()
```

### Cross-field Validation

```python
def validate_date_range(record, _):
    """Ensure start_date is before end_date."""
    start = record.get("start_date")
    end = record.get("end_date")
    
    if start and end and start > end:
        result = ValidationResult(valid=False)
        result.add_error("date_range", "Start must be before end")
        return result
    
    return ValidationResult(valid=True)

# Add to validator
validator = RecordValidator(
    field_validators={
        "start_date": DateValidator(),
        "end_date": DateValidator(),
    },
    record_validators=[CustomValidator(validate_date_range)]
)
```

### Available Validators

- `RequiredValidator`: Field must be present and not null
- `TypeValidator`: Field must be of specific type(s)
- `RangeValidator`: Numeric value within min/max range
- `LengthValidator`: String/collection length constraints
- `PatternValidator`: Regex pattern matching
- `ChoiceValidator`: Value must be in allowed choices
- `EmailValidator`: Valid email format
- `DateValidator`: Date parsing and range validation
- `UniqueValidator`: Field uniqueness across records
- `CompositeValidator`: Combine multiple validators

## Advanced Features

### Scheduled Pipelines

```python
# Requires whiskey_jobs extension
@app.scheduled_pipeline("hourly_sync", cron="0 * * * *")
class HourlySyncPipeline(Pipeline):
    source = "api"
    sink = "warehouse"
```

### Parallel Processing

```python
from whiskey_etl.pipeline import Stage, StageType

@app.pipeline("parallel_pipeline")
class ParallelPipeline(Pipeline):
    def get_stages(self):
        return [
            Stage("extract", StageType.EXTRACT, "api_source"),
            Stage("transform", StageType.TRANSFORM, "process_data", 
                  parallel=True, workers=4),
            Stage("load", StageType.LOAD, "database")
        ]
```

## License

MIT