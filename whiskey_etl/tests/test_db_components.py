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


async def test_etl_with_database_pipeline(app, mock_database):
    """Test complete ETL pipeline with database components."""
    # Define pipeline
    @app.pipeline("db_sync")
    class DatabaseSyncPipeline:
        source = "table"
        transforms = ["enrich_user"]
        sink = "upsert"
        
        def __init__(self, context):
            super().__init__(context)
            # Configure source
            self.source_config = {
                "table_name": "orders",
                "key_column": "order_id"
            }
            # Configure sink
            self.sink_config = {
                "table_name": "processed_orders",
                "key_columns": ["order_id"],
                "update_columns": ["status", "processed_at"]
            }
    
    # Define transform
    @app.sql_transform("lookup",
        lookup_query="SELECT name, email FROM users WHERE id = :user_id",
        input_fields=["user_id"],
        output_fields=["customer_name", "customer_email"])
    async def enrich_user(record, transform):
        return await transform.transform(record)
    
    # Mock source to return test data
    async def mock_extract(*args, **kwargs):
        for i in range(2):
            yield {"order_id": i, "user_id": i + 100, "amount": (i + 1) * 50}
    
    TableSource.extract = mock_extract
    
    # Run pipeline
    result = await app.pipelines.run("db_sync")
    
    assert result.is_success
    assert result.records_processed == 2
    assert result.records_failed == 0