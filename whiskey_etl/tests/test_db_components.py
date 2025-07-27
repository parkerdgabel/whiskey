"""Tests for database ETL components."""

import pytest
from unittest.mock import AsyncMock, MagicMock, call

from whiskey import Whiskey
from whiskey_sql import Database, SQL
from whiskey_etl import (
    etl_extension,
    DatabaseSource,
    TableSource,
    QuerySource,
    SQLFileSource,
    TableSink,
    UpsertSink,
    BulkUpdateSink,
    SQLExecuteSink,
    LookupTransform,
    JoinTransform,
    ValidateTransform,
    AggregateTransform,
)
from whiskey_etl.errors import TransformError


@pytest.fixture
def mock_database():
    """Create a mock database instance."""
    db = MagicMock(spec=Database)
    db.dialect = "postgresql"
    
    # Mock streaming
    async def mock_stream(query, params=None, fetch_size=100):
        # Yield some test data
        for i in range(3):
            yield {"id": i, "name": f"Record {i}"}
    
    db.stream = mock_stream
    
    # Mock fetch methods
    db.fetch_all = AsyncMock(return_value=[
        {"id": 1, "name": "Record 1"},
        {"id": 2, "name": "Record 2"},
    ])
    db.fetch_one = AsyncMock(return_value={"id": 1, "name": "Record 1"})
    db.fetch_val = AsyncMock(return_value=True)
    db.execute_many = AsyncMock()
    db.transaction = MagicMock()
    
    return db


@pytest.fixture
async def app(mock_database):
    """Create Whiskey app with ETL and mocked database."""
    app = Whiskey()
    app.use(etl_extension)
    
    # Register mock database
    app.container[Database] = mock_database
    
    async with app:
        yield app


class TestDatabaseSource:
    """Test database source implementations."""

    async def test_database_source_with_query(self, mock_database):
        """Test DatabaseSource with raw query."""
        source = DatabaseSource(mock_database)
        
        records = []
        async for record in source.extract(query="SELECT * FROM users"):
            records.append(record)
        
        assert len(records) == 3
        assert records[0]["name"] == "Record 0"

    async def test_database_source_with_table(self, mock_database):
        """Test DatabaseSource with table name."""
        source = DatabaseSource(mock_database)
        
        records = []
        async for record in source.extract(
            table="users",
            columns=["id", "name"],
            where="active = true",
            order_by="created_at DESC",
            limit=10
        ):
            records.append(record)
        
        assert len(records) == 3

    async def test_database_source_no_streaming(self, mock_database):
        """Test DatabaseSource without streaming."""
        source = DatabaseSource(mock_database, fetch_size=100)
        
        records = []
        async for record in source.extract(
            query="SELECT * FROM users",
            stream=False
        ):
            records.append(record)
        
        assert len(records) == 2  # fetch_all returns 2 records
        mock_database.fetch_all.assert_called_once()

    async def test_table_source(self, mock_database):
        """Test TableSource with pagination."""
        source = TableSource(mock_database, "products", key_column="sku")
        
        records = []
        async for record in source.extract(
            start_key="A100",
            end_key="Z999",
            columns=["sku", "name", "price"]
        ):
            records.append(record)
        
        assert len(records) == 3

    async def test_query_source(self, mock_database):
        """Test QuerySource with parameters."""
        source = QuerySource(
            mock_database,
            "SELECT * FROM orders WHERE status = :status AND date >= :start_date"
        )
        
        records = []
        async for record in source.extract(status="pending", start_date="2024-01-01"):
            records.append(record)
        
        assert len(records) == 3


