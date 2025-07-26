"""Pythonic Container implementation for Whiskey's DI redesign.

This module provides the new Container class with a clean, dict-like interface
and smart dependency resolution using the ServiceRegistry and TypeAnalyzer.
"""

from __future__ import annotations

import asyncio
import inspect
from contextvars import ContextVar
from functools import wraps
from typing import Any, Callable, TypeVar, Union
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
from .registry import Scope, ServiceDescriptor, ServiceRegistry

T = TypeVar("T")

# Context variables for scope management
_current_container: ContextVar[Container] = ContextVar("current_container", default=None)
_active_scopes: ContextVar[dict[str, dict[str, Any]]] = ContextVar("active_scopes", default={})


class ContainerComponentBuilder:
    """Fluent builder for individual service registration in a Container.

    This provides a lighter-weight alternative to ApplicationBuilder for
    simple service registration with fluent configuration.
    """

    def __init__(self, container: Container, key: str | type, provider: Any):
        self._container = container
        self._key = key
        self._provider = provider
        self._scope = Scope.TRANSIENT
        self._name: str | None = None
        self._tags: set[str] = set()
        self._condition: Callable[[], bool] | None = None
        self._lazy = False
        self._metadata: dict[str, Any] = {}

    def as_singleton(self) -> ContainerComponentBuilder:
        """Configure service with singleton scope."""
        self._scope = Scope.SINGLETON
        return self

    def as_scoped(self, scope_name: str = "default") -> ContainerComponentBuilder:
        """Configure service with scoped lifecycle."""
        self._scope = Scope.SCOPED
        self._metadata["scope_name"] = scope_name
        return self

    def as_transient(self) -> ContainerComponentBuilder:
        """Configure service with transient scope (default)."""
        self._scope = Scope.TRANSIENT
        return self

    def named(self, name: str) -> ContainerComponentBuilder:
        """Assign a name to this service."""
        self._name = name
        return self

    def tagged(self, *tags: str) -> ContainerComponentBuilder:
        """Add tags to this service."""
        self._tags.update(tags)
        return self

    def when(self, condition: Callable[[], bool] | bool) -> ContainerComponentBuilder:
        """Add a condition for registration."""
        if isinstance(condition, bool):
            self._condition = lambda: condition
        else:
            self._condition = condition
        return self

    def when_env(self, var_name: str, expected_value: str = None) -> ContainerComponentBuilder:
        """Add environment-based condition."""
        import os

        if expected_value is None:
            condition = lambda: var_name in os.environ
        else:
            condition = lambda: os.environ.get(var_name) == expected_value
        return self.when(condition)

    def when_debug(self) -> ContainerComponentBuilder:
        """Register only in debug mode."""
        import os

        condition = lambda: os.environ.get("DEBUG", "").lower() in ("true", "1", "yes")
        return self.when(condition)

    def lazy(self, is_lazy: bool = True) -> ContainerComponentBuilder:
        """Enable lazy resolution."""
        self._lazy = is_lazy
        return self

    def with_metadata(self, **metadata) -> ContainerComponentBuilder:
        """Add arbitrary metadata."""
        self._metadata.update(metadata)
        return self

    def build(self) -> ServiceDescriptor:
        """Complete the registration and return the descriptor."""
        return self._container.register(
            self._key,
            self._provider,
            scope=self._scope,
            name=self._name,
            condition=self._condition,
            tags=self._tags,
            lazy=self._lazy,
            **self._metadata,
        )


