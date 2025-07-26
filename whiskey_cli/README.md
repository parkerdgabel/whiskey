# Whiskey CLI Extension 💻

Build powerful command-line applications with Whiskey's dependency injection. This extension provides a clean, decorator-based API for creating CLIs without coupling to any specific CLI framework.

## Why Whiskey CLI?

Building maintainable CLI applications is challenging. Whiskey CLI provides:

- **Dependency Injection**: Inject services into commands automatically
- **Framework Agnostic**: Your code doesn't depend on Click, argparse, or others
- **Type-Safe Commands**: Full typing support with argument validation
- **Async Support**: Commands can be sync or async
- **Testable**: Easy to test commands in isolation
- **Extensible**: Integrates with all Whiskey features

## Installation

```bash
pip install whiskey[cli]  # Includes whiskey-cli
# or
pip install whiskey-cli
```

## Quick Start

```python
from whiskey import Application, inject
from whiskey_cli import cli_extension

# Create app with CLI extension
app = Application()
app.use(cli_extension)

# Define services
@app.component
class GreetingService:
    def __init__(self):
        self.greetings = {
            "en": "Hello",
            "es": "Hola",
            "fr": "Bonjour"
        }
    
    def greet(self, name: str, language: str = "en") -> str:
        greeting = self.greetings.get(language, "Hello")
        return f"{greeting}, {name}!"

# Create CLI commands with DI
@app.command()
@app.argument("name", help="Name to greet")
@app.option("--language", "-l", default="en", help="Language for greeting")
@app.option("--loud", is_flag=True, help="Shout the greeting")
@inject
def hello(
    name: str,
    language: str,
    loud: bool,
    service: Annotated[GreetingService, Inject()]
):
    """Greet someone in different languages."""
    message = service.greet(name, language)
    if loud:
        message = message.upper()
    print(message)

# Run the CLI
if __name__ == "__main__":
    app.run_cli()
```

## Core Features

### 1. Command Registration

Define commands using decorators with full DI support:

```python
@app.command()
@inject
def status(
    db: Annotated[Database, Inject()],
    cache: Annotated[Cache, Inject()]
):
    """Show application status."""
    db_status = "connected" if db.is_connected() else "disconnected"
    cache_status = "connected" if cache.is_connected() else "disconnected"
    
    print(f"Database: {db_status}")
    print(f"Cache: {cache_status}")

# Custom command names and aliases
@app.command(name="db:migrate", aliases=["migrate"])
@inject
async def migrate_database(
    db: Annotated[Database, Inject()],
    migrator: Annotated[Migrator, Inject()]
):
    """Run database migrations."""
    print("Running migrations...")
    await migrator.run_pending_migrations()
    print("✅ Migrations complete")
```

### 2. Arguments and Options

Rich argument and option support with type validation:

```python
@app.command()
@app.argument("source", help="Source file or directory")
@app.argument("destination", help="Destination path")
@app.option("--recursive", "-r", is_flag=True, help="Copy recursively")
@app.option("--force", "-f", is_flag=True, help="Overwrite existing files")
@app.option("--exclude", multiple=True, help="Patterns to exclude")
@app.option("--workers", "-w", type=int, default=4, help="Number of workers")
@inject
async def copy(
    source: str,
    destination: str,
    recursive: bool,
    force: bool,
    exclude: list[str],
    workers: int,
    file_service: Annotated[FileService, Inject()]
):
    """Copy files with advanced options."""
    options = CopyOptions(
        recursive=recursive,
        force=force,
        exclude_patterns=exclude,
        workers=workers
    )
    
    result = await file_service.copy(source, destination, options)
    print(f"Copied {result.file_count} files ({result.total_size} bytes)")
```

### 3. Command Groups

Organize related commands hierarchically:

```python
# Create command groups
db_group = app.group("db", help="Database management commands")
user_group = app.group("user", help="User management commands")

@app.command(group="db")
@inject
async def migrate(migrator: Annotated[Migrator, Inject()]):
    """Run database migrations."""
    await migrator.run()

@app.command(group="db")
@inject
async def seed(
    seeder: Annotated[DatabaseSeeder, Inject()],
    count: int = app.option(default=100, help="Number of records")
):
    """Seed the database with test data."""
    await seeder.seed_users(count)
    await seeder.seed_posts(count * 5)
    print(f"✅ Seeded {count} users and {count * 5} posts")

# Nested groups
admin_group = app.group("admin", parent="user", help="Admin commands")

@app.command(group="user/admin")
@inject
async def promote(
    username: str = app.argument(help="Username to promote"),
    user_service: Annotated[UserService, Inject()] = None
):
    """Promote a user to admin."""
    user = await user_service.promote_to_admin(username)
    print(f"✅ {user.username} is now an admin")
```