class TestDatabaseSink:
    """Test database sink implementations."""

    async def test_table_sink_insert(self, mock_database):
        """Test TableSink basic insert."""
        sink = TableSink(mock_database, "users")
        
        records = [
            {"id": 1, "name": "Alice", "email": "alice@example.com"},
            {"id": 2, "name": "Bob", "email": "bob@example.com"},
        ]
        
        await sink.load(records)
        
        # Verify execute_many was called
        mock_database.execute_many.assert_called_once()
        query_arg = mock_database.execute_many.call_args[0][0]
        assert isinstance(query_arg, SQL)
        assert "INSERT INTO users" in str(query_arg)

    async def test_table_sink_with_transaction(self, mock_database):
        """Test TableSink with transaction."""
        # Mock transaction context manager
        mock_transaction = AsyncMock()
        mock_transaction.__aenter__ = AsyncMock(return_value=mock_transaction)
        mock_transaction.__aexit__ = AsyncMock(return_value=None)
        mock_database.transaction.return_value = mock_transaction
        
        sink = TableSink(mock_database, "users", use_transaction=True)
        
        records = [{"id": 1, "name": "Alice"}]
        await sink.load(records)
        
        # Verify transaction was used
        mock_database.transaction.assert_called_once()
        mock_transaction.__aenter__.assert_called_once()
        mock_transaction.__aexit__.assert_called_once()

    async def test_upsert_sink(self, mock_database):
        """Test UpsertSink functionality."""
        sink = UpsertSink(
            mock_database,
            "products",
            key_columns=["sku"],
            update_columns=["name", "price"],
            columns=["sku", "name", "price", "category"]
        )
        
        records = [
            {"sku": "ABC123", "name": "Product 1", "price": 99.99, "category": "Electronics"},
            {"sku": "XYZ789", "name": "Product 2", "price": 49.99, "category": "Books"},
        ]
        
        await sink.load(records)
        
        # Verify the query includes ON CONFLICT
        query_arg = mock_database.execute_many.call_args[0][0]
        query_str = str(query_arg)
        assert "ON CONFLICT (sku) DO UPDATE SET" in query_str
        assert "name = EXCLUDED.name" in query_str
        assert "price = EXCLUDED.price" in query_str

    async def test_bulk_update_sink(self, mock_database):
        """Test BulkUpdateSink functionality."""
        sink = BulkUpdateSink(
            mock_database,
            "inventory",
            key_columns=["warehouse_id", "sku"],
            update_columns=["quantity", "last_updated"]
        )
        
        records = [
            {"warehouse_id": 1, "sku": "ABC123", "quantity": 100, "last_updated": "2024-01-01"},
            {"warehouse_id": 2, "sku": "XYZ789", "quantity": 50, "last_updated": "2024-01-01"},
        ]
        
        await sink.load(records)
        
        # Verify UPDATE query
        query_arg = mock_database.execute_many.call_args[0][0]
        query_str = str(query_arg)
        assert "UPDATE inventory SET" in query_str
        assert "quantity = :quantity" in query_str
        assert "WHERE warehouse_id = :key_warehouse_id AND sku = :key_sku" in query_str

    async def test_sql_execute_sink(self, mock_database):
        """Test SQLExecuteSink with custom query."""
        sink = SQLExecuteSink(
            mock_database,
            "CALL process_order(:order_id, :status)"
        )
        
        records = [
            {"order_id": 123, "status": "shipped"},
            {"order_id": 456, "status": "delivered"},
        ]
        
        await sink.load(records)
        
        mock_database.execute_many.assert_called_once()