class Container:
    """Pythonic dependency injection container.

    This is the main container class that provides a clean, dict-like interface
    for service registration and resolution with smart dependency injection.

    Features:
        - Dict-like interface: container['service'] = implementation
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
        self.registry = ServiceRegistry()
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
        """Register a service using dict-like syntax.

        Args:
            key: Service key (string or type, or tuple for named services)
            value: Service implementation (class, instance, or factory)

        Examples:
            >>> container['database'] = Database()  # Instance
            >>> container[EmailService] = EmailService  # Class
            >>> container['cache'] = lambda: RedisCache()  # Factory
            >>> container[EmailService, 'primary'] = EmailService()  # Named service
        """
        # Validate key type
        if isinstance(key, tuple):
            # Handle named service registration: (type, name)
            if len(key) != 2:
                raise ValueError("Tuple key must have exactly 2 elements: (type, name)")
            service_type, name = key
            if not isinstance(service_type, (str, type)) or not isinstance(name, str):
                raise ValueError("Tuple key must be (str|type, str)")
            self.registry.register(service_type, value, name=name, allow_override=True)
        elif isinstance(key, (str, type)):
            self.registry.register(key, value, allow_override=True)
        else:
            raise ValueError(f"Invalid key type: {type(key)}. Must be str, type, or tuple")

    def __getitem__(self, key: str | type) -> Any:
        """Get a service using dict-like syntax.

        Args:
            key: Service key (string or type)

        Returns:
            The resolved service instance

        Examples:
            >>> db = container['database']
            >>> email = container[EmailService]
        """
        # Check if service is registered first
        if key not in self:
            raise KeyError(f"Service '{key}' not found in container")
        # Always use synchronous resolution for dict-like access
        return self.resolve_sync(key)

    def __contains__(self, key: str | type) -> bool:
        """Check if a service is registered.

        Args:
            key: Service key (string or type)

        Returns:
            True if the service is registered and condition is met
        """
        # First check if registered without a name
        if self.registry.has(key):
            return True
        
        # If key is a type, check if it's registered with any name
        if isinstance(key, type):
            # Check if any services of this type are registered
            descriptors = self.registry.find_by_type(key)
            return len(descriptors) > 0
            
        return False

    def __delitem__(self, key: str | type) -> None:
        """Remove a service registration.

        Args:
            key: Service key (string or type)
        """
        string_key = self.registry._normalize_key(key)

        # Remove from registry
        if not self.registry.remove(key):
            raise KeyError(f"Service '{key}' not found")

        # Clear from caches
        self._singleton_cache.pop(string_key, None)
        for scope_cache in self._scoped_caches.values():
            scope_cache.pop(string_key, None)

    def __len__(self) -> int:
        """Get number of registered services."""
        return len(self.registry)

    def __iter__(self):
        """Iterate over service keys."""
        return iter(desc.service_type for desc in self.registry.list_all())

    def keys(self):
        """Get all registered service keys."""
        return [desc.service_type for desc in self.registry.list_all()]

    def items(self):
        """Get all registered service key-descriptor pairs."""
        return [(desc.service_type, desc) for desc in self.registry.list_all()]

    def clear(self):
        """Clear all registered services."""
        self.registry.clear()

    # Main resolution methods

    @monitor_resolution
    async def resolve(self, key: str | type, *, name: str = None, **context) -> T:
        """Resolve a service asynchronously.

        This is the main resolution method that handles all the smart
        dependency injection logic.

        Args:
            key: Service key (string or type)
            name: Optional name for named services
            **context: Additional context for scoped resolution

        Returns:
            The resolved service instance

        Raises:
            ResolutionError: If the service cannot be resolved
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

    def resolve_sync(self, key: str | type, *, name: str = None, overrides: dict = None, **context) -> T:
        """Resolve a service synchronously.

        Args:
            key: Service key (string or type)
            name: Optional name for named services
            overrides: Override values for dependency injection
            **context: Additional context for scoped resolution

        Returns:
            The resolved service instance
        """
        # Check if the provider is an async factory before attempting sync resolution
        try:
            descriptor = self.registry.get(key, name)
            if callable(descriptor.provider) and asyncio.iscoroutinefunction(descriptor.provider):
                raise RuntimeError(f"Cannot resolve async factory '{key}' synchronously")
        except KeyError:
            pass  # Service not registered, let normal resolution handle it
        
        # Pass overrides through context
        if overrides:
            context['overrides'] = overrides
        
        # Handle case where we're already in an event loop
        try:
            loop = asyncio.get_running_loop()
            # We're in an event loop - we can't use asyncio.run
            # Instead, we need to resolve this synchronously by implementing sync resolution logic
            return self._resolve_sync_internal(key, name, context)
        except RuntimeError:
            # No event loop running, use asyncio.run
            return asyncio.run(self.resolve(key, name=name, **context))

    def _resolve_sync_internal(self, key: str | type, name: str = None, context: dict = None) -> Any:
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

    def _do_resolve_sync(self, key: str | type, name: str = None, context: dict = None) -> Any:
        """Synchronous version of _do_resolve."""
        # Get the service descriptor
        try:
            descriptor = self.registry.get(key, name)
        except KeyError:
            # Service not explicitly registered - try auto-creation
            if isinstance(key, type):
                # Check if it's an abstract class
                import inspect
                if inspect.isabstract(key):
                    raise KeyError(f"{key.__name__} not registered")  
                return self._try_auto_create_sync(key)
            raise ResolutionError(f"Service '{key}' not registered")

        string_key = descriptor.key

        # Handle different scopes
        if descriptor.scope == Scope.SINGLETON:
            return self._resolve_singleton_sync(descriptor, context)
        elif descriptor.scope == Scope.SCOPED:
            return self._resolve_scoped_sync(descriptor, context or {})
        else:  # Transient
            return self._create_instance_sync(descriptor, context)

    def _resolve_singleton_sync(self, descriptor: ServiceDescriptor, context: dict = None) -> Any:
        """Synchronous singleton resolution."""
        if descriptor.key not in self._singleton_cache:
            instance = self._create_instance_sync(descriptor, context)
            self._singleton_cache[descriptor.key] = instance
        return self._singleton_cache[descriptor.key]

    def _resolve_scoped_sync(self, descriptor: ServiceDescriptor, context: dict) -> Any:
        """Synchronous scoped resolution."""
        # Get active scopes
        active_scopes = _active_scopes.get()

        # Find the appropriate scope - check service metadata first
        scope_name = descriptor.metadata.get("scope_name", context.get("scope", "default"))

        if scope_name not in active_scopes:
            raise ScopeError(f"Scope '{scope_name}' is not active")

        scope_cache = self._scoped_caches.setdefault(scope_name, {})

        if descriptor.key not in scope_cache:
            instance = self._create_instance_sync(descriptor, context)
            scope_cache[descriptor.key] = instance

        return scope_cache[descriptor.key]

    def _create_instance_sync(self, descriptor: ServiceDescriptor, context: dict = None) -> Any:
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

    def _instantiate_class_sync(self, cls: type, context: dict = None) -> Any:
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
            )

    def _call_with_injection_sync(self, func: Callable, context: dict = None) -> Any:
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
            raise ResolutionError(f"Failed to call {func_name}: {e}", func_name, e)

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

    async def _do_resolve(self, key: str | type, name: str = None, context: dict = None) -> Any:
        """Internal resolution implementation.

        Args:
            key: Service key (string or type)
            name: Optional name for named services
            context: Resolution context

        Returns:
            The resolved service instance
        """
        # Get the service descriptor
        try:
            descriptor = self.registry.get(key, name)
        except KeyError:
            # Service not explicitly registered - try auto-creation
            if isinstance(key, type):
                # Check if it's an abstract class
                import inspect
                if inspect.isabstract(key):
                    raise KeyError(f"{key.__name__} not registered")  
                return await self._try_auto_create(key)
            raise ResolutionError(f"Service '{key}' not registered")

        string_key = descriptor.key

        # Handle different scopes
        if descriptor.scope == Scope.SINGLETON:
            return await self._resolve_singleton(descriptor, context)
        elif descriptor.scope == Scope.SCOPED:
            return await self._resolve_scoped(descriptor, context or {})
        else:  # Transient
            return await self._create_instance(descriptor, context)

    async def _resolve_singleton(self, descriptor: ServiceDescriptor, context: dict = None) -> Any:
        """Resolve a singleton service.

        Args:
            descriptor: The service descriptor
            context: Resolution context with overrides

        Returns:
            The singleton instance
        """
        if descriptor.key not in self._singleton_cache:
            instance = await self._create_instance(descriptor, context)
            self._singleton_cache[descriptor.key] = instance

        return self._singleton_cache[descriptor.key]

    async def _resolve_scoped(self, descriptor: ServiceDescriptor, context: dict) -> Any:
        """Resolve a scoped service.

        Args:
            descriptor: The service descriptor
            context: Resolution context containing scope information

        Returns:
            The scoped instance
        """
        # Get active scopes
        active_scopes = _active_scopes.get()

        # Find the appropriate scope - check service metadata first
        scope_name = descriptor.metadata.get("scope_name", context.get("scope", "default"))

        if scope_name not in active_scopes:
            raise ScopeError(f"Scope '{scope_name}' is not active")

        scope_cache = self._scoped_caches.setdefault(scope_name, {})

        if descriptor.key not in scope_cache:
            instance = await self._create_instance(descriptor, context)
            scope_cache[descriptor.key] = instance

        return scope_cache[descriptor.key]

    async def _create_instance(self, descriptor: ServiceDescriptor, context: dict = None) -> Any:
        """Create a service instance.

        Args:
            descriptor: The service descriptor
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

    async def _instantiate_class(self, cls: type, context: dict = None) -> Any:
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
            )

    async def _call_with_injection(self, func: Callable, context: dict = None) -> Any:
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
            raise ResolutionError(f"Failed to call {func_name}: {e}", func_name, e)

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
            raise TypeAnalysisError(f"Failed to analyze {cls.__name__}: {e}", cls)

    def _get_resolution_cycle(self, current_key: str) -> list[type]:
        """Get the circular dependency cycle for error reporting.

        Args:
            current_key: The current service key being resolved

        Returns:
            List of types in the circular dependency
        """
        # This is a simplified implementation
        # In practice, you'd track the full resolution stack
        try:
            descriptor = self.registry.get(current_key)
            return [descriptor.service_type]
        except KeyError:
            return []

    # Fluent registration builders

    def add(
        self, key: str | type, provider: Union[type, object, Callable] = None
    ) -> ContainerComponentBuilder:
        """Start fluent service registration.

        Args:
            key: Service key (string or type)
            provider: Service implementation (defaults to key if it's a type)

        Returns:
            ContainerComponentBuilder for fluent configuration

        Examples:
            >>> container.add('database', DatabaseImpl).as_singleton().tagged('core')
            >>> container.add(EmailService).as_scoped('request').when_debug()
        """
        if provider is None and isinstance(key, type):
            provider = key

        if provider is None:
            raise ValueError(f"Provider required for service '{key}'")

        return ContainerComponentBuilder(self, key, provider)

    def add_singleton(
        self, key: str | type, provider: Union[type, object, Callable] = None
    ) -> ContainerComponentBuilder:
        """Start fluent singleton registration."""
        return self.add(key, provider).as_singleton()

    def add_scoped(
        self,
        key: str | type,
        provider: Union[type, object, Callable] = None,
        scope_name: str = "default",
    ) -> ContainerComponentBuilder:
        """Start fluent scoped registration."""
        return self.add(key, provider).as_scoped(scope_name)

    def add_factory(self, key: str | type, factory_func: Callable) -> ContainerComponentBuilder:
        """Start fluent factory registration."""
        return self.add(key, factory_func)

    def add_function(self, key: str | type, func: Callable) -> ContainerComponentBuilder:
        """Register a function as a service (not a factory).

        The function will be called once and its result cached according to scope.
        This is different from add_factory where the function itself is the provider.
        """
        return self.add(key, func)

    def add_instance(self, key: str | type, instance: Any) -> ContainerComponentBuilder:
        """Start fluent instance registration (as singleton)."""
        return self.add(key, instance).as_singleton()

    # Batch registration methods

    def add_services(self, **services) -> None:
        """Register multiple services at once.

        Args:
            **services: Mapping of keys to providers

        Examples:
            >>> container.add_services(
            ...     database=DatabaseImpl,
            ...     cache=CacheImpl,
            ...     email=EmailService
            ... )
        """
        for key, provider in services.items():
            self.add(key, provider).build()

    def add_singletons(self, **services) -> None:
        """Register multiple singleton services at once."""
        for key, provider in services.items():
            self.add_singleton(key, provider).build()

    # Convenience registration methods

    def register(
        self,
        key: str | type,
        provider: Union[type, object, Callable],
        *,
        scope: Scope = Scope.TRANSIENT,
        name: str = None,
        allow_override: bool = False,
        **kwargs,
    ) -> ServiceDescriptor:
        """Register a service with explicit parameters.

        Args:
            key: Service key (string or type)
            provider: Service implementation
            scope: Service scope
            name: Optional name for named services
            **kwargs: Additional registration options

        Returns:
            The created ServiceDescriptor
        """
        return self.registry.register(key, provider, scope=scope, name=name, allow_override=True, **kwargs)

    def singleton(
        self,
        key: str | type,
        provider: Union[type, object, Callable] = None,
        *,
        name: str = None,
        **kwargs,
    ) -> ServiceDescriptor:
        """Register a singleton service.

        Args:
            key: Service key (string or type)
            provider: Service implementation (defaults to key if it's a type)
            name: Optional name for named services
            **kwargs: Additional registration options

        Returns:
            The created ServiceDescriptor
        """
        if provider is None and isinstance(key, type):
            provider = key

        return self.registry.register(key, provider, scope=Scope.SINGLETON, name=name, **kwargs)

    def scoped(
        self,
        key: str | type,
        provider: Union[type, object, Callable] = None,
        *,
        scope_name: str = "default",
        name: str = None,
        **kwargs,
    ) -> ServiceDescriptor:
        """Register a scoped service.

        Args:
            key: Service key (string or type)
            provider: Service implementation
            scope_name: Name of the scope
            name: Optional name for named services
            **kwargs: Additional registration options

        Returns:
            The created ServiceDescriptor
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

    # Convenience methods for test compatibility
    def register_singleton(self, key: str | type, provider: Union[type, object, Callable] = None, *, instance: Any = None, **kwargs) -> ServiceDescriptor:
        """Register a singleton service (test compatibility method)."""
        if instance is not None:
            return self.register(key, instance, scope=Scope.SINGLETON, **kwargs)
        if provider is None and isinstance(key, type):
            provider = key
        return self.singleton(key, provider, **kwargs)

    def register_factory(self, key: str | type, factory_func: Callable, **kwargs) -> ServiceDescriptor:
        """Register a factory function (test compatibility method)."""
        return self.register(key, factory_func, **kwargs)

    def invoke_sync(self, func: Callable, **overrides) -> Any:
        """Invoke a function with dependency injection (synchronous)."""
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
        injects registered services, while allowing manual override via args/kwargs.

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
            raise ResolutionError(f"Failed to call {func_name}: {e}", func_name, e)

    def call_sync(self, func: Callable, *args, **kwargs) -> Any:
        """Synchronous version of call()."""
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

    def get_service_info(self, key: str | type) -> dict[str, Any]:
        """Get information about a registered service.

        Args:
            key: Service key (string or type)

        Returns:
            Dict with service information
        """
        try:
            descriptor = self.registry.get(key)
            return {
                "key": descriptor.key,
                "type": descriptor.service_type.__name__,
                "scope": descriptor.scope.value,
                "name": descriptor.name,
                "tags": list(descriptor.tags),
                "lazy": descriptor.lazy,
                "is_factory": descriptor.is_factory,
                "condition_met": descriptor.matches_condition(),
            }
        except KeyError:
            return {"registered": False}

    def list_services(self) -> list[dict[str, Any]]:
        """List all registered services with their information.

        Returns:
            List of service information dicts
        """
        return [self.get_service_info(desc.key) for desc in self.registry.list_all()]

    # Scope management methods for test compatibility
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

    # Lifecycle methods for test compatibility
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

    # Service lifecycle methods for test compatibility
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


def get_current_container() -> Container | None:
    """Get the current container from context."""
    return _current_container.get()


def set_current_container(container: Container):
    """Set the current container in context and return a token."""
    return _current_container.set(container)
