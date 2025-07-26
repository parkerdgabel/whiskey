"""Fluent application builder for Whiskey's Pythonic DI redesign.

This module provides the WhiskeyBuilder class which offers a fluent,
chainable API for configuring dependency injection containers and applications.
"""

from __future__ import annotations

from typing import Any, Callable, Type, TypeVar, Union

from .container import Container
from .errors import ConfigurationError
from .registry import Scope, ServiceDescriptor

T = TypeVar("T")


class ComponentBuilder:
    """Fluent builder for individual component configuration.

    This class provides a chainable interface for configuring specific
    components with various options like scope, tags, conditions, etc.
    """

    def __init__(self, app_builder: WhiskeyBuilder, key: str | type, provider: Any):
        self._app_builder = app_builder
        self._key = key
        self._provider = provider
        self._scope = Scope.TRANSIENT
        self._name: str | None = None
        self._tags: set[str] = set()
        self._condition: Callable[[], bool] | None = None
        self._lazy = False
        self._metadata: dict[str, Any] = {}

    def as_singleton(self) -> ComponentBuilder:
        """Configure component with singleton scope."""
        self._scope = Scope.SINGLETON
        return self

    def as_scoped(self, scope_name: str = "default") -> ComponentBuilder:
        """Configure component with scoped lifecycle."""
        self._scope = Scope.SCOPED
        self._metadata["scope_name"] = scope_name
        return self

    def as_transient(self) -> ComponentBuilder:
        """Configure component with transient scope (default)."""
        self._scope = Scope.TRANSIENT
        return self

    def named(self, name: str) -> ComponentBuilder:
        """Assign a name to this component for multiple implementations."""
        self._name = name
        return self

    def tagged(self, *tags: str) -> ComponentBuilder:
        """Add tags to this component for categorization."""
        self._tags.update(tags)
        return self

    def when(self, condition: Callable[[], bool] | bool) -> ComponentBuilder:
        """Add a condition for conditional registration."""
        if isinstance(condition, bool):
            # Convert static bool to callable
            self._condition = lambda: condition
        else:
            self._condition = condition
        return self

    def lazy(self, is_lazy: bool = True) -> ComponentBuilder:
        """Enable or disable lazy resolution."""
        self._lazy = is_lazy
        return self

    def with_metadata(self, **metadata) -> ComponentBuilder:
        """Add arbitrary metadata to the component."""
        self._metadata.update(metadata)
        return self

    def priority(self, level: int) -> ComponentBuilder:
        """Set priority for component resolution order."""
        self._metadata["priority"] = level
        return self

    def build(self) -> WhiskeyBuilder:
        """Complete component configuration and return to application builder."""
        # Register the component with the accumulated configuration
        self._app_builder._register_component(
            self._key,
            self._provider,
            scope=self._scope,
            name=self._name,
            condition=self._condition,
            tags=self._tags,
            lazy=self._lazy,
            **self._metadata,
        )
        return self._app_builder


