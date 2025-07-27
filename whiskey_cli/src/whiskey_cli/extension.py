"""CLI extension for Whiskey applications."""

from __future__ import annotations

import asyncio
import functools
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

import click

if TYPE_CHECKING:
    from whiskey import Whiskey


@dataclass
class CommandMetadata:
    """Metadata for a CLI command."""


    func: Callable
    name: str
    description: Optional[str] = None
    group: Optional[str] = None
    arguments: List[Dict[str, Any]] = field(default_factory=list)
    options: List[Dict[str, Any]] = field(default_factory=list)


class CLIManager:
    """Manages CLI commands and groups."""

    def __init__(self, app: Whiskey):
        self.app = app
        self.cli_group = click.Group()
        self.commands: Dict[str, CommandMetadata] = {}
        self.groups: Dict[str, click.Group] = {}


    def add_command(self, metadata: CommandMetadata) -> None:
        """Add a command to the CLI."""
        # Build Click command from metadata
        func = metadata.func
        # Add Click decorators for arguments and options
        for arg in reversed(metadata.arguments):
            func = click.argument(arg["name"], **{k: v for k, v in arg.items() if k != "name"})(
                func
            )

        for opt in reversed(metadata.options):
            opt_args = opt["name"]
            opt_kwargs = {k: v for k, v in opt.items() if k != "name"}
            # Handle list of option names (e.g., ["-v", "--verbose"])
            if isinstance(opt_args, list):
                func = click.option(*opt_args, **opt_kwargs)(func)
            else:
                func = click.option(opt_args, **opt_kwargs)(func)

        # Create Click command
        cmd = click.command(name=metadata.name, help=metadata.description)(func)

        # Wrap to handle async and DI
        original_callback = metadata.func
        is_async = asyncio.iscoroutinefunction(original_callback)

        @functools.wraps(original_callback)
        def wrapped_callback(*args, **kwargs):
            # The lifecycle should already be active from run_cli
            # Execute the command with DI support
            try:
                loop = asyncio.get_running_loop()
                # We're in an async context, create coroutine for execution
                async def execute():
                    return await self.app.call_async(original_callback, *args, **kwargs)
                
                # Run the coroutine in the current event loop
                future = asyncio.ensure_future(execute())
                return loop.run_until_complete(future)
            except RuntimeError:
                # No event loop - shouldn't happen with proper CLI usage
                # Fall back to sync execution
                return self.app.call_sync(original_callback, *args, **kwargs)

        cmd.callback = wrapped_callback

        # Add to appropriate group
        if metadata.group:
            if metadata.group not in self.groups:
                self.groups[metadata.group] = click.Group(metadata.group)
                self.cli_group.add_command(self.groups[metadata.group])
            self.groups[metadata.group].add_command(cmd)
        else:
            self.cli_group.add_command(cmd)

        self.commands[metadata.name] = metadata

    def create_group(self, name: str, description: Optional[str] = None) -> Any:
        """Create a command group."""
        group = click.Group(name, help=description)
        self.groups[name] = group
        self.cli_group.add_command(group)
        return group


def cli_extension(app: Whiskey) -> None:
    """CLI extension that adds command-line interface capabilities.

    This extension provides a framework-agnostic API for building CLIs:
    - @app.command() decorator with argument() and option() methods
    - @app.argument() and @app.option() for adding parameters
    - app.group() for creating command groups
    - app.run_cli() to run the CLI
<<<<<<< HEAD

    Example:
        app = Application()
        app.use(cli_extension)

=======
    
    Example:
        app = Application()
        app.use(cli_extension)
        
>>>>>>> origin/main
        @app.command()
        @app.argument("name")
        @app.option("--greeting", default="Hello")
        @inject
        async def greet(name: str, greeting: str, service: GreetingService):
            message = service.create_message(greeting, name)
            print(message)


        app.run_cli()
    """
    # Create CLI manager
    manager = CLIManager(app)

    # Store manager in app
    app.cli_manager = manager
    app.cli = manager.cli_group

    # Track pending commands that are being built
    manager.pending_commands: Dict[str, CommandMetadata] = {}

    def command(
        name: Optional[str] = None, description: Optional[str] = None, group: Optional[str] = None
    ):
        """Decorator to register a CLI command.

        Args:
            name: Command name (defaults to function name)
            description: Command description (defaults to docstring)
            group: Group to add command to


        Example:
            @app.command()
            def hello():
                print("Hello!")


            @app.command(name="db-migrate", group="database")
            async def migrate():
                print("Running migrations...")
        """


        def decorator(func: Callable) -> Callable:
            # Get command info
            cmd_name = name or func.__name__.replace("_", "-")
            cmd_description = description or func.__doc__
