# Whiskey Framework Testing Analysis

## 1. whiskey/core/container.py

### Key Classes/Functions
- `Container` - Main dependency injection container
- Registration methods: `register`, `register_singleton`, `register_transient`, `register_scoped`
- Resolution methods: `resolve`, `resolve_sync`, `resolve_all`
- Inspection methods: `has_service`, `get_descriptor`, `get_all_services`
- Container management: `create_child`, `dispose`

### Critical Functionality
- Service registration with different scopes
- Dependency resolution with async support
- Parent-child container hierarchy
- Service lifecycle management
- Thread-safe operations with locks

### Edge Cases
- Registering service with multiple implementation types (should fail)
- Resolving non-existent services
- Circular parent-child relationships
- Concurrent access to singleton services
- Disposing already disposed container
- Registering services after disposal
- Empty or None service keys
- String-based service keys vs type-based keys

### Error Conditions
- `InvalidServiceError` when registering without implementation/factory/instance
- `InvalidServiceError` when registering in disposed container
- Resolution errors for missing services
- Type mismatch errors

### Integration Points
- `DependencyResolver` for resolution logic
- `ScopeManager` for scope management
- Parent containers for hierarchical resolution

## 2. whiskey/core/resolver.py

### Key Classes/Functions
- `DependencyResolver` - Handles dependency resolution with cycle detection
- `_resolve_internal` - Core resolution logic
- `_create_instance` - Instance creation from descriptors
- `_create_from_factory` - Factory-based creation
- `_create_from_class` - Class-based creation
- `_get_injection_points` - Extract dependencies from callables
- `_resolve_dependencies` - Resolve all dependencies for injection

### Critical Functionality
- Circular dependency detection
- Async dependency resolution
- Optional dependency handling
- Type annotation parsing
- Factory function support (sync and async)
- Automatic dependency injection into constructors

### Edge Cases
- Self-referential dependencies
- Optional types with None defaults
- Forward references in type hints
- Classes without `__init__` methods
- Multiple levels of nested dependencies
- Mixing sync and async factories
- Generic types as dependencies
- Union types in parameters

### Error Conditions
- `CircularDependencyError` for dependency cycles
- `ServiceNotFoundError` for missing services
- `InjectionError` for injection failures
- `ResolutionError` for general resolution failures

### Integration Points
- Container for service lookup
- Scope management for instance storage
- Type inspection utilities

## 3. whiskey/core/scopes.py

### Key Classes/Functions
- `Scope` (ABC) - Base scope interface
- `SingletonScope` - Application-lifetime instances
- `TransientScope` - New instance per request
- `ContextVarScope` - Base for context-specific scopes
- `RequestScope`, `SessionScope`, `ConversationScope`, `AIContextScope`, `BatchScope`, `StreamScope`
- `ScopeManager` - Manages all scopes
- `ScopedInstances` - Thread-safe instance storage

### Critical Functionality
- Instance lifecycle management per scope
- Context variable-based scoping
- Async-safe instance storage
- Disposable instance cleanup
- Custom scope registration

### Edge Cases
- Concurrent access to scoped instances
- Context propagation across async boundaries
- Nested contexts with same scope
- Disposing instances that throw errors
- Clearing scopes with active references
- Custom scope name conflicts

### Error Conditions
- `ScopeError` for unknown scopes
- `ScopeError` for duplicate scope registration
- Disposal errors (logged but not raised)

### Integration Points
- Container for scope usage
- Async context management
- Disposable protocol implementation

## 4. whiskey/core/decorators.py

### Key Classes/Functions
- `provide` - Register class as service
- `singleton` - Register as singleton
- `inject` - Inject dependencies into functions
- `factory` - Register factory functions
- `named` - Create named bindings
- `scoped` - Specify scope
- Container management: `get_default_container`, `set_default_container`

### Critical Functionality
- Decorator-based service registration
- Automatic dependency injection
- Support for both sync and async functions
- Parameter override support
- Default container management

### Edge Cases
- Decorating already decorated functions
- Injecting into methods vs functions
- Optional parameters with no defaults
- Overriding injected dependencies
- Mixed sync/async injection targets
- Decorating classes vs instances
- Multiple decorators on same target

### Error Conditions
- Missing type annotations
- Unresolvable dependencies
- Invalid decorator syntax usage

### Integration Points
- Default container instance
- Service registration
- Dependency resolution

## 5. whiskey/core/types.py

### Key Classes/Functions
- `ScopeType` enum - Built-in scope types
- `ServiceDescriptor` - Service registration metadata
- `InjectionPoint` - Injection location metadata
- Protocols: `Injectable`, `Disposable`, `Initializable`
- `ResolverContext` - Resolution state tracking
- Type utilities: `is_generic_type`, `is_optional_type`, `unwrap_optional`

### Critical Functionality
- Type safety for service registration
- Protocol definitions for lifecycle hooks
- Generic type handling
- Optional type detection

### Edge Cases
- Complex generic types (List[T], Dict[K,V])
- Nested optional types
- Protocol implementation validation
- Circular context references

### Error Conditions
- `ValueError` for invalid ServiceDescriptor
- Type inspection failures

### Integration Points
- Used throughout the framework
- Protocol compliance checking

