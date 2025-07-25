"""
Real-World Microservice Example

This comprehensive example demonstrates a complete microservice built with Whiskey,
showcasing all major features working together:
- Named dependencies for multiple implementations
- Conditional registration based on environment
- Lazy resolution for performance
- Rich application framework with lifecycle
- Event-driven architecture
- Background tasks and monitoring
- Component discovery and introspection

This represents a realistic e-commerce order processing service.

Run this example:
    python examples/10_real_world_microservice.py
"""

import asyncio
import os
import time
from datetime import datetime
from typing import Annotated, Protocol

from whiskey import (
    Application, ApplicationConfig, Container,
    inject, provide, singleton, factory, scoped,
    Inject, Initializable, Disposable
)
from whiskey.core.conditions import env_equals, env_exists, env_truthy, all_conditions
from whiskey.core.lazy import Lazy, LazyDescriptor
from whiskey.core.scopes import ContextVarScope


# Step 1: Infrastructure Interfaces and Implementations
# ======================================================

class Database(Protocol):
    """Database interface."""
    async def query(self, sql: str) -> list[dict]: ...
    async def execute(self, sql: str) -> bool: ...
    async def health_check(self) -> dict: ...


class Cache(Protocol):
    """Cache interface."""
    def get(self, key: str) -> str | None: ...
    def set(self, key: str, value: str, ttl: int = 300) -> None: ...
    def health_check(self) -> dict: ...


class MessageQueue(Protocol):
    """Message queue interface."""
    async def publish(self, topic: str, message: dict) -> None: ...
    async def subscribe(self, topic: str, handler) -> None: ...


# Database Implementations (conditionally registered)
@singleton(
    name="primary", 
    condition=all_conditions(
        env_equals("DB_TYPE", "postgres"),
        env_exists("DATABASE_URL")
    )
)
class PostgresDatabase(Initializable, Disposable):
    """PostgreSQL database implementation."""
    
    def __init__(self):
        self.url = os.getenv("DATABASE_URL", "postgresql://localhost/orders")
        self.connected = False
        self.query_count = 0
        
    async def initialize(self):
        print(f"🐘 Connecting to PostgreSQL: {self.url}")
        await asyncio.sleep(0.2)  # Simulate connection
        self.connected = True
        print("✅ PostgreSQL connected")
        
    async def dispose(self):
        print("🐘 Disconnecting from PostgreSQL")
        self.connected = False
        
    async def query(self, sql: str) -> list[dict]:
        if not self.connected:
            raise RuntimeError("Database not connected")
        self.query_count += 1
        print(f"🐘 PostgreSQL Query #{self.query_count}: {sql}")
        return [{"id": 1, "data": f"postgres_result_{self.query_count}"}]
        
    async def execute(self, sql: str) -> bool:
        if not self.connected:
            raise RuntimeError("Database not connected")
        self.query_count += 1
        print(f"🐘 PostgreSQL Execute #{self.query_count}: {sql}")
        return True
        
    async def health_check(self) -> dict:
        return {
            "status": "healthy" if self.connected else "unhealthy",
            "type": "postgresql",
            "queries_executed": self.query_count,
            "url": self.url
        }


@singleton(
    name="primary",
    condition=env_equals("DB_TYPE", "sqlite")
)
class SQLiteDatabase(Initializable):
    """SQLite database implementation (fallback)."""
    
    def __init__(self):
        self.db_file = "orders.db"
        self.query_count = 0
        
    async def initialize(self):
        print(f"💾 Initializing SQLite database: {self.db_file}")
        await asyncio.sleep(0.1)
        print("✅ SQLite ready")
        
    async def query(self, sql: str) -> list[dict]:
        self.query_count += 1
        print(f"💾 SQLite Query #{self.query_count}: {sql}")
        return [{"id": 1, "data": f"sqlite_result_{self.query_count}"}]
        
    async def execute(self, sql: str) -> bool:
        self.query_count += 1
        print(f"💾 SQLite Execute #{self.query_count}: {sql}")
        return True
        
    async def health_check(self) -> dict:
        return {
            "status": "healthy",
            "type": "sqlite",
            "queries_executed": self.query_count,
            "file": self.db_file
        }


