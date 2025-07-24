"""Whiskey plugin system."""

from .base import BasePlugin, PluginMetadata, WhiskeyPlugin
from .loader import (
    discover_plugins,
    initialize_plugins,
    load_plugins,
    register_discovered_plugins,
    register_plugin_manually,
)
from .registry import (
    PluginDependencyError,
    PluginError,
    PluginLoadError,
    PluginNotFoundError,
    PluginRegistry,
    get_plugin_registry,
)

__all__ = [
    "BasePlugin",
    "PluginDependencyError",
    "PluginError",
    "PluginLoadError",
    "PluginMetadata",
    "PluginNotFoundError",
    # Registry
    "PluginRegistry",
    # Base
    "WhiskeyPlugin",
    # Loader
    "discover_plugins",
    "get_plugin_registry",
    "initialize_plugins",
    "load_plugins",
    "register_discovered_plugins",
    "register_plugin_manually",
]
