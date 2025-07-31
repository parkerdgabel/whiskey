"""Component metadata and registry system for dependency injection.

This module implements the component registry, which serves as the single source
of truth for all registered components and their metadata. It provides a clean
abstraction over component registration, supporting multiple scopes, conditional
registration, tagging, and named components.

Classes:
    Scope: Enumeration of component lifecycle scopes (singleton, transient, scoped)
    ComponentDescriptor: Complete metadata for a registered component
    ComponentRegistry: Central registry managing all component registrations

Key Concepts:
    - Components are identified by a key (string) which can be a type or custom name
    - Each component has a scope determining its lifecycle
    - Components can be tagged for categorization and filtering
    - Named components allow multiple implementations of the same interface
    - Conditional registration based on runtime conditions
    - Metadata storage for additional component information

Example:
    >>> registry = ComponentRegistry()
    >>>
    >>> # Register a singleton component
    >>> descriptor = registry.register(
    ...     Database,                    # key/type
    ...     PostgresDatabase,           # implementation
    ...     scope=Scope.SINGLETON,
    ...     tags={'infrastructure', 'critical'},
    ...     metadata={'version': '1.0'}
    ... )
    >>>
    >>> # Register named implementations
    >>> registry.register(Cache, RedisCache, name='redis')
    >>> registry.register(Cache, MemoryCache, name='memory')
    >>>
    >>> # Query components
    >>> db_descriptor = registry.get(Database)
    >>> cache_descriptors = registry.get_all(Cache)
    >>> tagged = registry.get_by_tag('critical')

See Also:
    - whiskey.core.container: Uses registry for component storage
    - whiskey.core.analyzer: Type analysis for registration decisions
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from .errors import RegistrationError


class Scope(Enum):
    """Component lifecycle scopes."""

    SINGLETON = "singleton"  # One instance for entire application
    TRANSIENT = "transient"  # New instance for each resolution
    SCOPED = "scoped"  # One instance per scope context


@dataclass
class ComponentDescriptor:
    """Complete metadata for a registered component.

    This is the single source of truth for all component information,
    eliminating the need for multiple dictionaries in the old system.

    Attributes:
        key: Unique string identifier (e.g., "database" or "database:primary")
        component_type: The interface/type this component provides
        provider: The class, instance, or factory that provides the component
        scope: Lifecycle scope for the component
        name: Optional name for multiple implementations of same type
        condition: Optional condition function for conditional registration
        tags: Set of tags for categorization and filtering
        lazy: Whether this component should use lazy resolution
        is_factory: True if provider is a factory function
        metadata: Additional arbitrary metadata
    """

    key: str
    component_type: type
    provider: type | object | Callable
    scope: Scope = Scope.TRANSIENT
    name: str | None = None
    condition: Callable[[], bool] | None = None
    tags: set[str] = field(default_factory=set)
    lazy: bool = False
    is_factory: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate and normalize descriptor data."""
        # Ensure key is always a string
        if not isinstance(self.key, str):
            raise ValueError(f"Component key must be string, got {type(self.key)}")

        # Validate provider type
        if not (
            isinstance(self.provider, type)
            or callable(self.provider)
            or hasattr(self.provider, "__class__")
        ):
            raise ValueError(
                f"Provider must be type, callable, or instance, got {type(self.provider)}"
            )

        # Auto-detect if provider is a factory function
        if callable(self.provider) and not isinstance(self.provider, type):
            self.is_factory = True

    def matches_condition(self) -> bool:
        """Check if this component's registration condition is met.

        Returns:
            True if no condition or condition evaluates to True
        """
        if self.condition is None:
            return True

        try:
            return bool(self.condition())
        except Exception:
            # If condition evaluation fails, don't register
            return False

    def has_tag(self, tag: str) -> bool:
        """Check if component has a specific tag."""
        return tag in self.tags

    def has_any_tag(self, tags: set[str]) -> bool:
        """Check if component has any of the given tags."""
        if not tags:
            return False
        return bool(self.tags & tags)

    def has_all_tags(self, tags: set[str]) -> bool:
        """Check if component has all of the given tags."""
        if not tags:
            return True
        return tags.issubset(self.tags)

    def add_tag(self, tag: str) -> None:
        """Add a tag to this component."""
        self.tags.add(tag)


