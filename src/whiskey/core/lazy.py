"""Lazy resolution support for Whiskey.

This module provides the Lazy wrapper type that enables deferred dependency
resolution, allowing dependencies to be resolved only when first accessed.
"""

from __future__ import annotations

import asyncio
from typing import Any, Generic, TypeVar, cast
from weakref import ref as weakref

from whiskey.core.container import Container, get_current_container

T = TypeVar("T")


class Lazy(Generic[T]):
    """A lazy wrapper that defers dependency resolution until first access.

    This class acts as a proxy for a service, resolving it from the container
    only when it's first accessed. This is useful for:
    - Breaking circular dependencies
    - Improving startup performance
    - Optional dependencies that may not be used

    Attributes:
        _service_type: The type to resolve
        _name: Optional name for named dependencies
        _container_ref: Weak reference to the container
        _instance: Cached instance after resolution
        _resolved: Whether the dependency has been resolved

    Examples:
        Using Lazy in a service:

        >>> class ExpensiveService:
        ...     def __init__(self):
        ...         print("Expensive initialization!")
        ...
        >>> class ConsumerService:
        ...     def __init__(self, expensive: Lazy[ExpensiveService]):
        ...         self._expensive = expensive
        ...         print("Consumer created")
        ...
        ...     def use_expensive(self):
        ...         # First access triggers initialization
        ...         return self._expensive.value.do_something()

        Using Lazy with type annotations:

        >>> from typing import Annotated
        >>> from whiskey.core.decorators import Inject
        >>>
        >>> class MyService:
        ...     def __init__(self,
        ...                  lazy_dep: Annotated[Lazy[Database], Inject()]):
        ...         self._db = lazy_dep
    """

    def __init__(
        self, service_type: type[T], name: str | None = None, container: Container | None = None
    ):
        """Initialize a lazy wrapper.

        Args:
            service_type: The type to lazily resolve
            name: Optional name for named dependencies
            container: Container to use (defaults to current container)
        """
        self._service_type = service_type
        self._name = name
        self._container_ref = weakref(container) if container is not None else None
        self._instance: T | None = None
        self._resolved = False
        self._resolving = False  # Prevent recursive resolution

    @property
    def value(self) -> T:
        """Get the resolved value, resolving it if necessary.

        Returns:
            The resolved service instance

        Raises:
            RuntimeError: If resolution fails or no container is available
        """
        if not self._resolved:
            self._resolve()
        return cast(T, self._instance)

    @property
    def is_resolved(self) -> bool:
        """Check if the dependency has been resolved.

        Returns:
            True if the dependency has been resolved
        """
        return self._resolved

    def _resolve(self) -> None:
        """Resolve the dependency from the container."""
        if self._resolving:
            raise RuntimeError(f"Circular lazy resolution detected for {self._service_type}")

        self._resolving = True
        try:
            # Get container
            if self._container_ref:
                container = self._container_ref()
                if container is None:
                    raise RuntimeError("Container has been garbage collected")
            else:
                container = get_current_container()
                if container is None:
                    raise RuntimeError("No container available for lazy resolution")

            # Check if we're in an async context
            try:
                loop = asyncio.get_running_loop()
                # We're in an async context
                # Since we can't await here (not an async method), we need to handle this differently
                # For now, raise an error suggesting to use await on the container directly
                raise RuntimeError(
                    "Cannot resolve Lazy values synchronously in async context. "
                    "Consider resolving the service directly with 'await container.resolve()'"
                )
            except RuntimeError as e:
                if "no running event loop" not in str(e):
                    # Re-raise if it's a different RuntimeError
                    raise
                # No event loop, safe to use sync resolution
                self._instance = container.resolve_sync(self._service_type, name=self._name)

            self._resolved = True
        finally:
            self._resolving = False

    def __getattr__(self, name: str) -> Any:
        """Proxy attribute access to the resolved instance.

        Args:
            name: Attribute name

        Returns:
            The attribute from the resolved instance
        """
        return getattr(self.value, name)

    def __repr__(self) -> str:
        """String representation of the lazy wrapper."""
        if self._resolved:
            return f"Lazy[{self._service_type.__name__}](resolved={self._instance!r})"
        else:
            name_str = f", name='{self._name}'" if self._name else ""
            return f"Lazy[{self._service_type.__name__}](unresolved{name_str})"

    def __bool__(self) -> bool:
        """Check if the lazy wrapper has a resolved value.

        Returns:
            True if resolved and instance is truthy
        """
        if not self._resolved:
            return True  # Unresolved lazy is considered truthy
        return bool(self._instance)


class LazyDescriptor(Generic[T]):
    """A descriptor that creates Lazy instances for class attributes.

    This allows for cleaner syntax when using lazy dependencies:

    Example:
        >>> class MyService:
        ...     database: LazyDescriptor[Database] = LazyDescriptor(Database)
        ...     cache: LazyDescriptor[Cache] = LazyDescriptor(Cache, name="redis")
        ...
        ...     def use_database(self):
        ...         # First access creates and returns a Lazy instance
        ...         return self.database.value.query("SELECT * FROM users")
    """

    def __init__(self, service_type: type[T], name: str | None = None):
        """Initialize the lazy descriptor.

        Args:
            service_type: The type to lazily resolve
            name: Optional name for named dependencies
        """
        self._service_type = service_type
        self._name = name
        self._attr_name: str | None = None

    def __set_name__(self, owner: type, name: str) -> None:
        """Called when the descriptor is assigned to a class attribute.

        Args:
            owner: The class that owns this descriptor
            name: The attribute name
        """
        self._attr_name = f"_{name}_lazy"

    def __get__(self, instance: Any, owner: type) -> Lazy[T]:
        """Get or create a Lazy instance for this attribute.

        Args:
            instance: The instance accessing the attribute
            owner: The class that owns this descriptor

        Returns:
            A Lazy instance for the service type
        """
        if instance is None:
            return self  # type: ignore

        if self._attr_name is None:
            raise RuntimeError("LazyDescriptor not properly initialized")

        # Check if we already have a Lazy instance
        lazy_instance = getattr(instance, self._attr_name, None)
        if lazy_instance is None:
            # Try to get container from instance or current context
            container = None
            if hasattr(instance, "_container"):
                container = instance._container
            elif hasattr(instance, "container"):
                container = instance.container
            else:
                container = get_current_container()

            # Create new Lazy instance
            lazy_instance = Lazy(self._service_type, self._name, container)
            setattr(instance, self._attr_name, lazy_instance)

        return lazy_instance


def lazy_inject(service_type: type[T], name: str | None = None) -> Lazy[T]:
    """Create a lazy dependency for injection.

    This is a convenience function for use with dependency injection:

    Example:
        >>> from typing import Annotated
        >>> from whiskey.core.decorators import Inject
        >>>
        >>> class MyService:
        ...     def __init__(self,
        ...                  # Regular injection
        ...                  db: Annotated[Database, Inject()],
        ...                  # Lazy injection
        ...                  cache: Annotated[Cache, Inject()] = lazy_inject(Cache)):
        ...         self.db = db
        ...         self.cache = cache

    Args:
        service_type: The type to lazily resolve
        name: Optional name for named dependencies

    Returns:
        A Lazy instance that will resolve when accessed
    """
    return Lazy(service_type, name)