# Cache Implementations (conditionally registered)
@provide(name="redis", condition=env_exists("REDIS_URL"))
class RedisCache:
    """Redis cache implementation."""
    
    def __init__(self):
        self.url = os.getenv("REDIS_URL", "redis://localhost")
        self.data = {}
        print(f"🔴 Redis cache initialized: {self.url}")
        
    def get(self, key: str) -> str | None:
        return self.data.get(key)
        
    def set(self, key: str, value: str, ttl: int = 300) -> None:
        self.data[key] = value
        print(f"🔴 Redis SET: {key} (TTL: {ttl}s)")
        
    def health_check(self) -> dict:
        return {
            "status": "healthy",
            "type": "redis",
            "entries": len(self.data),
            "url": self.url
        }


@provide(name="memory", condition=lambda: not env_exists("REDIS_URL")())
class MemoryCache:
    """In-memory cache implementation (fallback)."""
    
    def __init__(self):
        self.data = {}
        print("🧠 Memory cache initialized")
        
    def get(self, key: str) -> str | None:
        return self.data.get(key)
        
    def set(self, key: str, value: str, ttl: int = 300) -> None:
        self.data[key] = value
        print(f"🧠 Memory SET: {key}")
        
    def health_check(self) -> dict:
        return {
            "status": "healthy",
            "type": "memory",
            "entries": len(self.data)
        }


# Message Queue Implementations
@provide(condition=env_truthy("ENABLE_MESSAGING"))
class RabbitMQMessageQueue:
    """RabbitMQ message queue implementation."""
    
    def __init__(self):
        self.url = os.getenv("RABBITMQ_URL", "amqp://localhost")
        self.handlers = {}
        print(f"🐰 RabbitMQ initialized: {self.url}")
        
    async def publish(self, topic: str, message: dict) -> None:
        print(f"🐰 Publishing to {topic}: {message}")
        
    async def subscribe(self, topic: str, handler) -> None:
        self.handlers[topic] = handler
        print(f"🐰 Subscribed to {topic}")


@provide(condition=lambda: not env_truthy("ENABLE_MESSAGING")())
class NoOpMessageQueue:
    """No-op message queue (fallback)."""
    
    def __init__(self):
        print("🚫 No-op message queue (messaging disabled)")
        
    async def publish(self, topic: str, message: dict) -> None:
        print(f"🚫 Would publish to {topic}: {message}")
        
    async def subscribe(self, topic: str, handler) -> None:
        print(f"🚫 Would subscribe to {topic}")


# Step 2: Business Domain Services
# =================================

class Customer:
    """Customer entity."""
    
    def __init__(self, id: int, name: str, email: str, tier: str = "standard"):
        self.id = id
        self.name = name
        self.email = email
        self.tier = tier
        
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "tier": self.tier
        }


class Product:
    """Product entity."""
    
    def __init__(self, id: int, name: str, price: float, stock: int):
        self.id = id
        self.name = name
        self.price = price
        self.stock = stock
        
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "price": self.price,
            "stock": self.stock
        }


class Order:
    """Order entity."""
    
    def __init__(self, id: int, customer_id: int, items: list, total: float):
        self.id = id
        self.customer_id = customer_id
        self.items = items
        self.total = total
        self.status = "pending"
        self.created_at = datetime.now()
        
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "items": self.items,
            "total": self.total,
            "status": self.status,
            "created_at": self.created_at.isoformat()
        }


# Repository Layer
@provide
class CustomerRepository:
    """Repository for customer data."""
    _discoverable = True
    
    def __init__(self, db: Annotated[Database, Inject(name="primary")]):
        self.db = db
        self.customers = {
            1: Customer(1, "Alice Johnson", "alice@example.com", "premium"),
            2: Customer(2, "Bob Smith", "bob@example.com", "standard"),
            3: Customer(3, "Charlie Brown", "charlie@example.com", "premium")
        }
        print("👥 CustomerRepository initialized")
        
    async def find_by_id(self, customer_id: int) -> Customer | None:
        await self.db.query(f"SELECT * FROM customers WHERE id = {customer_id}")
        return self.customers.get(customer_id)
        
    async def find_by_email(self, email: str) -> Customer | None:
        await self.db.query(f"SELECT * FROM customers WHERE email = '{email}'")
        for customer in self.customers.values():
            if customer.email == email:
                return customer
        return None