class ComponentRegistry:
    """Central registry for all component descriptors.

    This class maintains the single source of truth for component registration,
    providing efficient lookup and querying capabilities.

    Features:
        - String-based keys for simplicity
        - Reverse lookup (type → keys)
        - Tag-based filtering
        - Condition evaluation
        - Efficient querying
    """

    def __init__(self):
        """Initialize an empty registry."""
        # Primary storage: key → descriptor
        self._descriptors: dict[str, ComponentDescriptor] = {}

        # Reverse lookups for efficient querying
        self._type_to_keys: dict[type, set[str]] = defaultdict(set)
        self._tag_to_keys: dict[str, set[str]] = defaultdict(set)
        self._scope_to_keys: dict[Scope, set[str]] = defaultdict(set)

        # Compatibility properties for tests
        self._components = self._descriptors  # Alias for old tests
        self._tag_index = self._tag_to_keys  # Alias for old tests
        self._type_index = self._type_to_keys  # Alias for old tests

    def register(
        self,
        key: str | type,
        provider: type | object | Callable,
        *,
        component_type: type | None = None,
        scope: Scope = Scope.TRANSIENT,
        name: str | None = None,
        condition: Callable[[], bool] | None = None,
        tags: set[str] | None = None,
        lazy: bool = False,
        metadata: dict[str, Any] | None = None,
        allow_override: bool = False,
        **extra_metadata,
    ) -> ComponentDescriptor:
        """Register a component with the registry.

        Args:
            key: Component key (string) or type (converted to string)
            provider: Class, instance, or factory that provides the component
            component_type: The interface type (defaults to provider type)
            scope: Component lifecycle scope
            name: Optional name for multiple implementations
            condition: Optional registration condition
            tags: Set of tags for categorization
            lazy: Whether to use lazy resolution
            metadata: Additional arbitrary metadata
            **extra_metadata: Additional metadata via kwargs

        Returns:
            The created ComponentDescriptor

        Examples:
            >>> registry.register("database", DatabaseImpl, scope=Scope.SINGLETON)
            >>> registry.register(Database, DatabaseImpl, name="primary")
            >>> registry.register("cache", create_cache, tags={"infrastructure"})
        """
        # Allow None provider for special cases (returns None when resolved)
        # This is useful for optional dependencies and testing

        # Normalize key to string
        string_key = self._normalize_key(key, name)

        # Check for duplicate registration unless override is allowed
        if string_key in self._descriptors and not allow_override:
            raise RegistrationError(f"Component '{string_key}' is already registered")

        # Determine component type
        if component_type is None:
            if isinstance(provider, type):
                component_type = provider
            elif callable(provider) and not isinstance(provider, type):
                # For factory functions, try to infer from return type annotation
                import inspect

                try:
                    sig = inspect.signature(provider)
                    if sig.return_annotation != inspect.Signature.empty:
                        component_type = sig.return_annotation
                    else:
                        component_type = type(provider)
                except Exception:
                    component_type = type(provider)
            else:
                component_type = type(provider)

        # Combine metadata
        final_metadata = metadata or {}
        if extra_metadata:
            final_metadata.update(extra_metadata)

        # Create descriptor
        descriptor = ComponentDescriptor(
            key=string_key,
            component_type=component_type,
            provider=provider,
            scope=scope,
            name=name,
            condition=condition,
            tags=tags or set(),
            lazy=lazy,
            metadata=final_metadata,
        )

        # Store in primary registry
        self._descriptors[string_key] = descriptor

        # Update reverse lookups
        self._type_to_keys[component_type].add(string_key)
        self._scope_to_keys[scope].add(string_key)

        for tag in descriptor.tags:
            self._tag_to_keys[tag].add(string_key)

        return descriptor

    def get(self, key: str | type, name: str | None = None) -> ComponentDescriptor:
        """Get a component descriptor by key.

        Args:
            key: Component key (string or type)
            name: Optional name for named components

        Returns:
            The ComponentDescriptor

        Raises:
            KeyError: If component is not registered
        """
        string_key = self._normalize_key(key, name)

        # Try the key as-is first
        if string_key in self._descriptors:
            descriptor = self._descriptors[string_key]
        else:
            # For backwards compatibility, try case-insensitive lookup for types
            if isinstance(key, type) and hasattr(key, "__name__"):
                # Try lowercase version
                lowercase_key = key.__name__.lower() + (f":{name}" if name else "")
                if lowercase_key in self._descriptors:
                    descriptor = self._descriptors[lowercase_key]
                else:
                    raise KeyError(f"Component '{string_key}' not registered")
            elif isinstance(key, str):
                # Try lowercase version for string keys too
                lowercase_key = key.lower() + (f":{name}" if name else "")
                if lowercase_key in self._descriptors:
                    descriptor = self._descriptors[lowercase_key]
                else:
                    raise KeyError(f"Component '{string_key}' not registered")
            else:
                raise KeyError(f"Component '{string_key}' not registered")

        # Check condition if present
        if not descriptor.matches_condition():
            raise KeyError(f"Component '{string_key}' condition not met")

        return descriptor

    def has(self, key: str | type, name: str | None = None) -> bool:
        """Check if a component is registered.

        Args:
            key: Component key (string or type)
            name: Optional name for named components

        Returns:
            True if component is registered and condition is met
        """
        try:
            self.get(key, name)
            return True
        except KeyError:
            return False

    def remove(self, key: str | type, name: str | None = None) -> bool:
        """Remove a component from the registry.

        Args:
            key: Component key (string or type)
            name: Optional name for named components

        Returns:
            True if component was removed, False if not found
        """
        string_key = self._normalize_key(key, name)

        if string_key not in self._descriptors:
            return False

        descriptor = self._descriptors.pop(string_key)

        # Update reverse lookups
        self._type_to_keys[descriptor.component_type].discard(string_key)
        self._scope_to_keys[descriptor.scope].discard(string_key)

        for tag in descriptor.tags:
            self._tag_to_keys[tag].discard(string_key)

        return True

    def find_by_type(self, component_type: type) -> list[ComponentDescriptor]:
        """Find all components that provide a specific type.

        Args:
            component_type: The type to search for

        Returns:
            List of matching ComponentDescriptors
        """
        keys = self._type_to_keys.get(component_type, set())
        descriptors = []

        for key in keys:
            descriptor = self._descriptors[key]
            if descriptor.matches_condition():
                descriptors.append(descriptor)

        return descriptors

    def find_by_tag(self, tag: str) -> list[ComponentDescriptor]:
        """Find all components with a specific tag.

        Args:
            tag: The tag to search for

        Returns:
            List of matching ComponentDescriptors
        """
        keys = self._tag_to_keys.get(tag, set())
        descriptors = []

        for key in keys:
            descriptor = self._descriptors[key]
            if descriptor.matches_condition():
                descriptors.append(descriptor)

        return descriptors

    def find_by_scope(self, scope: Scope) -> list[ComponentDescriptor]:
        """Find all components with a specific scope.

        Args:
            scope: The scope to search for

        Returns:
            List of matching ComponentDescriptors
        """
        keys = self._scope_to_keys.get(scope, set())
        descriptors = []

        for key in keys:
            descriptor = self._descriptors[key]
            if descriptor.matches_condition():
                descriptors.append(descriptor)

        return descriptors

    def list_all(self) -> list[ComponentDescriptor]:
        """Get all registered components that meet their conditions.

        Returns:
            List of all active ComponentDescriptors
        """
        descriptors = []

        for descriptor in self._descriptors.values():
            if descriptor.matches_condition():
                descriptors.append(descriptor)

        return descriptors

    def clear(self) -> None:
        """Clear all registered components."""
        self._descriptors.clear()
        self._type_to_keys.clear()
        self._tag_to_keys.clear()
        self._scope_to_keys.clear()

    def _normalize_key(self, key: str | type, name: str | None = None) -> str:
        """Convert key to normalized string format.

        Args:
            key: Component key (string or type)
            name: Optional name for named components

        Returns:
            Normalized string key

        Examples:
            >>> _normalize_key("database") → "database"
            >>> _normalize_key(Database) → "database"
            >>> _normalize_key(Database, "primary") → "database:primary"
        """
        if isinstance(key, str):
            base_key = key
        elif hasattr(key, "__name__"):
            # Convert type to string (preserve original case)
            base_key = key.__name__
        else:
            # Convert other types (like numbers) to string
            base_key = str(key)

        if name:
            return f"{base_key}:{name}"

        return base_key

    def __len__(self) -> int:
        """Get number of registered components."""
        return len(self._descriptors)

    def __contains__(self, key: str | type) -> bool:
        """Support 'in' operator."""
        return self.has(key)

    def __iter__(self):
        """Iterate over all component keys."""
        return iter(self._descriptors.keys())

    def keys(self):
        """Get all component keys."""
        return self._descriptors.keys()

    def values(self):
        """Get all component descriptors."""
        return self._descriptors.values()

    def items(self):
        """Get all (key, descriptor) pairs."""
        return self._descriptors.items()
