# Whiskey CLI Extension - Run API Migration Status

## Migration Summary

The Whiskey CLI extension has been updated to use the new standardized run API. Here are the key changes:

### ✅ Completed

1. **Removed direct `app.run` modification** - The extension no longer modifies the `app.run` method
2. **Added `register_runner`** - The CLI runner is now registered using `app.register_runner("cli", run_cli)`
3. **Updated lifecycle management** - Commands now execute within the app's lifecycle context
4. **Maintained backward compatibility** - `app.run_cli()` is still available for direct CLI execution

### 🔧 Known Issues

1. **Nested event loop warnings** - When running in environments with existing event loops (like Jupyter or during tests)
2. **Command registration timing** - Some edge cases with decorator ordering affecting argument/option registration

### 📝 Usage Examples

#### Basic Usage (Recommended)

```python
from whiskey import Whiskey
from whiskey_cli import cli_extension

# Create app with CLI support
app = Whiskey()
app.use(cli_extension)

# Define commands
@app.command()
def hello():
    print("Hello, World!")

# Run the CLI (will parse sys.argv)
if __name__ == "__main__":
    app.run()  # Automatically uses CLI runner
```

#### Direct CLI Execution

```python
# Run specific commands programmatically
app.run_cli(["hello"])

# Or with arguments
app.run_cli(["greet", "Alice", "--loud"])
```

#### Mixed Usage

```python
# Run custom main function
@inject
async def main(service: MyService):
    return await service.do_work()

# Can run either CLI or custom main
if len(sys.argv) > 1:
    app.run()  # CLI mode
else:
    result = app.run(main)  # Custom main
```

## Technical Details

### How It Works

1. The CLI extension registers a runner using the new API:
   ```python
   app.register_runner("cli", run_cli)
   ```

2. When `app.run()` is called without arguments, it finds and uses the CLI runner

3. The CLI runner manages the lifecycle:
   ```python
   async def cli_main():
       async with app.lifespan:
           # Execute Click CLI here
   ```

4. Commands are executed with dependency injection support through `app.call_async()`

### Benefits

- **Consistency**: Uses the same lifecycle management as other runners
- **Compatibility**: Multiple extensions can register runners without conflicts
- **Flexibility**: Users can choose between CLI mode and custom main functions
- **Testing**: Easier to test with predictable lifecycle behavior

## Next Steps

1. **Optimize event loop handling** - Better handle nested event loop scenarios
2. **Improve decorator robustness** - Ensure all decorator combinations work correctly
3. **Add more examples** - Show advanced patterns and edge cases
4. **Performance optimization** - Reduce overhead of lifecycle management for simple commands