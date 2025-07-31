# Core Module Consolidation Plan

## Overview
This plan consolidates the core module to create a more cohesive and loosely coupled architecture for the resolver system.

## Current Issues
1. **Tight Coupling**: Container class mixes too many concerns (resolution, registration, scope management)
2. **Scattered Logic**: Resolution logic spread across multiple files (container.py, smart_resolution.py, analyzer.py, generic_resolution.py)
3. **Complex Inheritance**: Multiple mixins (SmartResolver, SmartDictAccess, SmartCalling) make the code hard to follow
4. **Duplicate Code**: Similar resolution patterns repeated in multiple places

## New Architecture

### 1. Unified Resolver System (resolver.py)
- **TypeResolver**: Handles type analysis and injection decisions
  - Integrates TypeAnalyzer functionality
  - Integrates GenericTypeResolver functionality
  - Manages type analysis caching
  
- **DependencyResolver**: Handles dependency graph resolution
  - Resolves constructor/function dependencies
  - Manages injection caching
  - Handles auto-creation of unregistered types
  
- **ScopeResolver**: Handles scope-based resolution
  - Manages singleton instances
  - Handles scoped instances
  - Implements scope validation
  
- **AsyncResolver**: Handles async/sync context adaptation
  - Detects execution context
  - Provides appropriate resolution strategy
  - Clear error messages for context mismatches

- **UnifiedResolver**: Main coordinator
  - Combines all resolvers
  - Provides clean API
  - Maintains loose coupling between components

### 2. Simplified Container (container_v2.py)
- Focuses only on API and registration
- Delegates all resolution logic to UnifiedResolver
- Cleaner, more maintainable code
- Better separation of concerns

### 3. Benefits
- **Single Responsibility**: Each component has one clear purpose
- **Loose Coupling**: Components communicate through well-defined interfaces
- **Better Testing**: Each resolver can be tested independently
- **Easier Maintenance**: Logic is organized and easy to find
- **Performance**: Centralized caching and optimization
- **Extensibility**: Easy to add new resolution strategies

## Migration Steps

### Phase 1: Create New Components
1. ✅ Create resolver.py with unified resolver system
2. ✅ Create container_v2.py with simplified container
3. Create comprehensive tests for new components

### Phase 2: Gradual Migration
1. Update imports to use new resolver system
2. Migrate functionality from smart_resolution.py mixins
3. Consolidate analyzer.py and generic_resolution.py into TypeResolver
4. Update existing tests to work with new architecture

### Phase 3: Cleanup
1. Remove smart_resolution.py (mixins now integrated)
2. Simplify analyzer.py (keep only utility functions)
3. Remove redundant code from container.py
4. Update documentation

### Phase 4: Optimization
1. Implement advanced caching strategies
2. Add performance monitoring hooks
3. Optimize hot paths
4. Add resolver plugins/extensions support

## Code Organization After Consolidation

```
core/
├── __init__.py          # Public API exports
├── container.py         # Simplified container (from container_v2.py)
├── resolver.py          # Unified resolver system
├── registry.py          # Component registry (unchanged)
├── analyzer.py          # Type analysis utilities (simplified)
├── errors.py           # Error types (unchanged)
├── scopes.py           # Scope management (unchanged)
├── decorators.py       # Decorator functions (unchanged)
├── types.py            # Type definitions (unchanged)
└── performance.py      # Performance monitoring (unchanged)
```

## Removed/Consolidated Files
- smart_resolution.py → Integrated into resolver.py and container.py
- generic_resolution.py → Integrated into resolver.py (TypeResolver)
- Parts of analyzer.py → Moved to resolver.py (TypeResolver)

## API Compatibility
The public API remains unchanged:
- `container.resolve()` - Smart resolution
- `container.resolve_sync()` - Explicit sync
- `container.resolve_async()` - Explicit async
- `container[key]` - Dict-like access
- Registration methods unchanged

## Next Steps
1. Review and approve the plan
2. Implement comprehensive tests for new components
3. Begin gradual migration
4. Monitor for any regressions
5. Complete consolidation