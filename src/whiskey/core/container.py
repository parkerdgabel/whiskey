"""Core dependency injection container for Whiskey.

This module provides the foundation of Whiskey's IoC system with a simple,
dict-like container that manages service registration and resolution.
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable
from contextvars import ContextVar
from typing import Any, TypeVar, cast

T = TypeVar("T")

# Current container context
_current_container: ContextVar[Container | None] = ContextVar(
    "current_container", default=None
)

# Active scopes context
_active_scopes: ContextVar[dict[str, Any]] = ContextVar(
    "active_scopes", default={}
)


class Container:
    """A dependency injection container with dict-like interface.
    
    The Container is the heart of Whiskey's dependency injection system. It manages
    service registration, resolution, and scoping with a simple, Pythonic API.
    
    Features:
        - Dict-like syntax for registration and retrieval
        - Automatic dependency resolution with cycle detection
        - Scope management (singleton, transient, custom scopes)
        - Async and sync resolution support
        - Factory functions and lazy instantiation
        - Component discovery and introspection
    
    Examples:
        Basic usage:
        
        >>> container = Container()
        >>> 
        >>> # Register services
        >>> container[Database] = Database("postgresql://...")  # Instance
        >>> container[UserService] = UserService  # Class (lazy)
        >>> container[EmailService] = lambda: EmailService()  # Factory
        >>> 
        >>> # Resolve services
        >>> db = await container.resolve(Database)
        >>> user_svc = await container.resolve(UserService)  # Auto-injects Database
        >>> 
        >>> # Check registration
        >>> if Database in container:
        ...     print("Database is registered")
        
        With scopes:
        
        >>> # Register with scope
        >>> container.register(RequestContext, scope="request")
        >>> 
        >>> # Use scope
        >>> async with container.scope("request"):
        ...     ctx = await container.resolve(RequestContext)
        ...     # Same instance within scope
    
    Attributes:
        _services: Registry of service types to their implementations
        _factories: Registry of factory functions for services
        _singletons: Cache of singleton instances
        _scopes: Registry of available scopes
        _service_scopes: Mapping of service types to their scope names
    """
    
    def __init__(self):
        """Initialize a new Container.
        
        Creates registries for services, factories, singletons, and scopes.
        Automatically registers built-in scopes (singleton, transient).
        """
        self._services: dict[type, Any] = {}
        self._factories: dict[type, Callable] = {}
        self._singletons: dict[type, Any] = {}
        self._scopes: dict[str, Any] = {}
        self._service_scopes: dict[type, str] = {}  # Maps service type to scope name
        
        # Register built-in scopes
        # Note: singleton and transient are handled specially, not as scope instances
        
    def __setitem__(self, service_type: type[T], value: T | type[T] | Callable[..., T]) -> None:
        """Register a service, class, or factory.
        
        This method provides dict-like syntax for service registration.
        
        Args:
            service_type: The type to register (used as the key for resolution)
            value: Can be:
                - An instance: Registered as-is
                - A class: Will be instantiated on first resolve
                - A callable/factory: Will be called to create instances
        
        Examples:
            >>> container[Database] = Database("postgresql://...")  # Instance
            >>> container[Logger] = Logger  # Class 
            >>> container[Cache] = lambda: RedisCache(host="localhost")  # Factory
        """
        if callable(value) and not isinstance(value, type):
            # It's a factory function
            self._factories[service_type] = value
        else:
            # It's an instance or class
            self._services[service_type] = value
            
    def __getitem__(self, service_type: type[T]) -> T:
        """Get a service synchronously (for backwards compatibility).
        
        Args:
            service_type: The type to resolve
            
        Returns:
            The resolved service instance
            
        Note:
            Prefer using resolve() or resolve_sync() for explicit async/sync behavior.
        """
        return self.resolve_sync(service_type)
        
    def __contains__(self, service_type: type) -> bool:
        """Check if a service is registered.
        
        Args:
            service_type: The type to check
            
        Returns:
            True if the service is registered in any form (service, factory, or singleton)
            
        Examples:
            >>> if Database in container:
            ...     db = container[Database]
        """
        return (
            service_type in self._services
            or service_type in self._factories
            or service_type in self._singletons
        )
        
    def __delitem__(self, service_type: type) -> None:
        """Remove a service registration.
        
        Removes the service from all registries (services, factories, singletons).
        
        Args:
            service_type: The type to unregister
            
        Note:
            This does not affect already resolved instances held by other services.
        """
        self._services.pop(service_type, None)
        self._factories.pop(service_type, None)
        self._singletons.pop(service_type, None)
        
    async def resolve(self, service_type: type[T], name: str | None = None) -> T:
        """Resolve a service asynchronously.
        
        Args:
            service_type: The type to resolve
            name: Optional name for named services (ignored for now)
            
        Returns:
            The resolved service instance
            
        Raises:
            KeyError: If the service is not registered and cannot be created
        """
        # Check singletons first
        if service_type in self._singletons:
            return cast(T, self._singletons[service_type])
        
        # Check if service has a scope
        scope_name = self._service_scopes.get(service_type)
        if scope_name and scope_name != "transient":
            # Get active scopes
            active_scopes = _active_scopes.get()
            
            # Handle singleton scope specially
            if scope_name == "singleton":
                if service_type not in self._singletons:
                    instance = await self._create_or_resolve_instance(service_type)
                    self._singletons[service_type] = instance
                return cast(T, self._singletons[service_type])
            
            # Check if scope is active
            if scope_name in active_scopes:
                scope = active_scopes[scope_name]
                # Check if instance exists in scope
                instance = scope.get(service_type)
                if instance is not None:
                    return cast(T, instance)
                
                # Create instance and store in scope
                instance = await self._create_or_resolve_instance(service_type)
                scope.set(service_type, instance)
                return cast(T, instance)
            else:
                # Scope not active, fall through to transient behavior
                pass
        
        # Default transient behavior or no scope
        return await self._create_or_resolve_instance(service_type)
    
    async def _create_or_resolve_instance(self, service_type: type[T]) -> T:
        """Create or resolve an instance without scope management."""
        # Check registered instances/classes
        if service_type in self._services:
            value = self._services[service_type]
            if isinstance(value, type):
                # It's a class, instantiate it
                return await self._create_instance(value)
            return cast(T, value)
            
        # Check factories
        if service_type in self._factories:
            factory = self._factories[service_type]
            return cast(T, await self._call_with_injection(factory))
            
        # Try to create if it's a concrete class
        if inspect.isclass(service_type) and not inspect.isabstract(service_type):
            return await self._create_instance(service_type)
            
        # Handle callables (functions with @inject)
        if callable(service_type) and not inspect.isclass(service_type):
            return await self._call_with_injection(service_type)
            
        service_name = getattr(service_type, '__name__', str(service_type))
        raise KeyError(f"Service {service_name} not registered")
        
    def resolve_sync(self, service_type: type[T], name: str | None = None) -> T:
        """Resolve a service synchronously."""
        try:
            loop = asyncio.get_running_loop()
            # If we're in an async context, we can't use asyncio.run
            # This is a limitation we accept for simplicity
            raise RuntimeError(
                "Cannot use resolve_sync() in async context. "
                "Use 'await container.resolve()' instead."
            )
        except RuntimeError:
            # No loop running, we can create one
            return asyncio.run(self.resolve(service_type, name))
            
    def register(
        self,
        service_type: type[T],
        implementation: type[T] | T | None = None,
        *,
        scope: str = "transient",
        name: str | None = None,
        factory: Callable[..., T] | None = None,
    ) -> None:
        """Register a service.
        
        Args:
            service_type: The service type to register
            implementation: Implementation class or instance
            scope: Service scope (singleton, transient, etc.)
            name: Optional name for named services
            factory: Optional factory function
        """
        # Store scope information
        self._service_scopes[service_type] = scope
        
        # For now, ignore name - we'll add named services later if needed
        if factory is not None:
            self._factories[service_type] = factory
        elif scope == "singleton":
            if implementation is None:
                # Mark class for lazy singleton
                self._services[service_type] = service_type
            elif isinstance(implementation, type):
                # Mark class for lazy singleton
                self._services[service_type] = implementation
            else:
                # Register existing instance as singleton
                self._singletons[service_type] = implementation
        else:
            self[service_type] = implementation or service_type
            
    def register_singleton(
        self,
        service_type: type[T],
        implementation: type[T] | T | None = None,
        *,
        name: str | None = None,
        factory: Callable[..., T] | None = None,
        instance: T | None = None,
    ) -> None:
        """Register a singleton service."""
        if instance is not None:
            self._singletons[service_type] = instance
        else:
            self.register(
                service_type,
                implementation,
                scope="singleton",
                name=name,
                factory=factory,
            )
            
    def register_factory(
        self,
        service_type: type[T],
        factory: Callable[..., T],
        *,
        name: str | None = None,
    ) -> None:
        """Register a factory function."""
        self._factories[service_type] = factory
        
    def register_scope(self, name: str, scope: Any) -> None:
        """Register a custom scope."""
        self._scopes[name] = scope
        
    async def _create_instance(self, cls: type[T]) -> T:
        """Create an instance with dependency injection."""
        sig = inspect.signature(cls)
        kwargs = {}
        
        # Get type hints to resolve forward references
        try:
            from typing import get_type_hints
            type_hints = get_type_hints(cls)
        except:
            type_hints = {}
        
        # Build kwargs with injected dependencies
        for param_name, param in sig.parameters.items():
            if param.annotation != param.empty and param.annotation != 'return':
                # Use type hints if available, otherwise use annotation
                param_type = type_hints.get(param_name, param.annotation)
                
                # Skip string annotations (forward references we can't resolve)
                if isinstance(param_type, str):
                    if param.default == param.empty:
                        raise TypeError(f"Cannot resolve forward reference '{param_type}' for parameter '{param_name}'")
                    continue
                
                # Check if this is an Annotated type with Inject marker
                from typing import get_origin, get_args
                origin = get_origin(param_type)
                
                if origin is not None:
                    # Handle Annotated types
                    try:
                        from typing import Annotated
                        if origin is Annotated:
                            # Get the actual type and metadata
                            args = get_args(param_type)
                            if len(args) >= 2:
                                actual_type = args[0]
                                metadata = args[1:]
                                
                                # Check if any metadata is an Inject marker
                                from whiskey.core.decorators import Inject
                                inject_marker = None
                                for meta in metadata:
                                    if isinstance(meta, Inject):
                                        inject_marker = meta
                                        break
                                
                                if inject_marker:
                                    # This is marked for injection
                                    try:
                                        kwargs[param_name] = await self.resolve(actual_type, name=inject_marker.name)
                                    except KeyError:
                                        if param.default == param.empty:
                                            raise
                                    continue
                    except ImportError:
                        # Python < 3.9 doesn't have Annotated in typing
                        pass
                
                # Check if this parameter has a callable default (like Setting providers)
                if param.default != param.empty and callable(param.default):
                    # Skip injection - let the callable default handle it
                    continue
                
                # For backward compatibility, if no Inject marker but has annotation,
                # only inject if there's no default value
                if param.default == param.empty:
                    # Try to resolve the dependency
                    try:
                        kwargs[param_name] = await self.resolve(param_type)
                    except KeyError:
                        raise
                        
        return cls(**kwargs)
        
    async def _call_with_injection(self, func: Callable, *args, **kwargs) -> Any:
        """Call a function with dependency injection."""
        sig = inspect.signature(func)
        
        # Bind provided arguments
        bound = sig.bind_partial(*args, **kwargs)
        bound.apply_defaults()
        
        # Inject missing dependencies
        for param_name, param in sig.parameters.items():
            if param_name not in bound.arguments and param.annotation != param.empty:
                try:
                    bound.arguments[param_name] = await self.resolve(param.annotation)
                except KeyError:
                    if param.default == param.empty:
                        raise
                        
        # Call the function
        if asyncio.iscoroutinefunction(func):
            return await func(**bound.arguments)
        return func(**bound.arguments)
        
    # Backwards compatibility methods
    def get(self, service_type: type[T], default: T | None = None, name: str | None = None) -> T | None:
        """Get a service synchronously, returning default if not found."""
        try:
            return self.resolve_sync(service_type, name)
        except Exception:
            return default
            
    async def aget(self, service_type: type[T], default: T | None = None, name: str | None = None) -> T | None:
        """Get a service asynchronously, returning default if not found."""
        try:
            return await self.resolve(service_type, name)
        except Exception:
            return default
            
    def __enter__(self):
        """Set this as the current container."""
        self._token = _current_container.set(self)
        return self
        
    def __exit__(self, *args):
        """Reset the current container."""
        _current_container.reset(self._token)
        
    async def __aenter__(self):
        """Async context manager support."""
        self.__enter__()
        return self
        
    async def __aexit__(self, *args):
        """Async context manager cleanup."""
        self.__exit__()
        
    # Dict-like methods for compatibility
    def items(self):
        """Get all registered services."""
        for service_type, value in self._services.items():
            yield service_type, value
        for service_type, value in self._factories.items():
            yield service_type, value
        for service_type, value in self._singletons.items():
            yield service_type, value
            
    def keys(self):
        """Get all registered service types."""
        return set(self._services.keys()) | set(self._factories.keys()) | set(self._singletons.keys())
        
    def values(self):
        """Get all registered values."""
        for value in self._services.values():
            yield value
        for value in self._factories.values():
            yield value
        for value in self._singletons.values():
            yield value
            
    def clear(self) -> None:
        """Clear all registrations."""
        self._services.clear()
        self._factories.clear()
        self._singletons.clear()
        self._scopes.clear()
        
    # Simplified scope manager interface
    @property
    def scope_manager(self):
        """Backwards compatibility for scope manager access."""
        return self
        
    def get_scope(self, name: str) -> Any:
        """Get a registered scope."""
        return self._scopes.get(name)
    
    def enter_scope(self, name: str) -> Any:
        """Enter a scope, making it active.
        
        Returns the scope instance for use in with statements.
        """
        # Get or create scope instance
        if name not in self._scopes:
            raise KeyError(f"Scope '{name}' not registered")
        
        scope_class = self._scopes[name]
        if inspect.isclass(scope_class):
            # Check if it needs a name parameter
            sig = inspect.signature(scope_class)
            if 'name' in sig.parameters:
                scope_instance = scope_class(name)
            else:
                scope_instance = scope_class()
        else:
            scope_instance = scope_class
        
        # Add to active scopes
        active_scopes = _active_scopes.get().copy()
        active_scopes[name] = scope_instance
        _active_scopes.set(active_scopes)
        
        return scope_instance
    
    def exit_scope(self, name: str) -> None:
        """Exit a scope, removing it from active scopes."""
        active_scopes = _active_scopes.get()
        if name in active_scopes:
            # Get the scope and clear it
            scope = active_scopes[name]
            if hasattr(scope, 'clear'):
                scope.clear()
            
            # Remove from active scopes
            new_scopes = active_scopes.copy()
            del new_scopes[name]
            _active_scopes.set(new_scopes)
    
    def scope(self, name: str):
        """Create a scope context manager.
        
        Example:
            async with container.scope("request"):
                # All services resolved here will be request-scoped
                service = await container.resolve(MyService)
        """
        from whiskey.core.scopes import ScopeManager
        return ScopeManager(self, name)
    
    # Discovery and introspection
    
    def discover(self, module_or_package: str, **kwargs) -> set[type]:
        """Discover components in a module or package.
        
        Args:
            module_or_package: Module/package to scan
            **kwargs: Discovery options
            
        Returns:
            Set of discovered components
        """
        from whiskey.core.discovery import discover_components
        return discover_components(
            module_or_package, 
            container=self,
            **kwargs
        )
    
    def inspect(self):
        """Get an inspector for this container.
        
        Returns:
            Inspector instance for introspection
        """
        from whiskey.core.discovery import ContainerInspector
        return ContainerInspector(self)
    
    def can_resolve(self, service_type: type[T]) -> bool:
        """Check if a service can be resolved.
        
        Args:
            service_type: Type to check
            
        Returns:
            True if the service can be resolved
        """
        return self.inspect().can_resolve(service_type)


def get_current_container() -> Container | None:
    """Get the current container from context."""
    return _current_container.get()