"""Scope management for Whiskey framework."""

from __future__ import annotations

import asyncio
import contextvars
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from whiskey.core.exceptions import ScopeError
from whiskey.core.types import Disposable, ScopeType, ServiceKey


class Scope(ABC):
    """Base class for all scopes."""

    def __init__(self, name: str):
        self.name = name
        self._instances: dict[ServiceKey, Any] = {}

    @abstractmethod
    async def get(self, key: ServiceKey) -> Any | None:
        """Get an instance from the scope."""
        pass

    @abstractmethod
    async def set(self, key: ServiceKey, instance: Any) -> None:
        """Store an instance in the scope."""
        pass

    @abstractmethod
    async def remove(self, key: ServiceKey) -> None:
        """Remove an instance from the scope."""
        pass

    @abstractmethod
    async def clear(self) -> None:
        """Clear all instances from the scope."""
        pass

    async def dispose(self) -> None:
        """Dispose of all instances in the scope."""
        for key, instance in list(self._instances.items()):
            if isinstance(instance, Disposable):
                try:
                    await instance.dispose()
                except Exception as e:
                    logger.error(f"Error disposing {key}: {e}")
        await self.clear()


class SingletonScope(Scope):
    """Scope that maintains a single instance for the application lifetime."""

    def __init__(self):
        super().__init__("singleton")
        self._lock = asyncio.Lock()

    async def get(self, key: ServiceKey) -> Any | None:
        return self._instances.get(key)

    async def set(self, key: ServiceKey, instance: Any) -> None:
        async with self._lock:
            if key not in self._instances:
                self._instances[key] = instance

    async def remove(self, key: ServiceKey) -> None:
        async with self._lock:
            self._instances.pop(key, None)

    async def clear(self) -> None:
        async with self._lock:
            self._instances.clear()


class TransientScope(Scope):
    """Scope that creates a new instance for each request."""

    def __init__(self):
        super().__init__("transient")

    async def get(self, key: ServiceKey) -> Any | None:
        # Always return None to force new instance creation
        return None

    async def set(self, key: ServiceKey, instance: Any) -> None:
        # Transient scope doesn't store instances
        pass

    async def remove(self, key: ServiceKey) -> None:
        # Nothing to remove in transient scope
        pass

    async def clear(self) -> None:
        # Nothing to clear in transient scope
        pass


@dataclass
class ScopedInstances:
    """Container for scoped instances."""

    instances: dict[ServiceKey, Any] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def get(self, key: ServiceKey) -> Any | None:
        return self.instances.get(key)

    async def set(self, key: ServiceKey, instance: Any) -> None:
        async with self._lock:
            self.instances[key] = instance

    async def remove(self, key: ServiceKey) -> None:
        async with self._lock:
            self.instances.pop(key, None)

    async def clear(self) -> None:
        async with self._lock:
            # Dispose of disposable instances
            for instance in self.instances.values():
                if isinstance(instance, Disposable):
                    try:
                        await instance.dispose()
                    except Exception as e:
                        logger.error(f"Error disposing instance: {e}")
            self.instances.clear()


class ContextVarScope(Scope):
    """Base class for scopes that use context variables."""

    def __init__(self, name: str):
        super().__init__(name)
        self._context_var: contextvars.ContextVar[ScopedInstances | None] = contextvars.ContextVar(
            f"whiskey_{name}_scope", default=None
        )

    def _get_instances(self) -> ScopedInstances | None:
        return self._context_var.get()

    def _ensure_instances(self) -> ScopedInstances:
        instances = self._get_instances()
        if instances is None:
            instances = ScopedInstances()
            self._context_var.set(instances)
        return instances

    async def get(self, key: ServiceKey) -> Any | None:
        instances = self._get_instances()
        if instances:
            return await instances.get(key)
        return None

    async def set(self, key: ServiceKey, instance: Any) -> None:
        instances = self._ensure_instances()
        await instances.set(key, instance)

    async def remove(self, key: ServiceKey) -> None:
        instances = self._get_instances()
        if instances:
            await instances.remove(key)

    async def clear(self) -> None:
        instances = self._get_instances()
        if instances:
            await instances.clear()
            self._context_var.set(None)


class RequestScope(ContextVarScope):
    """Scope for HTTP request lifecycle."""

    def __init__(self):
        super().__init__("request")


class SessionScope(ContextVarScope):
    """Scope for user session lifecycle."""

    def __init__(self):
        super().__init__("session")


class ConversationScope(ContextVarScope):
    """Scope for AI conversation lifecycle."""

    def __init__(self):
        super().__init__("conversation")


class AIContextScope(ContextVarScope):
    """Scope for AI context (prompt + response) lifecycle."""

    def __init__(self):
        super().__init__("ai_context")


class BatchScope(ContextVarScope):
    """Scope for batch processing lifecycle."""

    def __init__(self):
        super().__init__("batch")


class StreamScope(ContextVarScope):
    """Scope for streaming response lifecycle."""

    def __init__(self):
        super().__init__("stream")


class ScopeManager:
    """Manages all scopes in the container."""

    def __init__(self):
        self._scopes: dict[ScopeType, Scope] = {}
        self._custom_scopes: dict[str, Scope] = {}
        self._initialize_default_scopes()

    def _initialize_default_scopes(self):
        """Initialize core scopes only."""
        self._scopes[ScopeType.SINGLETON] = SingletonScope()
        self._scopes[ScopeType.TRANSIENT] = TransientScope()
        self._scopes[ScopeType.REQUEST] = RequestScope()

    def get_scope(self, scope_type: ScopeType | str) -> Scope:
        """Get a scope by type."""
        if isinstance(scope_type, ScopeType):
            scope = self._scopes.get(scope_type)
            if scope:
                return scope
        
        # Check custom scopes
        if isinstance(scope_type, str):
            scope = self._custom_scopes.get(scope_type)
            if scope:
                return scope
        
        raise ScopeError(f"Unknown scope: {scope_type}")

    def register_scope(self, name: str, scope: Scope) -> None:
        """Register a custom scope."""
        if name in self._custom_scopes:
            raise ScopeError(f"Scope '{name}' already registered")
        self._custom_scopes[name] = scope

    async def dispose_all(self) -> None:
        """Dispose all scopes."""
        for scope in self._scopes.values():
            await scope.dispose()
        for scope in self._custom_scopes.values():
            await scope.dispose()