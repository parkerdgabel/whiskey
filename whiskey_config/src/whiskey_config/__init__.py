"""Whiskey configuration management extension."""

from .extension import config_extension, Setting
from .manager import ConfigurationManager
from .schema import ConfigurationError

__all__ = [
    "config_extension",
    "ConfigurationManager", 
    "ConfigurationError",
    "Setting",
]

__version__ = "0.1.0"