@provide  
class ProductRepository:
    """Repository for product data."""
    _discoverable = True
    
    def __init__(self, db: Annotated[Database, Inject(name="primary")]):
        self.db = db
        self.products = {
            101: Product(101, "Laptop", 999.99, 50),
            102: Product(102, "Mouse", 29.99, 200),
            103: Product(103, "Keyboard", 79.99, 150),
            104: Product(104, "Monitor", 299.99, 75)
        }
        print("📦 ProductRepository initialized")
        
    async def find_by_id(self, product_id: int) -> Product | None:
        await self.db.query(f"SELECT * FROM products WHERE id = {product_id}")
        return self.products.get(product_id)
        
    async def update_stock(self, product_id: int, new_stock: int) -> bool:
        await self.db.execute(f"UPDATE products SET stock = {new_stock} WHERE id = {product_id}")
        if product_id in self.products:
            self.products[product_id].stock = new_stock
            return True
        return False


@provide
class OrderRepository:
    """Repository for order data."""
    _discoverable = True
    
    def __init__(self, db: Annotated[Database, Inject(name="primary")]):
        self.db = db
        self.orders = {}
        self.next_id = 1000
        print("🛒 OrderRepository initialized")
        
    async def save(self, order: Order) -> Order:
        await self.db.execute(f"INSERT INTO orders VALUES ({order.to_dict()})")
        self.orders[order.id] = order
        return order
        
    async def find_by_id(self, order_id: int) -> Order | None:
        await self.db.query(f"SELECT * FROM orders WHERE id = {order_id}")
        return self.orders.get(order_id)
        
    async def find_by_customer(self, customer_id: int) -> list[Order]:
        await self.db.query(f"SELECT * FROM orders WHERE customer_id = {customer_id}")
        return [order for order in self.orders.values() if order.customer_id == customer_id]
        
    def generate_id(self) -> int:
        order_id = self.next_id
        self.next_id += 1
        return order_id


# Service Layer with Lazy Dependencies
class OrderService:
    """Core order processing service with lazy dependencies."""
    _discoverable = True
    
    def __init__(self,
                 customer_repo: Annotated[Lazy[CustomerRepository], Inject()],
                 product_repo: Annotated[Lazy[ProductRepository], Inject()],
                 order_repo: Annotated[Lazy[OrderRepository], Inject()]):
        self.customer_repo = customer_repo
        self.product_repo = product_repo  
        self.order_repo = order_repo
        print("🛒 OrderService initialized with lazy dependencies")
        
    async def create_order(self, customer_id: int, items: list[dict]) -> Order:
        """Create a new order."""
        # Verify customer exists (triggers lazy loading)
        customer = await self.customer_repo.value.find_by_id(customer_id)
        if not customer:
            raise ValueError(f"Customer {customer_id} not found")
            
        # Verify products and calculate total
        total = 0.0
        order_items = []
        
        for item in items:
            product_id = item["product_id"]
            quantity = item["quantity"]
            
            product = await self.product_repo.value.find_by_id(product_id)
            if not product:
                raise ValueError(f"Product {product_id} not found")
                
            if product.stock < quantity:
                raise ValueError(f"Insufficient stock for product {product_id}")
                
            item_total = product.price * quantity
            total += item_total
            
            order_items.append({
                "product_id": product_id,
                "product_name": product.name,
                "quantity": quantity,
                "unit_price": product.price,
                "total": item_total
            })
            
        # Apply customer tier discount
        if customer.tier == "premium":
            total *= 0.9  # 10% discount
            print(f"💎 Applied premium discount for {customer.name}")
            
        # Create and save order
        order_id = self.order_repo.value.generate_id()
        order = Order(order_id, customer_id, order_items, total)
        await self.order_repo.value.save(order)
        
        # Update product stock
        for item in items:
            product_id = item["product_id"]
            quantity = item["quantity"]
            product = await self.product_repo.value.find_by_id(product_id)
            new_stock = product.stock - quantity
            await self.product_repo.value.update_stock(product_id, new_stock)
            
        print(f"🛒 Created order {order.id} for customer {customer.name} - Total: ${total:.2f}")
        return order
        
    async def get_order(self, order_id: int) -> Order | None:
        """Get an order by ID."""
        return await self.order_repo.value.find_by_id(order_id)
        
    async def get_customer_orders(self, customer_id: int) -> list[Order]:
        """Get all orders for a customer."""
        return await self.order_repo.value.find_by_customer(customer_id)


