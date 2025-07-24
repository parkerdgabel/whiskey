"""Base plugin interface and types for Whiskey plugin system."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from whiskey.core.application import Application
    from whiskey.core.container import Container


@runtime_checkable
class WhiskeyPlugin(Protocol):
    """Protocol defining the interface for Whiskey plugins."""

    @property
    def name(self) -> str:
        """Plugin name."""
        ...

    @property
    def version(self) -> str:
        """Plugin version."""
        ...

    @property
    def description(self) -> str:
        """Plugin description."""
        ...

    @property
    def dependencies(self) -> list[str]:
        """List of plugin names this plugin depends on."""
        ...

    def register(self, container: Container) -> None:
        """Register plugin services with the container.

        This is called during plugin discovery to register all services,
        factories, and other components the plugin provides.

        Args:
            container: The application container to register services with
        """
        ...

    def initialize(self, app: Application) -> None:
        """Initialize the plugin with the application.

        This is called after all plugins are registered, allowing plugins
        to set up event handlers, middleware, and other application-level
        components.

        Args:
            app: The application instance
        """
        ...


class BasePlugin(ABC):
    """Base class for plugin implementations."""

    def __init__(self, name: str, version: str, description: str = ""):
        self._name = name
        self._version = version
        self._description = description
        self._dependencies: list[str] = []

    @property
    def name(self) -> str:
        """Plugin name."""
        return self._name

    @property
    def version(self) -> str:
        """Plugin version."""
        return self._version

    @property
    def description(self) -> str:
        """Plugin description."""
        return self._description

    @property
    def dependencies(self) -> list[str]:
        """List of plugin names this plugin depends on."""
        return self._dependencies

    @abstractmethod
    def register(self, container: Container) -> None:
        """Register plugin services with the container."""
        pass

    def initialize(self, app: Application) -> None:
        """Initialize the plugin with the application.

        Default implementation does nothing. Override in subclasses
        to add event handlers, middleware, etc.
        """
        pass


class PluginMetadata:
    """Metadata about a loaded plugin."""

    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        entry_point: str | None = None,
        module_name: str | None = None,
        plugin_class: type[WhiskeyPlugin] | None = None,
    ):
        self.name = name
        self.version = version
        self.description = description
        self.entry_point = entry_point
        self.module_name = module_name
        self.plugin_class = plugin_class
        self.instance: WhiskeyPlugin | None = None
        self.loaded = False
        self.initialized = False

    def __repr__(self) -> str:
        return (
            f"PluginMetadata(name={self.name!r}, version={self.version!r}, "
            f"loaded={self.loaded}, initialized={self.initialized})"
        )
