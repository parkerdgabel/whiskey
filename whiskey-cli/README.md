# Whiskey CLI Extension

Natural CLI creation using Whiskey's IoC system.

## Installation

```bash
pip install whiskey-cli
```

## Quick Start

```python
import click
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
@click.argument("name")
@inject
def hello(name: str, greeting: GreetingService):
    """Say hello to someone."""
    message = greeting.greet(name)
    click.echo(message)

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
    click.echo("Status: OK")

# Custom command name
@app.command(name="db-migrate")
def migrate():
    """Run database migrations."""
    click.echo("Running migrations...")
```

### Dependency Injection

Commands can use `@inject` to automatically resolve dependencies:

```python
@app.command()
@inject
async def process(data_service: DataService, logger: Logger):
    """Process data with injected services."""
    await data_service.process()
    logger.info("Processing complete")
```

### Command Groups

Organize related commands into groups:

```python
# Create a group
db_group = app.group("database")

@db_group.command()
def migrate():
    """Run migrations."""
    pass

@db_group.command()
def backup():
    """Backup database."""
    pass

# Or use the group parameter
@app.command(group="admin")
def users():
    """Manage users."""
    pass
```

### Async Commands

Both sync and async commands are supported:

```python
@app.command()
async def fetch_data():
    """Async command example."""
    await asyncio.sleep(1)
    click.echo("Data fetched!")
```

### Click Integration

All Click decorators work seamlessly:

```python
@app.command()
@click.argument("name")
@click.option("--count", default=1, help="Number of greetings")
@click.option("--shout", is_flag=True, help="Shout the greeting")
@inject
def greet(name: str, count: int, shout: bool, service: GreetingService):
    """Greet someone multiple times."""
    for _ in range(count):
        message = service.greet(name)
        if shout:
            message = message.upper()
        click.echo(message)
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
@inject
async def create_user(name: str, user_service: UserService):
    """Create a new user."""
    user = user_service.create(name)
    await app.emit("user.created", {"id": user.id, "name": user.name})
    click.echo(f"Created user: {user.name}")

@app.on("user.created")
async def log_user_creation(data: dict):
    """Log user creation events."""
    print(f"User created: {data}")
```

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