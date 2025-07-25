"""Simple, Pythonic dependency injection container."""

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


class Container:
    """A simple dependency injection container with dict-like interface.
    
    Examples:
        container = Container()
        
        # Register services
        container[Database] = Database("connection_string")  # Instance
        container[UserService] = UserService  # Class (auto-instantiated)
        container[EmailService] = lambda: EmailService()  # Factory
        
        # Resolve services
        db = await container.resolve(Database)
        
        # Check registration
        if Database in container:
            print("Database is registered")
    """
    
    def __init__(self):
        self._services: dict[type, Any] = {}
        self._factories: dict[type, Callable] = {}
        self._singletons: dict[type, Any] = {}
        self._scopes: dict[str, Any] = {}
        
    def __setitem__(self, service_type: type[T], value: T | type[T] | Callable[..., T]) -> None:
        """Register a service, class, or factory."""
        if callable(value) and not isinstance(value, type):
            # It's a factory function
            self._factories[service_type] = value
        else:
            # It's an instance or class
            self._services[service_type] = value
            
    def __getitem__(self, service_type: type[T]) -> T:
        """Get a service synchronously (for backwards compatibility)."""
        return self.resolve_sync(service_type)
        
    def __contains__(self, service_type: type) -> bool:
        """Check if a service is registered."""
        return (
            service_type in self._services
            or service_type in self._factories
            or service_type in self._singletons
        )
        
    def __delitem__(self, service_type: type) -> None:
        """Remove a service registration."""
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
            
        # Check registered instances/classes
        if service_type in self._services:
            value = self._services[service_type]
            if isinstance(value, type):
                # Check if it's marked as singleton
                if hasattr(value, "_singleton") and value._singleton:
                    # Check if we already have an instance
                    if service_type not in self._singletons:
                        # Create and cache the singleton
                        instance = await self._create_instance(value)
                        self._singletons[service_type] = instance
                    return cast(T, self._singletons[service_type])
                else:
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
        # For now, ignore name - we'll add named services later if needed
        if factory is not None:
            self._factories[service_type] = factory
        elif scope == "singleton":
            if implementation is None:
                # Mark class for lazy singleton
                self._services[service_type] = service_type
                if inspect.isclass(service_type):
                    service_type._singleton = True
            elif isinstance(implementation, type):
                # Mark class for lazy singleton
                self._services[service_type] = implementation
                implementation._singleton = True
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
                    
                # Try to resolve the dependency
                try:
                    kwargs[param_name] = await self.resolve(param_type)
                except KeyError:
                    if param.default == param.empty:
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


def get_current_container() -> Container | None:
    """Get the current container from context."""
    return _current_container.get()