### 4. Interactive Commands

Build interactive CLI experiences:

```python
@app.command()
@inject
async def setup(
    config_service: Annotated[ConfigService, Inject()],
    prompt: Annotated[Prompter, Inject()]
):
    """Interactive setup wizard."""
    print("Welcome to MyApp Setup Wizard!\n")
    
    # Prompt for configuration
    config = {}
    
    config['app_name'] = await prompt.text(
        "Application name:",
        default="MyApp"
    )
    
    config['database_url'] = await prompt.text(
        "Database URL:",
        default="sqlite:///app.db",
        password=True  # Hide input
    )
    
    config['port'] = await prompt.integer(
        "Server port:",
        default=8000,
        min_value=1,
        max_value=65535
    )
    
    config['enable_ssl'] = await prompt.confirm(
        "Enable SSL?",
        default=False
    )
    
    if config['enable_ssl']:
        config['ssl_cert'] = await prompt.path(
            "SSL certificate path:",
            must_exist=True,
            file_okay=True,
            dir_okay=False
        )
    
    # Save configuration
    await config_service.save(config)
    print("\n✅ Configuration saved successfully!")
```

### 5. Progress and Output

Rich output with progress tracking:

```python
@app.command()
@inject
async def process_files(
    directory: str = app.argument(help="Directory to process"),
    file_processor: Annotated[FileProcessor, Inject()] = None,
    progress: Annotated[ProgressBar, Inject()] = None
):
    """Process all files in a directory."""
    files = await file_processor.list_files(directory)
    
    with progress.task(total=len(files), description="Processing files") as task:
        for file in files:
            result = await file_processor.process(file)
            
            if result.success:
                task.log(f"✅ {file.name}")
            else:
                task.log(f"❌ {file.name}: {result.error}", style="red")
            
            task.advance()
    
    print(f"\nProcessed {len(files)} files")
```

### 6. Async and Background Tasks

Handle long-running operations gracefully:

```python
@app.command()
@inject
async def backup(
    backup_service: Annotated[BackupService, Inject()],
    notification: Annotated[NotificationService, Inject()],
    background: bool = app.option(
        "--background", "-b",
        help="Run backup in background"
    )
):
    """Create a full system backup."""
    if background:
        # Queue background task
        task_id = await backup_service.queue_backup()
        print(f"Backup queued with ID: {task_id}")
        print("Use 'myapp backup-status {task_id}' to check progress")
    else:
        # Run interactively with progress
        print("Starting backup...")
        
        async for progress in backup_service.backup_with_progress():
            print(f"\r{progress.percent}% - {progress.current_file}", end="")
        
        print("\n✅ Backup complete!")
        await notification.send("Backup completed successfully")
```

### 7. Context and State

Share state between commands using scopes:

```python
# CLI session scope
@scoped("cli_session")
class CLIContext:
    def __init__(self):
        self.current_project = None
        self.verbose = False
        self.output_format = "text"

@app.command()
@inject
async def use_project(
    name: str = app.argument(help="Project name"),
    context: Annotated[CLIContext, Inject()],
    project_service: Annotated[ProjectService, Inject()]
):
    """Switch to a different project."""
    project = await project_service.get(name)
    if not project:
        print(f"❌ Project '{name}' not found")
        return
    
    context.current_project = project
    print(f"✅ Now using project: {project.name}")

@app.command()
@inject
async def deploy(
    context: Annotated[CLIContext, Inject()],
    deploy_service: Annotated[DeployService, Inject()],
    environment: str = app.option(
        "--env", "-e",
        default="staging",
        help="Target environment"
    )
):
    """Deploy the current project."""
    if not context.current_project:
        print("❌ No project selected. Use 'myapp use-project NAME' first")
        return
    
    print(f"Deploying {context.current_project.name} to {environment}...")
    result = await deploy_service.deploy(
        context.current_project,
        environment
    )
    
    if result.success:
        print(f"✅ Deployed successfully to {result.url}")
    else:
        print(f"❌ Deployment failed: {result.error}")
```

### 8. Plugin Commands

Extend your CLI with plugin commands:

```python
# In your plugin
def register_commands(app: Application):
    """Register plugin commands."""
    
    plugin_group = app.group("myplugin", help="My plugin commands")
    
    @app.command(group="myplugin")
    @inject
    async def hello(
        name: str = app.argument(),
        plugin_service: Annotated[MyPluginService, Inject()]
    ):
        """Say hello from the plugin."""
        message = plugin_service.generate_greeting(name)
        print(message)

# In your main app
app.load_plugin("myplugin")
```

