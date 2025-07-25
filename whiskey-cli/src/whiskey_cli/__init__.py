"""Whiskey CLI extension - CLI framework integration."""

from typing import TYPE_CHECKING

from .builder import CLIApplicationBuilder, cli

if TYPE_CHECKING:
    from whiskey import Application


def cli_extension(app: "Application") -> None:
    """CLI extension that adds command-line interface capabilities to Whiskey.
    
    Usage:
        from whiskey import Application
        from whiskey_cli import cli_extension
        
        app = Application()
        app.extend(cli_extension)
    """
    # CLI services can be registered here if needed
    # For now, the builder pattern handles most CLI needs
    pass


# For backwards compatibility
extend = cli_extension


__all__ = [
    "cli_extension",
    "extend",
    "CLIApplicationBuilder",
    "cli",
]