# Whiskey Standardized Run API Migration Guide

This guide helps extension developers migrate to the new standardized run API introduced in Whiskey.

## Overview

The new `app.run()` method provides a unified way to execute programs within the Whiskey IoC context. It handles:

- Application lifecycle (startup/shutdown)
- Dependency injection for the main callable
- Async/sync execution detection
- Extension-specific runners (CLI, ASGI, etc.)

## Key Changes

### Before (Old Pattern)

Extensions would modify the `run` method directly:

```python
def my_extension(app: Application):
    # Save original run
    original_run = app.run
    
    def enhanced_run(main=None):
        if main is None and hasattr(app, "my_runner"):
            app.my_runner()
        else:
            original_run(main)
    
    app.run = enhanced_run
    app.my_runner = lambda: print("Running my extension")
```

### After (New Pattern)  

Extensions should register runners using the standardized API:

```python
def my_extension(app: Whiskey):
    def run_my_extension(**kwargs):
        """Run my extension."""
        async def main():
            async with app.lifespan():
                # Extension logic here
                return 0
        
        return asyncio.run(main())
    
    # Register the runner
    app.register_runner("my_extension", run_my_extension)
    
    # Optionally, also add as a method for direct access
    app.run_my_extension = run_my_extension
```

## Migration Steps

### 1. Update Runner Implementation

Ensure your runner:
- Uses `app.lifespan()` for lifecycle management
- Returns a result (e.g., exit code for CLI, None for servers)
- Accepts `**kwargs` for flexibility

```python
def run_cli(**kwargs):
    """Run the CLI application."""
    async def cli_main():
        async with app.lifespan():
            # Parse arguments
            args = kwargs.get('args', sys.argv[1:])
            
            # Execute command with DI
            result = await app.call_async(command_func, *args)
            
            return 0 if result else 1
    
    return asyncio.run(cli_main())
```

### 2. Register the Runner

Use `app.register_runner()` instead of modifying `app.run`:

```python
# Register runner
app.register_runner("cli", run_cli)

# Also add as method for backward compatibility
app.run_cli = run_cli
```

### 3. Remove Run Method Modifications

Remove any code that modifies `app.run` directly:

```python
# REMOVE THIS:
# original_run = app.run
# app.run = enhanced_run
```

### 4. Update Documentation

Update your extension docs to show the new usage:

```python
# Users can now run in multiple ways:

# 1. Auto-detect runner (uses first registered)
app.run()

# 2. Run with specific runner method
app.run_cli()

# 3. Run with custom main function
@inject
async def main(service: MyService):
    await service.do_work()

app.run(main)
```

## Complete Example: CLI Extension

Here's how the CLI extension should be updated:

```python
def cli_extension(app: Whiskey):
    """CLI extension using standardized run API."""
    
    # Initialize CLI manager
    manager = CLIManager(app)
    app.cli_manager = manager
    
    # ... (command registration logic) ...
    
    def run_cli(args=None, **kwargs):
        """Run the CLI application."""
        import sys
        
        # Use provided args or sys.argv
        if args is None:
            args = sys.argv[1:]
        
        async def cli_main():
            async with app.lifespan():
                # Set up CLI context
                app.container[Application] = app
                
                # Parse and execute commands
                return manager.execute(args)
        
        return asyncio.run(cli_main())
    
    # Register runner
    app.register_runner("cli", run_cli)
    app.run_cli = run_cli
    
    # Add CLI decorators
    app.add_decorator("command", command)
    app.add_decorator("argument", argument)
    app.add_decorator("option", option)
```

## Complete Example: ASGI Extension

Here's how the ASGI extension should be updated:

```python
def asgi_extension(app: Whiskey):
    """ASGI extension using standardized run API."""
    
    # Initialize ASGI manager
    manager = ASGIManager(app)
    app.asgi_manager = manager
    app.asgi = manager.create_asgi_handler()
    
    # ... (route registration logic) ...
    
    def run_asgi(host="127.0.0.1", port=8000, **kwargs):
        """Run the ASGI server."""
        try:
            import uvicorn
        except ImportError:
            raise ImportError("uvicorn required: pip install uvicorn")
        
        # The ASGI handler already manages lifecycle via lifespan protocol
        # So we can run uvicorn directly
        uvicorn.run(app.asgi, host=host, port=port, **kwargs)
    
    # Register runner  
    app.register_runner("asgi", run_asgi)
    app.run_asgi = run_asgi
    
    # Add route decorators
    app.add_decorator("get", create_route_decorator(["GET"]))
    app.add_decorator("post", create_route_decorator(["POST"]))
    # ... etc ...
```

## Benefits of the New API

1. **Consistency**: All extensions use the same pattern
2. **Composability**: Multiple extensions can register runners without conflicts  
3. **Lifecycle Management**: Automatic startup/shutdown handling
4. **Flexibility**: Users can provide custom main functions or use extension runners
5. **Testing**: Easier to test with consistent execution model

## Testing Your Migration

```python
import pytest
from whiskey import Whiskey
from my_extension import my_extension

def test_runner_registration():
    app = Whiskey()
    app.use(my_extension)
    
    # Runner should be registered
    assert hasattr(app, 'run_my_extension')
    
    # Should work with app.run()
    result = app.run()
    assert result is not None

def test_custom_main():
    app = Whiskey()
    app.use(my_extension)
    
    @inject
    async def main(service: MyService):
        return await service.get_data()
    
    # Should work with custom main
    result = app.run(main)
    assert result is not None

@pytest.mark.asyncio
async def test_lifecycle():
    app = Whiskey()
    app.use(my_extension)
    
    startup_called = False
    shutdown_called = False
    
    @app.on_startup
    async def startup():
        nonlocal startup_called
        startup_called = True
    
    @app.on_shutdown  
    async def shutdown():
        nonlocal shutdown_called
        shutdown_called = True
    
    # Run should trigger lifecycle
    app.run(lambda: None)
    
    assert startup_called
    assert shutdown_called
```

## Backward Compatibility

To maintain backward compatibility:

1. Keep the `run_*` methods (e.g., `run_cli`, `run_asgi`)
2. Document both old and new usage patterns
3. Consider adding deprecation warnings in future versions

## Questions?

If you have questions about migrating your extension, please:

1. Check the `examples/run_api_example.py` for detailed examples
2. Review the test suite for usage patterns
3. Open an issue on GitHub for clarification