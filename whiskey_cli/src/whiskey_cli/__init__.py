"""Whiskey CLI extension - Natural CLI creation with IoC."""

from typing import TYPE_CHECKING

from .extension import cli_extension

if TYPE_CHECKING:
    from whiskey import Whiskey


__all__ = [
    "cli_extension",
]
