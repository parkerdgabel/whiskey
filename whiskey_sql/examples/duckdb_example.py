"""Example of using DuckDB with Whiskey SQL for analytics."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
import random

from whiskey import Whiskey
from whiskey_sql import SQL, sql_extension


@dataclass
class SalesData:
    """Sales data model."""
    id: int
    product_name: str
    category: str
    quantity: int
    unit_price: float
    sale_date: datetime
    region: str


@dataclass
class ProductAnalytics:
    """Product analytics results."""
    product_name: str
    total_quantity: int
    total_revenue: float
    avg_price: float
    sale_count: int


async def main():
    """Demonstrate DuckDB analytics capabilities."""
    # Create application
    app = Whiskey()
    
    # Add SQL support with DuckDB
    app.use(sql_extension, 
        dialect="duckdb",
        url=":memory:",  # In-memory for demo
    )
    
    async with app.lifespan:
        # Get database
        from whiskey_sql import Database
        db = await app.container.resolve(Database)
        
        # Create sales table
        await db.execute(SQL("""
            CREATE TABLE sales (
                id INTEGER PRIMARY KEY,
                product_name VARCHAR NOT NULL,
                category VARCHAR NOT NULL,
                quantity INTEGER NOT NULL,
                unit_price DECIMAL(10, 2) NOT NULL,
                sale_date DATE NOT NULL,
                region VARCHAR NOT NULL
            )
        """))
        
        print("📊 DuckDB Analytics Example\n")
        
        # Generate sample data
        print("1️⃣ Generating sample sales data...")
        products = [
            ("Laptop", "Electronics", 1200.00),
            ("Mouse", "Electronics", 25.00),
            ("Keyboard", "Electronics", 75.00),
            ("Monitor", "Electronics", 300.00),
            ("Desk", "Furniture", 450.00),
            ("Chair", "Furniture", 250.00),
            ("Notebook", "Stationery", 5.00),
            ("Pen", "Stationery", 2.00),
        ]
        regions = ["North", "South", "East", "West"]
        
        # Insert sample data
        sales_data = []
        for i in range(1000):
            product = random.choice(products)
            sales_data.append({
                "id": i + 1,
                "product_name": product[0],
                "category": product[1],
                "quantity": random.randint(1, 10),
                "unit_price": product[2] * random.uniform(0.9, 1.1),  # ±10% price variation
                "sale_date": (datetime.now() - timedelta(days=random.randint(0, 365))).date(),
                "region": random.choice(regions),
            })
        
        await db.execute_many(
            SQL("""
                INSERT INTO sales (id, product_name, category, quantity, unit_price, sale_date, region)
                VALUES (:id, :product_name, :category, :quantity, :unit_price, :sale_date, :region)
            """),
            sales_data
        )
        print(f"✅ Inserted {len(sales_data)} sales records\n")
        
        # 2. Basic Analytics
        print("2️⃣ Basic Analytics:")
        
        # Total sales
        total_revenue = await db.fetch_val(SQL("""
            SELECT SUM(quantity * unit_price) as total_revenue
            FROM sales
        """))
        print(f"   Total Revenue: ${total_revenue:,.2f}")
        
        # Top products by revenue
        print("\n   Top 5 Products by Revenue:")
        top_products = await db.fetch_all(
            SQL("""
                SELECT 
                    product_name,
                    SUM(quantity) as total_quantity,
                    SUM(quantity * unit_price) as total_revenue,
                    AVG(unit_price) as avg_price,
                    COUNT(*) as sale_count
                FROM sales
                GROUP BY product_name
                ORDER BY total_revenue DESC
                LIMIT 5
            """),
            result_type=ProductAnalytics
        )
        
        for p in top_products:
            print(f"   - {p.product_name}: ${p.total_revenue:,.2f} ({p.sale_count} sales)")
        
        # 3. Time Series Analysis
        print("\n3️⃣ Monthly Sales Trend:")
        monthly_sales = await db.fetch_all(SQL("""
            SELECT 
                DATE_TRUNC('month', sale_date) as month,
                SUM(quantity * unit_price) as revenue,
                COUNT(*) as transactions
            FROM sales
            GROUP BY DATE_TRUNC('month', sale_date)
            ORDER BY month DESC
            LIMIT 6
        """))
        
        for row in monthly_sales:
            month = row["month"].strftime("%B %Y")
            print(f"   {month}: ${row['revenue']:,.2f} ({row['transactions']} transactions)")
        
        # 4. Window Functions
        print("\n4️⃣ Category Rankings (Window Functions):")
        category_rankings = await db.fetch_all(SQL("""
            WITH category_sales AS (
                SELECT 
                    category,
                    product_name,
                    SUM(quantity * unit_price) as product_revenue,
                    RANK() OVER (PARTITION BY category ORDER BY SUM(quantity * unit_price) DESC) as rank_in_category,
                    SUM(SUM(quantity * unit_price)) OVER (PARTITION BY category) as category_total
                FROM sales
                GROUP BY category, product_name
            )
            SELECT 
                category,
                product_name,
                product_revenue,
                rank_in_category,
                ROUND(100.0 * product_revenue / category_total, 2) as pct_of_category
            FROM category_sales
            WHERE rank_in_category <= 2
            ORDER BY category, rank_in_category
        """))
        
        current_category = None
        for row in category_rankings:
            if row["category"] != current_category:
                current_category = row["category"]
                print(f"\n   {current_category}:")
            print(f"     #{row['rank_in_category']} {row['product_name']}: "
                  f"${row['product_revenue']:,.2f} ({row['pct_of_category']}%)")
        
        # 5. Regional Analysis
        print("\n5️⃣ Regional Performance:")
        regional_stats = await db.fetch_all(SQL("""
            SELECT 
                region,
                COUNT(DISTINCT product_name) as products_sold,
                SUM(quantity) as units_sold,
                SUM(quantity * unit_price) as revenue,
                AVG(quantity * unit_price) as avg_order_value
            FROM sales
            GROUP BY region
            ORDER BY revenue DESC
        """))
        
        for row in regional_stats:
            print(f"   {row['region']}: ${row['revenue']:,.2f} "
                  f"({row['units_sold']} units, {row['products_sold']} products)")
        
        # 6. Export to Parquet
        print("\n6️⃣ Exporting Data:")
        
        # Export aggregated data to Parquet
        await db.export_parquet(
            SQL("""
                SELECT 
                    DATE_TRUNC('week', sale_date) as week,
                    category,
                    SUM(quantity) as units,
                    SUM(quantity * unit_price) as revenue
                FROM sales
                GROUP BY week, category
                ORDER BY week, category
            """),
            "weekly_sales.parquet"
        )
        print("   ✅ Exported weekly sales to weekly_sales.parquet")
        
        # Export to CSV
        await db.export_csv(
            SQL("SELECT * FROM sales ORDER BY sale_date DESC LIMIT 100"),
            "recent_sales.csv"
        )
        print("   ✅ Exported recent sales to recent_sales.csv")
        
        # 7. Complex Analytics Query
        print("\n7️⃣ Advanced Analytics - Moving Averages:")
        moving_avg = await db.fetch_all(SQL("""
            WITH daily_sales AS (
                SELECT 
                    sale_date,
                    SUM(quantity * unit_price) as daily_revenue
                FROM sales
                GROUP BY sale_date
            )
            SELECT 
                sale_date,
                daily_revenue,
                AVG(daily_revenue) OVER (
                    ORDER BY sale_date 
                    ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
                ) as moving_avg_7d,
                daily_revenue - LAG(daily_revenue, 1) OVER (ORDER BY sale_date) as daily_change
            FROM daily_sales
            ORDER BY sale_date DESC
            LIMIT 10
        """))
        
        print("   Date         Revenue    7-Day Avg   Change")
        print("   " + "-" * 45)
        for row in moving_avg:
            date_str = row["sale_date"].strftime("%Y-%m-%d")
            change = row["daily_change"] or 0
            change_str = f"+${change:,.2f}" if change >= 0 else f"-${abs(change):,.2f}"
            print(f"   {date_str}  ${row['daily_revenue']:>8,.2f}  "
                  f"${row['moving_avg_7d']:>8,.2f}  {change_str:>10}")
        
        print("\n✨ DuckDB provides powerful analytics capabilities with SQL!")
        print("   - Window functions for rankings and moving averages")
        print("   - Efficient columnar storage for analytical queries")
        print("   - Native Parquet and CSV export support")
        print("   - Perfect for data analysis and reporting workloads")


if __name__ == "__main__":
    asyncio.run(main())