# Caching Service with Named Dependencies
class CacheService:
    """Service that manages caching with fallback."""
    _discoverable = True
    
    def __init__(self):
        # These will be resolved based on environment conditions
        self.primary_cache = None
        self.fallback_cache = None
        print("🗄️ CacheService initialized")
        
    async def initialize_caches(self, container: Container):
        """Initialize caches based on what's available."""
        try:
            self.primary_cache = await container.resolve(RedisCache, name="redis")
            print("✅ Primary cache: Redis")
        except KeyError:
            pass
            
        try:
            self.fallback_cache = await container.resolve(MemoryCache, name="memory")
            print("✅ Fallback cache: Memory")
        except KeyError:
            pass
            
    def get_active_cache(self) -> Cache:
        """Get the active cache (prefer Redis, fallback to memory)."""
        return self.primary_cache or self.fallback_cache
        
    async def cache_customer(self, customer: Customer):
        """Cache customer data."""
        cache = self.get_active_cache()
        if cache:
            cache.set(f"customer:{customer.id}", str(customer.to_dict()))
            
    async def get_cached_customer(self, customer_id: int) -> dict | None:
        """Get cached customer data."""
        cache = self.get_active_cache()
        if cache:
            cached = cache.get(f"customer:{customer_id}")
            if cached:
                print(f"💨 Cache hit for customer {customer_id}")
                return eval(cached)  # In real app, use proper JSON
        return None


# Application Service (Façade)
class OrderProcessingService:
    """Main application service that coordinates order processing."""
    
    # Lazy descriptors for expensive services
    order_service = LazyDescriptor(OrderService)
    cache_service = LazyDescriptor(CacheService)
    
    def __init__(self,
                 message_queue: Annotated[MessageQueue, Inject()]):
        self.message_queue = message_queue
        print("🎯 OrderProcessingService initialized")
        
    async def process_order_request(self, customer_id: int, items: list[dict]) -> dict:
        """Process a complete order request with caching and messaging."""
        try:
            # Check cache for customer info first
            cached_customer = await self.cache_service.value.get_cached_customer(customer_id)
            if not cached_customer:
                print(f"🔍 Customer {customer_id} not in cache, will fetch from database")
                
            # Create the order (this will initialize lazy dependencies as needed)
            order = await self.order_service.value.create_order(customer_id, items)
            
            # Cache customer info for future requests
            customer_repo = await self.order_service.value.customer_repo.value.find_by_id(customer_id)
            if customer_repo:
                await self.cache_service.value.cache_customer(customer_repo)
                
            # Publish order created event
            await self.message_queue.publish("order.created", {
                "order_id": order.id,
                "customer_id": customer_id,
                "total": order.total,
                "timestamp": order.created_at.isoformat()
            })
            
            return {
                "success": True,
                "order": order.to_dict(),
                "message": f"Order {order.id} created successfully"
            }
            
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Order processing failed: {error_msg}")
            
            # Publish error event
            await self.message_queue.publish("order.error", {
                "customer_id": customer_id,
                "error": error_msg,
                "timestamp": datetime.now().isoformat()
            })
            
            return {
                "success": False,
                "error": error_msg
            }


# Step 3: Application Setup and Configuration
# ============================================

def setup_environment(scenario: str):
    """Setup environment for different deployment scenarios."""
    # Clear environment
    env_vars = ["DB_TYPE", "DATABASE_URL", "REDIS_URL", "RABBITMQ_URL", "ENABLE_MESSAGING"]
    for var in env_vars:
        if var in os.environ:
            del os.environ[var]
            
    if scenario == "production":
        os.environ["DB_TYPE"] = "postgres"
        os.environ["DATABASE_URL"] = "postgresql://prod-server/orders"
        os.environ["REDIS_URL"] = "redis://prod-cache"
        os.environ["RABBITMQ_URL"] = "amqp://prod-queue"
        os.environ["ENABLE_MESSAGING"] = "true"
        
    elif scenario == "staging":
        os.environ["DB_TYPE"] = "postgres"
        os.environ["DATABASE_URL"] = "postgresql://staging-server/orders"
        os.environ["REDIS_URL"] = "redis://staging-cache"
        os.environ["ENABLE_MESSAGING"] = "true"
        
    elif scenario == "development":
        os.environ["DB_TYPE"] = "sqlite"
        os.environ["REDIS_URL"] = "redis://localhost"
        os.environ["ENABLE_MESSAGING"] = "true"
        
    elif scenario == "minimal":
        os.environ["DB_TYPE"] = "sqlite"
        # No Redis, no messaging


