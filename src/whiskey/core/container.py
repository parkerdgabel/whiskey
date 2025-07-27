"""Component container with dict-like interface and automatic dependency resolution.

This module implements Whiskey's core Container class, which serves as the central
component registry and dependency resolver. The Container provides a Pythonic,
dict-like interface for component registration while handling complex dependency
graphs, circular dependency detection, and scope management automatically.

Key Features:
    - Dict-like syntax: container[Component] = implementation
    - Automatic dependency injection based on type hints
    - Scope management (singleton, transient, scoped)
    - Circular dependency detection with clear error messages
    - Async-first design with sync compatibility
    - Performance optimizations with caching

Classes:
    Container: Main component container with automatic dependency resolution
    
Functions:
    get_current_container: Get the current container from context
    set_current_container: Set the current container in context

Example:
    >>> container = Container()
    >>> 
    >>> # Register components using dict syntax
    >>> container[Database] = PostgresDatabase
    >>> container['cache'] = RedisCache()
    >>> 
    >>> # Register with specific scopes
    >>> container.singleton(Logger)
    >>> container.scoped(RequestContext, scope_name='request')
    >>> 
    >>> # Resolve with automatic dependency injection
    >>> component = await container.resolve(UserService)
    >>> # UserService dependencies are automatically resolved
    
See Also:
    - whiskey.core.registry: Component metadata and registration
    - whiskey.core.analyzer: Type analysis for injection decisions
    - whiskey.core.scopes: Lifecycle scope management
"""

from __future__ import annotations

import asyncio
import inspect
from contextvars import ContextVar
from functools import wraps
from typing import Any, Callable, TypeVar
from weakref import WeakKeyDictionary

from .analyzer import InjectDecision, TypeAnalyzer
from .errors import (
    CircularDependencyError,
    InjectionError,
    ResolutionError,
    ScopeError,
    TypeAnalysisError,
)
from .performance import (
    WeakValueCache,
    is_performance_monitoring_enabled,
    monitor_resolution,
    record_error,
)
from .registry import Scope, ComponentDescriptor, ComponentRegistry

T = TypeVar("T")

# Context variables for scope management
_current_container: ContextVar[Container] = ContextVar("current_container", default=None)
_active_scopes: ContextVar[dict[str, dict[str, Any]] | None] = ContextVar("active_scopes", default=None)


# Removed ContainerComponentBuilder - using direct method chaining instead


