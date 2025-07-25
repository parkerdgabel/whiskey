# Whiskey CLI Extension

Framework-agnostic CLI creation using Whiskey's IoC system.

## Installation

```bash
pip install whiskey-cli
```

## Quick Start

```python
from whiskey import Application, inject
from whiskey_cli import cli_extension

# Create app with CLI extension
app = Application()
app.use(cli_extension)

# Define a service
class GreetingService:
    def greet(self, name: str) -> str:
        return f"Hello, {name}!"

# Register the service
app.container[GreetingService] = GreetingService()

# Create a CLI command with dependency injection
@app.command()
@app.argument("name")
@inject
def hello(name: str, greeting: GreetingService):
    """Say hello to someone."""
    message = greeting.greet(name)
    print(message)

# Run the CLI
if __name__ == "__main__":
    app.run_cli()
```

## Features

### Command Registration

Use the `@app.command()` decorator to register CLI commands:

```python
@app.command()
def status():
    """Show application status."""
    print("Status: OK")

# Custom command name
@app.command(name="db-migrate")
def migrate():
    """Run database migrations."""
    print("Running migrations...")
```

### Arguments and Options

Use Whiskey's own decorators for CLI parameters:

```python
@app.command()
@app.argument("filename")
@app.argument("count", type=int)
@app.option("--verbose", "-v", is_flag=True, help="Verbose output")
@app.option("--output", "-o", default="output.txt", help="Output file")
def process(filename: str, count: int, verbose: bool, output: str):
    """Process a file."""
    if verbose:
        print(f"Processing {filename} {count} times")
    print(f"Output will be written to {output}")
```

### Dependency Injection

Commands can use `@inject` to automatically resolve dependencies:

```python
@app.command()
@app.argument("user_id", type=int)
@inject
async def get_user(user_id: int, db: Database, cache: Cache):
    """Get user details."""
    # Check cache first
    cached = await cache.get(f"user:{user_id}")
    if cached:
        return cached
        
    # Fetch from database
    user = await db.users.find(user_id)
    await cache.set(f"user:{user_id}", user)
    return user
```

### Command Groups

Organize related commands into groups:

```python
# Using the group parameter
@app.command(group="database")
def migrate():
    """Run migrations."""
    pass

@app.command(group="database")
def backup():
    """Backup database."""
    pass

# Or create a group explicitly
db_group = app.group("database", "Database management commands")
```

### Async Commands

Both sync and async commands are supported:

```python
@app.command()
async def fetch_data():
    """Async command example."""
    await asyncio.sleep(1)
    print("Data fetched!")
```

### Application Lifespan

Commands run within the application's lifespan, ensuring proper initialization:

```python
@app.on_startup
async def initialize():
    """This runs before CLI commands execute."""
    await db.connect()

@app.on_shutdown
async def cleanup():
    """This runs after CLI commands complete."""
    await db.disconnect()
```

### Event Emission

Commands can emit events that handlers can respond to:

```python
@app.command()
@app.argument("name")
@inject
async def create_user(name: str, user_service: UserService):
    """Create a new user."""
    user = user_service.create(name)
    await app.emit("user.created", {"id": user.id, "name": user.name})
    print(f"Created user: {user.name}")

@app.on("user.created")
async def log_user_creation(data: dict):
    """Log user creation events."""
    print(f"User created: {data}")
```

## Framework-Agnostic Design

The CLI extension provides its own API for defining commands, arguments, and options. This keeps your code independent of any specific CLI framework:

- `@app.command()` - Register a command
- `@app.argument()` - Add positional arguments
- `@app.option()` - Add optional flags and parameters
- `app.group()` - Create command groups
- `app.run_cli()` - Run the CLI application

Under the hood, the extension currently uses Click, but your code doesn't need to know about it. The extension could be reimplemented with any CLI framework without changing your application code.

## Complete Example

See the [examples directory](examples/) for complete examples including:
- `simple_cli.py` - Basic CLI with dependency injection
- `cli_example.py` - Full-featured todo list CLI application

## Integration with Application

The CLI extension integrates seamlessly with Whiskey's Application class:

```python
# If no main function is provided, app.run() runs the CLI
app.run()  # Runs CLI

# Or explicitly run CLI
app.run_cli()

# Or run with a main function
@app.main
async def main():
    # This runs instead of CLI
    pass

app.run()
```