async def create_order_processing_microservice(scenario: str) -> Application:
    """Create and configure the order processing microservice."""
    
    print(f"\n{'='*60}")
    print(f"CREATING ORDER PROCESSING MICROSERVICE - {scenario.upper()}")
    print('='*60)
    
    setup_environment(scenario)
    
    # Show configuration
    print(f"\n📋 Environment Configuration:")
    env_vars = ["DB_TYPE", "DATABASE_URL", "REDIS_URL", "RABBITMQ_URL", "ENABLE_MESSAGING"]
    for var in env_vars:
        value = os.getenv(var, "NOT SET")
        print(f"  {var}: {value}")
        
    # Create application
    app = Application(ApplicationConfig(
        name="OrderProcessingService",
        version="2.0.0",
        description=f"Order processing microservice ({scenario} environment)"
    ))
    
    # Register core services
    app.component(OrderProcessingService)
    
    # The conditional services will be registered automatically
    # based on the environment conditions we set up
    
    print(f"\n🔍 Services registered based on conditions:")
    registered_services = []
    
    # Check what got registered
    try:
        db_primary = await app.container.resolve(PostgresDatabase, name="primary")
        registered_services.append("PostgresDatabase (primary)")
    except KeyError:
        try:
            db_primary = await app.container.resolve(SQLiteDatabase, name="primary")
            registered_services.append("SQLiteDatabase (primary)")
        except KeyError:
            pass
            
    try:
        cache_redis = await app.container.resolve(RedisCache, name="redis")
        registered_services.append("RedisCache")
    except KeyError:
        pass
        
    try:
        cache_memory = await app.container.resolve(MemoryCache, name="memory")
        registered_services.append("MemoryCache")
    except KeyError:
        pass
        
    try:
        mq = await app.container.resolve(RabbitMQMessageQueue)
        registered_services.append("RabbitMQMessageQueue")
    except KeyError:
        try:
            mq = await app.container.resolve(NoOpMessageQueue)
            registered_services.append("NoOpMessageQueue")
        except KeyError:
            pass
    
    for service in registered_services:
        print(f"  ✅ {service}")
        
    return app


