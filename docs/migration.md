# Migration Guide: Explicit Back to Pythonic Injection  

This guide helps you migrate from Whiskey's explicit `Annotated` injection pattern back to the new pythonic implicit pattern using simple type hints.

## Why the Change?

The new pythonic implicit injection pattern provides:
- **Simplicity**: Clean, natural Python - no special imports needed
- **Clarity**: Simple rule - type hints without defaults get injected  
- **Flexibility**: Mix injected and non-injected parameters naturally
- **IDE Support**: Standard Python type hints work perfectly

## Quick Summary

**Old Pattern (Explicit):**
```python
from typing import Annotated
from whiskey import Inject

@inject
def process(
    user_id: int,  # Regular parameter  
    db: Annotated[Database, Inject()],  # Injected
    cache: Annotated[Cache, Inject()]   # Injected
):
    pass
```

**New Pattern (Pythonic):**
```python
@inject
def process(
    user_id: int,  # NOT injected - regular parameter (passed as argument)
    db: Database,  # Injected - has type hint, no default
    cache: Cache   # Injected - has type hint, no default
):
    pass
```

## Step-by-Step Migration

### 1. Update Imports

Add these imports to your files:

```python
from typing import Annotated
from whiskey import Inject  # New import
```

### 2. Update Function Parameters

For each function using `@inject`, update parameters that should be injected:

**Before:**
```python
@inject
async def send_email(
    to: str,
    subject: str,
    email_service: EmailService,
    template_engine: TemplateEngine
):
    pass
```

**After:**
```python
@inject
async def send_email(
    to: str,  # Regular parameter
    subject: str,  # Regular parameter
    email_service: Annotated[EmailService, Inject()],  # Injected
    template_engine: Annotated[TemplateEngine, Inject()]  # Injected
):
    pass
```

### 3. Update Class Constructors

The same pattern applies to class constructors:

**Before:**
```python
class OrderService:
    def __init__(self, db: Database, cache: Cache, timeout: int = 30):
        # Old pattern would try to inject db and cache
        # timeout would be problematic
        pass
```

**After:**
```python
class OrderService:
    def __init__(self,
                 db: Annotated[Database, Inject()],
                 cache: Annotated[Cache, Inject()],
                 timeout: int = 30):  # Clearly not injected
        pass
```

### 4. Handle Special Cases

#### Callable Defaults (Settings, ConfigSection)

The new pattern correctly handles callable defaults:

```python
from whiskey_config import Setting, ConfigSection

@inject
def create_server(
    # These work correctly with explicit injection
    port: int = Setting("server.port", default=8000),
    workers: int = Setting("server.workers", default=4),
    # Regular injection still works
    logger: Annotated[Logger, Inject()] = None
):
    pass
```

#### Optional Dependencies

Make optional dependencies clear:

**Before:**
```python
@inject
def process(required_service: RequiredService,
           optional_service: OptionalService = None):
    # Ambiguous - is optional_service injected or not?
    pass
```

**After:**
```python
@inject
def process(
    required_service: Annotated[RequiredService, Inject()],
    optional_service: Annotated[OptionalService, Inject()] | None = None
):
    # Clear that optional_service is injected if available
    pass
```

## Common Patterns

### Mixed Parameters

The new pattern makes it easy to mix injected and non-injected parameters:

```python
@inject
async def create_order(
    # Regular parameters from the request
    user_id: int,
    product_id: int,
    quantity: int,
    # Injected services
    order_service: Annotated[OrderService, Inject()],
    inventory: Annotated[InventoryService, Inject()],
    # Configuration with defaults
    max_quantity: int = Setting("orders.max_quantity", default=100)
):
    pass
```

### Factory Functions

When using factory decorators, apply the same pattern:

```python
@factory(DatabasePool)
@inject
def create_db_pool(
    config: Annotated[DatabaseConfig, Inject()],
    max_connections: int = 20  # Not injected
) -> DatabasePool:
    return DatabasePool(
        dsn=config.connection_string,
        max_connections=max_connections
    )
```

### Application Components

```python
@app.component
class BackgroundWorker:
    def __init__(self,
                 queue: Annotated[Queue, Inject()],
                 logger: Annotated[Logger, Inject()],
                 worker_id: str = None):  # Not injected
        self.queue = queue
        self.logger = logger
        self.worker_id = worker_id or generate_id()
```

## Testing Considerations

The explicit pattern makes testing clearer:

```python
# Test without injection - just pass parameters directly
async def test_service():
    mock_db = MockDatabase()
    mock_cache = MockCache()
    
    service = MyService(
        db=mock_db,  # Works even though it expects Annotated[Database, Inject()]
        cache=mock_cache,
        timeout=5  # Regular parameter
    )
    
    result = await service.process()
    assert result is not None
```

## Automated Migration

For large codebases, you can use this script to help identify functions that need updating:

