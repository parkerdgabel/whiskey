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

Whiskey is a simple, Pythonic dependency injection framework. The architecture is minimal and intuitive:

### Core DI System

**Container (with integrated resolver) → Scopes**

1. **Container** (`core/container.py`): Dict-like service registry with integrated dependency resolution
2. **Scopes** (`core/scopes.py`): Simple context managers for service lifetimes

### Decorator Flow

Simple decorators that work with the default container:
- `@provide`, `@singleton`, `@factory` → Register in default container
- `@inject` → Auto-resolve parameters from container
- `@scoped` → Register with custom scope

### Application (Rich IoC Container)

The `Application` class (`core/application.py`) provides rich IoC features:
1. Components registered via `@app.component` (or `provider`, `managed`, `system`)
2. Rich lifecycle phases: configure → register → before_startup → startup → after_startup → ready
3. Built-in event emitter with wildcard support
4. Component metadata (priority, requires, provides, critical)
5. Extension hooks for adding new decorators and lifecycle phases
6. Background tasks via `@app.task`
7. Error handling via `@app.on_error`

### Extensions

Extensions are simple functions that configure the container:
- `whiskey-ai`: Adds AI-specific scopes (session, conversation, ai_context)
- `whiskey-asgi`: Adds ASGI web framework support
- `whiskey-cli`: Adds CLI application support

### Key Design Principles

1. **Pythonic API**: 
   - Container works like a dict: `container[Service] = instance`
   - Natural Python patterns, no magic
   - Type hints for IDE support

2. **Minimal Core**:
   - Under 500 lines total
   - No required dependencies
   - Extensions add functionality

3. **Async-First**:
   - `await container.resolve()` is the primary API
   - Sync support where needed
   - Modern Python patterns

## Testing Approach

- Tests organized by module in `tests/core/`
- Simple, focused unit tests
- No complex mocking needed
- Use `@pytest.mark.unit` for unit tests

## Development Philosophy

- **Simple is better than complex** - Remove abstractions
- **Explicit is better than implicit** - No hidden behavior
- **Minimal dependencies** - Standard library only for core
- **Async-first** - Built for modern Python
- **Type-safe** - Full typing support
- **Extensible** - Easy to add features via extensions