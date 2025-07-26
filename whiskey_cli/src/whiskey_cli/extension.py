"""CLI extension for Whiskey applications."""

from __future__ import annotations

import asyncio
import functools
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import click


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

    def __init__(self, app: Application):
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

        if is_async or hasattr(original_callback, "__wrapped__"):
            # Async wrapper
            @functools.wraps(original_callback)
            async def async_callback(*args, **kwargs):
                async with self.app.lifespan():
                    self.app.container[Application] = self.app
                    return await original_callback(*args, **kwargs)

            @functools.wraps(original_callback)
            def wrapped_callback(*args, **kwargs):
                return asyncio.run(async_callback(*args, **kwargs))

            cmd.callback = wrapped_callback
        else:
            # Sync wrapper
            @functools.wraps(original_callback)
            def wrapped_callback(*args, **kwargs):
                # Setup app context
                async def setup():
                    async with self.app.lifespan():
                        self.app.container[Application] = self.app

                asyncio.run(setup())

                return original_callback(*args, **kwargs)

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


def cli_extension(app: Application) -> None:
    """CLI extension that adds command-line interface capabilities.

    This extension provides a framework-agnostic API for building CLIs:
    - @app.command() decorator with argument() and option() methods
    - @app.argument() and @app.option() for adding parameters
    - app.group() for creating command groups
    - app.run_cli() to run the CLI

    Example:
        app = Application()
        app.use(cli_extension)

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

    # Current command being built
    _current_command: Optional[CommandMetadata] = None

    # Track pending commands that are being built
    _pending_commands: Dict[str, CommandMetadata] = {}

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

            # Create metadata
            metadata = CommandMetadata(
                func=func, name=cmd_name, description=cmd_description, group=group
            )

            # Store in pending for argument/option decorators
            _pending_commands[cmd_name] = metadata

            # Register a wrapper that will finalize the command
            def wrapper(*args, **kwargs):
                # First time called, finalize and register
                if cmd_name in _pending_commands:
                    manager.add_command(_pending_commands[cmd_name])
                    del _pending_commands[cmd_name]
                return func(*args, **kwargs)

            # Copy attributes
            functools.update_wrapper(wrapper, func)

            # Immediately register if no arguments/options will be added
            # This happens after a short delay to allow decorators to be applied
            async def delayed_register():
                await asyncio.sleep(0.001)
                if cmd_name in _pending_commands:
                    manager.add_command(_pending_commands[cmd_name])
                    del _pending_commands[cmd_name]

            try:
                asyncio.create_task(delayed_register())
            except RuntimeError:
                # No event loop, register immediately
                if cmd_name in _pending_commands:
                    manager.add_command(_pending_commands[cmd_name])
                    del _pending_commands[cmd_name]

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
            # Find the command metadata in pending commands
            cmd_name = getattr(func, "__name__", str(func)).replace("_", "-")

            # Check if it's a wrapped function
            if hasattr(func, "__wrapped__"):
                cmd_name = func.__wrapped__.__name__.replace("_", "-")

            if cmd_name in _pending_commands:
                metadata = _pending_commands[cmd_name]
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
            # Find the command metadata in pending commands
            cmd_name = getattr(func, "__name__", str(func)).replace("_", "-")

            # Check if it's a wrapped function
            if hasattr(func, "__wrapped__"):
                cmd_name = func.__wrapped__.__name__.replace("_", "-")

            if cmd_name in _pending_commands:
                metadata = _pending_commands[cmd_name]

                # Handle shorthand like "-v/--verbose"
                if "/" in name:
                    parts = name.split("/")
                    opt_args = []
                    for part in parts:
                        opt_args.append(part)
                    metadata.options.append({"name": opt_args, **kwargs})
                else:
                    metadata.options.append({"name": name, **kwargs})

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
        """Run the CLI application.

        Args:
            args: Optional arguments (defaults to sys.argv)
        """
        manager.cli_group.main(args=args, standalone_mode=True)

    app.run_cli = run_cli

    # Register built-in commands
    @app.on_configure
    async def register_builtin_commands():
        @app.command(name="app-info", description="Show application information")
        def app_info():
            """Show application information."""
            print(f"Application: {app.config.name}")
            print(f"Debug mode: {app.config.debug}")

            # Show components
            components = list(app._component_metadata.keys())
            if components:
                print(f"\nComponents ({len(components)}):")
                for comp in components:
                    print(f"  - {comp.__name__}")

    # Enhanced run method
    original_run = app.run

    def enhanced_run(main: Optional[Callable] = None) -> None:
        """Enhanced run that can run CLI if no main provided."""
        if main is None and hasattr(app, "_main_func"):
            original_run()
        elif main is None and hasattr(app, "cli_manager"):
            app.run_cli()
        else:
            original_run(main)

    app.run = enhanced_run
