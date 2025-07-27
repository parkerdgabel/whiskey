"""CLI extension for Whiskey applications."""

from __future__ import annotations

import asyncio
import functools
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

import click

if TYPE_CHECKING:
    from whiskey import Whiskey


@dataclass
class CommandMetadata:
    """Metadata for a CLI command."""

    func: Callable
    name: str
    description: str | None = None
    group: str | None = None
    arguments: list[dict[str, Any]] = field(default_factory=list)
    options: list[dict[str, Any]] = field(default_factory=list)


class LazyClickGroup(click.Group):
    """Click group that finalizes pending commands when accessed."""
    
    def __init__(self, manager: CLIManager, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._manager = manager
    
    def main(self, *args, **kwargs):
        """Override main to finalize commands before running."""
        # Finalize any pending commands
        if hasattr(self._manager, 'finalize_pending'):
            self._manager.finalize_pending()
        
        # Override default Click behavior to return 0 when showing help
        try:
            return super().main(*args, **kwargs)
        except SystemExit as e:
            # If it's exit code 2 and we have no args, it's showing help - that's OK
            if e.code == 2 and not (args and args[0]):
                raise SystemExit(0) from None
            raise
    
    def invoke(self, ctx):
        """Override invoke to finalize commands before running."""
        # Finalize any pending commands
        if hasattr(self._manager, 'finalize_pending'):
            self._manager.finalize_pending()
        
        return super().invoke(ctx)


class CLIManager:
    """Manages CLI commands and groups."""

    def __init__(self, app: Whiskey):
        self.app = app
        self.cli_group = LazyClickGroup(self)
        self.commands: dict[str, CommandMetadata] = {}
        self.groups: dict[str, click.Group] = {}
        self.pending_commands: dict[str, CommandMetadata] = {}
    
    def finalize_pending(self) -> None:
        """Register any pending commands."""
        for cmd_name, metadata in list(self.pending_commands.items()):
            self.add_command(metadata)
            del self.pending_commands[cmd_name]

    def add_command(self, metadata: CommandMetadata) -> None:
        """Add a command to the CLI."""
        # Build Click command from metadata
        func = metadata.func
        
        # Auto-detect function parameters as arguments if no explicit arguments defined
        import inspect
        if not metadata.arguments and not metadata.options:
            sig = inspect.signature(metadata.func)
            
            # Check if the function is decorated with @inject
            has_inject = hasattr(metadata.func, "__wrapped__") or hasattr(metadata.func, "_inject_wrapper")
            
            for param_name, param in sig.parameters.items():
                # Skip parameters with defaults (they become options)
                # Skip **kwargs and *args
                if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
                    continue
                
                # Skip parameters that have type annotations for injection
                # unless they're basic types
                if has_inject and param.annotation != param.empty:
                    # Check if it's a basic type that shouldn't be injected
                    basic_types = (str, int, float, bool, bytes, list, dict, tuple, set)
                    if param.annotation not in basic_types:
                        # This will be injected, skip it
                        continue
                
                if param.default == param.empty:
                    # No default = positional argument
                    metadata.arguments.append({"name": param_name})
        
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

        @functools.wraps(original_callback)
        def wrapped_callback(*args, **kwargs):
            # Check if the function is already wrapped by @inject
            # If so, we should call the unwrapped version through the container
            # If not, we can try container.call or fall back to direct call
            
            target_func = original_callback
            
            # If function has @inject wrapper, get the original function
            if hasattr(original_callback, '__wrapped__'):
                # This is likely an @inject wrapped function
                # We'll use the container to call the unwrapped version
                target_func = original_callback.__wrapped__
            
            try:
                # Check if function is async
                if asyncio.iscoroutinefunction(target_func):
                    # For async functions, we need to handle them in the event loop context
                    async def async_call():
                        return await self.app.container.call(target_func, *args, **kwargs)
                    
                    try:
                        # Try to get existing event loop
                        loop = asyncio.get_running_loop()
                        # We're already in an event loop, run it
                        return loop.run_until_complete(async_call())
                    except RuntimeError:
                        # No event loop running, create one
                        return asyncio.run(async_call())
                else:
                    # For sync functions, use call_sync
                    return self.app.container.call_sync(target_func, *args, **kwargs)
            except Exception as e:
                # If container call fails, fallback to calling original function directly
                # This handles cases where the function doesn't need DI
                result = original_callback(*args, **kwargs)
                
                # Handle async results from direct call
                if asyncio.iscoroutine(result):
                    try:
                        loop = asyncio.get_running_loop()
                        return loop.run_until_complete(asyncio.create_task(result))
                    except RuntimeError:
                        return asyncio.run(result)
                
                return result

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

    def create_group(self, name: str, description: str | None = None) -> Any:
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

    def command(name: str | None = None, description: str | None = None, group: str | None = None):
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
            manager.pending_commands[cmd_name] = metadata

            # Store the original function reference and metadata
            func._cli_metadata = metadata
            func._cli_original = func
            func._cli_pending_name = cmd_name

            return func

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
            if hasattr(func, "_cli_metadata"):
                # Add argument to the metadata
                func._cli_metadata.arguments.append({"name": name, **kwargs})
            elif hasattr(func, "_cli_pending_name"):
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
            if hasattr(func, "_cli_metadata"):
                metadata = func._cli_metadata
            elif hasattr(func, "_cli_pending_name"):
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

            return func

        return decorator

    def group(name: str, description: str | None = None):
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

    def run_cli(args: list[str] | None = None) -> None:
        """Run the CLI application with proper lifecycle management.

        Args:
            args: Optional arguments (defaults to sys.argv)
        """
        # Register any pending commands before running
        manager.finalize_pending()

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
            asyncio.get_running_loop()
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
                raise SystemExit(exit_code) from None

    # Register the CLI runner with the new standardized API
    app.register_runner("cli", run_cli)
    app.run_cli = run_cli

    # Register built-in commands immediately
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
                    # Handle both old and new descriptor types
                    if hasattr(service, 'service_type'):
                        print(f"  - {service.service_type}")
                    elif hasattr(service, 'type'):
                        print(f"  - {service.type}")
                    else:
                        print(f"  - {service}")
                if len(services) > 10:
                    print(f"  ... and {len(services) - 10} more")
        except Exception:
            pass
