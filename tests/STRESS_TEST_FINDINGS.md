# Whiskey Framework Stress Test Findings

## Summary

The stress testing revealed several issues and limitations in the Whiskey framework that should be addressed to make it production-ready.

## Issues Found

### 1. Forward Reference Resolution
**Issue**: The framework cannot resolve forward references in type hints.
```python
@component
class ServiceA:
    def __init__(self, b: 'ServiceB'):  # Forward reference fails
        self.b = b
```
**Error**: `TypeError: Cannot resolve forward reference: 'ServiceB'`
**Impact**: Common pattern in Python for circular imports fails
**Fix Needed**: Implement proper forward reference resolution using `get_type_hints()`

### 2. Async/Sync Confusion
**Issue**: The API is inconsistent about async vs sync resolution.
```python
# This looks like it should work but doesn't
service = await app.resolve(ServiceClass)  # ServiceClass is not awaitable
```
**Impact**: Confusing API, unclear when to use async
**Fix Needed**: Clear separation of async/sync APIs or make everything consistently async

### 3. Factory Registration API
**Issue**: Factory decorator has confusing parameter requirements.
```python
@app.factory(int)  # Missing 'func' parameter
def create_int():
    return 42
```
**Impact**: Unclear how to properly register factories
**Fix Needed**: Better decorator API design

### 4. Scope Violation Detection
**Issue**: Scope violations are not properly detected at registration time.
- Singleton depending on scoped service should fail immediately
- Currently fails only at resolution time with unclear error

### 5. Generic Type Resolution
**Issue**: Complex generic types are not properly resolved.
```python
class Repository(Generic[T]): pass
class UserRepository(Repository[User]): pass

# Injection of Repository[User] fails
```
**Impact**: Cannot use generic types effectively
**Fix Needed**: Better type analysis for generics

### 6. Error Messages
**Issue**: Error messages are often unclear about the root cause.
- "Cannot auto-create X: not all parameters can be injected" doesn't say which parameter
- Missing component errors don't suggest solutions

### 7. Missing Features
Based on testing, these features would improve the framework:
- Circular dependency detection at registration time
- Better handling of Optional types
- Support for Protocol types
- Conditional registration that works properly
- Lifecycle hooks (post-construct, pre-destroy)

### 8. Thread Safety
**Issue**: The framework doesn't document thread safety guarantees.
- Singleton creation may not be thread-safe
- Container modifications during resolution could cause issues

### 9. Memory Management
**Issue**: No clear lifecycle management for components.
- No dispose/cleanup mechanism
- Scoped components may leak if scope isn't properly closed

### 10. Performance Concerns
**Issue**: Type analysis happens at resolution time, not registration.
- Could be optimized by analyzing types once during registration
- Reflection overhead on every resolution

## Recommendations

### High Priority Fixes

1. **Fix Forward References**: Implement proper forward reference resolution
2. **Clarify Async/Sync API**: Make the API consistent and clear
3. **Improve Error Messages**: Add context about what failed and why
4. **Add Lifecycle Hooks**: Support initialization and cleanup

### Medium Priority

5. **Generic Type Support**: Handle generic types properly
6. **Thread Safety**: Document and ensure thread safety
7. **Performance**: Cache type analysis results
8. **Scope Validation**: Validate scope dependencies at registration

### Nice to Have

9. **Better Factory API**: Simplify factory registration
10. **Debugging Tools**: Add container inspection and debugging aids

## Positive Findings

Despite the issues, the framework has good foundations:
- Clean decorator-based API
- Good separation of concerns
- Extensible architecture
- Type-hint based injection is intuitive

## Test Code That Should Work But Doesn't

```python
# 1. Forward references
@component
class A:
    def __init__(self, b: 'B'): pass

@component  
class B:
    def __init__(self): pass

# 2. Generic resolution
@component
class GenericService:
    def __init__(self, repo: Repository[User]):
        self.repo = repo

# 3. Protocol support
class Service(Protocol):
    def process(self) -> str: ...

@component
class MyService:
    def __init__(self, svc: Service):
        self.svc = svc

# 4. Clean factory syntax
@factory(ConnectionPool)
def create_pool(config: Config):
    return ConnectionPool(config.db_url)
```

## Conclusion

The Whiskey framework has a solid foundation but needs work to handle real-world Python patterns properly. The main issues revolve around type resolution, API consistency, and error handling. With the fixes outlined above, it could become a robust DI framework for Python.