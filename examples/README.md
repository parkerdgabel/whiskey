# Whiskey Examples

This directory contains comprehensive examples demonstrating all of Whiskey's dependency injection and application framework features. The examples are organized progressively from basic concepts to advanced real-world scenarios.

## Example Overview

### Core Foundation Examples

1. **[01_basic_di.py](01_basic_di.py)** - Basic Dependency Injection
   - Service registration with decorators (`@provide`, `@singleton`)
   - Automatic dependency resolution with `@inject`
   - Container as a service registry (dict-like API)
   - Factory functions and scope behaviors
   - **Start here** if you're new to Whiskey

2. **[02_scopes_and_lifecycle.py](02_scopes_and_lifecycle.py)** - Scopes and Lifecycle Management
   - Service scopes (singleton, transient, scoped)
   - Custom scopes with `ContextVarScope`
   - Service lifecycle management (`Initializable`, `Disposable`)
   - Resource cleanup and disposal patterns

3. **[03_application_framework.py](03_application_framework.py)** - Rich Whiskey Framework
   - Component registration with metadata
   - Whiskey lifecycle phases and hooks
   - Event system with wildcard patterns
   - Background tasks and health checking
   - Error handling and monitoring

### New Features (Core Enhancements)

4. **[04_named_dependencies.py](04_named_dependencies.py)** - Named Dependencies
   - Multiple implementations of the same interface
   - Named service registration and resolution
   - Use cases: primary/backup databases, different cache types
   - Clear service identification patterns

5. **[05_conditional_registration.py](05_conditional_registration.py)** - Conditional Registration
   - Environment-based service registration
   - Feature flag support with conditions
   - Runtime condition evaluation
   - Automatic fallback patterns

6. **[06_lazy_resolution.py](06_lazy_resolution.py)** - Lazy Resolution
   - Deferred dependency initialization
   - `Lazy[T]` wrapper for on-demand loading
   - `LazyDescriptor` for class-level lazy attributes
   - Performance optimization patterns

7. **[07_combined_features.py](07_combined_features.py)** - All Features Combined
   - Realistic microservice using all three new features
   - Environment-aware deployments
   - Graceful degradation and fallbacks
   - Production-ready patterns

### Advanced Patterns

8. **[08_discovery_and_inspection.py](08_discovery_and_inspection.py)** - Component Discovery
   - Automatic component discovery in modules
   - Filtering by predicates and markers
   - Container introspection and debugging
   - Dependency analysis and resolution troubleshooting

9. **[09_events_and_tasks.py](09_events_and_tasks.py)** - Events and Background Tasks
   - Event-driven architecture patterns
   - Background task management and coordination
   - Event handlers with wildcard patterns
   - System monitoring and health checks

10. **[10_real_world_microservice.py](10_real_world_microservice.py)** - Complete Microservice
    - Production-ready e-commerce order processing service
    - All Whiskey features working together
    - Multiple deployment scenarios (prod, staging, dev, minimal)
    - Hexagonal architecture with domain-driven design

### Legacy Examples (Maintained)

- **[simple_example.py](simple_example.py)** - Original simple example (maintained for compatibility)
- **[application_example.py](application_example.py)** - Original application example  
- **[discovery_example.py](discovery_example.py)** - Original discovery example

## Running the Examples

Each example is self-contained and can be run independently:

```bash
# Basic concepts
python examples/01_basic_di.py
python examples/02_scopes_and_lifecycle.py
python examples/03_application_framework.py

# New features
python examples/04_named_dependencies.py
python examples/05_conditional_registration.py
python examples/06_lazy_resolution.py
python examples/07_combined_features.py

# Advanced patterns
python examples/08_discovery_and_inspection.py
python examples/09_events_and_tasks.py
python examples/10_real_world_microservice.py
```

## Learning Path

### For Beginners
1. Start with `01_basic_di.py` to understand core concepts
2. Learn about scopes in `02_scopes_and_lifecycle.py`
3. Explore the application framework in `03_application_framework.py`

### For Intermediate Users
4. Learn the new features: `04_named_dependencies.py`, `05_conditional_registration.py`, `06_lazy_resolution.py`
5. See how they work together in `07_combined_features.py`
6. Explore discovery patterns in `08_discovery_and_inspection.py`

### For Advanced Users
7. Study event-driven patterns in `09_events_and_tasks.py`
8. Examine the complete microservice in `10_real_world_microservice.py`

## Key Concepts Demonstrated

### Dependency Injection Patterns
- **Constructor Injection**: Dependencies injected through class constructors
- **Explicit Injection**: Using `Annotated[Type, Inject()]` for clarity
- **Named Dependencies**: Multiple implementations with names
- **Conditional Registration**: Environment-aware service selection
- **Lazy Resolution**: On-demand dependency initialization

### Whiskey Architecture Patterns
- **Hexagonal Architecture**: Clean separation of concerns
- **Event-Driven Architecture**: Loose coupling through events
- **Domain-Driven Design**: Business logic encapsulation
- **Microservice Patterns**: Service decomposition and communication

### Advanced Features
- **Component Discovery**: Automatic service registration
- **Container Introspection**: Debugging and analysis tools
- **Background Tasks**: Async task management
- **Health Monitoring**: Service health and observability
- **Graceful Degradation**: Fallback and error handling

## Production Considerations

The examples demonstrate patterns suitable for production use:

- **Configuration Management**: Environment-based configuration
- **Error Handling**: Proper exception handling and recovery
- **Resource Management**: Connection pooling and cleanup
- **Monitoring**: Health checks and metrics collection  
- **Scalability**: Lazy loading and efficient resource usage
- **Testability**: Dependency injection enables easy testing

## Next Steps

After exploring these examples:

1. **Read the Documentation**: Check the main README.md for detailed API reference
2. **Explore Extensions**: Look for Whiskey extensions (whiskey-asgi, whiskey-cli, etc.)
3. **Build Your Whiskey**: Apply these patterns to your own projects
4. **Contribute**: Share your patterns and improvements with the community

## Need Help?

- **Issues**: Report bugs or request features on GitHub
- **Discussions**: Ask questions in GitHub Discussions
- **Documentation**: Check the main project documentation
- **Examples**: These examples cover most common use cases

---

*These examples represent current best practices with Whiskey v0.1.0. They are actively maintained and updated with new features.*