async def run_microservice_scenario(scenario: str):
    """Run a complete microservice scenario."""
    
    app = await create_order_processing_microservice(scenario)
    
    # Add event handlers
    @app.on("order.created")
    async def handle_order_created(data: dict):
        """Handle order created events."""
        print(f"📧 Sending order confirmation for order {data['order_id']}")
        print(f"💰 Processing payment for ${data['total']:.2f}")
        
    @app.on("order.error")
    async def handle_order_error(data: dict):
        """Handle order errors."""
        print(f"🚨 Order error for customer {data['customer_id']}: {data['error']}")
        
    # Background task for processing orders
    @app.task
    async def order_fulfillment_task():
        """Background task that fulfills orders."""
        print("📦 Order fulfillment task started")
        try:
            while True:
                await asyncio.sleep(10)
                print("📦 Checking for orders to fulfill...")
                # In a real service, this would process pending orders
        except asyncio.CancelledError:
            print("📦 Order fulfillment task stopped")
            raise
            
    # Health monitoring
    @app.task
    async def health_monitor():
        """Monitor service health."""
        try:
            while True:
                await asyncio.sleep(15)
                
                # Check database health
                try:
                    db = await app.container.resolve(Database, name="primary")
                    health = await db.health_check()
                    print(f"🏥 Database health: {health['status']} ({health['type']})")
                except Exception as e:
                    print(f"🏥 Database health check failed: {e}")
                    
                # Check cache health
                try:
                    cache_service = await app.container.resolve(CacheService)
                    cache = cache_service.get_active_cache()
                    if cache:
                        health = cache.health_check()
                        print(f"🏥 Cache health: {health['status']} ({health['type']}, {health['entries']} entries)")
                except Exception as e:
                    print(f"🏥 Cache health check failed: {e}")
                    
        except asyncio.CancelledError:
            print("🏥 Health monitor stopped")
            raise
    
    # Run the microservice
    try:
        async with app.lifespan():
            print(f"\n🚀 {app.config.name} is running!")
            
            # Initialize cache service
            cache_service = await app.container.resolve(CacheService)
            await cache_service.initialize_caches(app.container)
            
            # Get main service
            order_processor = await app.container.resolve(OrderProcessingService)
            
            print(f"\n--- PROCESSING SAMPLE ORDERS ---")
            
            # Process some orders
            orders = [
                {"customer_id": 1, "items": [{"product_id": 101, "quantity": 1}, {"product_id": 102, "quantity": 2}]},
                {"customer_id": 2, "items": [{"product_id": 103, "quantity": 1}]},
                {"customer_id": 3, "items": [{"product_id": 104, "quantity": 1}, {"product_id": 101, "quantity": 1}]},
            ]
            
            for i, order_request in enumerate(orders, 1):
                print(f"\n📝 Processing order request {i}:")
                result = await order_processor.process_order_request(
                    order_request["customer_id"],
                    order_request["items"]
                )
                
                if result["success"]:
                    print(f"✅ {result['message']}")
                else:
                    print(f"❌ Order failed: {result['error']}")
                    
                await asyncio.sleep(1)
                
            # Try an invalid order
            print(f"\n📝 Processing invalid order (non-existent customer):")
            invalid_result = await order_processor.process_order_request(
                999,  # Non-existent customer
                [{"product_id": 101, "quantity": 1}]
            )
            
            if not invalid_result["success"]:
                print(f"✅ Properly handled invalid order: {invalid_result['error']}")
                
            # Let background tasks run
            print(f"\n⏳ Letting microservice run for 20 seconds...")
            await asyncio.sleep(20)
            
    except Exception as e:
        print(f"💥 Microservice error: {e}")
        raise


async def main():
    """Run the complete real-world microservice demonstration."""
    
    print("🥃 Whiskey Real-World Microservice Example")
    print("=" * 50)
    print("This comprehensive example demonstrates:")
    print("✅ Named dependencies for multiple implementations")
    print("✅ Conditional registration based on environment")
    print("✅ Lazy resolution for performance optimization")
    print("✅ Rich application framework with lifecycle")
    print("✅ Event-driven architecture with messaging")
    print("✅ Background tasks and health monitoring")
    print("✅ Component discovery and auto-registration")
    print("✅ Real-world business logic (e-commerce orders)")
    
    # Run different deployment scenarios
    scenarios = ["production", "staging", "development", "minimal"]
    
    for scenario in scenarios:
        try:
            await run_microservice_scenario(scenario)
            await asyncio.sleep(2)  # Brief pause between scenarios
        except KeyboardInterrupt:
            print(f"\n⚠️ Scenario {scenario} interrupted")
            break
        except Exception as e:
            print(f"\n❌ Scenario {scenario} failed: {e}")
            continue
            
    print(f"\n{'='*60}")
    print("MICROSERVICE DEMONSTRATION COMPLETE")
    print('='*60)
    print("Key architectural patterns demonstrated:")
    print("🏗️  Hexagonal Architecture (ports & adapters)")
    print("🎯 Dependency Injection for loose coupling")
    print("🔄 Event-driven communication")
    print("🚀 Lazy loading for performance")
    print("⚙️  Configuration-driven behavior")
    print("🏥 Health monitoring and observability")
    print("📦 Domain-driven design principles")
    print("🌐 Microservice deployment patterns")
    
    print(f"\nThis microservice would typically be deployed with:")
    print("🐳 Docker containers")
    print("☸️  Kubernetes orchestration")
    print("📊 Prometheus metrics")
    print("📈 Grafana dashboards")
    print("🔍 Distributed tracing")
    print("📋 Centralized logging")


if __name__ == "__main__":
    asyncio.run(main())