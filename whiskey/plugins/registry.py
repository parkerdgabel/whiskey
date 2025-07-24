"""Plugin registry for managing plugin discovery and lifecycle."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

from loguru import logger

from whiskey.core.exceptions import WhiskeyError
from whiskey.plugins.base import PluginMetadata, WhiskeyPlugin

if TYPE_CHECKING:
    from whiskey.core.application import Application
    from whiskey.core.container import Container


class PluginError(WhiskeyError):
    """Base exception for plugin-related errors."""

    pass


class PluginNotFoundError(PluginError):
    """Raised when a plugin cannot be found."""

    pass


class PluginLoadError(PluginError):
    """Raised when a plugin fails to load."""

    pass


class PluginDependencyError(PluginError):
    """Raised when plugin dependencies cannot be resolved."""

    pass


class PluginRegistry:
    """Registry for managing Whiskey plugins."""

    def __init__(self):
        self._plugins: dict[str, PluginMetadata] = {}
        self._load_order: list[str] = []

    def register_plugin(self, metadata: PluginMetadata) -> None:
        """Register a plugin's metadata.

        Args:
            metadata: Plugin metadata

        Raises:
            PluginError: If plugin is already registered
        """
        if metadata.name in self._plugins:
            raise PluginError(f"Plugin '{metadata.name}' is already registered")

        self._plugins[metadata.name] = metadata
        logger.debug(f"Registered plugin: {metadata.name} v{metadata.version}")

    def get_plugin(self, name: str) -> PluginMetadata:
        """Get plugin metadata by name.

        Args:
            name: Plugin name

        Returns:
            Plugin metadata

        Raises:
            PluginNotFoundError: If plugin is not found
        """
        if name not in self._plugins:
            raise PluginNotFoundError(f"Plugin '{name}' not found")
        return self._plugins[name]

    def list_plugins(self) -> list[PluginMetadata]:
        """List all registered plugins.

        Returns:
            List of plugin metadata
        """
        return list(self._plugins.values())

    def load_plugin(self, name: str) -> WhiskeyPlugin:
        """Load a plugin by name.

        Args:
            name: Plugin name

        Returns:
            Loaded plugin instance

        Raises:
            PluginNotFoundError: If plugin is not found
            PluginLoadError: If plugin fails to load
        """
        metadata = self.get_plugin(name)

        if metadata.loaded and metadata.instance:
            return metadata.instance

        try:
            # Import the module
            if metadata.module_name:
                module = importlib.import_module(metadata.module_name)
            else:
                raise PluginLoadError(f"No module name specified for plugin '{name}'")

            # Get the plugin class
            if metadata.plugin_class:
                plugin_class = metadata.plugin_class
            elif metadata.entry_point:
                # Entry point format: "module:PluginClass"
                if ":" in metadata.entry_point:
                    _, class_name = metadata.entry_point.split(":", 1)
                    plugin_class = getattr(module, class_name)
                else:
                    raise PluginLoadError(
                        f"Invalid entry point format for plugin '{name}': {metadata.entry_point}"
                    )
            else:
                raise PluginLoadError(f"No plugin class specified for plugin '{name}'")

            # Instantiate the plugin
            plugin = plugin_class()

            # Verify it implements the protocol
            if not isinstance(plugin, WhiskeyPlugin):
                raise PluginLoadError(f"Plugin '{name}' does not implement WhiskeyPlugin protocol")

            metadata.instance = plugin
            metadata.loaded = True

            logger.info(f"Loaded plugin: {name} v{metadata.version}")
            return plugin

        except ImportError as e:
            raise PluginLoadError(f"Failed to import plugin '{name}': {e}") from e
        except Exception as e:
            raise PluginLoadError(f"Failed to load plugin '{name}': {e}") from e

    def resolve_dependencies(self) -> list[str]:
        """Resolve plugin dependencies and return load order.

        Returns:
            List of plugin names in dependency order

        Raises:
            PluginDependencyError: If dependencies cannot be resolved
        """
        # Build dependency graph
        graph: dict[str, set[str]] = {}
        for name, metadata in self._plugins.items():
            if not metadata.loaded:
                plugin = self.load_plugin(name)
                deps = plugin.dependencies
            else:
                deps = metadata.instance.dependencies if metadata.instance else []

            graph[name] = set(deps)

        # Topological sort
        visited = set()
        stack = []

        def visit(node: str, path: set[str]) -> None:
            if node in path:
                cycle = " -> ".join(path) + f" -> {node}"
                raise PluginDependencyError(f"Circular dependency detected: {cycle}")

            if node in visited:
                return

            path.add(node)

            if node not in graph:
                raise PluginDependencyError(f"Dependency '{node}' not found")

            for dep in graph[node]:
                visit(dep, path.copy())

            visited.add(node)
            stack.append(node)

        for node in graph:
            if node not in visited:
                visit(node, set())

        self._load_order = stack
        return stack

    def load_all_plugins(self, container: Container) -> None:
        """Load all registered plugins in dependency order.

        Args:
            container: Container to register services with

        Raises:
            PluginLoadError: If any plugin fails to load
        """
        load_order = self.resolve_dependencies()

        for name in load_order:
            metadata = self._plugins[name]
            if not metadata.loaded:
                self.load_plugin(name)

            if metadata.instance:
                metadata.instance.register(container)
                logger.debug(f"Registered services from plugin: {name}")

    def initialize_all_plugins(self, app: Application) -> None:
        """Initialize all loaded plugins with the application.

        Args:
            app: Application instance

        Raises:
            PluginError: If any plugin fails to initialize
        """
        for name in self._load_order:
            metadata = self._plugins[name]
            if metadata.loaded and metadata.instance and not metadata.initialized:
                try:
                    metadata.instance.initialize(app)
                    metadata.initialized = True
                    logger.debug(f"Initialized plugin: {name}")
                except Exception as e:
                    raise PluginError(f"Failed to initialize plugin '{name}': {e}") from e

    def clear(self) -> None:
        """Clear all registered plugins."""
        self._plugins.clear()
        self._load_order.clear()


# Global plugin registry
_registry = PluginRegistry()


def get_plugin_registry() -> PluginRegistry:
    """Get the global plugin registry.

    Returns:
        The global plugin registry
    """
    return _registry