<<<<<<< HEAD

            # Create metadata
            metadata = CommandMetadata(
                func=func, name=cmd_name, description=cmd_description, group=group
            )

            # Store in pending for argument/option decorators
            manager.pending_commands[cmd_name] = metadata

            # Register a wrapper that will finalize the command
            def wrapper(*args, **kwargs):
                # First time called, finalize and register
                if cmd_name in manager.pending_commands:
                    manager.add_command(manager.pending_commands[cmd_name])
                    del manager.pending_commands[cmd_name]
                return func(*args, **kwargs)

            # Copy attributes
            functools.update_wrapper(wrapper, func)

            # Store the original function reference and metadata
            wrapper._cli_metadata = metadata
            wrapper._cli_original = func
            wrapper._cli_pending_name = cmd_name
            
            # The command will be registered when all decorators are applied
            # This is handled by checking pending commands before CLI execution
            
            return wrapper

        return decorator

    def argument(name: str, **kwargs):
        """Add a positional argument to a command.

        Args:
            name: Argument name
            **kwargs: Additional argument configuration

        Example:
            @app.command()
            @app.argument("filename")
            @app.argument("count", type=int)
            def process(filename: str, count: int):
                pass
        """

        def decorator(func: Callable) -> Callable:
            # Check if this function has CLI metadata attached
            if hasattr(func, '_cli_metadata'):
                # Add argument to the metadata
                func._cli_metadata.arguments.append({"name": name, **kwargs})
            elif hasattr(func, '_cli_pending_name'):
                # Function was wrapped by @command, get metadata from pending
                cmd_name = func._cli_pending_name
                if cmd_name in manager.pending_commands:
                    metadata = manager.pending_commands[cmd_name]
                    metadata.arguments.append({"name": name, **kwargs})
            else:
                # Try to find in pending commands by name
                cmd_name = getattr(func, "__name__", str(func)).replace("_", "-")
                
                # Check if it's a wrapped function
                if hasattr(func, "__wrapped__"):
                    cmd_name = func.__wrapped__.__name__.replace("_", "-")
                
                if cmd_name in manager.pending_commands:
                    metadata = manager.pending_commands[cmd_name]
                    metadata.arguments.append({"name": name, **kwargs})

            return func

        return decorator

    def option(name: str, **kwargs):
        """Add an option to a command.

        Args:
            name: Option name (e.g., "--verbose" or "-v/--verbose")
            **kwargs: Additional option configuration

        Example:
            @app.command()
            @app.option("--count", default=1, help="Number of times")
            @app.option("-v/--verbose", is_flag=True)
            def hello(count: int, verbose: bool):
                pass
        """
        def decorator(func: Callable) -> Callable:
            metadata = None
            
            # Check if this function has CLI metadata attached
            if hasattr(func, '_cli_metadata'):
                metadata = func._cli_metadata
            elif hasattr(func, '_cli_pending_name'):
                # Function was wrapped by @command, get metadata from pending
                cmd_name = func._cli_pending_name
                if cmd_name in manager.pending_commands:
                    metadata = manager.pending_commands[cmd_name]
            else:
                # Try to find in pending commands by name
                cmd_name = getattr(func, "__name__", str(func)).replace("_", "-")
                
                # Check if it's a wrapped function
                if hasattr(func, "__wrapped__"):
                    cmd_name = func.__wrapped__.__name__.replace("_", "-")
                
                if cmd_name in manager.pending_commands:
                    metadata = manager.pending_commands[cmd_name]
            
            if metadata:
                # Add option to metadata
                # Handle shorthand like "-v/--verbose"
                if "/" in name:
                    parts = name.split("/")
                    opt_args = []
                    for part in parts:
                        opt_args.append(part)
                    metadata.options.append({"name": opt_args, **kwargs})
                else:
                    metadata.options.append({"name": name, **kwargs})
<<<<<<< HEAD

            return func

        return decorator

    def group(name: str, description: Optional[str] = None):
        """Create a command group.

        Args:
            name: Group name
            description: Group description

        Returns:
            A group object that can have commands added to it

        Example:
            db = app.group("database", "Database commands")

            @app.command(group="database")
            def migrate():
                pass
        """
        return manager.create_group(name, description)


    # Add methods to app
    app.add_decorator("command", command)
    app.add_decorator("argument", argument)
    app.add_decorator("option", option)
    app.group = group

    def run_cli(args: Optional[List[str]] = None) -> None:
        """Run the CLI application with proper lifecycle management.

        Args:
            args: Optional arguments (defaults to sys.argv)
        """
        # Register any pending commands before running
        for cmd_name, metadata in list(manager.pending_commands.items()):
            manager.add_command(metadata)
            del manager.pending_commands[cmd_name]
        
        # Run the CLI within the app's lifecycle context
        async def cli_main():
            async with app.lifespan:
                # Make app available in container
                app.container[type(app)] = app
                
                # Execute the CLI in a sync context since Click expects sync
                # But we need the lifecycle to be active
                def run_click():
                    manager.cli_group.main(args=args, standalone_mode=False)
                    return 0
                
                try:
                    run_click()
                    return 0
                except SystemExit as e:
                    return e.code if e.code is not None else 0
                except Exception as e:
                    print(f"Error: {e}")
                    return 1
        
        # Check if we're already in an event loop
        try:
            loop = asyncio.get_running_loop()
            # Already in a loop - this can happen when called from app.run()
            # Just run Click directly since lifecycle is already active
            try:
                manager.cli_group.main(args=args, standalone_mode=False)
            except SystemExit as e:
                if e.code != 0:
                    raise
        except RuntimeError:
            # No event loop - use asyncio.run for clean lifecycle
            exit_code = asyncio.run(cli_main())
            if exit_code != 0:
                raise SystemExit(exit_code)

    # Register the CLI runner with the new standardized API
    app.register_runner("cli", run_cli)
    app.run_cli = run_cli

    # Register built-in commands
    @app.on("configure")
    async def register_builtin_commands():
        @app.command(name="app-info", description="Show application information")
        def app_info():
            """Show application information."""
            print(f"Application: {getattr(app, 'name', 'Whiskey App')}")
            
            # Show registered services
            try:
                services = list(app.container.registry.list_all())
                if services:
                    print(f"\nRegistered services ({len(services)}):")
                    for service in services[:10]:  # Show first 10
                        print(f"  - {service.service_type}")
                    if len(services) > 10:
                        print(f"  ... and {len(services) - 10} more")
            except Exception:
                pass
    
