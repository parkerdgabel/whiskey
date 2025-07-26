# Whiskey ETL

A declarative ETL (Extract, Transform, Load) extension for the Whiskey dependency injection framework.

## Features

- **Declarative Pipeline Definition**: Define data pipelines using decorators and classes
- **Dependency Injection**: Inject services into transforms, sources, and sinks
- **Built-in Components**: CSV, JSON, and JSON Lines sources/sinks
- **Transform Utilities**: Filter, map, validate, and clean data with ease
- **Error Handling**: Retry logic, error callbacks, and detailed error reporting
- **Monitoring**: Track pipeline progress and metrics
- **Flexible Architecture**: Easy to extend with custom sources, sinks, and transforms

## Installation

```bash
pip install whiskey-etl
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