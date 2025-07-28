# Advanced Patterns and Performance

This guide covers advanced patterns, performance optimization, and complex scenarios in Whiskey applications.

## Advanced Dependency Patterns

### Abstract Base Classes and Interfaces

Define contracts using Python's ABC:

```python
from abc import ABC, abstractmethod
from whiskey import component, inject

class Repository(ABC):
    @abstractmethod
    async def find(self, id: int): pass
    
    @abstractmethod
    async def save(self, entity: dict): pass

@component
class PostgresRepository(Repository):
    def __init__(self, db: Database):
        self.db = db
    
    async def find(self, id: int):
        return await self.db.query(f"SELECT * FROM entities WHERE id = {id}")
    
    async def save(self, entity: dict):
        await self.db.execute("INSERT INTO entities VALUES (...)")

# Register the implementation for the interface
container.add_transient(Repository, implementation=PostgresRepository)

# Use the abstraction
@inject
async def process_entity(entity_id: int, repo: Repository):
    entity = await repo.find(entity_id)
    # Works with any Repository implementation
```

### Generic Types

Support generic type resolution:

```python
from typing import Generic, TypeVar

T = TypeVar('T')

class Cache(Generic[T]):
    def __init__(self):
        self._cache: dict[str, T] = {}
    
    async def get(self, key: str) -> T | None:
        return self._cache.get(key)
    
    async def set(self, key: str, value: T):
        self._cache[key] = value

# Register specific generic instances
@factory(Cache[User], scope=Scope.SINGLETON)
def create_user_cache():
    return Cache[User]()

@factory(Cache[Product], scope=Scope.SINGLETON)
def create_product_cache():
    return Cache[Product]()

# Use with type safety
@inject
async def cache_user(user: User, cache: Cache[User]):
    await cache.set(f"user:{user.id}", user)
```

### Decorator Factories

Create custom decorator patterns:

```python
def transactional(isolation_level="READ_COMMITTED"):
    """Decorator factory for transactional methods"""
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            async with self.db.transaction(isolation_level):
                return await func(self, *args, **kwargs)
        return wrapper
    return decorator

@component
class OrderService:
    def __init__(self, db: Database):
        self.db = db
    
    @transactional(isolation_level="SERIALIZABLE")
    async def place_order(self, order: Order):
        # Automatically wrapped in transaction
        await self.db.save(order)
        await self.update_inventory(order.items)
```

### Plugin Architecture

Build extensible applications with plugins:

```python
from typing import Protocol

class Plugin(Protocol):
    """Plugin protocol"""
    name: str
    
    async def initialize(self, app: Whiskey): ...
    async def shutdown(self): ...

class PluginManager:
    def __init__(self):
        self.plugins: list[Plugin] = []
    
    def register(self, plugin: Plugin):
        self.plugins.append(plugin)
    
    async def initialize_all(self, app: Whiskey):
        for plugin in self.plugins:
            await plugin.initialize(app)

# Create plugins
class MetricsPlugin:
    name = "metrics"
    
    async def initialize(self, app: Whiskey):
        @app.singleton
        class MetricsCollector:
            def __init__(self):
                self.metrics = {}

class LoggingPlugin:
    name = "logging"
    
    async def initialize(self, app: Whiskey):
        @app.singleton
        class Logger:
            def log(self, message: str):
                print(f"[LOG] {message}")

# Use plugins
app = Whiskey()
plugin_manager = PluginManager()
plugin_manager.register(MetricsPlugin())
plugin_manager.register(LoggingPlugin())

await plugin_manager.initialize_all(app)
```

## Performance Optimization

### Lazy Loading

Defer expensive initialization:

```python
from functools import cached_property

@singleton(lazy=True)
class ExpensiveService:
    def __init__(self):
        # Constructor is only called when first accessed
        self._data = None
    
    @cached_property
    def processed_data(self):
        # Expensive computation cached after first access
        print("Processing data...")
        return self._process_large_dataset()
    
    def _process_large_dataset(self):
        # Simulate expensive operation
        import time
        time.sleep(2)
        return "processed"

# Service is not created until first use
@inject
async def use_service(service: ExpensiveService):
    # Now the service is created
    data = service.processed_data  # Computed once
    return data
```

### Connection Pooling

Efficiently manage database connections:

```python
from asyncio import Queue
from contextlib import asynccontextmanager

@singleton
class ConnectionPool:
    def __init__(self, db_config: DatabaseConfig):
        self.config = db_config
        self.pool: Queue = Queue(maxsize=db_config.pool_size)
        self._initialized = False
    
    async def initialize(self):
        if self._initialized:
            return
        
        # Create connection pool
        for _ in range(self.config.pool_size):
            conn = await create_connection(self.config.url)
            await self.pool.put(conn)
        
        self._initialized = True
    
    @asynccontextmanager
    async def acquire(self):
        """Acquire connection from pool"""
        await self.initialize()
        conn = await self.pool.get()
        try:
            yield conn
        finally:
            await self.pool.put(conn)

@component
class DatabaseService:
    def __init__(self, pool: ConnectionPool):
        self.pool = pool
    
    async def query(self, sql: str):
        async with self.pool.acquire() as conn:
            return await conn.execute(sql)
```