## 6. whiskey/core/exceptions.py

### Key Classes/Functions
- `WhiskeyError` - Base exception
- `ServiceNotFoundError` - Missing service
- `CircularDependencyError` - Dependency cycles
- `ScopeError` - Scope issues
- `InvalidServiceError` - Invalid registration
- `InjectionError` - Injection failures
- `ConfigurationError` - Config issues
- `LifecycleError` - Lifecycle failures
- `ResolutionError` - Resolution failures

### Critical Functionality
- Detailed error messages
- Error context preservation
- Helpful suggestions in errors

### Edge Cases
- Very long dependency chains in errors
- Multiple nested exceptions
- Unicode in error messages

### Error Conditions
- All are error conditions by definition

### Integration Points
- Used throughout for error reporting

## 7. whiskey/core/application.py

### Key Classes/Functions
- `ApplicationConfig` - App configuration
- `Application` - Main IoC container
- Decorators: `service`, `task`, `on`, `middleware`
- Lifecycle methods: `startup`, `shutdown`, `run`
- `lifespan` context manager

### Critical Functionality
- Application lifecycle management
- Service auto-discovery
- Background task management
- Event handler registration
- Signal handling
- Middleware pipeline

### Edge Cases
- Multiple app instances
- Tasks failing during startup
- Shutdown during startup
- Signal handling on different platforms
- Module discovery with circular imports
- Background tasks with errors

### Error Conditions
- Module import failures
- Service initialization errors
- Task execution failures
- Signal handling errors

### Integration Points
- Container management
- Event bus integration
- Service lifecycle hooks

## 8. whiskey/core/events.py

### Key Classes/Functions
- `Event` - Base event class
- `EventBus` - Event routing
- Event handler registration: `on`, `off`
- Event emission: `emit`, `emit_sync`
- Middleware support
- Built-in events: `ApplicationStarted`, `ServiceInitialized`, etc.

### Critical Functionality
- Async event processing
- Middleware chain execution
- Event queue management
- Worker task lifecycle

### Edge Cases
- Events emitted before bus started
- Recursive event emission
- Handler errors during processing
- Very large event queues
- Middleware modifying events
- Concurrent event emission

### Error Conditions
- Handler execution errors
- Middleware errors
- Queue overflow scenarios

### Integration Points
- Application lifecycle events
- Service initialization events
- Error reporting

## 9. whiskey/core/commands.py

### Key Classes/Functions
- `Command`, `Query` - Base classes
- `CommandHandler`, `QueryHandler` - Handler interfaces
- `CommandBus` - Command routing
- Registration: `register_command`, `register_query`
- Execution: `execute`, `query`

### Critical Functionality
- CQRS pattern implementation
- Automatic handler DI
- Type-safe command/query handling

### Edge Cases
- Unregistered command types
- Multiple handlers for same command
- Generic query types
- Handler registration order
- Async vs sync handlers

### Error Conditions
- No handler registered
- Handler execution failures
- DI resolution failures

### Integration Points
- Container for handler resolution
- Decorator-based registration

## 10. whiskey/core/config.py

### Key Classes/Functions
- `ConfigSource` (ABC) - Config source interface
- `EnvironmentSource` - Environment variables
- `YamlSource` - YAML files
- `ConfigurationManager` - Config aggregation
- Decorators: `config_value`, `config_class`

### Critical Functionality
- Multiple config source support
- Type-safe config classes
- Nested key support
- Config reloading
- Caching

### Edge Cases
- Missing YAML module
- Non-existent config files
- Circular config dependencies
- Type conversion failures
- Deeply nested config keys
- Config file permissions

### Error Conditions
- File I/O errors
- YAML parsing errors
- Type conversion errors
- Missing required config

### Integration Points
- Container for config class registration
- Environment variable integration

## 11. whiskey/ai/context/ai_context.py

### Key Classes/Functions
- `AIContext` - AI operation context
- `AIContextManager` - Context lifecycle
- Context access: `get_current_context`, `set_current_context`
- Usage tracking methods
- Message history management

### Critical Functionality
- Token usage tracking
- Cost calculation
- Conversation history
- Context nesting
- Metadata storage

### Edge Cases
- Nested AI contexts
- Context without active conversation
- Very large message histories
- Concurrent context access
- Context serialization with circular refs

### Error Conditions
- Context not found
- Invalid token counts
- Serialization errors

### Integration Points
- Context variables for propagation
- Logging integration
- Cost tracking systems

## Testing Strategy Recommendations

### Unit Tests
- Test each class/function in isolation
- Mock dependencies
- Test all error conditions
- Verify edge cases

### Integration Tests
- Test component interactions
- Test full registration/resolution cycles
- Test scope propagation
- Test event flow

### Performance Tests
- Concurrent resolution
- Large dependency graphs
- Many services registered
- Event throughput

### Example Test Cases
1. Container: Register and resolve with all scope types
2. Resolver: Create circular dependency scenario
3. Scopes: Test context propagation across async calls
4. Decorators: Test injection with missing dependencies
5. Application: Test full startup/shutdown cycle
6. Events: Test concurrent event emission
7. Commands: Test CQRS with complex handlers
8. Config: Test multi-source priority
9. AI Context: Test token accumulation across operations