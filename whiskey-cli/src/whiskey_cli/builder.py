"""CLI application builder."""

from __future__ import annotations

import asyncio
from typing import Any, Callable

import click
from whiskey import ApplicationConfig
from whiskey.core.bootstrap import ApplicationBuilder


class CLIApplicationBuilder(ApplicationBuilder[click.Group]):
    """Builder for CLI applications."""
    
    def __init__(self, config: ApplicationConfig | None = None):
        super().__init__(config)
        # Always include the CLI plugin
        self.plugin("whiskey-cli")
        self._cli_group = click.Group()
        self._commands: list[tuple[click.Command, bool]] = []  # (command, needs_app)
    
    def command(
        self,
        name: str | None = None,
        needs_app: bool = True,
        **kwargs: Any,
    ) -> Callable[[Callable], Callable]:
        """Decorator to add a CLI command."""
        def decorator(func: Callable) -> Callable:
            # Create click command
            cmd = click.command(name=name, **kwargs)(func)
            self._commands.append((cmd, needs_app))
            return func
        return decorator
    
    def group(self, name: str, **kwargs: Any) -> click.Group:
        """Create a command group."""
        group = click.Group(name, **kwargs)
        self._cli_group.add_command(group)
        return group
    
    async def build_async(self) -> click.Group:
        """Build the CLI application."""
        # Run setup
        await self._run_setup()
        
        # Process commands
        for cmd, needs_app in self._commands:
            if needs_app:
                # Wrap command to inject the app
                original_callback = cmd.callback
                
                @click.pass_context
                def wrapped_callback(ctx, *args, **kwargs):
                    # Store app in context
                    ctx.obj = self.app
                    # Run the original callback
                    result = original_callback(*args, **kwargs)
                    # Handle async commands
                    if asyncio.iscoroutine(result):
                        return asyncio.run(result)
                    return result
                
                cmd.callback = wrapped_callback
            
            self._cli_group.add_command(cmd)
        
        return self._cli_group
    
    def run(self) -> None:
        """Build and run the CLI application."""
        cli = self.build()
        cli()


def cli(config: ApplicationConfig | None = None) -> CLIApplicationBuilder:
    """Create a builder for a CLI application."""
    return CLIApplicationBuilder(config)