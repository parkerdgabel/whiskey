"""Simplified container implementation using the unified resolver system.

This is a cleaner, more maintainable version of the container that delegates
all resolution logic to the unified resolver system.
"""

from __future__ import annotations

import asyncio
import inspect
from contextvars import ContextVar
from typing import Any, Callable, TypeVar

from .errors import ResolutionError
from .registry import ComponentDescriptor, ComponentRegistry, Scope
from .resolver import UnifiedResolver, create_resolver
from .scopes import ScopeManager

T = TypeVar("T")

# Context variables for scope management
_current_container: ContextVar[Container] = ContextVar("current_container", default=None)
_active_scopes: ContextVar[dict[str, dict[str, Any]] | None] = ContextVar(
    "active_scopes", default=None
)


class Container:
    """Simplified dependency injection container.
    
    This container provides a clean, Pythonic interface while delegating all
    complex resolution logic to the unified resolver system.
    """
    
    def __init__(self, parent: Container | None = None):
        """Initialize a new container.
        
        Args:
            parent: Optional parent container for hierarchical resolution
        """
        self.parent = parent
        self.registry = ComponentRegistry()
        self.resolver = create_resolver(self.registry)
    
    # Dict-like interface for registration
    
    def __setitem__(self, key: str | type, provider: Any) -> None:
        """Register a component using dict syntax."""
        if isinstance(key, tuple):
            # Support for named components: container[Service, 'name'] = impl
            key, name = key
            self.register(key, provider, name=name)
        else:
            self.register(key, provider)
    
    def __getitem__(self, key: str | type) -> Any:
        """Resolve a component using dict syntax."""
        try:
            return self.resolve_sync(key)
        except RuntimeError as e:
            if "async" in str(e).lower():
                raise RuntimeError(
                    f"Component '{key}' requires async resolution. "
                    f"Use 'await container.resolve({key})' instead of container[{key}]"
                ) from e
            raise
    
    def __contains__(self, key: str | type) -> bool:
        """Check if a component is registered."""
        return self.registry.has(key)
    
    def __delitem__(self, key: str | type) -> None:
        """Remove a component registration."""
        self.registry.remove(key)
    
    # Smart resolution methods
    
    def resolve(self, key: str | type, *, name: str | None = None, **context) -> Any:
        """Smart resolution that works in both sync and async contexts.
        
        In sync context: Returns the resolved instance
        In async context: Returns a coroutine
        """
        return self.resolver.resolve(key, name=name, scope_context=_active_scopes.get(), **context)
    
    def resolve_sync(self, key: str | type, *, name: str | None = None, **context) -> T:
        """Explicitly synchronous resolution."""
        if asyncio.get_running_loop() if asyncio._get_running_loop() else None:
            # Provide helpful error in async context
            raise RuntimeError(
                f"Cannot use resolve_sync() in async context. Use 'await resolve()' instead."
            )
        return self.resolver._resolve_sync(key, name=name, scope_context=_active_scopes.get(), **context)
    
    async def resolve_async(self, key: str | type, *, name: str | None = None, **context) -> T:
        """Explicitly asynchronous resolution."""
        return await self.resolver._resolve_async(key, name=name, scope_context=_active_scopes.get(), **context)
    
    # Function calling with injection
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Smart function calling with dependency injection."""
        if asyncio.get_running_loop() if asyncio._get_running_loop() else None:
            return self._call_async(func, *args, **kwargs)
        else:
            return self._call_sync(func, *args, **kwargs)
    
    def _call_sync(self, func: Callable, *args, **kwargs) -> Any:
        """Synchronous function calling with injection."""
        if asyncio.iscoroutinefunction(func):
            raise RuntimeError(f"Cannot call async function '{func.__name__}' synchronously")
        
        # Get injection plan
        analysis = self.resolver.type_resolver.analyze_callable(func)
        
        # Build final kwargs
        sig = inspect.signature(func)
        final_kwargs = {}
        
        for i, (param_name, param) in enumerate(sig.parameters.items()):
            if i < len(args):
                continue  # Provided via args
            
            if param_name in kwargs:
                final_kwargs[param_name] = kwargs[param_name]
            elif param_name in analysis:
                inject_result = analysis[param_name]
                if inject_result.decision.value == "inject":
                    final_kwargs[param_name] = self.resolve_sync(inject_result.type_hint)
                elif inject_result.decision.value == "optional":
                    try:
                        final_kwargs[param_name] = self.resolve_sync(inject_result.inner_type)
                    except ResolutionError:
                        final_kwargs[param_name] = None
        
        return func(*args, **final_kwargs)
    
    async def _call_async(self, func: Callable, *args, **kwargs) -> Any:
        """Asynchronous function calling with injection."""
        # Get injection plan
        analysis = self.resolver.type_resolver.analyze_callable(func)
        
        # Build final kwargs
        sig = inspect.signature(func)
        final_kwargs = {}
        
        for i, (param_name, param) in enumerate(sig.parameters.items()):
            if i < len(args):
                continue  # Provided via args
            
            if param_name in kwargs:
                final_kwargs[param_name] = kwargs[param_name]
            elif param_name in analysis:
                inject_result = analysis[param_name]
                if inject_result.decision.value == "inject":
                    final_kwargs[param_name] = await self.resolve_async(inject_result.type_hint)
                elif inject_result.decision.value == "optional":
                    try:
                        final_kwargs[param_name] = await self.resolve_async(inject_result.inner_type)
                    except ResolutionError:
                        final_kwargs[param_name] = None
        
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **final_kwargs)
        else:
            return func(*args, **final_kwargs)
    
    # Registration methods
    
    def register(
        self,
        key: str | type,
        provider: Any = None,
        *,
        scope: Scope = Scope.TRANSIENT,
        name: str | None = None,
        **metadata
    ) -> ComponentDescriptor:
        """Register a component with the container."""
        if provider is None and isinstance(key, type):
            provider = key
        
        return self.registry.register(
            key, provider, scope=scope, name=name, **metadata
        )
    
    def singleton(self, key: str | type, provider: Any = None, **kwargs) -> ComponentDescriptor:
        """Register a singleton component."""
        if provider is None and isinstance(key, type):
            provider = key
        return self.register(key, provider, scope=Scope.SINGLETON, **kwargs)
    
    def scoped(
        self, key: str | type, provider: Any = None, *, scope_name: str = "default", **kwargs
    ) -> ComponentDescriptor:
        """Register a scoped component."""
        if provider is None and isinstance(key, type):
            provider = key
        return self.register(
            key, provider, scope=Scope.SCOPED, metadata={"scope_name": scope_name}, **kwargs
        )
    
    def factory(self, key: str | type, factory_func: Callable, **kwargs) -> ComponentDescriptor:
        """Register a factory function."""
        return self.register(key, factory_func, **kwargs)
    
    # Scope management
    
    def scope(self, scope_name: str) -> ScopeManager:
        """Create a scope context manager."""
        return ScopeManager(self, scope_name)
    
    def enter_scope(self, scope_name: str) -> None:
        """Enter a named scope."""
        active_scopes = _active_scopes.get() or {}
        active_scopes = active_scopes.copy()
        active_scopes[scope_name] = {}
        _active_scopes.set(active_scopes)
    
    def exit_scope(self, scope_name: str) -> None:
        """Exit a named scope."""
        # Clear scope cache
        self.resolver.scope_resolver.clear_scope(scope_name)
        
        # Update context
        active_scopes = _active_scopes.get()
        if active_scopes and scope_name in active_scopes:
            active_scopes = active_scopes.copy()
            del active_scopes[scope_name]
            _active_scopes.set(active_scopes if active_scopes else None)
    
    # Generic type support
    
    def register_generic_implementation(self, generic_type: Any, concrete_type: type) -> None:
        """Register a concrete implementation for a generic type."""
        self.resolver.type_resolver.register_generic_implementation(generic_type, concrete_type)
    
    # Context management
    
    def __enter__(self):
        """Set as current container."""
        self._token = _current_container.set(self)
        return self
    
    def __exit__(self, *args):
        """Reset current container."""
        _current_container.reset(self._token)
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self.__enter__()
    
    async def __aexit__(self, *args):
        """Async context manager exit."""
        self.__exit__(*args)


# Helper functions

def get_current_container() -> Container | None:
    """Get the current container from context."""
    return _current_container.get()


def set_current_container(container: Container) -> None:
    """Set the current container in context."""
    _current_container.set(container)