class TestSQLTransforms:
    """Test SQL transform implementations."""

    async def test_lookup_transform(self, mock_database):
        """Test LookupTransform enrichment."""
        mock_database.fetch_one.return_value = {
            "name": "John Doe",
            "email": "john@example.com",
            "department": "Engineering"
        }
        
        transform = LookupTransform(
            mock_database,
            lookup_query="SELECT name, email, department FROM users WHERE id = :user_id",
            input_fields=["user_id"],
            output_fields=["name", "email"]
        )
        
        record = {"order_id": 123, "user_id": 456, "amount": 99.99}
        result = await transform.transform(record)
        
        assert result["order_id"] == 123
        assert result["user_id"] == 456
        assert result["amount"] == 99.99
        assert result["name"] == "John Doe"
        assert result["email"] == "john@example.com"
        assert "department" not in result  # Not in output_fields

    async def test_lookup_transform_with_cache(self, mock_database):
        """Test LookupTransform caching."""
        mock_database.fetch_one.return_value = {"name": "John"}
        
        transform = LookupTransform(
            mock_database,
            "SELECT name FROM users WHERE id = :id",
            input_fields=["id"],
            cache_size=10
        )
        
        # First call
        await transform.transform({"id": 1})
        assert mock_database.fetch_one.call_count == 1
        
        # Second call with same id - should use cache
        await transform.transform({"id": 1})
        assert mock_database.fetch_one.call_count == 1
        
        # Different id - should query again
        await transform.transform({"id": 2})
        assert mock_database.fetch_one.call_count == 2

    async def test_join_transform(self, mock_database):
        """Test JoinTransform functionality."""
        mock_database.fetch_one.return_value = {
            "category_name": "Electronics",
            "discount_rate": 0.1
        }
        
        transform = JoinTransform(
            mock_database,
            join_table="categories",
            join_keys={"category_id": "id"},
            select_fields=["category_name", "discount_rate"]
        )
        
        record = {"product_id": 123, "category_id": 5, "price": 99.99}
        result = await transform.transform(record)
        
        assert result["product_id"] == 123
        assert result["category_id"] == 5
        assert result["price"] == 99.99
        assert result["categories_category_name"] == "Electronics"
        assert result["categories_discount_rate"] == 0.1

    async def test_validate_transform_drop(self, mock_database):
        """Test ValidateTransform with drop mode."""
        mock_database.fetch_val.return_value = False
        
        transform = ValidateTransform(
            mock_database,
            validation_query="SELECT 1 FROM products WHERE sku = :sku",
            validation_fields=["sku"],
            on_invalid="drop"
        )
        
        record = {"sku": "INVALID", "name": "Bad Product"}
        result = await transform.transform(record)
        
        assert result is None  # Record dropped

    async def test_validate_transform_mark(self, mock_database):
        """Test ValidateTransform with mark mode."""
        mock_database.fetch_val.side_effect = [False, True]  # First invalid, then valid
        
        transform = ValidateTransform(
            mock_database,
            "SELECT 1 FROM products WHERE sku = :sku",
            validation_fields=["sku"],
            on_invalid="mark",
            invalid_field="_valid"
        )
        
        # Invalid record
        record1 = {"sku": "INVALID", "name": "Bad Product"}
        result1 = await transform.transform(record1)
        assert result1["_valid"] is False
        
        # Valid record
        record2 = {"sku": "VALID", "name": "Good Product"}
        result2 = await transform.transform(record2)
        assert result2["_valid"] is True

    async def test_aggregate_transform(self, mock_database):
        """Test AggregateTransform functionality."""
        mock_database.fetch_one.return_value = {
            "total_orders": 42,
            "total_revenue": 12345.67,
            "avg_order_value": 294.18
        }
        
        transform = AggregateTransform(
            mock_database,
            aggregate_query="""
                SELECT COUNT(*) as total_orders,
                       SUM(amount) as total_revenue,
                       AVG(amount) as avg_order_value
                FROM orders
                WHERE customer_id = :customer_id
            """,
            group_by_fields=["customer_id"],
            aggregate_fields=["total_orders", "total_revenue"]
        )
        
        record = {"customer_id": 123, "order_id": 456}
        result = await transform.transform(record)
        
        assert result["customer_id"] == 123
        assert result["order_id"] == 456
        assert result["agg_total_orders"] == 42
        assert result["agg_total_revenue"] == 12345.67
        assert "agg_avg_order_value" not in result  # Not in aggregate_fields


async def test_database_sink_base_not_implemented(mock_database):
    """Test that DatabaseSink base class raises NotImplementedError."""
    from whiskey_etl import DatabaseSink
    
    sink = DatabaseSink(mock_database)
    with pytest.raises(NotImplementedError):
        await sink.load([])


async def test_sql_transform_base_not_implemented(mock_database):
    """Test that SQLTransform base class raises NotImplementedError."""
    from whiskey_etl import SQLTransform
    
    transform = SQLTransform(mock_database)
    with pytest.raises(NotImplementedError):
        await transform.transform({})


