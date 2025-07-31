"""Component lifecycle scope management with automatic cleanup.

This module implements Whiskey's scope system, which controls component instance
lifecycles and ensures proper resource management. Scopes define boundaries
within which component instances are shared and when they should be cleaned up.

Classes:
    Scope: Base class for custom scope implementations
    ContextVarScope: Thread-safe scope using Python's contextvars
    ScopeType: Constants for built-in scope types
    ScopeManager: Context manager for scope activation

Built-in Scopes:
    - singleton: One instance for entire application lifetime
    - transient: New instance for each resolution (default)
    - scoped: One instance per named scope (e.g., request, session)

Scope Lifecycle:
    1. Scope Entry: Context manager __enter__ or manual activation
    2. Component Resolution: Instances cached within scope
    3. Scope Exit: Automatic cleanup via __exit__
    4. Resource Disposal: dispose() called on all instances

Custom Scopes:
    Create custom scopes by extending the Scope class:
    - Override get/set for custom storage
    - Implement cleanup logic in clear()
    - Use context managers for activation

Example:
    >>> from whiskey.core.scopes import Scope, ScopeManager
    >>> from whiskey import Container
    >>>
    >>> # Built-in scope usage
    >>> container = Container()
    >>> container.scoped(RequestContext, scope_name='request')
    >>>
    >>> # Activate scope
    >>> with container.scope('request') as scope:
    ...     ctx1 = await container.resolve(RequestContext)
    ...     ctx2 = await container.resolve(RequestContext)
    ...     assert ctx1 is ctx2  # Same instance within scope
    >>> # ctx1 and ctx2 are disposed here
    >>>
    >>> # Custom scope implementation
    >>> class TenantScope(Scope):
    ...     def __init__(self, tenant_id: str):
    ...         super().__init__(f'tenant_{tenant_id}')
    ...         self.tenant_id = tenant_id

Thread Safety:
    - ContextVarScope provides thread-local storage
    - Each thread/task has isolated scope instances
    - Safe for concurrent async operations
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any, TypeVar

T = TypeVar("T")


class Scope:
    """Base class for dependency injection scopes.

    A scope controls the lifecycle of component instances. When a component is
    resolved within a scope, the same instance is returned for all resolutions
    within that scope's lifetime.

    Scopes use context managers to define their boundaries and automatically
    clean up resources when the scope ends.

    Examples:
        Creating a custom scope:

        >>> class RequestScope(Scope):
        ...     def __init__(self):
        ...         super().__init__("request")
        ...         self.request_id = generate_id()

        Using a scope:

        >>> with container.scope("request") as scope:
        ...     # All resolutions within this block share instances
        ...     component1 = await container.resolve(RequestService)
        ...     component2 = await container.resolve(RequestService)
        ...     assert component1 is component2  # Same instance
        ... # Resources cleaned up here

    Attributes:
        name: The scope identifier
        _instances: Cache of instances created in this scope
    """

    def __init__(self, name: str):
        self.name = name
        self._instances: dict[type, Any] = {}

    def get(self, component_type: type[T]) -> T | None:
        """Get a scoped instance if it exists.

        Args:
            component_type: The type to look up

        Returns:
            The cached instance or None if not found
        """
        return self._instances.get(component_type)

    def set(self, component_type: type[T], instance: T) -> None:
        """Store a scoped instance.

        Args:
            component_type: The type to cache the instance under
            instance: The instance to cache
        """
        self._instances[component_type] = instance

    def clear(self) -> None:
        """Clear all instances and run disposal.

        This method is called when the scope ends. It:
        1. Calls dispose() on any instances that have it
        2. Clears the instance cache

        Note:
            If an instance has a dispose() method, it will be called
            to allow proper cleanup (closing connections, etc.)
        """
        for instance in self._instances.values():
            # Call dispose if available
            if hasattr(instance, "dispose"):
                import asyncio

                if asyncio.iscoroutinefunction(instance.dispose):
                    asyncio.run(instance.dispose())
                else:
                    instance.dispose()
        self._instances.clear()

    def __enter__(self):
        """Enter the scope."""
        return self

    def __exit__(self, *args):
        """Exit the scope and clean up."""
        self.clear()

    async def __aenter__(self):
        """Async enter."""
        return self

    async def __aexit__(self, *args):
        """Async exit and clean up."""
        for instance in self._instances.values():
            if hasattr(instance, "dispose"):
                import asyncio

                if asyncio.iscoroutinefunction(instance.dispose):
                    await instance.dispose()
                else:
                    instance.dispose()
        self._instances.clear()


class ContextVarScope(Scope):
    """Scope that uses contextvars for thread-safe storage."""

    def __init__(self, name: str):
        super().__init__(name)
        self._context_var: ContextVar[dict[type, Any] | None] = ContextVar(
            f"scope_{name}", default=None
        )

    def get(self, component_type: type[T]) -> T | None:
        """Get from context."""
        instances = self._context_var.get()
        if instances is None:
            return None
        return instances.get(component_type)

    def set(self, component_type: type[T], instance: T) -> None:
        """Set in context."""
        instances = self._context_var.get()
        instances = {} if instances is None else instances.copy()
        instances[component_type] = instance
        self._context_var.set(instances)

    def clear(self) -> None:
        """Clear context."""
        self._context_var.set(None)


# Built-in scope types
class ScopeType:
    """Core scope types as simple string constants."""

    SINGLETON = "singleton"
    TRANSIENT = "transient"


class ScopeManager:
    """Context manager for entering/exiting scopes in a container."""

    def __init__(self, container: Any, scope_name: str):
        self.container = container
        self.scope_name = scope_name
        self.scope_instance = None

    def __enter__(self):
        """Enter the scope."""
        self.scope_instance = self.container.enter_scope(self.scope_name)
        return self.scope_instance

    def __exit__(self, *args):
        """Exit the scope."""
        self.container.exit_scope(self.scope_name)

    async def __aenter__(self):
        """Async enter."""
        self.scope_instance = self.container.enter_scope(self.scope_name)
        return self.scope_instance

    async def __aexit__(self, *args):
        """Async exit."""
        self.container.exit_scope(self.scope_name)