class WhiskeyBuilder:
    """Fluent builder for configuring dependency injection applications.
    
    This class provides a chainable API for registering components, configuring
    scopes, setting up application lifecycle, and building the final container.
    
    Examples:
        Basic component registration:
        
        >>> app = WhiskeyBuilder() \\
        ...     .component('database', DatabaseImpl).as_singleton() \\
        ...     .component(EmailService, EmailService).tagged('infrastructure') \\
        ...     .factory('cache', create_redis_cache) \\
        ...     .build()
        
        Conditional registration:
        
        >>> app = WhiskeyBuilder() \\
        ...     .component('db', PostgresDB).when(lambda: os.getenv('DB_TYPE') == 'postgres') \\
        ...     .component('db', SqliteDB).when(lambda: os.getenv('DB_TYPE') == 'sqlite') \\
        ...     .build()
        
        Named components:
        
        >>> app = WhiskeyBuilder() \\
        ...     .component(Database, PostgresDB).named('primary').as_singleton() \\
        ...     .component(Database, RedisDB).named('cache').as_singleton() \\
        ...     .build()
    """

    def __init__(self):
        """Initialize a new WhiskeyBuilder."""
        self._container = Container()
        self._configuration_callbacks: list[Callable[[Container], None]] = []
        self._startup_callbacks: list[Callable[[], None]] = []
        self._shutdown_callbacks: list[Callable[[], None]] = []
        self._error_handlers: dict[Type[Exception], Callable] = {}

    # Service registration methods

    def component(
        self, key: str | type, provider: Union[type, object, Callable] = None
    ) -> ComponentBuilder:
        """Register a component with fluent configuration.

        Args:
            key: Service key (string or type)
            provider: Service implementation (defaults to key if it's a type)

        Returns:
            ComponentBuilder for fluent configuration
        """
        if provider is None and isinstance(key, type):
            provider = key

        if provider is None:
            raise ConfigurationError(f"Provider required for component '{key}'")

        return ComponentBuilder(self, key, provider)

    def singleton(
        self, key: str | type, provider: Union[type, object, Callable] = None
    ) -> ComponentBuilder:
        """Register a singleton component with fluent configuration."""
        return self.component(key, provider).as_singleton()

    def scoped(
        self,
        key: str | type,
        provider: Union[type, object, Callable] = None,
        scope_name: str = "default",
    ) -> ComponentBuilder:
        """Register a scoped component with fluent configuration."""
        return self.component(key, provider).as_scoped(scope_name)

    def factory(self, key: str | type, factory_func: Callable) -> ComponentBuilder:
        """Register a factory function with fluent configuration."""
        return self.component(key, factory_func)

    def instance(self, key: str | type, instance: Any) -> ComponentBuilder:
        """Register an existing instance with fluent configuration."""
        return self.component(key, instance).as_singleton()

    # Batch operations

    def components(self, **components) -> WhiskeyBuilder:
        """Register multiple components at once.

        Args:
            **components: Mapping of keys to providers

        Returns:
            Self for chaining
        """
        for key, provider in components.items():
            self.component(key, provider).build()
        return self

    def singletons(self, **components) -> WhiskeyBuilder:
        """Register multiple singleton components at once."""
        for key, provider in components.items():
            self.singleton(key, provider).build()
        return self

    def tag_components(self, tag: str, *keys: str | type) -> WhiskeyBuilder:
        """Add a tag to multiple existing components.

        Args:
            tag: The tag to add
            *keys: Service keys to tag

        Returns:
            Self for chaining
        """
        for key in keys:
            # Find and update existing component
            try:
                descriptor = self._container.registry.get(key)
                descriptor.add_tag(tag)
            except KeyError:
                raise ConfigurationError(f"Service '{key}' not found for tagging")
        return self

    # Configuration and lifecycle

    def configure(self, config_func: Callable[[Container], None]) -> WhiskeyBuilder:
        """Add a configuration callback.

        Args:
            config_func: Function that configures the container

        Returns:
            Self for chaining
        """
        self._configuration_callbacks.append(config_func)
        return self

    def on_startup(self, callback: Callable[[], None]) -> WhiskeyBuilder:
        """Add a startup callback.

        Args:
            callback: Function to call on application startup

        Returns:
            Self for chaining
        """
        self._startup_callbacks.append(callback)
        return self

    def on_shutdown(self, callback: Callable[[], None]) -> WhiskeyBuilder:
        """Add a shutdown callback.

        Args:
            callback: Function to call on application shutdown

        Returns:
            Self for chaining
        """
        self._shutdown_callbacks.append(callback)
        return self

    def on_error(self, exception_type: Type[Exception], handler: Callable) -> WhiskeyBuilder:
        """Add an error handler.

        Args:
            exception_type: The exception type to handle
            handler: Function to handle the exception

        Returns:
            Self for chaining
        """
        self._error_handlers[exception_type] = handler
        return self


    # Environment and conditions

    def when_env(self, var_name: str, expected_value: str = None) -> ConditionBuilder:
        """Create a condition based on environment variable.

        Args:
            var_name: Environment variable name
            expected_value: Expected value (if None, just checks existence)

        Returns:
            ConditionBuilder for applying to components
        """
        import os

        if expected_value is None:
            condition = lambda: var_name in os.environ
        else:
            condition = lambda: os.environ.get(var_name) == expected_value

        return ConditionBuilder(self, condition)

    def when_debug(self) -> ConditionBuilder:
        """Create a condition for debug mode."""
        import os

        condition = lambda: os.environ.get("DEBUG", "").lower() in ("true", "1", "yes")
        return ConditionBuilder(self, condition)

    def when_production(self) -> ConditionBuilder:
        """Create a condition for production mode."""
        import os

        condition = lambda: os.environ.get("ENV", "").lower() in ("prod", "production")
        return ConditionBuilder(self, condition)

    # Build methods

    def build(self) -> Container:
        """Build the final container with all configurations.

        Returns:
            Configured Container instance
        """
        # Apply all configuration callbacks
        for callback in self._configuration_callbacks:
            callback(self._container)

        # Store lifecycle callbacks in container metadata
        self._container._startup_callbacks = self._startup_callbacks
        self._container._shutdown_callbacks = self._shutdown_callbacks
        self._container._error_handlers = self._error_handlers

        return self._container

    def build_app(self) -> Whiskey:
        """Build a full Whiskey instance with lifecycle management.

        Returns:
            Whiskey instance with all configurations
        """
        from .application import Whiskey

        container = self.build()
        return Whiskey(container)

    # Internal methods

    def _register_component(
        self, key: str | type, provider: Union[type, object, Callable], **kwargs
    ) -> ServiceDescriptor:
        """Internal method to register a component with the container."""
        return self._container.register(key, provider, **kwargs)


class ConditionBuilder:
    """Builder for applying conditions to multiple components."""

    def __init__(self, app_builder: WhiskeyBuilder, condition: Callable[[], bool]):
        self._app_builder = app_builder
        self._condition = condition

    def register(
        self, key: str | type, provider: Union[type, object, Callable]
    ) -> ComponentBuilder:
        """Register a component with this condition."""
        return self._app_builder.component(key, provider).when(self._condition)

    def singleton(
        self, key: str | type, provider: Union[type, object, Callable] = None
    ) -> ComponentBuilder:
        """Register a singleton component with this condition."""
        return self._app_builder.singleton(key, provider).when(self._condition)

    def factory(self, key: str | type, factory_func: Callable) -> ComponentBuilder:
        """Register a factory with this condition."""
        return self._app_builder.factory(key, factory_func).when(self._condition)


# Convenience function for starting a new builder
def create_app() -> WhiskeyBuilder:
    """Create a new WhiskeyBuilder for fluent configuration.
    
    Returns:
        New WhiskeyBuilder instance
        
    Examples:
        >>> app = create_app() \\
        ...     .component('database', DatabaseImpl).as_singleton() \\
        ...     .component(EmailService, EmailService) \\
        ...     .build()
    """
    return WhiskeyBuilder()
