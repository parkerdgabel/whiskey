"""Whiskey configuration management extension."""

from .extension import config_extension
from .manager import ConfigurationManager
from .providers import Setting
from .schema import ConfigurationError

__all__ = [
    "ConfigurationError",
    "ConfigurationManager",
    "Setting",
    "config_extension",
]

__version__ = "0.1.0"