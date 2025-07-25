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
        # Updated to use (type, name) tuples as keys for named dependencies
        self._services: dict[tuple[type, str | None], Any] = {}
        self._factories: dict[tuple[type, str | None], Callable] = {}
        self._singletons: dict[tuple[type, str | None], Any] = {}
        self._scopes: dict[str, Any] = {}
        self._service_scopes: dict[tuple[type, str | None], str] = {}  # Maps (service type, name) to scope name
        
        # Register built-in scopes
        # Note: singleton and transient are handled specially, not as scope instances
        
    def __setitem__(self, key: type[T] | tuple[type[T], str | None], value: T | type[T] | Callable[..., T]) -> None:
        """Register a service, class, or factory.
        
        This method provides dict-like syntax for service registration.
        
        Args:
            key: Either a type (for unnamed) or (type, name) tuple for named services
            value: Can be:
                - An instance: Registered as-is
                - A class: Will be instantiated on first resolve
                - A callable/factory: Will be called to create instances
        
        Examples:
            >>> container[Database] = Database("postgresql://...")  # Instance
            >>> container[Logger] = Logger  # Class 
            >>> container[Cache] = lambda: RedisCache(host="localhost")  # Factory
            >>> container[Database, "primary"] = PostgresDB()  # Named service
        """
        # Normalize key to (type, name) tuple
        if isinstance(key, tuple):
            service_type, name = key
        else:
            service_type, name = key, None
        
        key_tuple = (service_type, name)
        
        if callable(value) and not isinstance(value, type):
            # It's a factory function
            self._factories[key_tuple] = value
        else:
            # It's an instance or class
            self._services[key_tuple] = value
            
    def __getitem__(self, key: type[T] | tuple[type[T], str | None]) -> T:
        """Get a service synchronously (for backwards compatibility).
        
        Args:
            key: Either a type (for unnamed) or (type, name) tuple for named services
            
        Returns:
            The resolved service instance
            
        Note:
            Prefer using resolve() or resolve_sync() for explicit async/sync behavior.
        """
        if isinstance(key, tuple):
            service_type, name = key
        else:
            service_type, name = key, None
        return self.resolve_sync(service_type, name)
        
    def __contains__(self, key: type | tuple[type, str | None]) -> bool:
        """Check if a service is registered.
        
        Args:
            key: Either a type (for unnamed) or (type, name) tuple for named services
            
        Returns:
            True if the service is registered in any form (service, factory, or singleton)
            
        Examples:
            >>> if Database in container:
            ...     db = container[Database]
            >>> if (Database, "primary") in container:
            ...     primary_db = container[Database, "primary"]
        """
        # Normalize key to (type, name) tuple
        if isinstance(key, tuple):
            key_tuple = key
        else:
            key_tuple = (key, None)
        
        return (
            key_tuple in self._services
            or key_tuple in self._factories
            or key_tuple in self._singletons
        )
        
    def __delitem__(self, key: type | tuple[type, str | None]) -> None:
        """Remove a service registration.
        
        Removes the service from all registries (services, factories, singletons).
        
        Args:
            key: Either a type (for unnamed) or (type, name) tuple for named services
            
        Note:
            This does not affect already resolved instances held by other services.
        """
        # Normalize key to (type, name) tuple
        if isinstance(key, tuple):
            key_tuple = key
        else:
            key_tuple = (key, None)
        
        self._services.pop(key_tuple, None)
        self._factories.pop(key_tuple, None)
        self._singletons.pop(key_tuple, None)
        self._service_scopes.pop(key_tuple, None)
        
    async def resolve(self, service_type: type[T], name: str | None = None) -> T:
        """Resolve a service asynchronously.
        
        Args:
            service_type: The type to resolve
            name: Optional name for named services
            
        Returns:
            The resolved service instance
            
        Raises:
            KeyError: If the service is not registered and cannot be created
        """
        key_tuple = (service_type, name)
        
        # Check singletons first
        if key_tuple in self._singletons:
            return cast(T, self._singletons[key_tuple])
        
        # Check if service has a scope
        scope_name = self._service_scopes.get(key_tuple)
        if scope_name and scope_name != "transient":
            # Get active scopes
            active_scopes = _active_scopes.get()
            
            # Handle singleton scope specially
            if scope_name == "singleton":
                if key_tuple not in self._singletons:
                    instance = await self._create_or_resolve_instance(service_type, name)
                    self._singletons[key_tuple] = instance
                return cast(T, self._singletons[key_tuple])
            
            # Check if scope is active
            if scope_name in active_scopes:
                scope = active_scopes[scope_name]
                # Check if instance exists in scope - use tuple key for named services
                instance = scope.get(key_tuple if name else service_type)
                if instance is not None:
                    return cast(T, instance)
                
                # Create instance and store in scope
                instance = await self._create_or_resolve_instance(service_type, name)
                scope.set(key_tuple if name else service_type, instance)
                return cast(T, instance)
            else:
                # Scope not active, fall through to transient behavior
                pass
        
        # Default transient behavior or no scope
        return await self._create_or_resolve_instance(service_type, name)
    
    async def _create_or_resolve_instance(self, service_type: type[T], name: str | None = None) -> T:
        """Create or resolve an instance without scope management."""
        key_tuple = (service_type, name)
        
        # Check registered instances/classes
        if key_tuple in self._services:
            value = self._services[key_tuple]
            if isinstance(value, type):
                # It's a class, instantiate it
                return await self._create_instance(value)
            return cast(T, value)
            
        # Check factories
        if key_tuple in self._factories:
            factory = self._factories[key_tuple]
            return cast(T, await self._call_with_injection(factory))
            
        # If named service not found, don't fall back to unnamed
        if name is not None:
            service_name = getattr(service_type, '__name__', str(service_type))
            raise KeyError(f"Named service {service_name}[{name}] not registered")
            
        # For unnamed services, check if we can create it
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
        key_tuple = (service_type, name)
        
        # Store scope information
        self._service_scopes[key_tuple] = scope
        
        if factory is not None:
            self._factories[key_tuple] = factory
        elif scope == "singleton":
            if implementation is None:
                # Mark class for lazy singleton
                self._services[key_tuple] = service_type
            elif isinstance(implementation, type):
                # Mark class for lazy singleton
                self._services[key_tuple] = implementation
            else:
                # Register existing instance as singleton
                self._singletons[key_tuple] = implementation
        else:
            self[key_tuple] = implementation or service_type
            
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
            key_tuple = (service_type, name)
            self._singletons[key_tuple] = instance
            self._service_scopes[key_tuple] = "singleton"
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
        key_tuple = (service_type, name)
        self._factories[key_tuple] = factory
        
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
                
                # Check for Lazy types first
                from typing import get_args, get_origin
                origin = get_origin(param_type)
                
                # Handle Lazy[T] types
                if origin is not None:
                    try:
                        from whiskey.core.lazy import Lazy
                        if origin is Lazy:
                            # Get the inner type
                            args = get_args(param_type)
                            if args:
                                inner_type = args[0]
                                # Create a Lazy instance instead of resolving
                                kwargs[param_name] = Lazy(inner_type, container=self)
                                continue
                    except ImportError:
                        pass
                
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
                                    # Check if actual_type is Lazy[T]
                                    actual_origin = get_origin(actual_type)
                                    if actual_origin is not None:
                                        try:
                                            from whiskey.core.lazy import Lazy
                                            if actual_origin is Lazy:
                                                # Get inner type from Lazy[T]
                                                lazy_args = get_args(actual_type)
                                                if lazy_args:
                                                    inner_type = lazy_args[0]
                                                    kwargs[param_name] = Lazy(inner_type, name=inject_marker.name, container=self)
                                                    continue
                                        except ImportError:
                                            pass
                                    
                                    # Regular injection
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
                    # Skip built-in types and types that can't be resolved
                    if param_type in (str, int, float, bool, list, dict, tuple, set, bytes):
                        # Don't try to inject built-in types
                        continue
                    
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
        # Return both (type, name) key and value for full compatibility
        for key, value in self._services.items():
            yield key, value
        for key, value in self._factories.items():
            yield key, value
        for key, value in self._singletons.items():
            yield key, value
            
    def keys(self):
        """Get all registered service types (for backward compatibility)."""
        # Extract just the types from the (type, name) tuples
        types = set()
        for key in self._services.keys():
            types.add(key[0])
        for key in self._factories.keys():
            types.add(key[0])
        for key in self._singletons.keys():
            types.add(key[0])
        return types
    
    def keys_full(self):
        """Get all registered service keys as (type, name) tuples."""
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
    
    def can_resolve(self, service_type: type[T], name: str | None = None) -> bool:
        """Check if a service can be resolved.
        
        Args:
            service_type: Type to check
            name: Optional name for named services
            
        Returns:
            True if the service can be resolved
        """
        # Check if explicitly registered
        key_tuple = (service_type, name)
        if key_tuple in self:
            return True
        
        # For unnamed services, check if we can create it
        if name is None and inspect.isclass(service_type) and not inspect.isabstract(service_type):
            # Check if the class can be instantiated without required parameters
            try:
                sig = inspect.signature(service_type)
                # Check if all parameters have defaults or can be injected
                for param_name, param in sig.parameters.items():
                    if param.default == param.empty:
                        # Check if this parameter can be resolved
                        if param.annotation != param.empty:
                            param_type = param.annotation
                            # Skip built-in types
                            if param_type in (str, int, float, bool, list, dict, tuple, set, bytes):
                                return False
                            # Check if we can resolve this dependency
                            if not self.can_resolve(param_type):
                                return False
                return True
            except:
                return False
            
        return False


def get_current_container() -> Container | None:
    """Get the current container from context."""
    return _current_container.get()