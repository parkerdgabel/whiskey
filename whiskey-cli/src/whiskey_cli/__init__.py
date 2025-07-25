"""Whiskey CLI plugin - CLI framework integration."""

from .builder import CLIApplicationBuilder, cli
from .plugin import CLIPlugin

__all__ = [
    "CLIApplicationBuilder",
    "CLIPlugin",
    "cli",
]