## Advanced Patterns

### Command Composition

```python
# Base command functionality
class BaseCommand:
    @inject
    async def setup(self, logger: Annotated[Logger, Inject()]):
        self.logger = logger
        await self.logger.info(f"Running {self.__class__.__name__}")

# Composed command
@app.command()
class DataImportCommand(BaseCommand):
    @inject
    async def execute(
        self,
        file: str = app.argument(),
        importer: Annotated[DataImporter, Inject()] = None
    ):
        await self.setup()  # Initialize base functionality
        
        await self.logger.info(f"Importing from {file}")
        result = await importer.import_file(file)
        
        print(f"✅ Imported {result.record_count} records")
```

### Command Pipelines

```python
@app.command()
@inject
async def pipeline(
    steps: list[str] = app.argument(nargs=-1, help="Pipeline steps"),
    pipeline_service: Annotated[PipelineService, Inject()]
):
    """Execute a series of commands as a pipeline."""
    
    # Parse pipeline: "extract data.csv | transform | load db"
    pipeline = pipeline_service.parse(steps)
    
    # Execute pipeline with data flow
    result = None
    for step in pipeline.steps:
        print(f"Running: {step.name}")
        result = await step.execute(result)
    
    print(f"✅ Pipeline complete: {pipeline.summary()}")
```

### Testing CLI Commands

```python
import pytest
from whiskey.testing import CLITestRunner

@pytest.fixture
def runner(app):
    return CLITestRunner(app)

def test_hello_command(runner):
    result = runner.invoke(["hello", "World", "--loud"])
    
    assert result.exit_code == 0
    assert "HELLO, WORLD!" in result.output

@pytest.mark.asyncio
async def test_async_command(runner):
    result = await runner.invoke_async(["fetch-data", "--source", "api"])
    
    assert result.exit_code == 0
    assert "Data fetched" in result.output
```

## Best Practices

### 1. Use Explicit Injection

```python
# ✅ Good - explicit about dependencies
@app.command()
@inject
def process(
    file: str = app.argument(),
    processor: Annotated[FileProcessor, Inject()]
):
    pass

# ❌ Avoid - unclear what gets injected
@app.command()
def process(file: str, processor: FileProcessor):
    pass
```

### 2. Provide Clear Help Text

```python
# ✅ Good - helpful documentation
@app.command(help="Deploy application to the specified environment")
@app.argument("environment", help="Target environment (dev, staging, prod)")
@app.option("--version", "-v", help="Version to deploy (default: latest)")
@inject
def deploy(environment: str, version: str = "latest", ...):
    """
    Deploy the application to the specified environment.
    
    This command will:
    1. Build the application
    2. Run tests
    3. Deploy to the target environment
    4. Run smoke tests
    """
    pass
```

### 3. Handle Errors Gracefully

```python
@app.command()
@inject
async def risky_operation(
    service: Annotated[RiskyService, Inject()],
    force: bool = app.option("--force", help="Skip confirmation")
):
    """Perform a risky operation."""
    try:
        if not force:
            confirm = input("Are you sure? [y/N]: ")
            if confirm.lower() != 'y':
                print("Operation cancelled")
                return
        
        await service.perform_operation()
        print("✅ Operation completed successfully")
        
    except PermissionError:
        print("❌ Permission denied. Try running with sudo.")
        raise SystemExit(1)
    
    except ServiceError as e:
        print(f"❌ Operation failed: {e}")
        raise SystemExit(1)
```

## Examples

See the `examples/` directory for complete examples:
- `todo_cli.py` - Full-featured todo list CLI
- `deploy_cli.py` - Deployment automation CLI
- `data_cli.py` - Data processing CLI with pipelines
- `interactive_cli.py` - Interactive setup wizard

## Integration with Other Extensions

### With whiskey-config

```python
from whiskey_config import config_extension, Setting

app.use(config_extension)

@app.command()
@inject
def server(
    port: int = Setting("server.port", default=8000),
    workers: int = Setting("server.workers", default=4)
):
    """Start the server with configuration."""
    print(f"Starting server on port {port} with {workers} workers")
```

### With whiskey-asgi

```python
from whiskey_asgi import asgi_extension

app.use(asgi_extension)

@app.command()
@inject
async def serve(
    port: int = app.option(default=8000),
    reload: bool = app.option("--reload", help="Auto-reload on changes")
):
    """Start the web server."""
    import uvicorn
    uvicorn.run(app.asgi, port=port, reload=reload)
```

## Contributing

We welcome contributions! See the main [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](../LICENSE) for details.