### Caching Strategies

Implement efficient caching:

```python
from functools import lru_cache
import asyncio
from datetime import datetime, timedelta

class CacheEntry:
    def __init__(self, value, expires_at):
        self.value = value
        self.expires_at = expires_at
    
    @property
    def is_expired(self):
        return datetime.now() > self.expires_at

@singleton
class SmartCache:
    def __init__(self):
        self._cache: dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()
    
    async def get_or_set(self, key: str, factory, ttl: int = 300):
        """Get from cache or compute and set"""
        async with self._lock:
            # Check cache
            if key in self._cache:
                entry = self._cache[key]
                if not entry.is_expired:
                    return entry.value
            
            # Compute value
            value = await factory()
            
            # Cache it
            expires_at = datetime.now() + timedelta(seconds=ttl)
            self._cache[key] = CacheEntry(value, expires_at)
            
            return value

@component
class UserService:
    def __init__(self, db: Database, cache: SmartCache):
        self.db = db
        self.cache = cache
    
    async def get_user(self, user_id: int):
        return await self.cache.get_or_set(
            f"user:{user_id}",
            lambda: self.db.find_user(user_id),
            ttl=600  # 10 minutes
        )
```

### Batch Processing

Process items in batches for efficiency:

```python
from asyncio import Queue, gather
from typing import List

@component
class BatchProcessor:
    def __init__(self, service: ProcessingService):
        self.service = service
        self.queue = Queue()
        self.batch_size = 100
        self.flush_interval = 1.0
    
    async def add(self, item):
        await self.queue.put(item)
    
    async def process_batch(self, items: List):
        """Process a batch of items"""
        results = await gather(*[
            self.service.process(item) 
            for item in items
        ])
        return results
    
    async def run(self):
        """Background task to process batches"""
        batch = []
        
        while True:
            try:
                # Collect items with timeout
                item = await asyncio.wait_for(
                    self.queue.get(), 
                    timeout=self.flush_interval
                )
                batch.append(item)
                
                # Process when batch is full
                if len(batch) >= self.batch_size:
                    await self.process_batch(batch)
                    batch = []
                    
            except asyncio.TimeoutError:
                # Process partial batch on timeout
                if batch:
                    await self.process_batch(batch)
                    batch = []
```

## Complex Scenarios

### Multi-Tenant Applications

Support multiple tenants with scoped dependencies:

```python
@scoped("tenant")
class TenantContext:
    def __init__(self):
        self.tenant_id = None
        self.config = None

@component
class TenantAwareDatabase:
    def __init__(self, context: TenantContext, pool: ConnectionPool):
        self.context = context
        self.pool = pool
    
    async def query(self, sql: str):
        # Add tenant filtering
        tenant_sql = f"{sql} WHERE tenant_id = {self.context.tenant_id}"
        async with self.pool.acquire() as conn:
            return await conn.execute(tenant_sql)

# Middleware to set tenant context
async def tenant_middleware(request, handler):
    tenant_id = request.headers.get("X-Tenant-ID")
    
    async with container.scope("tenant") as tenant_scope:
        # Set tenant context
        context = await tenant_scope.resolve(TenantContext)
        context.tenant_id = tenant_id
        
        # Process request in tenant scope
        return await handler(request, scope=tenant_scope)
```

### Event-Driven Architecture

Implement event sourcing and CQRS:

```python
from dataclasses import dataclass
from datetime import datetime
from typing import List

@dataclass
class Event:
    aggregate_id: str
    event_type: str
    data: dict
    timestamp: datetime

class EventStore:
    async def append(self, event: Event): ...
    async def get_events(self, aggregate_id: str) -> List[Event]: ...

@singleton
class EventBus:
    def __init__(self):
        self.handlers = {}
    
    def register(self, event_type: str, handler):
        if event_type not in self.handlers:
            self.handlers[event_type] = []
        self.handlers[event_type].append(handler)
    
    async def publish(self, event: Event):
        handlers = self.handlers.get(event.event_type, [])
        await gather(*[handler(event) for handler in handlers])

@component
class OrderAggregate:
    def __init__(self, event_store: EventStore, event_bus: EventBus):
        self.event_store = event_store
        self.event_bus = event_bus
    
    async def place_order(self, order_id: str, items: List):
        # Create event
        event = Event(
            aggregate_id=order_id,
            event_type="OrderPlaced",
            data={"items": items},
            timestamp=datetime.now()
        )
        
        # Store and publish
        await self.event_store.append(event)
        await self.event_bus.publish(event)
    
    async def get_order(self, order_id: str):
        # Rebuild from events
        events = await self.event_store.get_events(order_id)
        order = self._rebuild_from_events(events)
        return order
```

### Distributed Systems

Handle distributed system concerns:

