"""Core container implementation for Whiskey framework."""

from __future__ import annotations

import asyncio
import inspect
from typing import Any, TypeVar, overload

from loguru import logger

from whiskey.core.exceptions import (
    InvalidServiceError,
)
from whiskey.core.resolver import DependencyResolver
from whiskey.core.scopes import ScopeManager, ScopeType
from whiskey.core.types import (
    ServiceDescriptor,
    ServiceFactory,
    ServiceKey,
)

T = TypeVar("T")


class Container:
    """Main dependency injection container."""

    def __init__(self, parent: Container | None = None):
        self._parent = parent
        self._services: dict[ServiceKey, ServiceDescriptor] = {}
        self._scope_manager = ScopeManager()
        self._resolver = DependencyResolver(self)
        self._is_disposed = False
        self._lock = asyncio.Lock()

    @property
    def parent(self) -> Container | None:
        """Get the parent container."""
        return self._parent

    @property
    def scope_manager(self) -> ScopeManager:
        """Get the scope manager."""
        return self._scope_manager

    # Service Registration Methods

    def register(
        self,
        service_type: type[T],
        implementation: type[T] | None = None,
        factory: ServiceFactory[T] | None = None,
        instance: T | None = None,
        scope: ScopeType | str = ScopeType.TRANSIENT,
        name: str | None = None,
        **metadata: Any,
    ) -> Container:
        """Register a service in the container."""
        if self._is_disposed:
            raise InvalidServiceError("Cannot register services in a disposed container")

        # Validate registration
        if sum(x is not None for x in [implementation, factory, instance]) != 1:
            raise InvalidServiceError(
                "Exactly one of implementation, factory, or instance must be provided"
            )

        # Create service key
        key = self._make_service_key(service_type, name)

        # Create descriptor
        descriptor = ServiceDescriptor(
            service_type=service_type,
            implementation=implementation,
            factory=factory,
            instance=instance,
            scope=scope if isinstance(scope, ScopeType) else ScopeType(scope),
            name=name,
            metadata=metadata,
        )

        # Extract dependencies if implementation provided
        if implementation:
            descriptor.dependencies = self._extract_dependencies(implementation)

        # Register the service
        self._services[key] = descriptor
        logger.debug(f"Registered service: {key} with scope {scope}")

        return self

    def register_singleton(
        self,
        service_type: type[T],
        implementation: type[T] | None = None,
        factory: ServiceFactory[T] | None = None,
        instance: T | None = None,
        name: str | None = None,
        **metadata: Any,
    ) -> Container:
        """Register a singleton service."""
        return self.register(
            service_type=service_type,
            implementation=implementation,
            factory=factory,
            instance=instance,
            scope=ScopeType.SINGLETON,
            name=name,
            **metadata,
        )

    def register_transient(
        self,
        service_type: type[T],
        implementation: type[T] | None = None,
        factory: ServiceFactory[T] | None = None,
        name: str | None = None,
        **metadata: Any,
    ) -> Container:
        """Register a transient service."""
        return self.register(
            service_type=service_type,
            implementation=implementation,
            factory=factory,
            scope=ScopeType.TRANSIENT,
            name=name,
            **metadata,
        )

    def register_scoped(
        self,
        scope: ScopeType | str,
        service_type: type[T],
        implementation: type[T] | None = None,
        factory: ServiceFactory[T] | None = None,
        name: str | None = None,
        **metadata: Any,
    ) -> Container:
        """Register a scoped service."""
        return self.register(
            service_type=service_type,
            implementation=implementation,
            factory=factory,
            scope=scope,
            name=name,
            **metadata,
        )

    # Service Resolution Methods

    @overload
    async def resolve(self, service_type: type[T], name: str | None = None) -> T:
        ...

    @overload
    async def resolve(self, service_type: str) -> Any:
        ...

    async def resolve(
        self, service_type: type[T] | str, name: str | None = None
    ) -> T | Any:
        """Resolve a service from the container."""
        if self._is_disposed:
            raise InvalidServiceError("Cannot resolve services from a disposed container")

        key = self._make_service_key(service_type, name)
        return await self._resolver.resolve(key)

    def resolve_sync(self, service_type: type[T], name: str | None = None) -> T:
        """Synchronously resolve a service (for non-async contexts)."""
        return asyncio.run(self.resolve(service_type, name))

    async def resolve_all(self, service_type: type[T]) -> list[T]:
        """Resolve all services of a given type."""
        instances = []
        
        # Find all matching services
        for key, descriptor in self._services.items():
            if isinstance(key, type) and issubclass(descriptor.service_type, service_type):
                instance = await self._resolver.resolve(key)
                instances.append(instance)
        
        # Check parent container
        if self._parent:
            parent_instances = await self._parent.resolve_all(service_type)
            instances.extend(parent_instances)
        
        return instances

    # Service Inspection Methods

    def has_service(self, service_type: type[T], name: str | None = None) -> bool:
        """Check if a service is registered."""
        key = self._make_service_key(service_type, name)
        if key in self._services:
            return True
        return self._parent.has_service(service_type, name) if self._parent else False

    def get_descriptor(
        self, service_type: type[T], name: str | None = None
    ) -> ServiceDescriptor | None:
        """Get the descriptor for a service."""
        key = self._make_service_key(service_type, name)
        descriptor = self._services.get(key)
        
        if descriptor is None and self._parent:
            return self._parent.get_descriptor(service_type, name)
        
        return descriptor

    def get_all_services(self) -> dict[ServiceKey, ServiceDescriptor]:
        """Get all registered services."""
        services = self._services.copy()
        
        if self._parent:
            # Include parent services that aren't overridden
            parent_services = self._parent.get_all_services()
            for key, descriptor in parent_services.items():
                if key not in services:
                    services[key] = descriptor
        
        return services

    # Container Management Methods

    def create_child(self) -> Container:
        """Create a child container."""
        return Container(parent=self)

    async def dispose(self) -> None:
        """Dispose of the container and all its resources."""
        if self._is_disposed:
            return

        async with self._lock:
            # Dispose all scopes
            await self._scope_manager.dispose_all()
            
            # Clear services
            self._services.clear()
            
            self._is_disposed = True
            logger.debug("Container disposed")

    # Private Methods

    def _make_service_key(
        self, service_type: type | str, name: str | None = None
    ) -> ServiceKey:
        """Create a service key from type and optional name."""
        if isinstance(service_type, str):
            return service_type
        
        if name:
            return f"{service_type.__module__}.{service_type.__name__}:{name}"
        
        return service_type

    def _extract_dependencies(self, implementation: type) -> list[ServiceKey]:
        """Extract dependencies from a class constructor."""
        dependencies = []
        
        # Get the __init__ method
        init_method = getattr(implementation, "__init__", None)
        if not init_method or init_method is object.__init__:
            return dependencies
        
        # Get signature
        sig = inspect.signature(init_method)
        
        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue
            
            # Get the type annotation
            if param.annotation != param.empty:
                # Handle both regular types and string annotations
                annotation = param.annotation
                if isinstance(annotation, str):
                    # For now, store string annotations as-is
                    dependencies.append(annotation)
                elif hasattr(annotation, "__module__"):
                    dependencies.append(annotation)
        
        return dependencies

    def __repr__(self) -> str:
        """String representation of the container."""
        service_count = len(self._services)
        return f"<Container services={service_count} parent={bool(self._parent)}>"
    
    # Syntactic Sugar Methods
    
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
    
    def __getitem__(self, service_type: type[T]) -> T:
        """Allow dict-like access to services."""
        return self.resolve_sync(service_type)
    
    def __contains__(self, service_type: type[T] | tuple[type[T], str]) -> bool:
        """Check if a service is registered using 'in' operator."""
        if isinstance(service_type, tuple):
            return self.has_service(service_type[0], service_type[1])
        return self.has_service(service_type)
    
    async def __aenter__(self) -> Container:
        """Async context manager support."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Cleanup on context exit."""
        await self.dispose()
    
    def __enter__(self) -> Container:
        """Sync context manager support."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Cleanup on context exit."""
        asyncio.run(self.dispose())
    
    def __len__(self) -> int:
        """Return the number of registered services."""
        return len(self.get_all_services())
    
    def __iter__(self):
        """Iterate over service keys."""
        return iter(self.get_all_services().keys())
    
    def items(self):
        """Get all services as key-value pairs."""
        return self.get_all_services().items()
    
    def keys(self):
        """Get all service keys."""
        return self.get_all_services().keys()
    
    def values(self):
        """Get all service descriptors."""
        return self.get_all_services().values()