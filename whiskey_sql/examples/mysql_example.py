"""MySQL example for Whiskey SQL extension."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from whiskey import Whiskey, inject, singleton
from whiskey_sql import SQL, Database, sql_extension


# Define your data models
@dataclass
class Product:
    id: int
    name: str
    price: Decimal
    stock: int
    created_at: datetime


@dataclass
class Order:
    id: int
    product_id: int
    quantity: int
    total_price: Decimal
    order_date: datetime
    status: str


# Create application with SQL extension
app = Whiskey()
app.use(sql_extension)

# Configure MySQL database
app.configure_database(
    url="mysql://root:password@localhost/whiskey_demo", pool_size=20, echo_queries=True
)


# Define SQL queries
@app.sql("products")
class ProductQueries:
    """SQL queries for product operations."""

    create_table = SQL("""
        CREATE TABLE IF NOT EXISTS products (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            price DECIMAL(10, 2) NOT NULL,
            stock INT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_name (name)
        )
    """)

    get_by_id = SQL("""
        SELECT id, name, price, stock, created_at
        FROM products
        WHERE id = :id
    """)

    list_available = SQL("""
        SELECT id, name, price, stock, created_at
        FROM products
        WHERE stock > 0
        ORDER BY name
    """)

    create = SQL("""
        INSERT INTO products (name, price, stock)
        VALUES (:name, :price, :stock)
    """)

    update_stock = SQL("""
        UPDATE products
        SET stock = stock - :quantity
        WHERE id = :id AND stock >= :quantity
    """)

    search = SQL("""
        SELECT id, name, price, stock, created_at
        FROM products
        WHERE name LIKE :pattern
        ORDER BY name
        LIMIT :limit
    """)

    # MySQL-specific: Using JSON functions
    get_low_stock = SQL("""
        SELECT 
            id,
            name,
            stock,
            JSON_OBJECT('id', id, 'name', name, 'stock', stock) as json_data
        FROM products
        WHERE stock < :threshold
        ORDER BY stock ASC
    """)


@app.sql("orders")
class OrderQueries:
    """SQL queries for order operations."""

    create_table = SQL("""
        CREATE TABLE IF NOT EXISTS orders (
            id INT AUTO_INCREMENT PRIMARY KEY,
            product_id INT NOT NULL,
            quantity INT NOT NULL,
            total_price DECIMAL(10, 2) NOT NULL,
            order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status ENUM('pending', 'completed', 'cancelled') DEFAULT 'pending',
            FOREIGN KEY (product_id) REFERENCES products(id),
            INDEX idx_status (status),
            INDEX idx_date (order_date)
        )
    """)

    create = SQL("""
        INSERT INTO orders (product_id, quantity, total_price, status)
        VALUES (:product_id, :quantity, :total_price, :status)
    """)

    get_by_id = SQL("""
        SELECT id, product_id, quantity, total_price, order_date, status
        FROM orders
        WHERE id = :id
    """)

    # MySQL-specific: WITH ROLLUP for grouping
    daily_sales = SQL("""
        SELECT 
            DATE(order_date) as sale_date,
            COUNT(*) as order_count,
            SUM(total_price) as total_revenue
        FROM orders
        WHERE status = 'completed'
          AND order_date >= :start_date
        GROUP BY DATE(order_date) WITH ROLLUP
    """)


@singleton
class ProductService:
    """Service for product operations."""

    def __init__(self, db: Database, queries: ProductQueries):
        self.db = db
        self.queries = queries

    async def create_product(self, name: str, price: Decimal, stock: int) -> int:
        """Create a new product."""
        await self.db.execute(self.queries.create, {"name": name, "price": price, "stock": stock})

        # Get the last inserted ID (MySQL specific)
        product_id = await self.db.fetch_val(SQL("SELECT LAST_INSERT_ID()"))
        return product_id

    async def get_product(self, product_id: int) -> Product | None:
        """Get product by ID."""
        return await self.db.fetch_one(self.queries.get_by_id, {"id": product_id}, Product)

    async def list_available(self) -> list[Product]:
        """List all available products."""
        return await self.db.fetch_all(self.queries.list_available, result_type=Product)

    async def search_products(self, search_term: str, limit: int = 10) -> list[Product]:
        """Search products by name."""
        return await self.db.fetch_all(
            self.queries.search,
            {"pattern": f"%{search_term}%", "limit": limit},
            result_type=Product,
        )

    async def get_low_stock_report(self, threshold: int = 10) -> list[dict]:
        """Get low stock products with JSON data."""
        return await self.db.fetch_all(self.queries.get_low_stock, {"threshold": threshold})


@singleton
class OrderService:
    """Service for order operations."""

    def __init__(self, db: Database, product_queries: ProductQueries, order_queries: OrderQueries):
        self.db = db
        self.product_queries = product_queries
        self.order_queries = order_queries

    async def place_order(self, product_id: int, quantity: int) -> Order | None:
        """Place an order with stock validation."""
        async with self.db.transaction() as tx:
            # Get product and check stock
            product = await tx.fetch_one(self.product_queries.get_by_id, {"id": product_id})

            if not product or product["stock"] < quantity:
                return None  # Insufficient stock

            # Calculate total
            total_price = product["price"] * quantity

            # Update stock
            await tx.execute(
                self.product_queries.update_stock, {"id": product_id, "quantity": quantity}
            )

            # Create order
            await tx.execute(
                self.order_queries.create,
                {
                    "product_id": product_id,
                    "quantity": quantity,
                    "total_price": total_price,
                    "status": "completed",
                },
            )

            # Get the created order
            order_id = await tx.fetch_val(SQL("SELECT LAST_INSERT_ID()"))

            return await self.db.fetch_one(self.order_queries.get_by_id, {"id": order_id}, Order)

    async def get_daily_sales(self, start_date: datetime) -> list[dict]:
        """Get daily sales report."""
        return await self.db.fetch_all(self.order_queries.daily_sales, {"start_date": start_date})


# Initialize database
@app.on_startup
async def init_database(db: Database, product_queries: ProductQueries, order_queries: OrderQueries):
    """Create database tables on startup."""
    print("🗄️  Initializing MySQL database...")

    await db.execute(product_queries.create_table)
    await db.execute(order_queries.create_table)

    print("✅ Database ready")


# Demo application
@app.main
@inject
async def main(product_service: ProductService, order_service: OrderService, db: Database):
    """Demonstrate MySQL usage."""

    print("\n=== Whiskey SQL MySQL Example ===\n")

    # Create some products
    print("Creating products...")
    products = [
        ("Laptop", Decimal("999.99"), 10),
        ("Mouse", Decimal("29.99"), 50),
        ("Keyboard", Decimal("79.99"), 30),
        ("Monitor", Decimal("299.99"), 15),
        ("Headphones", Decimal("149.99"), 20),
    ]

    product_ids = []
    for name, price, stock in products:
        pid = await product_service.create_product(name, price, stock)
        product_ids.append(pid)
        print(f"✅ Created {name} (ID: {pid})")

    # List available products
    print("\nAvailable products:")
    available = await product_service.list_available()
    for product in available:
        print(f"  - {product.name}: ${product.price} (stock: {product.stock})")

    # Search products
    print("\nSearching for 'phone'...")
    results = await product_service.search_products("phone")
    for product in results:
        print(f"  Found: {product.name}")

    # Place some orders
    print("\nPlacing orders...")
    orders = [
        (product_ids[0], 2),  # 2 Laptops
        (product_ids[1], 5),  # 5 Mice
        (product_ids[2], 3),  # 3 Keyboards
    ]

    for product_id, quantity in orders:
        order = await order_service.place_order(product_id, quantity)
        if order:
            print(f"✅ Order #{order.id}: {quantity} items, total: ${order.total_price}")
        else:
            print(f"❌ Failed to place order for product {product_id}")

    # Get low stock report
    print("\nLow stock report (threshold: 20):")
    low_stock = await product_service.get_low_stock_report(20)
    for item in low_stock:
        print(f"  - {item['name']}: {item['stock']} units")
        print(f"    JSON: {item['json_data']}")

    # Get sales report
    print("\nDaily sales report:")
    from datetime import date

    sales = await order_service.get_daily_sales(date.today())
    for row in sales:
        if row["sale_date"]:  # Skip the ROLLUP total row
            print(f"  {row['sale_date']}: {row['order_count']} orders, ${row['total_revenue']}")
        else:
            print(f"  TOTAL: {row['order_count']} orders, ${row['total_revenue']}")

    # Demonstrate MySQL-specific features
    print("\nMySQL-specific features:")

    # Check version
    version = await db.fetch_val(SQL("SELECT VERSION()"))
    print(f"  MySQL version: {version}")

    # Show table status
    status = await db.fetch_all(SQL("SHOW TABLE STATUS WHERE Name IN ('products', 'orders')"))
    for table in status:
        print(f"  Table {table['Name']}: {table['Rows']} rows, engine: {table['Engine']}")

    # Use streaming for large results
    print("\nStreaming all products:")
    async with db.stream(SQL("SELECT * FROM products")) as cursor:
        async for row in cursor:
            print(f"  Stream: {row['name']}")

    print("\n✅ Demo completed!")

    # Cleanup (optional)
    # await db.execute(SQL("DROP TABLE orders"))
    # await db.execute(SQL("DROP TABLE products"))


if __name__ == "__main__":
    # Run the application
    app.run()