class Container:
    """Pythonic dependency injection container.

    This is the main container class that provides a clean, dict-like interface
    for component registration and resolution with smart dependency injection.

    Features:
        - Dict-like interface: container['component'] = implementation
        - Smart type analysis for automatic injection
        - Scope management (singleton, transient, scoped)
        - Circular dependency detection
        - Clear error messages
        - Performance optimization with caching

    Examples:
        Basic usage:

        >>> container = Container()
        >>> container['database'] = Database()  # Register instance
        >>> container[EmailService] = EmailService  # Register class
        >>>
        >>> db = container['database']  # Get instance
        >>> email = await container.resolve(EmailService)  # Resolve with DI

        Auto-injection:

        >>> class UserService:
        ...     def __init__(self, db: Database, email: EmailService):
        ...         self.db = db
        ...         self.email = email
        >>>
        >>> container[UserService] = UserService  # Dependencies auto-injected
        >>> user_svc = await container.resolve(UserService)
    """

    def __init__(self):
        """Initialize a new Container."""
        self.registry = ComponentRegistry()
        self.analyzer = TypeAnalyzer(self.registry)

        # Instance caches for different scopes
        self._singleton_cache: dict[str, Any] = {}
        self._scoped_caches: dict[str, dict[str, Any]] = {}

        # Track resolution in progress to detect circular dependencies
        self._resolving: set[str] = set()

        # Cache for expensive operations
        self._injection_cache: WeakKeyDictionary = WeakKeyDictionary()

        # Performance optimizations
        self._weak_cache = WeakValueCache()
        self._resolution_depth = 0

    # Dict-like interface

    def __setitem__(self, key: str | type, value: Any) -> None:
        """Register a component using dict-like syntax.

        Args:
            key: Component key (string or type, or tuple for named components)
            value: Component implementation (class, instance, or factory)

        Examples:
            >>> container['database'] = Database()  # Instance
            >>> container[EmailService] = EmailService  # Class
            >>> container['cache'] = lambda: RedisCache()  # Factory
            >>> container[EmailService, 'primary'] = EmailService()  # Named component
        """
        # Validate key type
        if isinstance(key, tuple):
            # Handle named component registration: (type, name)
            if len(key) != 2:
                raise ValueError("Tuple key must have exactly 2 elements: (type, name)")
            component_type, name = key
            if not isinstance(component_type, (str, type)) or not isinstance(name, str):
                raise ValueError("Tuple key must be (str|type, str)")
            self.registry.register(component_type, value, name=name, allow_override=True)
        elif isinstance(key, (str, type)):
            self.registry.register(key, value, allow_override=True)
        else:
            raise ValueError(f"Invalid key type: {type(key)}. Must be str, type, or tuple")

    def __getitem__(self, key: str | type) -> Any:
        """Get a component using dict-like syntax.

        Args:
            key: Component key (string or type)

        Returns:
            The resolved component instance

        Examples:
            >>> db = container['database']
            >>> email = container[EmailService]
        """
        # Check if component is registered first
        if key not in self:
            raise KeyError(f"Component '{key}' not found in container")
        # Always use synchronous resolution for dict-like access
        return self.resolve_sync(key)

    def __contains__(self, key: str | type) -> bool:
        """Check if a component is registered.

        Args:
            key: Component key (string or type)

        Returns:
            True if the component is registered and condition is met
        """
        # First check if registered without a name
        if self.registry.has(key):
            return True
        
        # If key is a type, check if it's registered with any name
        if isinstance(key, type):
            # Check if any components of this type are registered
            descriptors = self.registry.find_by_type(key)
            return len(descriptors) > 0
            
        return False

    def __delitem__(self, key: str | type) -> None:
        """Remove a component registration.

        Args:
            key: Component key (string or type)
        """
        string_key = self.registry._normalize_key(key)

        # Remove from registry
        if not self.registry.remove(key):
            raise KeyError(f"Component '{key}' not found")

        # Clear from caches
        self._singleton_cache.pop(string_key, None)
        for scope_cache in self._scoped_caches.values():
            scope_cache.pop(string_key, None)

    def __len__(self) -> int:
        """Get number of registered components."""
        return len(self.registry)

    def __iter__(self):
        """Iterate over component keys."""
        return iter(desc.component_type for desc in self.registry.list_all())

    def keys(self):
        """Get all registered component keys."""
        return [desc.component_type for desc in self.registry.list_all()]

    def items(self):
        """Get all registered component key-descriptor pairs."""
        return [(desc.component_type, desc) for desc in self.registry.list_all()]

    def clear(self):
        """Clear all registered components."""
        self.registry.clear()

    # Main resolution methods

    @monitor_resolution
    async def resolve(self, key: str | type, *, name: str | None = None, **context) -> T:
        """Resolve a component asynchronously.

        This is the main resolution method that handles all the smart
        dependency injection logic.

        Args:
            key: Component key (string or type)
            name: Optional name for named components
            **context: Additional context for scoped resolution

        Returns:
            The resolved component instance

        Raises:
            ResolutionError: If the component cannot be resolved
            CircularDependencyError: If circular dependencies are detected
        """
        # Normalize the key
        string_key = self.registry._normalize_key(key, name)

        # Check for circular dependency
        if string_key in self._resolving:
            if is_performance_monitoring_enabled():
                record_error("circular_dependency")
            raise CircularDependencyError(self._get_resolution_cycle(string_key))

        try:
            self._resolving.add(string_key)
            self._resolution_depth += 1
            return await self._do_resolve(key, name, context)
        finally:
            self._resolving.discard(string_key)
            self._resolution_depth -= 1

    def resolve_sync(self, key: str | type, *, name: str | None = None, overrides: dict | None = None, **context) -> T:
        """Resolve a component synchronously.

        Args:
            key: Component key (string or type)
            name: Optional name for named components
            overrides: Override values for dependency injection
            **context: Additional context for scoped resolution

        Returns:
            The resolved component instance
        """
        # Check if the provider is an async factory before attempting sync resolution
        try:
            descriptor = self.registry.get(key, name)
            if callable(descriptor.provider) and asyncio.iscoroutinefunction(descriptor.provider):
                raise RuntimeError(f"Cannot resolve async factory '{key}' synchronously")
        except KeyError:
            pass  # Component not registered, let normal resolution handle it
        
        # Pass overrides through context
        if overrides:
            context['overrides'] = overrides
        
        # Handle case where we're already in an event loop
        try:
            asyncio.get_running_loop()
            # We're in an event loop - we can't use asyncio.run
            # Instead, we need to resolve this synchronously by implementing sync resolution logic
            return self._resolve_sync_internal(key, name, context)
        except RuntimeError:
            # No event loop running, use asyncio.run
            return asyncio.run(self.resolve(key, name=name, **context))

    def _resolve_sync_internal(self, key: str | type, name: str | None = None, context: dict | None = None) -> Any:
        """Internal synchronous resolution implementation for when we're in an async context."""
        # Normalize the key
        string_key = self.registry._normalize_key(key, name)

        # Check for circular dependency
        if string_key in self._resolving:
            raise CircularDependencyError(self._get_resolution_cycle(string_key))

        try:
            self._resolving.add(string_key)
            self._resolution_depth += 1
            return self._do_resolve_sync(key, name, context)
        finally:
            self._resolving.discard(string_key)
            self._resolution_depth -= 1

    def _do_resolve_sync(self, key: str | type, name: str | None = None, context: dict | None = None) -> Any:
        """Synchronous version of _do_resolve."""
        # Get the component descriptor
        try:
            descriptor = self.registry.get(key, name)
        except KeyError:
            # Component not explicitly registered - try auto-creation
            if isinstance(key, type):
                # Check if it's an abstract class
                import inspect
                if inspect.isabstract(key):
                    raise KeyError(f"{key.__name__} not registered") from None
                return self._try_auto_create_sync(key)
            raise ResolutionError(f"Component '{key}' not registered") from None


        # Handle different scopes
        if descriptor.scope == Scope.SINGLETON:
            return self._resolve_singleton_sync(descriptor, context)
        elif descriptor.scope == Scope.SCOPED:
            return self._resolve_scoped_sync(descriptor, context or {})
        else:  # Transient
            return self._create_instance_sync(descriptor, context)

    def _resolve_singleton_sync(self, descriptor: ComponentDescriptor, context: dict | None = None) -> Any:
        """Synchronous singleton resolution."""
        if descriptor.key not in self._singleton_cache:
            instance = self._create_instance_sync(descriptor, context)
            self._singleton_cache[descriptor.key] = instance
        return self._singleton_cache[descriptor.key]

    def _resolve_scoped_sync(self, descriptor: ComponentDescriptor, context: dict) -> Any:
        """Synchronous scoped resolution."""
        # Get active scopes
        active_scopes = _active_scopes.get()
        if active_scopes is None:
            active_scopes = {}

        # Find the appropriate scope - check component metadata first
        scope_name = descriptor.metadata.get("scope_name", context.get("scope", "default"))

        if scope_name not in active_scopes:
            raise ScopeError(f"Scope '{scope_name}' is not active")

        scope_cache = self._scoped_caches.setdefault(scope_name, {})

        if descriptor.key not in scope_cache:
            instance = self._create_instance_sync(descriptor, context)
            scope_cache[descriptor.key] = instance

        return scope_cache[descriptor.key]

    def _create_instance_sync(self, descriptor: ComponentDescriptor, context: dict | None = None) -> Any:
        """Synchronous instance creation."""
        provider = descriptor.provider

        if isinstance(provider, type):
            # Class - instantiate with dependency injection
            return self._instantiate_class_sync(provider, context)
        elif callable(provider):
            # Factory function - call with dependency injection
            return self._call_with_injection_sync(provider, context)
        else:
            # Instance - return as-is
            return provider

    def _instantiate_class_sync(self, cls: type, context: dict | None = None) -> Any:
        """Synchronous class instantiation."""
        # Check cache first
        if cls in self._injection_cache:
            injection_plan = self._injection_cache[cls]
        else:
            # Analyze the class constructor
            injection_plan = self._analyze_constructor(cls)
            self._injection_cache[cls] = injection_plan

        # Get overrides from context
        overrides = context.get('overrides', {}) if context else {}

        # Resolve dependencies
        kwargs = {}
        for param_name, inject_result in injection_plan.items():
            # Check if parameter has an override
            if param_name in overrides:
                kwargs[param_name] = overrides[param_name]
            elif inject_result.decision == InjectDecision.YES:
                kwargs[param_name] = self._resolve_sync_internal(inject_result.type_hint)
            elif inject_result.decision == InjectDecision.OPTIONAL:
                # For optional dependencies, only inject if explicitly registered
                if self.registry.has(inject_result.inner_type):
                    try:
                        kwargs[param_name] = self._resolve_sync_internal(inject_result.inner_type)
                    except ResolutionError:
                        kwargs[param_name] = None
                else:
                    kwargs[param_name] = None
            elif inject_result.decision == InjectDecision.ERROR:
                # Check if it's a forward reference error - convert to TypeError as expected by tests
                if "Cannot resolve forward reference" in inject_result.reason:
                    raise TypeError(inject_result.reason)
                else:
                    raise InjectionError(
                        f"Cannot inject parameter '{param_name}': {inject_result.reason}",
                        param_name,
                        inject_result.type_hint,
                    )

        # Create the instance
        try:
            return cls(**kwargs)
        except Exception as e:
            raise ResolutionError(
                f"Failed to instantiate {cls.__name__}: {e}", cls.__name__.lower(), e
            ) from e

    def _call_with_injection_sync(self, func: Callable, context: dict | None = None) -> Any:
        """Synchronous function call with injection."""
        # Check cache first
        if func in self._injection_cache:
            injection_plan = self._injection_cache[func]
        else:
            # Analyze the function
            injection_plan = self.analyzer.analyze_callable(func)
            self._injection_cache[func] = injection_plan

        # Get overrides from context
        overrides = context.get('overrides', {}) if context else {}

        # Resolve dependencies
        kwargs = {}
        for param_name, inject_result in injection_plan.items():
            # Check if parameter has an override
            if param_name in overrides:
                kwargs[param_name] = overrides[param_name]
            elif inject_result.decision == InjectDecision.YES:
                kwargs[param_name] = self._resolve_sync_internal(inject_result.type_hint)
            elif inject_result.decision == InjectDecision.OPTIONAL:
                # For optional dependencies, only inject if explicitly registered
                if self.registry.has(inject_result.inner_type):
                    try:
                        kwargs[param_name] = self._resolve_sync_internal(inject_result.inner_type)
                    except ResolutionError:
                        kwargs[param_name] = None
                else:
                    kwargs[param_name] = None
            elif inject_result.decision == InjectDecision.ERROR:
                # Check if it's a forward reference error - convert to TypeError as expected by tests
                if "Cannot resolve forward reference" in inject_result.reason:
                    raise TypeError(inject_result.reason)
                else:
                    raise InjectionError(
                        f"Cannot inject parameter '{param_name}': {inject_result.reason}",
                        param_name,
                        inject_result.type_hint,
                    )

        # Call the function
        try:
            result = func(**kwargs)
            # For sync resolution, we can't await async results, so this is a limitation
            if asyncio.iscoroutine(result):
                raise RuntimeError(f"Cannot call async factory '{func}' in synchronous context")
            return result
        except Exception as e:
            func_name = getattr(func, "__name__", str(func))
            raise ResolutionError(f"Failed to call {func_name}: {e}", func_name, e) from e

    def _try_auto_create_sync(self, cls: type) -> Any:
        """Synchronous auto-creation."""
        if not inspect.isclass(cls):
            raise ResolutionError(f"Cannot auto-create non-class: {cls}")

        if not self.analyzer.can_auto_create(cls):
            raise ResolutionError(
                f"Cannot auto-create {cls.__name__}: not all parameters can be injected"
            )

        # Auto-create by instantiating
        return self._instantiate_class_sync(cls)

    async def _do_resolve(self, key: str | type, name: str | None = None, context: dict | None = None) -> Any:
        """Internal resolution implementation.

        Args:
            key: Component key (string or type)
            name: Optional name for named components
            context: Resolution context

        Returns:
            The resolved component instance
        """
        # Get the component descriptor
        try:
            descriptor = self.registry.get(key, name)
        except KeyError:
            # Component not explicitly registered - try auto-creation
            if isinstance(key, type):
                # Check if it's an abstract class
                import inspect
                if inspect.isabstract(key):
                    raise KeyError(f"{key.__name__} not registered") from None
                return await self._try_auto_create(key)
            raise ResolutionError(f"Component '{key}' not registered") from None


        # Handle different scopes
        if descriptor.scope == Scope.SINGLETON:
            return await self._resolve_singleton(descriptor, context)
        elif descriptor.scope == Scope.SCOPED:
            return await self._resolve_scoped(descriptor, context or {})
        else:  # Transient
            return await self._create_instance(descriptor, context)

    async def _resolve_singleton(self, descriptor: ComponentDescriptor, context: dict | None = None) -> Any:
        """Resolve a singleton component.

        Args:
            descriptor: The component descriptor
            context: Resolution context with overrides

        Returns:
            The singleton instance
        """
        if descriptor.key not in self._singleton_cache:
            instance = await self._create_instance(descriptor, context)
            self._singleton_cache[descriptor.key] = instance

        return self._singleton_cache[descriptor.key]

    async def _resolve_scoped(self, descriptor: ComponentDescriptor, context: dict) -> Any:
        """Resolve a scoped component.

        Args:
            descriptor: The component descriptor
            context: Resolution context containing scope information

        Returns:
            The scoped instance
        """
        # Get active scopes
        active_scopes = _active_scopes.get()
        if active_scopes is None:
            active_scopes = {}

        # Find the appropriate scope - check component metadata first
        scope_name = descriptor.metadata.get("scope_name", context.get("scope", "default"))

        if scope_name not in active_scopes:
            raise ScopeError(f"Scope '{scope_name}' is not active")

        scope_cache = self._scoped_caches.setdefault(scope_name, {})

        if descriptor.key not in scope_cache:
            instance = await self._create_instance(descriptor, context)
            scope_cache[descriptor.key] = instance

        return scope_cache[descriptor.key]

    async def _create_instance(self, descriptor: ComponentDescriptor, context: dict | None = None) -> Any:
        """Create a component instance.

        Args:
            descriptor: The component descriptor
            context: Resolution context with overrides

        Returns:
            The created instance
        """
        provider = descriptor.provider

        if isinstance(provider, type):
            # Class - instantiate with dependency injection
            return await self._instantiate_class(provider, context)
        elif callable(provider):
            # Factory function - call with dependency injection
            return await self._call_with_injection(provider, context)
        else:
            # Instance - return as-is
            return provider

    async def _instantiate_class(self, cls: type, context: dict | None = None) -> Any:
        """Instantiate a class with automatic dependency injection.

        Args:
            cls: The class to instantiate
            context: Resolution context with overrides

        Returns:
            The created instance
        """
        # Check cache first
        if cls in self._injection_cache:
            injection_plan = self._injection_cache[cls]
        else:
            # Analyze the class constructor
            injection_plan = self._analyze_constructor(cls)
            self._injection_cache[cls] = injection_plan

        # Get overrides from context
        overrides = context.get('overrides', {}) if context else {}

        # Resolve dependencies
        kwargs = {}
        for param_name, inject_result in injection_plan.items():
            # Check if parameter has an override
            if param_name in overrides:
                kwargs[param_name] = overrides[param_name]
            elif inject_result.decision == InjectDecision.YES:
                kwargs[param_name] = await self.resolve(inject_result.type_hint)
            elif inject_result.decision == InjectDecision.OPTIONAL:
                # For optional dependencies, only inject if explicitly registered
                if self.registry.has(inject_result.inner_type):
                    try:
                        kwargs[param_name] = await self.resolve(inject_result.inner_type)
                    except ResolutionError:
                        kwargs[param_name] = None
                else:
                    kwargs[param_name] = None
            elif inject_result.decision == InjectDecision.ERROR:
                # Check if it's a forward reference error - convert to TypeError as expected by tests
                if "Cannot resolve forward reference" in inject_result.reason:
                    raise TypeError(inject_result.reason)
                else:
                    raise InjectionError(
                        f"Cannot inject parameter '{param_name}': {inject_result.reason}",
                        param_name,
                        inject_result.type_hint,
                    )

        # Create the instance
        try:
            return cls(**kwargs)
        except Exception as e:
            raise ResolutionError(
                f"Failed to instantiate {cls.__name__}: {e}", cls.__name__.lower(), e
            ) from e

    async def _call_with_injection(self, func: Callable, context: dict | None = None) -> Any:
        """Call a function with automatic dependency injection.

        Args:
            func: The function to call
            context: Resolution context with overrides

        Returns:
            The function result
        """
        # Check cache first
        if func in self._injection_cache:
            injection_plan = self._injection_cache[func]
        else:
            # Analyze the function
            injection_plan = self.analyzer.analyze_callable(func)
            self._injection_cache[func] = injection_plan

        # Get overrides from context
        overrides = context.get('overrides', {}) if context else {}

        # Resolve dependencies
        kwargs = {}
        for param_name, inject_result in injection_plan.items():
            # Check if parameter has an override
            if param_name in overrides:
                kwargs[param_name] = overrides[param_name]
            elif inject_result.decision == InjectDecision.YES:
                kwargs[param_name] = await self.resolve(inject_result.type_hint)
            elif inject_result.decision == InjectDecision.OPTIONAL:
                # For optional dependencies, only inject if explicitly registered
                if self.registry.has(inject_result.inner_type):
                    try:
                        kwargs[param_name] = await self.resolve(inject_result.inner_type)
                    except ResolutionError:
                        kwargs[param_name] = None
                else:
                    kwargs[param_name] = None
            elif inject_result.decision == InjectDecision.ERROR:
                # Check if it's a forward reference error - convert to TypeError as expected by tests
                if "Cannot resolve forward reference" in inject_result.reason:
                    raise TypeError(inject_result.reason)
                else:
                    raise InjectionError(
                        f"Cannot inject parameter '{param_name}': {inject_result.reason}",
                        param_name,
                        inject_result.type_hint,
                    )

        # Call the function
        try:
            result = func(**kwargs)
            if asyncio.iscoroutine(result):
                return await result
            return result
        except Exception as e:
            func_name = getattr(func, "__name__", str(func))
            raise ResolutionError(f"Failed to call {func_name}: {e}", func_name, e) from e

    async def _try_auto_create(self, cls: type) -> Any:
        """Try to auto-create an unregistered class.

        Args:
            cls: The class to create

        Returns:
            The created instance

        Raises:
            ResolutionError: If auto-creation is not possible
        """
        if not inspect.isclass(cls):
            raise ResolutionError(f"Cannot auto-create non-class: {cls}")

        if not self.analyzer.can_auto_create(cls):
            raise ResolutionError(
                f"Cannot auto-create {cls.__name__}: not all parameters can be injected"
            )

        # Auto-create by instantiating
        return await self._instantiate_class(cls)

    def _analyze_constructor(self, cls: type) -> dict[str, Any]:
        """Analyze a class constructor for dependency injection.

        Args:
            cls: The class to analyze

        Returns:
            Dict mapping parameter names to InjectResults
        """
        try:
            return self.analyzer.analyze_callable(cls.__init__)
        except Exception as e:
            raise TypeAnalysisError(f"Failed to analyze {cls.__name__}: {e}", cls) from e

    def _get_resolution_cycle(self, current_key: str) -> list[type]:
        """Get the circular dependency cycle for error reporting.

        Args:
            current_key: The current component key being resolved

        Returns:
            List of types in the circular dependency
        """
        # This is a simplified implementation
        # In practice, you'd track the full resolution stack
        try:
            descriptor = self.registry.get(current_key)
            return [descriptor.component_type]
        except KeyError:
            return []

    # Batch registration methods

    def services(self, **services) -> Container:
        """Register multiple components at once.

        Args:
            **services: Mapping of keys to providers

        Returns:
            Self for chaining

        Examples:
            >>> container.services(
            ...     database=DatabaseImpl,
            ...     cache=CacheImpl,
            ...     email=EmailService
            ... )
        """
        for key, provider in services.items():
            self.register(key, provider)
        return self

    def singletons(self, **services) -> Container:
        """Register multiple singleton components at once.
        
        Args:
            **services: Mapping of keys to providers
            
        Returns:
            Self for chaining
        """
        for key, provider in services.items():
            self.singleton(key, provider)
        return self
    
    def factory(self, key: str | type, factory_func: Callable, **kwargs) -> ComponentDescriptor:
        """Register a factory function.
        
        Args:
            key: Component key 
            factory_func: Factory function that creates instances
            **kwargs: Additional registration options
            
        Returns:
            ComponentDescriptor
        """
        return self.register(key, factory_func, **kwargs)

    # Convenience registration methods

    def register(
        self,
        key: str | type,
        provider: type | object | Callable,
        *,
        scope: Scope = Scope.TRANSIENT,
        name: str | None = None,
        allow_override: bool = False,
        **kwargs,
    ) -> ComponentDescriptor:
        """Register a component with explicit parameters.

        Args:
            key: Component key (string or type)
            provider: Component implementation
            scope: Component scope
            name: Optional name for named components
            **kwargs: Additional registration options

        Returns:
            The created ComponentDescriptor
        """
        return self.registry.register(key, provider, scope=scope, name=name, allow_override=True, **kwargs)

    def singleton(
        self,
        key: str | type,
        provider: type | object | Callable = None,
        *,
        name: str | None = None,
        instance: Any = None,
        **kwargs,
    ) -> ComponentDescriptor:
        """Register a singleton component.

        Args:
            key: Component key (string or type)
            provider: Component implementation (defaults to key if it's a type)
            name: Optional name for named components
            instance: Pre-created instance to use as singleton
            **kwargs: Additional registration options

        Returns:
            The created ComponentDescriptor
        """
        # Handle instance parameter
        if instance is not None:
            provider = instance
        elif provider is None and isinstance(key, type):
            provider = key

        return self.registry.register(key, provider, scope=Scope.SINGLETON, name=name, **kwargs)

    def scoped(
        self,
        key: str | type,
        provider: type | object | Callable = None,
        *,
        scope_name: str = "default",
        name: str | None = None,
        **kwargs,
    ) -> ComponentDescriptor:
        """Register a scoped component.

        Args:
            key: Component key (string or type)
            provider: Component implementation
            scope_name: Name of the scope
            name: Optional name for named components
            **kwargs: Additional registration options

        Returns:
            The created ComponentDescriptor
        """
        if provider is None and isinstance(key, type):
            provider = key

        return self.registry.register(
            key,
            provider,
            scope=Scope.SCOPED,
            name=name,
            metadata={"scope_name": scope_name},
            **kwargs,
        )

    # Deprecated methods for backward compatibility
    def register_singleton(self, key: str | type, provider: type | object | Callable = None, *, instance: Any = None, **kwargs) -> ComponentDescriptor:
        """Deprecated: Use singleton() instead."""
        import warnings
        warnings.warn("register_singleton is deprecated, use singleton() instead", DeprecationWarning, stacklevel=2)
        if instance is not None:
            return self.register(key, instance, scope=Scope.SINGLETON, **kwargs)
        if provider is None and isinstance(key, type):
            provider = key
        return self.singleton(key, provider, **kwargs)

    def register_factory(self, key: str | type, factory_func: Callable, **kwargs) -> ComponentDescriptor:
        """Deprecated: Use register() or factory() instead."""
        import warnings
        warnings.warn("register_factory is deprecated, use register() or factory() instead", DeprecationWarning, stacklevel=2)
        return self.register(key, factory_func, **kwargs)

    def invoke_sync(self, func: Callable, **overrides) -> Any:
        """Deprecated: Use call_sync() instead."""
        import warnings
        warnings.warn("invoke_sync is deprecated, use call_sync() instead", DeprecationWarning, stacklevel=2)
        return self.call_sync(func, **overrides)

    # Context management

    def __enter__(self):
        """Set this container as the current container."""
        self._token = _current_container.set(self)
        return self

    def __exit__(self, *args):
        """Reset the current container."""
        _current_container.reset(self._token)

    async def __aenter__(self):
        """Async context manager entry."""
        self.__enter__()
        return self

    async def __aexit__(self, *args):
        """Async context manager exit."""
        self.__exit__(*args)

    # Function injection and calling methods

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Call a function with dependency injection for its parameters.

        This method analyzes the function's parameters and automatically
        injects registered components, while allowing manual override via args/kwargs.

        Args:
            func: The function to call
            *args: Positional arguments (override automatic injection)
            **kwargs: Keyword arguments (override automatic injection)

        Returns:
            The function's return value

        Examples:
            >>> def process_data(db: Database, cache: Cache, user_id: int):
            ...     return db.get_user(user_id) + cache.get(f"user_{user_id}")
            >>>
            >>> result = await container.call(process_data, user_id=123)
            >>> # db and cache are injected, user_id is provided manually
        """
        # Get function signature
        sig = inspect.signature(func)

        # Build final kwargs by merging injected and provided
        final_kwargs = {}

        # Process each parameter
        for param_name, param in sig.parameters.items():
            if param_name in kwargs:
                # Use provided value
                final_kwargs[param_name] = kwargs[param_name]
            elif param.kind == param.POSITIONAL_ONLY:
                # Skip positional-only params (handled by *args)
                continue
            else:
                # Try to inject
                try:
                    inject_result = self.analyzer.should_inject(param)
                    if inject_result.decision == InjectDecision.YES:
                        final_kwargs[param_name] = await self.resolve(inject_result.type_hint)
                    elif inject_result.decision == InjectDecision.OPTIONAL:
                        try:
                            final_kwargs[param_name] = await self.resolve(inject_result.inner_type)
                        except ResolutionError:
                            final_kwargs[param_name] = None
                    # For NO or ERROR decisions, don't inject
                except Exception:
                    # If injection fails, don't add to kwargs
                    pass

        # Call the function
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **final_kwargs)
            else:
                result = func(*args, **final_kwargs)
                if asyncio.iscoroutine(result):
                    return await result
                return result
        except Exception as e:
            func_name = getattr(func, "__name__", str(func))
            raise ResolutionError(f"Failed to call {func_name}: {e}", func_name, e) from e

    def call_sync(self, func: Callable, *args, **kwargs) -> Any:
        """Synchronous version of call().
        
        This method works both when called from sync context (no event loop)
        and when called from within an async context (existing event loop).
        """
        try:
            # Check if we're already in an event loop
            loop = asyncio.get_running_loop()
            
            # We're in an async context, but we need to return a sync result
            # Use a ThreadPoolExecutor to run the async code in a separate thread
            import concurrent.futures
            import threading
            
            # This is a complex workaround for the fundamental issue:
            # We're trying to call async code synchronously from within an async context
            
            def run_in_thread():
                # Create a new event loop in this thread
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    return new_loop.run_until_complete(self.call(func, *args, **kwargs))
                finally:
                    new_loop.close()
                    asyncio.set_event_loop(None)
            
            # Run in a separate thread with a new event loop
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_in_thread)
                return future.result()
                
        except RuntimeError:
            # No event loop running, use asyncio.run as normal
            return asyncio.run(self.call(func, *args, **kwargs))

    async def invoke(self, func: Callable, **overrides) -> Any:
        """Invoke a function with full dependency injection.

        Similar to call() but only accepts keyword overrides for clarity.

        Args:
            func: The function to invoke
            **overrides: Explicit parameter values to override injection

        Returns:
            The function's return value
        """
        return await self.call(func, **overrides)

    def wrap_with_injection(self, func: Callable) -> Callable:
        """Wrap a function to always use dependency injection when called.

        Args:
            func: The function to wrap

        Returns:
            Wrapped function that uses automatic injection

        Examples:
            >>> def process_data(db: Database, user_id: int):
            ...     return db.get_user(user_id)
            >>>
            >>> injected_process = container.wrap_with_injection(process_data)
            >>> result = await injected_process(user_id=123)  # db is auto-injected
        """
        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await self.call(func, *args, **kwargs)

            return async_wrapper
        else:

            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                # Check if we're in an async context
                try:
                    loop = asyncio.get_running_loop()
                    # We're in async context, create a task for the call
                    return loop.create_task(self.call(func, *args, **kwargs))
                except RuntimeError:
                    # No event loop, use asyncio.run
                    return asyncio.run(self.call(func, *args, **kwargs))

            return sync_wrapper

    async def create_injected_partial(self, func: Callable, **fixed_kwargs) -> Callable:
        """Create a partial function with some parameters pre-injected.

        Args:
            func: The function to create a partial for
            **fixed_kwargs: Fixed parameter values

        Returns:
            Partial function with injected dependencies
        """
        # Analyze function to determine which params can be injected
        injection_plan = self.analyzer.analyze_callable(func)

        # Resolve injectable parameters now
        injected_kwargs = {}
        for param_name, inject_result in injection_plan.items():
            if param_name not in fixed_kwargs:
                if inject_result.decision == InjectDecision.YES:
                    injected_kwargs[param_name] = await self.resolve(inject_result.type_hint)
                elif inject_result.decision == InjectDecision.OPTIONAL:
                    try:
                        injected_kwargs[param_name] = await self.resolve(inject_result.inner_type)
                    except ResolutionError:
                        injected_kwargs[param_name] = None

        # Combine with fixed kwargs
        all_kwargs = {**injected_kwargs, **fixed_kwargs}

        # Return partial function
        from functools import partial

        return partial(func, **all_kwargs)

    # Utility methods

    def clear_caches(self) -> None:
        """Clear all resolution caches."""
        self._singleton_cache.clear()
        self._scoped_caches.clear()
        self._injection_cache.clear()
        self._weak_cache.clear()
        self.analyzer.clear_cache()

    def get_component_info(self, key: str | type) -> dict[str, Any]:
        """Get information about a registered component.

        Args:
            key: Component key (string or type)

        Returns:
            Dict with component information
        """
        try:
            descriptor = self.registry.get(key)
            return {
                "key": descriptor.key,
                "type": descriptor.component_type.__name__,
                "scope": descriptor.scope.value,
                "name": descriptor.name,
                "tags": list(descriptor.tags),
                "lazy": descriptor.lazy,
                "is_factory": descriptor.is_factory,
                "condition_met": descriptor.matches_condition(),
            }
        except KeyError:
            return {"registered": False}

    def list_components(self) -> list[dict[str, Any]]:
        """List all registered components with their information.

        Returns:
            List of component information dicts
        """
        return [self.get_component_info(desc.key) for desc in self.registry.list_all()]

    # Test compatibility methods have been moved to whiskey.core.testing module
    # Use TestContainer or add_test_compatibility_methods() for legacy test support


# ScopeContext and ScopeContextManager moved to testing module


def get_current_container() -> Container | None:
    """Get the current container from context."""
    return _current_container.get()


def set_current_container(container: Container):
    """Set the current container in context and return a token."""
    return _current_container.set(container)
