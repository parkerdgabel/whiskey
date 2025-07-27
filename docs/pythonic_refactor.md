# Pythonic Refactor of Whiskey DI/IoC

## Overview

This document outlines a proposed refactor to make Whiskey's core DI/IoC system more Pythonic, minimal, and intuitive.

## Key Principles

1. **Simple is better than complex** - Remove unnecessary abstractions
2. **Explicit is better than implicit** - Make behavior obvious
3. **Flat is better than nested** - Avoid deep inheritance hierarchies
4. **Duck typing over protocols** - Leverage Python's dynamic nature
5. **Async-first, sync-friendly** - Modern Python is async

## Core API Comparison

### Current (Complex) API

```python
# Complex initialization
from whiskey import Container, ServiceDescriptor, ScopeType
from whiskey.core.types import ServiceKey

container = Container()
descriptor = ServiceDescriptor(
    service_type=UserService,
    implementation=UserServiceImpl,
    scope=ScopeType.SINGLETON,
    name="primary"
)
container.register_descriptor(descriptor)

# Verbose resolution
user_service = container.resolve_sync(UserService, name="primary")

# Complex decorators with overloading
@provide(scope=ScopeType.REQUEST, name="db")
class DatabaseService:
    pass
```

### Proposed (Pythonic) API

```python
# Simple initialization
from whiskey import Container

container = Container()
container[UserService] = UserService()  # Instance
container[Database] = lambda: Database()  # Factory

# Natural resolution
user_service = await container.resolve(UserService)

# Simple decorators
@provide
class DatabaseService:
    pass
```

## Major Simplifications

### 1. Container (300+ lines → ~100 lines)

**Before:**
- Complex parent-child hierarchies
- ServiceKey with string manipulation
- ServiceDescriptor abstraction
- Separate sync/async methods
- Complex overloaded methods

**After:**
- Simple dict-like interface
- Direct type mapping
- Single async API
- Context manager support
- No inheritance needed

### 2. Resolver (200+ lines → integrated)

**Before:**
- Separate Resolver class
- Manual circular dependency tracking
- Complex context passing
- Type hint extraction logic

**After:**
- Simple recursive function in Container
- Python's natural recursion limit
- Direct inspect.signature usage
- Let KeyError bubble up naturally

### 3. Decorators (150+ lines → ~50 lines)

**Before:**
- Global mutable state
- Complex overloading
- Duplicate sync/async paths
- Multiple registration methods

**After:**
- Contextvar for current container
- Single signature per decorator
- Async-first with simple wrapper
- Composable functions

### 4. Scopes (300+ lines → ~30 lines)

**Before:**
- Abstract base classes
- Enum limitations
- Complex scope managers
- Lifecycle management

**After:**
- Simple context managers
- Dict-based storage
- Automatic cleanup
- No inheritance

### 5. Dependencies

**Current:**
- loguru (logging)
- Complex event system
- Command bus
- Many custom exceptions

**Proposed Core:**
- Standard library only
- Optional extensions for extras

## Migration Strategy

### Phase 1: Create New Core
```python
# whiskey/core/simple.py
class Container:
    """New simplified container."""
    
# Keep old container for compatibility
# whiskey/core/container.py stays unchanged
```

### Phase 2: Adapter Layer
```python
# Make old API work with new core
class LegacyContainer(SimpleContainer):
    """Compatibility wrapper."""
    
    def resolve_sync(self, service_type, name=None):
        # Delegate to new API
        return asyncio.run(self.resolve(service_type))
```

### Phase 3: Update Extensions
- Convert extensions to use new API
- Provide migration guide
- Update documentation

## Benefits

1. **Easier to Learn**
   - Familiar dict-like interface
   - No complex concepts to understand
   - Works like Python developers expect

2. **Easier to Debug**
   - Simple stack traces
   - Clear error messages
   - No magic behavior

3. **Better Performance**
   - Less abstraction overhead
   - Direct type lookups
   - Minimal object creation

4. **More Pythonic**
   - Follows Python idioms
   - Uses standard library patterns
   - Leverages language features

## Example: Complete App

```python
import asyncio
from whiskey import Container, inject

# Setup
container = Container()
container[Database] = lambda: Database("postgresql://localhost/db")
container.singleton(EmailService)
container[UserService] = UserService  # Auto-resolves dependencies

# Use
@inject
async def create_user(name: str, users: UserService):
    return await users.create(name)

# Run
with container:
    asyncio.run(create_user("Alice"))
```

## Next Steps

1. Implement `whiskey.core.simple` module
2. Create compatibility layer
3. Update first-party extensions
4. Provide migration tooling
5. Update documentation