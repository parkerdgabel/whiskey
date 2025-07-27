"""Test compatibility utilities for Whiskey.

This module contains deprecated methods and utilities that are maintained
for backward compatibility with existing tests.
"""

from typing import Any, Callable
import asyncio
import types
from contextvars import ContextVar
from .container import Container, _active_scopes


class ScopeContext:
    """Simple scope context for test compatibility."""
    def __init__(self, name: str):
        self.name = name


class ScopeContextManager:
    """Scope context manager for test compatibility."""
    def __init__(self, container: Container, scope_name: str):
        self.container = container
        self.scope_name = scope_name

    def __enter__(self):
        # Activate the scope in the context variable
        active_scopes = _active_scopes.get({})
        active_scopes[self.scope_name] = {}
        self._token = _active_scopes.set(active_scopes)
        return self.container.enter_scope(self.scope_name)

    def __exit__(self, *args):
        # Deactivate the scope
        _active_scopes.reset(self._token)
        self.container.exit_scope(self.scope_name)

    async def __aenter__(self):
        # Activate the scope in the context variable
        active_scopes = _active_scopes.get({})
        active_scopes[self.scope_name] = {}
        self._token = _active_scopes.set(active_scopes)
        return self.container.enter_scope(self.scope_name)

    async def __aexit__(self, *args):
        # Deactivate the scope
        _active_scopes.reset(self._token)
        self.container.exit_scope(self.scope_name)


def add_test_compatibility_methods(container: Container) -> None:
    """Add test compatibility methods to a container instance.
    
    This function patches a container with deprecated methods that some
    tests might still rely on. New code should not use these methods.
    
    Args:
        container: The container to patch
    """
    # Scope management methods
    def enter_scope(self, scope_name: str):
        """Enter a scope and return a scope context object."""
        if not hasattr(self, '_scopes'):
            self._scopes = {}
        
        scope_context = ScopeContext(scope_name)
        self._scopes[scope_name] = scope_context
        return scope_context

    def exit_scope(self, scope_name: str):
        """Exit a scope and clean up its services."""
        if hasattr(self, '_scopes') and scope_name in self._scopes:
            del self._scopes[scope_name]

    def scope(self, scope_name: str):
        """Create a scope context manager."""
        return ScopeContextManager(self, scope_name)

    # Lifecycle methods
    def on_startup(self, callback: Callable):
        """Register a startup callback."""
        if not hasattr(self, '_startup_callbacks'):
            self._startup_callbacks = []
        self._startup_callbacks.append(callback)

    def on_shutdown(self, callback: Callable):
        """Register a shutdown callback."""
        if not hasattr(self, '_shutdown_callbacks'):
            self._shutdown_callbacks = []
        self._shutdown_callbacks.append(callback)

    async def startup(self):
        """Run startup callbacks."""
        if hasattr(self, '_startup_callbacks'):
            for callback in self._startup_callbacks:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()

    async def shutdown(self):
        """Run shutdown callbacks."""
        if hasattr(self, '_shutdown_callbacks'):
            for callback in self._shutdown_callbacks:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()

    # Service lifecycle methods
    async def _initialize_service(self, service):
        """Initialize a service if it implements Initializable."""
        from .types import Initializable
        if isinstance(service, Initializable):
            await service.initialize()

    async def _dispose_service(self, service):
        """Dispose a service if it implements Disposable."""
        from .types import Disposable
        if isinstance(service, Disposable):
            await service.dispose()

    # Attach methods to container using types.MethodType for proper binding
    container.enter_scope = types.MethodType(enter_scope, container)
    container.exit_scope = types.MethodType(exit_scope, container)
    container.scope = types.MethodType(scope, container)
    container.on_startup = types.MethodType(on_startup, container)
    container.on_shutdown = types.MethodType(on_shutdown, container)
    container.startup = types.MethodType(startup, container)
    container.shutdown = types.MethodType(shutdown, container)
    container._initialize_service = types.MethodType(_initialize_service, container)
    container._dispose_service = types.MethodType(_dispose_service, container)


class TestContainer(Container):
    """Container subclass with test compatibility methods pre-applied.
    
    This is a convenience class for tests that need the deprecated methods.
    New tests should use the standard Container class.
    """
    
    def __init__(self):
        super().__init__()
        add_test_compatibility_methods(self)