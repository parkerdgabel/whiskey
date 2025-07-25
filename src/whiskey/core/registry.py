"""Service registry system for Whiskey's Pythonic DI redesign.

This module provides the core service metadata and registry functionality
that serves as the single source of truth for all registered services.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Union


class Scope(Enum):
    """Service lifecycle scopes."""

    SINGLETON = "singleton"  # One instance for entire application
    TRANSIENT = "transient"  # New instance for each resolution
    SCOPED = "scoped"  # One instance per scope context


@dataclass
class ServiceDescriptor:
    """Complete metadata for a registered service.

    This is the single source of truth for all service information,
    eliminating the need for multiple dictionaries in the old system.

    Attributes:
        key: Unique string identifier (e.g., "database" or "database:primary")
        service_type: The interface/type this service provides
        provider: The class, instance, or factory that provides the service
        scope: Lifecycle scope for the service
        name: Optional name for multiple implementations of same type
        condition: Optional condition function for conditional registration
        tags: Set of tags for categorization and filtering
        lazy: Whether this service should use lazy resolution
        is_factory: True if provider is a factory function
        metadata: Additional arbitrary metadata
    """

    key: str
    service_type: type
    provider: Union[type, object, Callable]
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
            raise ValueError(f"Service key must be string, got {type(self.key)}")

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
        if (
            callable(self.provider)
            and not isinstance(self.provider, type)
            and not hasattr(self.provider, "__class__")
        ):
            self.is_factory = True

    def matches_condition(self) -> bool:
        """Check if this service's registration condition is met.

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
        """Check if service has a specific tag."""
        return tag in self.tags

    def add_tag(self, tag: str) -> None:
        """Add a tag to this service."""
        self.tags.add(tag)