async def test_lookup_transform_with_all_fields(mock_database):
    """Test LookupTransform returns all fields when output_fields is None."""
    from whiskey_etl import LookupTransform
    
    mock_database.fetch_one.return_value = {
        "name": "John",
        "email": "john@example.com",
        "department": "Engineering",
        "level": 5
    }
    
    transform = LookupTransform(
        mock_database,
        "SELECT * FROM users WHERE id = :user_id",
        input_fields=["user_id"],
        output_fields=None,  # Should include all fields
    )
    
    result = await transform.transform({"user_id": 123, "order_id": 456})
    
    # Should have all fields from lookup
    assert result["name"] == "John"
    assert result["email"] == "john@example.com"
    assert result["department"] == "Engineering"
    assert result["level"] == 5
    assert result["order_id"] == 456


async def test_lookup_transform_error_on_missing(mock_database):
    """Test LookupTransform with on_missing='error'."""
    from whiskey_etl import LookupTransform
    
    mock_database.fetch_one.return_value = None
    
    transform = LookupTransform(
        mock_database,
        "SELECT * FROM users WHERE id = :user_id",
        input_fields=["user_id"],
        on_missing="error",
    )
    
    with pytest.raises(TransformError) as exc_info:
        await transform.transform({"user_id": 999})
    
    assert "Lookup returned no results" in str(exc_info.value)


async def test_sql_file_source(mock_database, tmp_path):
    """Test SQLFileSource functionality."""
    from whiskey_etl import SQLFileSource
    
    # Create SQL file
    sql_file = tmp_path / "query.sql"
    sql_file.write_text("SELECT * FROM users WHERE active = :active")
    
    source = SQLFileSource(mock_database, str(sql_file))
    
    records = []
    async for record in source.extract(active=True):
        records.append(record)
    
    assert len(records) == 3


async def test_table_source_with_stream_disabled(mock_database):
    """Test TableSource without streaming."""
    from whiskey_etl import TableSource
    
    source = TableSource(mock_database, "products")
    
    records = []
    async for record in source.extract(stream=False):
        records.append(record)
    
    assert len(records) == 2  # fetch_all returns 2 records
    mock_database.fetch_all.assert_called()


async def test_create_sql_transform_invalid_type():
    """Test create_sql_transform with invalid type."""
    from whiskey_etl import create_sql_transform
    from whiskey_sql import Database
    
    mock_db = MagicMock(spec=Database)
    
    with pytest.raises(ValueError) as exc_info:
        create_sql_transform("invalid_type", mock_db)
    
    assert "Unknown transform type" in str(exc_info.value)


async def test_table_sink_empty_records(mock_database):
    """Test TableSink with empty records list."""
    from whiskey_etl import TableSink
    
    sink = TableSink(mock_database, "users")
    await sink.load([])  # Should return early without error
    
    mock_database.execute_many.assert_not_called()


async def test_join_transform_inner_no_match(mock_database):
    """Test JoinTransform INNER join with no match filters record."""
    from whiskey_etl import JoinTransform
    
    mock_database.fetch_one.return_value = None  # No match
    
    transform = JoinTransform(
        mock_database,
        "categories",
        join_keys={"category_id": "id"},
        join_type="INNER",
    )
    
    result = await transform.transform({"product_id": 123, "category_id": 999})
    
    assert result is None  # INNER join with no match returns None


async def test_join_transform_missing_key(mock_database):
    """Test JoinTransform with missing join key."""
    from whiskey_etl import JoinTransform
    
    transform = JoinTransform(
        mock_database,
        "categories",
        join_keys={"category_id": "id"},
    )
    
    with pytest.raises(TransformError) as exc_info:
        await transform.transform({"product_id": 123})
    
    assert "Missing join key field" in str(exc_info.value)


async def test_validate_transform_error_mode(mock_database):
    """Test ValidateTransform with on_invalid='error'."""
    from whiskey_etl import ValidateTransform
    
    mock_database.fetch_val.return_value = False
    
    transform = ValidateTransform(
        mock_database,
        "SELECT 1 FROM products WHERE sku = :sku",
        validation_fields=["sku"],
        on_invalid="error",
    )
    
    with pytest.raises(TransformError) as exc_info:
        await transform.transform({"sku": "INVALID"})
    
    assert "Record failed validation" in str(exc_info.value)


