"""Plugin loader for discovering and loading Whiskey plugins."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from loguru import logger

from whiskey.plugins.base import PluginMetadata
from whiskey.plugins.registry import PluginError, get_plugin_registry

if TYPE_CHECKING:
    from whiskey.core.application import Application
    from whiskey.core.container import Container

# Handle different Python versions for entry points
if sys.version_info >= (3, 10):
    from importlib.metadata import entry_points
else:
    from importlib_metadata import entry_points


PLUGIN_ENTRY_POINT_GROUP = "whiskey.plugins"


def discover_plugins() -> list[PluginMetadata]:
    """Discover all available Whiskey plugins via entry points.

    Returns:
        List of discovered plugin metadata
    """
    discovered = []

    # Get entry points for our plugin group
    if sys.version_info >= (3, 10):
        eps = entry_points(group=PLUGIN_ENTRY_POINT_GROUP)
    else:
        eps = entry_points().get(PLUGIN_ENTRY_POINT_GROUP, [])

    for ep in eps:
        try:
            # Create metadata from entry point
            metadata = PluginMetadata(
                name=ep.name,
                version="0.0.0",  # Will be updated when loaded
                description=f"Plugin loaded from entry point: {ep.value}",
                entry_point=ep.value,
                module_name=ep.module,
            )
            discovered.append(metadata)
            logger.debug(f"Discovered plugin '{ep.name}' from entry point: {ep.value}")
        except Exception as e:
            logger.warning(f"Failed to process entry point '{ep.name}': {e}")

    return discovered


def register_discovered_plugins() -> None:
    """Discover and register all available plugins.

    This discovers plugins via entry points and registers them
    with the global plugin registry.
    """
    registry = get_plugin_registry()

    for metadata in discover_plugins():
        try:
            registry.register_plugin(metadata)
        except PluginError as e:
            logger.warning(f"Failed to register plugin '{metadata.name}': {e}")


def load_plugins(
    container: Container,
    plugins: list[str] | None = None,
    exclude: list[str] | None = None,
) -> None:
    """Load plugins into the container.

    Args:
        container: Container to register services with
        plugins: List of plugin names to load (None = all)
        exclude: List of plugin names to exclude
    """
    registry = get_plugin_registry()

    # Discover plugins if not already done
    if not registry.list_plugins():
        register_discovered_plugins()

    # Filter plugins to load
    all_plugins = registry.list_plugins()
    to_load = []

    for metadata in all_plugins:
        # Skip if excluded
        if exclude and metadata.name in exclude:
            logger.debug(f"Excluding plugin: {metadata.name}")
            continue

        # Include if in plugins list or loading all
        if plugins is None or metadata.name in plugins:
            to_load.append(metadata.name)

    # Load plugins in dependency order
    if to_load:
        # Temporarily register only the plugins we want to load
        temp_registry = get_plugin_registry()
        temp_registry.clear()

        for name in to_load:
            metadata = registry.get_plugin(name)
            temp_registry.register_plugin(metadata)

        # Load all plugins
        temp_registry.load_all_plugins(container)

        # Restore original registry with loaded state
        for name in to_load:
            metadata = temp_registry.get_plugin(name)
            registry._plugins[name] = metadata


def initialize_plugins(app: Application) -> None:
    """Initialize all loaded plugins with the application.

    Args:
        app: Application instance
    """
    registry = get_plugin_registry()
    registry.initialize_all_plugins(app)


def register_plugin_manually(
    name: str,
    plugin_class: type,
    version: str = "0.0.0",
    description: str = "",
) -> None:
    """Manually register a plugin class.

    This is useful for testing or when not using entry points.

    Args:
        name: Plugin name
        plugin_class: Plugin class
        version: Plugin version
        description: Plugin description
    """
    metadata = PluginMetadata(
        name=name,
        version=version,
        description=description,
        plugin_class=plugin_class,
    )

    registry = get_plugin_registry()
    registry.register_plugin(metadata)
