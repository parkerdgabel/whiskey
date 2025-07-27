"""Basic ETL pipeline example using Whiskey ETL extension."""

import asyncio

# Import ETL extension and built-in components
import sys
from pathlib import Path

from whiskey import Whiskey

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from whiskey_etl import etl_extension
from whiskey_etl.pipeline import Pipeline
from whiskey_etl.sinks import ConsoleSink, JsonSink
from whiskey_etl.sources import CsvSource


async def main():
    """Demonstrate basic ETL pipeline functionality."""

    # Create Whiskey app with ETL extension
    app = Whiskey()
    app.use(etl_extension, default_batch_size=10)

    # Register built-in sources and sinks
    app.container[CsvSource] = CsvSource()
    app.container[JsonSink] = JsonSink(indent=2)
    app.container[ConsoleSink] = ConsoleSink()

    @app.source("csv_file")
    class CsvFileSource(CsvSource):
        """CSV file source with default settings."""

        pass

    @app.sink("json_file")
    class JsonFileSink(JsonSink):
        """JSON file sink with pretty printing."""

        pass

    @app.sink("console")
    class ConsoleDebugSink(ConsoleSink):
        """Console sink for debugging."""

        def __init__(self):
            super().__init__(format="json", prefix="Record")

    # Define transform functions
    @app.transform
    async def clean_email(record: dict) -> dict:
        """Clean and normalize email addresses."""
        if "email" in record:
            record["email"] = record["email"].lower().strip()
        return record

    @app.transform
    async def add_timestamp(record: dict) -> dict:
        """Add processing timestamp."""
        from datetime import datetime

        record["processed_at"] = datetime.now().isoformat()
        return record

    @app.transform(name="validate_email")
    async def validate_email_format(record: dict) -> dict:
        """Validate email format."""
        import re

        email = record.get("email", "")
        if not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", email):
            # You could return None to filter out invalid records
            # or raise an error
            record["email_valid"] = False
        else:
            record["email_valid"] = True

        return record

    # Example service that can be injected into transforms
    @app.singleton
    class EmailValidator:
        def is_valid(self, email: str) -> bool:
            import re

            return bool(re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", email))

    # Transform with dependency injection
    @app.transform
    async def validate_with_service(
        record: dict,
        validator: EmailValidator,  # Injected automatically!
    ) -> dict:
        """Validate email using injected service."""
        email = record.get("email", "")
        record["email_verified"] = validator.is_valid(email)
        return record

    # Define pipeline
    @app.pipeline("user_data_pipeline")
    class UserDataPipeline(Pipeline):
        """Pipeline to process user data from CSV."""

        source = "csv_file"
        transforms = [
            clean_email,
            add_timestamp,
            validate_with_service,
        ]
        sink = "json_file"

        # Configuration
        batch_size = 5

        async def on_start(self, context):
            await context.log("Starting user data processing")

        async def on_complete(self, context):
            await context.log(f"Processed {context.metrics['records_processed']} records")

        async def on_error(self, error, record=None):
            print(f"Error processing record: {error}")
            if record:
                print(f"Record: {record}")

    # Create sample CSV data
    sample_csv = Path("users.csv")
    sample_csv.write_text("""name,email,age
John Doe,john.doe@example.com,30
Jane Smith,JANE.SMITH@EXAMPLE.COM,25
Bob Wilson,bob@invalid,40
Alice Brown,alice.brown@example.com,35
Invalid User,not-an-email,20
""")

    print("Sample CSV created:", sample_csv)
    print()

    # Run pipeline
    async with app:
        print("Running pipeline...")
        result = await app.pipelines.run("user_data_pipeline", file_path=str(sample_csv))

        print("\nPipeline completed!")
        print(f"State: {result.state}")
        print(f"Records processed: {result.records_processed}")
        print(f"Records failed: {result.records_failed}")
        print(f"Duration: {result.duration}")

        # Check output
        output_file = Path("users.json")
        if output_file.exists():
            print(f"\nOutput written to: {output_file}")
            print("Output preview:")
            import json

            with open(output_file) as f:
                data = json.load(f)
                for i, record in enumerate(data[:3]):
                    print(f"  Record {i + 1}: {record}")

    # Example 2: Pipeline with console output
    @app.pipeline("debug_pipeline")
    class DebugPipeline(Pipeline):
        """Pipeline that outputs to console for debugging."""

        source = "csv_file"
        transforms = [clean_email, validate_email_format]
        sink = "console"
        batch_size = 2

    print("\n" + "=" * 50)
    print("Running debug pipeline (console output)...")

    async with app:
        await app.pipelines.run("debug_pipeline", file_path=str(sample_csv))

    # Cleanup
    sample_csv.unlink()
    if output_file.exists():
        output_file.unlink()


if __name__ == "__main__":
    asyncio.run(main())
