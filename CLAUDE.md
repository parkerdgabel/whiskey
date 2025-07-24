# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Essential Commands

All Python commands must be run through `uv`:

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest                              # Run all tests
uv run pytest tests/core/test_container.py # Run specific test file
uv run pytest -k "test_resolve_simple"     # Run specific test by name
uv run pytest -xvs                         # Stop on first failure, verbose

# Coverage
uv run pytest --cov=whiskey --cov-report=term-missing  # With coverage report

# Linting and formatting
uv run ruff check                    # Run linter
uv run ruff check --fix             # Auto-fix issues
uv run ruff format                  # Format code

# Type checking
uv run mypy whiskey
```

## Architecture Overview

Whiskey is a dependency injection and IoC framework designed specifically for AI applications. The architecture consists of several interconnected systems:

### Core DI System

**Container → Resolver → Scopes**

1. **Container** (`core/container.py`): Stores service registrations and manages parent-child hierarchies
2. **Resolver** (`core/resolver.py`): Creates instances with recursive dependency resolution and circular dependency detection
3. **Scopes** (`core/scopes.py`): Manages service lifetimes using contextvars for thread-safe isolation

### Decorator Flow

Decorators modify the default container or create metadata:
- `@provide`, `@singleton`, `@factory` → Register in default container
- `@inject` → Wraps functions to auto-resolve parameters from container
- `@scoped` → Creates custom scoped services

### Application Lifecycle (IoC)

The `Application` class (`core/application.py`) implements true IoC:
1. Services registered via `@app.service` 
2. On startup: Initialize all `Initializable` services in dependency order
3. Background tasks started via `@app.task`
4. Event handlers connected via `@app.on(event)`
5. On shutdown: Dispose all `Disposable` services in reverse order

### AI-Specific Architecture

- **AIContext** (`ai/context/ai_context.py`): Tracks token usage, costs, and conversation history
- **Conversation Scope**: Maintains state across multi-turn dialogues
- **Context Variables**: Thread-safe context propagation using Python's contextvars

### Event System

Event-driven architecture with:
- Async queue-based processing
- Middleware pipeline for cross-cutting concerns
- Type-safe event definitions

### Key Interactions

1. **Service Resolution**: 
   - Function decorated with `@inject` called
   - Resolver examines type hints
   - Recursively resolves dependencies from container
   - Scope determines if new instance or cached

2. **Scope Management**:
   - Request comes in → Request scope created
   - AI operation starts → AIContext scope created  
   - Scopes nest hierarchically
   - Disposal happens in reverse order when scope ends

3. **Async Patterns**:
   - All resolution is async (`await container.resolve()`)
   - Sync alternatives exist (`resolve_sync()` uses `asyncio.run`)
   - Event processing is queue-based and concurrent

## Testing Approach

- Tests organized by module in `tests/core/` and `tests/ai/`
- Fixtures in `tests/conftest.py` provide test services and containers
- 80% coverage requirement enforced in pytest config
- Use `@pytest.mark.unit` for unit tests

## Development Notes

- Place temporary test files in `/tmp`
- The framework is async-first but provides sync alternatives
- Scopes use contextvars, not thread-locals, for async safety
- Protocol classes need `@runtime_checkable` decorator
- Always check for circular dependencies in complex service graphs