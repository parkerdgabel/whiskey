"""CLI extension for Whiskey applications."""

from __future__ import annotations

import asyncio
import functools
import inspect
from typing import Any, Callable, Dict, Optional

import click

from whiskey import Application


class CLIManager:
    """Manages CLI commands and groups."""
    
    def __init__(self, app: Application):
        self.app = app
        self.cli_group = click.Group()
        self.commands: Dict[str, click.Command] = {}
        self.groups: Dict[str, click.Group] = {}
    
    def add_command(
        self, 
        func: Callable,
        name: Optional[str] = None,
        group: Optional[str] = None,
        **kwargs
    ) -> None:
        """Add a command to the CLI."""
        # Get command name
        cmd_name = name or func.__name__.replace("_", "-")
        
        # Store the original function before Click wraps it
        original_func = func
        
        # Create click command
        cmd = click.command(name=cmd_name, **kwargs)(func)
        
        # Use the original function for our wrapper, not Click's wrapped version
        original_callback = original_func
        
        # Check if the original function expects click context
        sig = inspect.signature(original_callback)
        expects_context = any(
            param.annotation == click.Context or param.name == "ctx"
            for param in sig.parameters.values()
        )
        
        # Determine if this is an async command
        is_async = asyncio.iscoroutinefunction(original_callback)
        
        if is_async or hasattr(original_callback, "__wrapped__"):
            # For async commands or commands with @inject, create async wrapper
            @functools.wraps(original_callback)
            @click.pass_context
            async def async_wrapped_callback(ctx: click.Context, *args, **kwargs):
                async with self.app.lifespan():
                    # Make app available for injection
                    self.app.container[Application] = self.app
                    
                    # Call the command
                    if hasattr(original_callback, "__wrapped__"):
                        # Command uses @inject - let it handle the call
                        return await original_callback(*args, **kwargs)
                    else:
                        # No injection
                        if expects_context:
                            return await original_callback(ctx, *args, **kwargs)
                        else:
                            return await original_callback(*args, **kwargs)
            
            # Convert async to sync for Click
            @functools.wraps(original_callback)
            @click.pass_context  
            def wrapped_callback(ctx: click.Context, *args, **kwargs):
                return asyncio.run(async_wrapped_callback(ctx, *args, **kwargs))
                
            cmd.callback = wrapped_callback
        else:
            # For sync commands without @inject, simpler wrapper
            @functools.wraps(original_callback)
            @click.pass_context
            def wrapped_callback(ctx: click.Context, *args, **kwargs):
                # Run lifespan synchronously
                async def setup():
                    async with self.app.lifespan():
                        self.app.container[Application] = self.app
                
                asyncio.run(setup())
                
                # Call sync command
                if expects_context:
                    return original_callback(ctx, *args, **kwargs)
                else:
                    return original_callback(*args, **kwargs)
                    
            cmd.callback = wrapped_callback
        
        # Add to appropriate group
        if group:
            if group not in self.groups:
                self.groups[group] = click.Group(group)
                self.cli_group.add_command(self.groups[group])
            self.groups[group].add_command(cmd)
        else:
            self.cli_group.add_command(cmd)
            
        self.commands[cmd_name] = cmd
    
    def create_group(self, name: str, **kwargs) -> click.Group:
        """Create a command group."""
        group = click.Group(name, **kwargs)
        self.groups[name] = group
        self.cli_group.add_command(group)
        return group


def cli_extension(app: Application) -> None:
    """CLI extension that adds command-line interface capabilities.
    
    Adds:
    - @app.command decorator for registering CLI commands
    - @app.group decorator for creating command groups
    - app.cli property to access the Click group
    - app.run_cli() method to run the CLI
    
    Example:
        app = Application()
        app.use(cli_extension)
        
        @app.command()
        @inject
        async def hello(name: str, greeting_service: GreetingService):
            message = await greeting_service.greet(name)
            click.echo(message)
            
        app.run_cli()
    """
    # Create CLI manager
    manager = CLIManager(app)
    
    # Store manager in app
    app.cli_manager = manager
    app.cli = manager.cli_group
    
    # Add command decorator
    def command(
        name: Optional[str] = None,
        group: Optional[str] = None,
        **kwargs
    ):
        """Decorator to register a CLI command.
        
        Args:
            name: Command name (defaults to function name)
            group: Group to add command to
            **kwargs: Additional arguments for click.command
            
        Example:
            @app.command()
            @inject
            async def process(data_service: DataService):
                await data_service.process()
                
            @app.command(name="db-migrate", group="database")
            async def migrate():
                click.echo("Running migrations...")
        """
        def decorator(func: Callable) -> Callable:
            manager.add_command(func, name, group, **kwargs)
            return func
        return decorator
    
    # Add group decorator
    def group(name: str, **kwargs):
        """Create a command group.
        
        Example:
            db_group = app.group("database")
            
            @db_group.command()
            async def migrate():
                pass
        """
        return manager.create_group(name, **kwargs)
    
    # Add decorators to app
    app.add_decorator("command", command)
    app.add_decorator("group", group)
    
    # Add run_cli method
    def run_cli(args: Optional[list] = None) -> None:
        """Run the CLI application.
        
        Args:
            args: Optional arguments (defaults to sys.argv)
        """
        manager.cli_group.main(args=args, standalone_mode=True)
    
    app.run_cli = run_cli
    
    # Register built-in commands if enabled
    @app.on_configure
    async def register_builtin_commands():
        # Add a default help command that shows app info
        @app.command(name="app-info")
        async def app_info():
            """Show application information."""
            click.echo(f"Application: {app.config.name}")
            click.echo(f"Debug mode: {app.config.debug}")
            
            # Show registered components
            components = list(app._component_metadata.keys())
            if components:
                click.echo(f"\nComponents ({len(components)}):")
                for comp in components:
                    metadata = app._component_metadata[comp]
                    click.echo(f"  - {comp.__name__}")
                    if metadata.provides:
                        click.echo(f"    Provides: {', '.join(metadata.provides)}")
                    if metadata.critical:
                        click.echo(f"    Critical: Yes")
            
            # Show event handlers
            if app._event_handlers:
                click.echo(f"\nEvent handlers:")
                for event, handlers in app._event_handlers.items():
                    click.echo(f"  - {event}: {len(handlers)} handler(s)")
    
    # Support running the CLI from app.run() if no main function
    original_run = app.run
    
    def enhanced_run(main: Optional[Callable] = None) -> None:
        """Enhanced run that can run CLI if no main provided."""
        if main is None and hasattr(app, '_main_func'):
            # Use registered main
            original_run()
        elif main is None and hasattr(app, 'cli_manager'):
            # Run as CLI app
            app.run_cli()
        else:
            # Normal run
            original_run(main)
    
    app.run = enhanced_run