class ServiceRegistry:
    """Central registry for all service descriptors.

    This class maintains the single source of truth for service registration,
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
        self._descriptors: dict[str, ServiceDescriptor] = {}

        # Reverse lookups for efficient querying
        self._type_to_keys: dict[type, set[str]] = defaultdict(set)
        self._tag_to_keys: dict[str, set[str]] = defaultdict(set)
        self._scope_to_keys: dict[Scope, set[str]] = defaultdict(set)

    def register(
        self,
        key: str | type,
        provider: Union[type, object, Callable],
        *,
        service_type: type | None = None,
        scope: Scope = Scope.TRANSIENT,
        name: str | None = None,
        condition: Callable[[], bool] | None = None,
        tags: set[str] | None = None,
        lazy: bool = False,
        **metadata,
    ) -> ServiceDescriptor:
        """Register a service with the registry.

        Args:
            key: Service key (string) or type (converted to string)
            provider: Class, instance, or factory that provides the service
            service_type: The interface type (defaults to provider type)
            scope: Service lifecycle scope
            name: Optional name for multiple implementations
            condition: Optional registration condition
            tags: Set of tags for categorization
            lazy: Whether to use lazy resolution
            **metadata: Additional arbitrary metadata

        Returns:
            The created ServiceDescriptor

        Examples:
            >>> registry.register("database", DatabaseImpl, scope=Scope.SINGLETON)
            >>> registry.register(Database, DatabaseImpl, name="primary")
            >>> registry.register("cache", create_cache, tags={"infrastructure"})
        """
        # Normalize key to string
        string_key = self._normalize_key(key, name)

        # Determine service type
        if service_type is None:
            if isinstance(provider, type):
                service_type = provider
            else:
                service_type = type(provider)

        # Create descriptor
        descriptor = ServiceDescriptor(
            key=string_key,
            service_type=service_type,
            provider=provider,
            scope=scope,
            name=name,
            condition=condition,
            tags=tags or set(),
            lazy=lazy,
            metadata=metadata,
        )

        # Store in primary registry
        self._descriptors[string_key] = descriptor

        # Update reverse lookups
        self._type_to_keys[service_type].add(string_key)
        self._scope_to_keys[scope].add(string_key)

        for tag in descriptor.tags:
            self._tag_to_keys[tag].add(string_key)

        return descriptor

    def get(self, key: str | type, name: str | None = None) -> ServiceDescriptor:
        """Get a service descriptor by key.

        Args:
            key: Service key (string or type)
            name: Optional name for named services

        Returns:
            The ServiceDescriptor

        Raises:
            KeyError: If service is not registered
        """
        string_key = self._normalize_key(key, name)

        if string_key not in self._descriptors:
            raise KeyError(f"Service '{string_key}' not registered")

        descriptor = self._descriptors[string_key]

        # Check condition if present
        if not descriptor.matches_condition():
            raise KeyError(f"Service '{string_key}' condition not met")

        return descriptor

    def has(self, key: str | type, name: str | None = None) -> bool:
        """Check if a service is registered.

        Args:
            key: Service key (string or type)
            name: Optional name for named services

        Returns:
            True if service is registered and condition is met
        """
        try:
            self.get(key, name)
            return True
        except KeyError:
            return False

    def remove(self, key: str | type, name: str | None = None) -> bool:
        """Remove a service from the registry.

        Args:
            key: Service key (string or type)
            name: Optional name for named services

        Returns:
            True if service was removed, False if not found
        """
        string_key = self._normalize_key(key, name)

        if string_key not in self._descriptors:
            return False

        descriptor = self._descriptors.pop(string_key)

        # Update reverse lookups
        self._type_to_keys[descriptor.service_type].discard(string_key)
        self._scope_to_keys[descriptor.scope].discard(string_key)

        for tag in descriptor.tags:
            self._tag_to_keys[tag].discard(string_key)

        return True

    def find_by_type(self, service_type: type) -> list[ServiceDescriptor]:
        """Find all services that provide a specific type.

        Args:
            service_type: The type to search for

        Returns:
            List of matching ServiceDescriptors
        """
        keys = self._type_to_keys.get(service_type, set())
        descriptors = []

        for key in keys:
            descriptor = self._descriptors[key]
            if descriptor.matches_condition():
                descriptors.append(descriptor)

        return descriptors

    def find_by_tag(self, tag: str) -> list[ServiceDescriptor]:
        """Find all services with a specific tag.

        Args:
            tag: The tag to search for

        Returns:
            List of matching ServiceDescriptors
        """
        keys = self._tag_to_keys.get(tag, set())
        descriptors = []

        for key in keys:
            descriptor = self._descriptors[key]
            if descriptor.matches_condition():
                descriptors.append(descriptor)

        return descriptors

    def find_by_scope(self, scope: Scope) -> list[ServiceDescriptor]:
        """Find all services with a specific scope.

        Args:
            scope: The scope to search for

        Returns:
            List of matching ServiceDescriptors
        """
        keys = self._scope_to_keys.get(scope, set())
        descriptors = []

        for key in keys:
            descriptor = self._descriptors[key]
            if descriptor.matches_condition():
                descriptors.append(descriptor)

        return descriptors

    def list_all(self) -> list[ServiceDescriptor]:
        """Get all registered services that meet their conditions.

        Returns:
            List of all active ServiceDescriptors
        """
        descriptors = []

        for descriptor in self._descriptors.values():
            if descriptor.matches_condition():
                descriptors.append(descriptor)

        return descriptors

    def clear(self) -> None:
        """Clear all registered services."""
        self._descriptors.clear()
        self._type_to_keys.clear()
        self._tag_to_keys.clear()
        self._scope_to_keys.clear()

    def _normalize_key(self, key: str | type, name: str | None = None) -> str:
        """Convert key to normalized string format.

        Args:
            key: Service key (string or type)
            name: Optional name for named services

        Returns:
            Normalized string key

        Examples:
            >>> _normalize_key("database") → "database"
            >>> _normalize_key(Database) → "database"
            >>> _normalize_key(Database, "primary") → "database:primary"
        """
        if isinstance(key, str):
            base_key = key
        else:
            # Convert type to lowercase string
            base_key = key.__name__.lower()

        if name:
            return f"{base_key}:{name}"

        return base_key

    def __len__(self) -> int:
        """Get number of registered services."""
        return len(self._descriptors)

    def __contains__(self, key: str | type) -> bool:
        """Support 'in' operator."""
        return self.has(key)

    def __iter__(self):
        """Iterate over all service keys."""
        return iter(self._descriptors.keys())

    def keys(self):
        """Get all service keys."""
        return self._descriptors.keys()

    def values(self):
        """Get all service descriptors."""
        return self._descriptors.values()

    def items(self):
        """Get all (key, descriptor) pairs."""
        return self._descriptors.items()
