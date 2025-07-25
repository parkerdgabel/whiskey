"""Simple scope implementations using context managers."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any, TypeVar

T = TypeVar("T")


class Scope:
    """Base scope using context managers for lifecycle management.
    
    Example:
        with Scope("request") as scope:
            # Services created in this scope
            db = await container.resolve(Database)
            # Automatically cleaned up when scope ends
    """
    
    def __init__(self, name: str):
        self.name = name
        self._instances: dict[type, Any] = {}
        
    def get(self, service_type: type[T]) -> T | None:
        """Get a scoped instance if it exists."""
        return self._instances.get(service_type)
        
    def set(self, service_type: type[T], instance: T) -> None:
        """Store a scoped instance."""
        self._instances[service_type] = instance
        
    def clear(self) -> None:
        """Clear all instances and run disposal."""
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
    REQUEST = "request"