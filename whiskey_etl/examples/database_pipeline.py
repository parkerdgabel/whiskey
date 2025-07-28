"""Example database ETL pipeline using whiskey_sql integration."""

import asyncio
from datetime import datetime

from whiskey import Whiskey
from whiskey_sql import sql_extension

from whiskey_etl import etl_extension


async def main():
    """Run database ETL examples."""
    # Create application
    app = Whiskey()

    # Add SQL support
    app.use(sql_extension)
    app.configure_database(
        url="postgresql://user:pass@localhost/etl_demo",
        pool_size=20,
        echo_queries=True,
    )

    # Add ETL support
    app.use(etl_extension)

    # Example 1: Simple table copy with transformations
    @app.pipeline("copy_users")
    class CopyUsersPipeline:
        """Copy users from source to destination with transformations."""
        source = "table"
        transforms = ["normalize_email", "add_metadata"]
        sink = "table"

        # Source configuration
        source_config = {
            "table_name": "raw_users",
            "key_column": "id",
            "batch_size": 1000,
        }

        # Sink configuration
        sink_config = {
            "table_name": "processed_users",
            "columns": ["id", "name", "email", "created_at", "processed_at"],
        }

    @app.transform
    async def normalize_email(record: dict) -> dict:
        """Normalize email addresses."""
        if "email" in record:
            record["email"] = record["email"].lower().strip()
        return record

    @app.transform
    async def add_metadata(record: dict) -> dict:
        """Add processing metadata."""
        record["processed_at"] = datetime.now()
        return record

    # Example 2: Data enrichment pipeline
    @app.pipeline("enrich_orders")
    class EnrichOrdersPipeline:
        """Enrich orders with customer and product information."""
        source = "query"
        transforms = ["enrich_customer", "enrich_product", "calculate_totals"]
        sink = "upsert"

        # Query recent orders
        source_config = {
            "query": """
                SELECT o.id, o.customer_id, o.product_id, o.quantity, o.unit_price
                FROM orders o
                WHERE o.created_at >= :start_date
                  AND o.status = 'pending'
                ORDER BY o.created_at
            """,
        }

        # Upsert enriched data
        sink_config = {
            "table_name": "enriched_orders",
            "key_columns": ["id"],
            "update_columns": [
                "customer_name", "customer_email", "customer_tier",
                "product_name", "product_category",
                "total_amount", "discount_amount", "final_amount"
            ],
        }

    @app.sql_transform("lookup",
        lookup_query="""
            SELECT name, email, tier, discount_rate
            FROM customers
            WHERE id = :customer_id
        """,
        input_fields=["customer_id"],
        output_fields=["customer_name", "customer_email", "customer_tier", "discount_rate"],
        cache_size=1000,  # Cache customer lookups
    )
    async def enrich_customer(record: dict, transform) -> dict:
        """Enrich with customer information."""
        return await transform.transform(record)

    @app.sql_transform("lookup",
        lookup_query="""
            SELECT name, category, weight
            FROM products
            WHERE id = :product_id
        """,
        input_fields=["product_id"],
        output_fields=["product_name", "product_category", "product_weight"],
        cache_size=5000,  # Products change less frequently
    )
    async def enrich_product(record: dict, transform) -> dict:
        """Enrich with product information."""
        return await transform.transform(record)

    @app.transform
    async def calculate_totals(record: dict) -> dict:
        """Calculate order totals with discounts."""
        quantity = record.get("quantity", 0)
        unit_price = record.get("unit_price", 0)
        discount_rate = record.get("discount_rate", 0)

        total_amount = quantity * unit_price
        discount_amount = total_amount * discount_rate
        final_amount = total_amount - discount_amount

        record.update({
            "total_amount": total_amount,
            "discount_amount": discount_amount,
            "final_amount": final_amount,
        })

        return record

    # Example 3: Data validation and cleanup
    @app.pipeline("validate_products")
    class ValidateProductsPipeline:
        """Validate and clean product data."""
        source = "table"
        transforms = [
            "validate_sku",
            "validate_price_range",
            "check_category",
            "standardize_data"
        ]
        sink = "sql_execute"

        source_config = {
            "table_name": "staging_products",
            "key_column": "id",
        }

        # Custom SQL for complex updates
        sink_config = {
            "query": """
                INSERT INTO products (sku, name, category_id, price, status)
                VALUES (:sku, :name, :category_id, :price, :status)
                ON CONFLICT (sku) DO UPDATE SET
                    name = EXCLUDED.name,
                    category_id = EXCLUDED.category_id,
                    price = EXCLUDED.price,
                    status = EXCLUDED.status,
                    updated_at = CURRENT_TIMESTAMP
            """,
        }

    @app.sql_transform("validate",
        validation_query="SELECT 1 FROM products WHERE sku = :sku",
        validation_fields=["sku"],
        on_invalid="mark",
        invalid_field="_sku_exists",
    )
    async def validate_sku(record: dict, transform) -> dict:
        """Check if SKU already exists."""
        return await transform.transform(record)

    @app.transform
    async def validate_price_range(record: dict) -> dict | None:
        """Validate price is within acceptable range."""
        price = record.get("price", 0)
        if price <= 0 or price > 10000:
            # Log invalid price and drop record
            print(f"Invalid price {price} for SKU {record.get('sku')}")
            return None
        return record

    @app.sql_transform("join",
        join_table="categories",
        join_keys={"category_name": "name"},
        select_fields=["id", "active"],
        join_type="LEFT",
    )
    async def check_category(record: dict, transform) -> dict:
        """Join with categories to get category ID."""
        result = await transform.transform(record)

        # Check if category exists and is active
        if result.get("categories_id"):
            result["category_id"] = result["categories_id"]
            result["status"] = "active" if result.get("categories_active") else "inactive"
        else:
            result["category_id"] = 1  # Default category
            result["status"] = "needs_review"

        # Clean up join fields
        for key in list(result.keys()):
            if key.startswith("categories_"):
                del result[key]

        return result

    @app.transform
    async def standardize_data(record: dict) -> dict:
        """Standardize data formats."""
        # Uppercase SKU
        if "sku" in record:
            record["sku"] = record["sku"].upper()

        # Title case name
        if "name" in record:
            record["name"] = record["name"].title()

        return record

    # Example 4: Aggregation pipeline
    @app.pipeline("sales_summary")
    class SalesSummaryPipeline:
        """Generate sales summary with aggregations."""
        source = "query"
        transforms = ["add_aggregates", "calculate_metrics"]
        sink = "table"

        source_config = {
            "query": """
                SELECT 
                    DATE_TRUNC('day', created_at) as sale_date,
                    product_id,
                    category_id,
                    SUM(quantity) as units_sold,
                    SUM(total_amount) as gross_revenue
                FROM sales
                WHERE created_at >= :start_date
                GROUP BY DATE_TRUNC('day', created_at), product_id, category_id
            """,
        }

        sink_config = {
            "table_name": "daily_sales_summary",
            "on_conflict": "(sale_date, product_id) DO UPDATE SET " +
                          "units_sold = EXCLUDED.units_sold, " +
                          "gross_revenue = EXCLUDED.gross_revenue, " +
                          "updated_at = CURRENT_TIMESTAMP",
        }

    @app.sql_transform("aggregate",
        aggregate_query="""
            SELECT 
                AVG(units_sold) as avg_daily_units,
                STDDEV(units_sold) as stddev_daily_units,
                MAX(gross_revenue) as max_daily_revenue
            FROM daily_sales_summary
            WHERE product_id = :product_id
              AND sale_date >= :sale_date - INTERVAL '30 days'
        """,
        group_by_fields=["product_id", "sale_date"],
        aggregate_fields=["avg_daily_units", "stddev_daily_units", "max_daily_revenue"],
    )
    async def add_aggregates(record: dict, transform) -> dict:
        """Add historical aggregates."""
        return await transform.transform(record)

    @app.transform
    async def calculate_metrics(record: dict) -> dict:
        """Calculate performance metrics."""
        # Performance vs average
        units_sold = record.get("units_sold", 0)
        avg_units = record.get("agg_avg_daily_units", 0)

        if avg_units > 0:
            record["performance_ratio"] = units_sold / avg_units
        else:
            record["performance_ratio"] = 0

        # Identify outliers (>2 std deviations)
        stddev = record.get("agg_stddev_daily_units", 0)
        if stddev > 0 and abs(units_sold - avg_units) > (2 * stddev):
            record["is_outlier"] = True
        else:
            record["is_outlier"] = False

        return record

    # Initialize application
    async with app:
        print("🚀 Starting database ETL examples...")

        # Run pipelines with different parameters

        # Copy all users
        print("\n📋 Copying users...")
        result = await app.pipelines.run("copy_users")
        print(f"✅ Copied {result.records_processed} users")

        # Enrich recent orders
        print("\n💰 Enriching orders...")
        result = await app.pipelines.run(
            "enrich_orders",
            start_date=datetime(2024, 1, 1)
        )
        print(f"✅ Enriched {result.records_processed} orders")

        # Validate products
        print("\n🔍 Validating products...")
        result = await app.pipelines.run("validate_products")
        print(f"✅ Validated {result.records_processed} products")
        if result.errors:
            print(f"⚠️  {len(result.errors)} validation errors")

        # Generate sales summary
        print("\n📊 Generating sales summary...")
        result = await app.pipelines.run(
            "sales_summary",
            start_date=datetime(2024, 1, 1)
        )
        print(f"✅ Generated summary for {result.records_processed} product-days")

        print("\n✨ All pipelines completed!")


if __name__ == "__main__":
    asyncio.run(main())
