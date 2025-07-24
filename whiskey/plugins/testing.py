"""Testing utilities for Whiskey plugins."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, ClassVar

import pytest

from whiskey import Application, ApplicationConfig, Container
from whiskey.plugins import register_plugin_manually

if TYPE_CHECKING:
    from whiskey.plugins.base import WhiskeyPlugin


class PluginTestCase:
    """Base test case for plugin testing."""

    plugin_class: ClassVar[type[WhiskeyPlugin] | None] = None
    plugin_name: ClassVar[str | None] = None
    plugin_dependencies: ClassVar[list[str]] = []

    @pytest.fixture
    async def container(self) -> Container:
        """Create a test container."""
        return Container()

    @pytest.fixture
    async def app(self) -> Application:
        """Create a test application with the plugin loaded."""
        if not self.plugin_class or not self.plugin_name:
            raise ValueError("plugin_class and plugin_name must be set")

        # Create app with only this plugin
        app = Application(
            ApplicationConfig(
                plugins=[self.plugin_name, *self.plugin_dependencies],
                auto_discover=False,
            )
        )

        # Register the plugin manually
        register_plugin_manually(
            self.plugin_name,
            self.plugin_class,
        )

        # Register dependencies if needed
        for _dep in self.plugin_dependencies:
            # In tests, dependencies should be registered manually
            pass

        async with app.lifespan():
            yield app

    @pytest.fixture
    async def plugin_instance(self, app: Application) -> WhiskeyPlugin:
        """Get the loaded plugin instance."""
        from whiskey.plugins import get_plugin_registry

        registry = get_plugin_registry()
        metadata = registry.get_plugin(self.plugin_name)
        return metadata.instance


def create_test_plugin(
    name: str = "test",
    version: str = "0.1.0",
    register_func: Callable[[Container], None] | None = None,
    initialize_func: Callable[[Application], None] | None = None,
) -> type[WhiskeyPlugin]:
    """Create a test plugin class for testing."""
    from whiskey.plugins import BasePlugin

    class TestPlugin(BasePlugin):
        def __init__(self):
            super().__init__(name=name, version=version)

        def register(self, container: Container) -> None:
            if register_func:
                register_func(container)

        def initialize(self, app: Application) -> None:
            if initialize_func:
                initialize_func(app)

    return TestPlugin


async def load_plugin_isolated(
    plugin_class: type[WhiskeyPlugin],
    plugin_name: str,
) -> tuple[Application, WhiskeyPlugin]:
    """Load a plugin in isolation for testing.

    Returns:
        Tuple of (app, plugin_instance)
    """
    app = Application(
        ApplicationConfig(
            plugins=[plugin_name],
            auto_discover=False,
        )
    )

    register_plugin_manually(plugin_name, plugin_class)

    await app.startup()

    from whiskey.plugins import get_plugin_registry

    registry = get_plugin_registry()
    metadata = registry.get_plugin(plugin_name)

    return app, metadata.instance


class MockService:
    """Mock service for testing plugin registration."""

    def __init__(self, value: str = "mock"):
        self.value = value
        self.initialized = False
        self.disposed = False

    async def initialize(self) -> None:
        self.initialized = True

    async def dispose(self) -> None:
        self.disposed = True