```python
import aioredis
from whiskey import singleton

@singleton
class DistributedLock:
    def __init__(self, redis: aioredis.Redis):
        self.redis = redis
    
    async def acquire(self, key: str, timeout: int = 10):
        """Acquire distributed lock"""
        return await self.redis.set(
            f"lock:{key}",
            "1",
            nx=True,
            ex=timeout
        )
    
    async def release(self, key: str):
        """Release distributed lock"""
        await self.redis.delete(f"lock:{key}")

@component
class DistributedService:
    def __init__(self, lock: DistributedLock):
        self.lock = lock
    
    async def process_once(self, job_id: str):
        """Ensure job runs only once across instances"""
        if await self.lock.acquire(f"job:{job_id}"):
            try:
                # Process job
                await self._process_job(job_id)
            finally:
                await self.lock.release(f"job:{job_id}")
```

### Performance Monitoring

Monitor application performance:

```python
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

@dataclass
class PerformanceMetrics:
    operation: str
    duration: float
    tags: dict = field(default_factory=dict)

@singleton
class PerformanceMonitor:
    def __init__(self):
        self.metrics: List[PerformanceMetrics] = []
    
    @asynccontextmanager
    async def measure(self, operation: str, **tags):
        start = time.perf_counter()
        try:
            yield
        finally:
            duration = time.perf_counter() - start
            metric = PerformanceMetrics(operation, duration, tags)
            self.metrics.append(metric)
    
    def get_stats(self):
        """Get performance statistics"""
        stats = {}
        for metric in self.metrics:
            op = metric.operation
            if op not in stats:
                stats[op] = {
                    "count": 0,
                    "total": 0,
                    "avg": 0,
                    "max": 0
                }
            
            stats[op]["count"] += 1
            stats[op]["total"] += metric.duration
            stats[op]["avg"] = stats[op]["total"] / stats[op]["count"]
            stats[op]["max"] = max(stats[op]["max"], metric.duration)
        
        return stats

# Use in services
@component
class MonitoredService:
    def __init__(self, monitor: PerformanceMonitor):
        self.monitor = monitor
    
    async def process(self, data):
        async with self.monitor.measure("process", size=len(data)):
            # Process data
            await asyncio.sleep(0.1)  # Simulate work
```

## Memory Management

### Weak References

Prevent memory leaks with weak references:

```python
import weakref

@singleton
class EventEmitter:
    def __init__(self):
        # Use weak references to prevent memory leaks
        self._listeners = weakref.WeakValueDictionary()
    
    def subscribe(self, event: str, listener):
        if event not in self._listeners:
            self._listeners[event] = weakref.WeakSet()
        self._listeners[event].add(listener)
    
    async def emit(self, event: str, data):
        listeners = self._listeners.get(event, set())
        for listener in listeners:
            if listener:  # Check if still alive
                await listener.handle(data)
```

### Resource Cleanup

Ensure proper resource cleanup:

```python
from contextlib import asynccontextmanager

@component
class ResourceManager:
    def __init__(self):
        self.resources = []
    
    async def acquire_resource(self, resource_id: str):
        resource = await create_resource(resource_id)
        self.resources.append(resource)
        return resource
    
    async def cleanup(self):
        """Clean up all resources"""
        for resource in self.resources:
            try:
                await resource.close()
            except Exception as e:
                logger.error(f"Failed to close resource: {e}")
        self.resources.clear()

# Use in application lifecycle
@app.on_shutdown
async def cleanup_resources(manager: ResourceManager):
    await manager.cleanup()
```

## Best Practices for Performance

1. **Profile Before Optimizing**
   ```python
   import cProfile
   import pstats
   
   profiler = cProfile.Profile()
   profiler.enable()
   # Run your code
   profiler.disable()
   stats = pstats.Stats(profiler)
   stats.sort_stats('cumulative')
   stats.print_stats()
   ```

2. **Use Async Effectively**
   ```python
   # Good - Concurrent execution
   results = await gather(
       service1.process(),
       service2.process(),
       service3.process()
   )
   
   # Bad - Sequential execution
   result1 = await service1.process()
   result2 = await service2.process()
   result3 = await service3.process()
   ```

3. **Batch Database Operations**
   ```python
   # Good - Single query
   users = await db.query(
       "SELECT * FROM users WHERE id IN ($1, $2, $3)",
       *user_ids
   )
   
   # Bad - N+1 queries
   users = []
   for user_id in user_ids:
       user = await db.query(
           "SELECT * FROM users WHERE id = $1",
           user_id
       )
       users.append(user)
   ```

4. **Cache Wisely**
   - Cache expensive computations
   - Set appropriate TTLs
   - Monitor cache hit rates
   - Implement cache warming

5. **Monitor and Alert**
   - Track response times
   - Monitor resource usage
   - Set up alerts for anomalies
   - Use distributed tracing

## Next Steps

- Review [Examples](examples.md) for complete implementations
- Explore specific [Extensions](extensions.md) for your use case
- Check out [Migration Guide](migration.md) if coming from another framework