async def test_bulk_update_sink_empty_records(mock_database):
    """Test BulkUpdateSink with empty records."""
    from whiskey_etl import BulkUpdateSink
    
    sink = BulkUpdateSink(
        mock_database,
        "inventory",
        key_columns=["id"],
        update_columns=["quantity"],
    )
    
    await sink.load([])
    mock_database.execute_many.assert_not_called()


async def test_sql_execute_sink_empty_records(mock_database):
    """Test SQLExecuteSink with empty records."""
    from whiskey_etl import SQLExecuteSink
    
    sink = SQLExecuteSink(mock_database, "CALL process_order(:id)")
    await sink.load([])
    
    mock_database.execute_many.assert_not_called()


async def test_sql_transform_factories(mock_database):
    """Test SQL transform factory functions."""
    from whiskey_etl import (
        create_lookup_transform,
        create_join_transform,
        create_validate_transform,
        create_aggregate_transform,
    )
    
    # Test lookup factory
    lookup = create_lookup_transform(
        mock_database,
        "SELECT * FROM users WHERE id = :id",
        input_fields=["id"],
    )
    assert callable(lookup)
    
    # Test join factory
    join = create_join_transform(
        mock_database,
        "categories",
        join_keys={"cat_id": "id"},
    )
    assert callable(join)
    
    # Test validate factory
    validate = create_validate_transform(
        mock_database,
        "SELECT 1 FROM products WHERE sku = :sku",
        validation_fields=["sku"],
    )
    assert callable(validate)
    
    # Test aggregate factory
    aggregate = create_aggregate_transform(
        mock_database,
        "SELECT COUNT(*) as count FROM orders WHERE user_id = :user_id",
        group_by_fields=["user_id"],
        aggregate_fields=["count"],
    )
    assert callable(aggregate)


async def test_etl_with_database_pipeline(mock_database):
    """Test complete ETL pipeline with database components."""
    from whiskey import Whiskey
    from whiskey_etl import etl_extension
    from whiskey_etl.sources import MemorySource
    from whiskey_etl.sinks import MemorySink
    from whiskey_etl.pipeline import PipelineManager
    
    app = Whiskey()
    app.use(etl_extension)
    
    # Use memory source/sink for the pipeline test
    test_data = [
        {"order_id": 0, "user_id": 100, "amount": 50},
        {"order_id": 1, "user_id": 101, "amount": 100},
    ]
    
    source = MemorySource(test_data)
    sink = MemorySink()
    
    # Define pipeline
    from whiskey_etl.pipeline import Pipeline
    
    @app.pipeline("db_sync")
    class DatabaseSyncPipeline(Pipeline):
        source = "memory"
        transforms = ["enrich_user"]
        sink = "memory"
        batch_size = 2
    
    # Define transform using mock database
    @app.transform
    async def enrich_user(record: dict) -> dict:
        # Simulate database lookup
        if record["user_id"] == 100:
            record["customer_name"] = "Alice"
            record["customer_email"] = "alice@example.com"
        elif record["user_id"] == 101:
            record["customer_name"] = "Bob" 
            record["customer_email"] = "bob@example.com"
        return record
    
    # Get pipeline manager
    manager = await app.container.resolve(PipelineManager)
    
    # Register built-in memory source/sink
    manager.source_registry.register("memory", MemorySource)
    manager.sink_registry.register("memory", MemorySink)
    
    # Set instances
    app.container[MemorySource] = source
    app.container[MemorySink] = sink
    
    # Run pipeline (no app context needed)
    result = await manager.run("db_sync")
    
    assert result.is_success
    assert result.records_processed == 2
    assert result.records_failed == 0
    
    # Check output
    output = sink.get_data()
    assert len(output) == 2
    assert all("customer_name" in r for r in output)
    assert all("customer_email" in r for r in output)