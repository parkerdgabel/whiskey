"""Scope management for controlling service lifecycles.

This module provides the scope system for Whiskey's dependency injection,
allowing fine-grained control over when instances are created and destroyed.

Built-in scopes:
    - singleton: One instance for the entire application lifetime
    - transient: New instance for each resolution (default)
    - Custom scopes can be created by extending the Scope class
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any, TypeVar

T = TypeVar("T")


class Scope:
    """Base class for dependency injection scopes.
    
    A scope controls the lifecycle of service instances. When a service is
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
        ...     service1 = await container.resolve(RequestService)
        ...     service2 = await container.resolve(RequestService)
        ...     assert service1 is service2  # Same instance
        ... # Resources cleaned up here
    
    Attributes:
        name: The scope identifier
        _instances: Cache of instances created in this scope
    """
    
    def __init__(self, name: str):
        self.name = name
        self._instances: dict[type, Any] = {}
        
    def get(self, service_type: type[T]) -> T | None:
        """Get a scoped instance if it exists.
        
        Args:
            service_type: The type to look up
            
        Returns:
            The cached instance or None if not found
        """
        return self._instances.get(service_type)
        
    def set(self, service_type: type[T], instance: T) -> None:
        """Store a scoped instance.
        
        Args:
            service_type: The type to cache the instance under
            instance: The instance to cache
        """
        self._instances[service_type] = instance
        
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
            if hasattr(instance, 'dispose'):
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
            if hasattr(instance, 'dispose'):
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
        self._context_var: ContextVar[dict[type, Any]] = ContextVar(
            f"scope_{name}", default={}
        )
        
    def get(self, service_type: type[T]) -> T | None:
        """Get from context."""
        instances = self._context_var.get()
        return instances.get(service_type)
        
    def set(self, service_type: type[T], instance: T) -> None:
        """Set in context."""
        instances = self._context_var.get().copy()
        instances[service_type] = instance
        self._context_var.set(instances)
        
    def clear(self) -> None:
        """Clear context."""
        self._context_var.set({})


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