```python
import ast
import sys
from pathlib import Path

class InjectFinder(ast.NodeVisitor):
    def __init__(self):
        self.inject_functions = []
        
    def visit_FunctionDef(self, node):
        # Check if function has @inject decorator
        for decorator in node.decorator_list:
            if (isinstance(decorator, ast.Name) and decorator.id == 'inject') or \
               (isinstance(decorator, ast.Attribute) and decorator.attr == 'inject'):
                self.inject_functions.append({
                    'name': node.name,
                    'line': node.lineno,
                    'args': [arg.arg for arg in node.args.args]
                })
        self.generic_visit(node)
        
    visit_AsyncFunctionDef = visit_FunctionDef

def find_inject_usage(file_path):
    with open(file_path, 'r') as f:
        tree = ast.parse(f.read())
    
    finder = InjectFinder()
    finder.visit(tree)
    return finder.inject_functions

# Usage
for py_file in Path('.').rglob('*.py'):
    functions = find_inject_usage(py_file)
    if functions:
        print(f"\n{py_file}:")
        for func in functions:
            print(f"  Line {func['line']}: {func['name']}({', '.join(func['args'])})")
```

## Migration Checklist

- [ ] Add `from typing import Annotated` import
- [ ] Add `from whiskey import Inject` import
- [ ] Update all `@inject` decorated functions
- [ ] Update all class constructors that use DI
- [ ] Test that regular parameters aren't being injected
- [ ] Verify callable defaults (Setting, ConfigSection) work correctly
- [ ] Update any custom decorators that use injection
- [ ] Run your test suite
- [ ] Update your team's coding standards

## Troubleshooting

### "TypeError: 'type' object is not subscriptable"

If you get this error, you're likely on Python < 3.9. Use:

```python
from __future__ import annotations  # Add at top of file
```

Or use string annotations:

```python
def __init__(self, db: "Annotated[Database, Inject()]"):
    pass
```

### Services Not Being Injected

Make sure you:
1. Have the `@inject` decorator on the function/method
2. Use `Annotated[Type, Inject()]` for parameters to inject
3. Have registered the service in the container

### Mixing Old and New Patterns

During migration, you can temporarily support both patterns, but it's not recommended long-term. Focus on migrating one module at a time.

## Benefits After Migration

Once migrated, you'll enjoy:

1. **Clearer Code**: Anyone reading your code knows exactly what's injected
2. **Better IDE Support**: Type checkers understand your intent
3. **More Flexibility**: Mix injected and non-injected parameters freely
4. **Future-Proof**: The explicit pattern is more maintainable and extensible

## Need Help?

If you encounter issues during migration:
1. Check the examples in the `examples/` directory
2. Refer to the updated documentation
3. Open an issue on GitHub with a minimal reproduction

Happy migrating! 🚀

---

# API Simplification Migration Guide

This section covers the API simplification changes made to make Whiskey more Pythonic.

## Removed Features

### 1. Container Builder Pattern

**Old:**
```python
# Builder pattern has been completely removed
container.add(Service).as_singleton().tagged("core").build()
container.add_singleton(Database).build()
```

**New:**
```python
# Direct registration methods
container.singleton(Service, tags={"core"})
container.singleton(Database)
```

### 2. Redundant Registration Methods

**Old:**
```python
container.register_singleton(Service)
container.register_factory(Service, factory_func)
container.add_services(db=Database, cache=Cache)
```

**New:**
```python
container.singleton(Service)
container.factory(Service, factory_func)
container.services(db=Database, cache=Cache)
```

### 3. Application Decorator Aliases

**Old:**
```python
@app.provider  # Alias for @app.component
class Service1: pass

@app.managed   # Alias for @app.component
class Service2: pass

@app.system    # Alias for @app.singleton
class Service3: pass
```

**New:**
```python
@app.component  # For transient services
class Service1: pass

@app.component  # Same decorator
class Service2: pass

@app.singleton  # For singleton services
class Service3: pass
```

### 4. Test-Specific Methods

The following methods have been moved to `whiskey.core.testing`:
- `container.enter_scope()`
- `container.exit_scope()`
- `container.on_startup()`
- `container.on_shutdown()`

**For tests:**
```python
from whiskey.core.testing import add_test_compatibility_methods

container = Container()
add_test_compatibility_methods(container)
# Now you can use enter_scope, etc.
```

## Migration Steps

1. **Remove builder chains**: Replace `.add().build()` with direct registration
2. **Update decorator aliases**: Replace `@app.provider`, `@app.managed`, `@app.system` with `@app.component` or `@app.singleton`
3. **Use new method names**: `add_services` → `services`, `add_singleton` → `singleton`
4. **Update tests**: Add test compatibility methods where needed

## Benefits

- **Cleaner API**: One obvious way to do things
- **Less confusion**: No multiple aliases for the same functionality
- **More Pythonic**: Follows Python's design principles
- **Easier to learn**: Fewer concepts to understand