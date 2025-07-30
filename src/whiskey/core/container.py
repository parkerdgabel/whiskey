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
    ConfigurationError,
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
from .smart_resolution import SmartResolver, SmartDictAccess, SmartCalling

T = TypeVar("T")

# Context variables for scope management
_current_container: ContextVar[Container] = ContextVar("current_container", default=None)
_active_scopes: ContextVar[dict[str, dict[str, Any]] | None] = ContextVar("active_scopes", default=None)


# Removed ContainerComponentBuilder - using direct method chaining instead


class Container(SmartResolver, SmartDictAccess, SmartCalling):
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
        
        # Track instances with lifecycle hooks for cleanup
        self._tracked_instances: dict[str, Any] = {}  # key -> instance mapping

        # Performance optimizations
        self._weak_cache = WeakValueCache()
        self._resolution_depth = 0
        
        # Scope validation and registry
        self._valid_scopes: set[str] = {"singleton", "transient", "request", "session", "default"}
        # Hierarchy from longest-lived to shortest-lived
        self._scope_hierarchy: list[str] = ["singleton", "session", "request", "default", "transient"]

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

    # Dict-like access is handled by SmartDictAccess mixin

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

    # Smart resolution implementation methods
    
    def _resolve_sync_impl(self, key: str | type, name: str | None = None, context: dict | None = None) -> Any:
        """Internal synchronous resolution implementation."""
        return self._resolve_sync_internal(key, name, context or {})
    
    async def _resolve_async_impl(self, key: str | type, name: str | None = None, context: dict | None = None) -> Any:
        """Internal asynchronous resolution implementation."""
        return await self._original_resolve(key, name=name, **(context or {}))

    def _call_sync_impl(self, func: callable, args: tuple, kwargs: dict) -> Any:
        """Internal synchronous calling implementation."""
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
                # Try to inject synchronously
                try:
                    inject_result = self.analyzer.should_inject(param)
                    if inject_result.decision == InjectDecision.YES:
                        final_kwargs[param_name] = self._resolve_sync_impl(inject_result.type_hint)
                    elif inject_result.decision == InjectDecision.OPTIONAL:
                        try:
                            final_kwargs[param_name] = self._resolve_sync_impl(inject_result.inner_type)
                        except ResolutionError:
                            final_kwargs[param_name] = None
                    # For NO or ERROR decisions, don't inject
                except Exception:
                    # If injection fails, don't add to kwargs
                    pass

        # Call the function
        try:
            if asyncio.iscoroutinefunction(func):
                raise RuntimeError(f"Cannot call async function '{getattr(func, '__name__', str(func))}' synchronously")
            
            result = func(*args, **final_kwargs)
            if asyncio.iscoroutine(result):
                raise RuntimeError(f"Function '{getattr(func, '__name__', str(func))}' returned a coroutine in sync context")
            return result
        except Exception as e:
            func_name = getattr(func, "__name__", str(func))
            raise ResolutionError(f"Failed to call {func_name}: {e}", func_name, e) from e
    
    async def _call_async_impl(self, func: callable, args: tuple, kwargs: dict) -> Any:
        """Internal asynchronous calling implementation."""
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
                        final_kwargs[param_name] = await self._resolve_async_impl(inject_result.type_hint)
                    elif inject_result.decision == InjectDecision.OPTIONAL:
                        try:
                            final_kwargs[param_name] = await self._resolve_async_impl(inject_result.inner_type)
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

    # Main resolution methods

    @monitor_resolution
    async def _original_resolve(self, key: str | type, *, name: str | None = None, **context) -> T:
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

    # resolve_sync is now handled by SmartResolver mixin

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
            instance = self._instantiate_class_sync(provider, context)
        elif callable(provider):
            # Factory function - call with dependency injection
            instance = self._call_with_injection_sync(provider, context)
        else:
            # Instance - return as-is
            instance = provider
        
        # Call initialize hook if present
        self._call_initialize_hook(instance)
        
        # Track instance for disposal if needed
        self._track_instance_for_disposal(descriptor.key, instance, descriptor.scope)
        
        return instance

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
        unresolvable_params = []
        
        # First pass: collect information about all parameters
        sig = inspect.signature(cls.__init__)
        
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
            elif inject_result.decision == InjectDecision.NO:
                # Track unresolvable parameters
                param = sig.parameters.get(param_name)
                if param and param.default == inspect.Parameter.empty:
                    # This parameter is required but can't be injected
                    type_hint = inject_result.type_hint or param.annotation
                    type_name = getattr(type_hint, '__name__', str(type_hint))
                    unresolvable_params.append(f"{param_name}: {type_name} - {inject_result.reason}")
        
        # Check if we have any required parameters that couldn't be resolved
        if unresolvable_params:
            from .errors import ParameterResolutionError
            # Find the first unresolvable parameter for detailed error
            for param_name, param in sig.parameters.items():
                if param_name == "self":
                    continue
                if param.default == inspect.Parameter.empty and param_name not in kwargs:
                    inject_result = injection_plan.get(param_name)
                    if inject_result is not None and inject_result.decision == InjectDecision.NO:
                        raise ParameterResolutionError(
                            class_name=cls.__name__,
                            parameter_name=param_name,
                            parameter_type=inject_result.type_hint or param.annotation,
                            reason=inject_result.reason,
                            missing_dependencies=unresolvable_params
                        )

        # Create the instance
        try:
            return cls(**kwargs)
        except TypeError as e:
            # Handle missing required arguments
            error_msg = str(e)
            if "missing" in error_msg and "required positional argument" in error_msg:
                # This means some parameters weren't injected - let's figure out which ones
                sig = inspect.signature(cls.__init__)
                missing_params = []
                uninjectable_params = []
                
                # Check each parameter
                for param_name, param in sig.parameters.items():
                    if param_name == "self":
                        continue
                    
                    # Skip if it has a default
                    if param.default != inspect.Parameter.empty:
                        continue
                    
                    # Check if it was provided
                    if param_name not in kwargs:
                        missing_params.append(param_name)
                        # Check why it wasn't injected
                        inject_result = injection_plan.get(param_name)
                        if inject_result is not None:
                            param_type = param.annotation if param.annotation != inspect.Parameter.empty else 'Any'
                            reason = inject_result.reason
                            uninjectable_params.append(f"{param_name}: {param_type} - {reason}")
                
                if uninjectable_params:
                    from .errors import ParameterResolutionError
                    # Report the first uninjectable parameter in detail
                    first_missing = missing_params[0] if missing_params else None
                    if first_missing and first_missing in sig.parameters:
                        param = sig.parameters[first_missing]
                        inject_result = injection_plan.get(first_missing)
                        raise ParameterResolutionError(
                            class_name=cls.__name__,
                            parameter_name=first_missing,
                            parameter_type=param.annotation if param.annotation != inspect.Parameter.empty else Any,
                            reason=inject_result.reason if inject_result else "Cannot be injected",
                            missing_dependencies=uninjectable_params
                        ) from e
            
            raise ResolutionError(
                f"Failed to instantiate {cls.__name__}: {e}", cls.__name__.lower(), e
            ) from e
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

        # Analyze why auto-creation might fail
        try:
            sig = inspect.signature(cls.__init__)
        except (ValueError, TypeError):
            raise ResolutionError(f"Cannot analyze constructor for {cls.__name__}")
        
        # Get detailed analysis of each parameter
        analysis = self.analyzer.analyze_callable(cls.__init__)
        unresolvable_params = []
        
        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue
            
            # Skip parameters with defaults
            if param.default != inspect.Parameter.empty:
                continue
                
            # Check if parameter can be injected
            inject_result = analysis.get(param_name)
            if inject_result is not None and inject_result.decision == InjectDecision.NO:
                type_hint = param.annotation if param.annotation != inspect.Parameter.empty else 'Any'
                unresolvable_params.append(f"{param_name}: {type_hint} ({inject_result.reason})")
        
        if unresolvable_params:
            from .errors import ParameterResolutionError
            # Use the first unresolvable parameter for the main error
            first_param = list(sig.parameters.items())[1]  # Skip 'self'
            if first_param and first_param[0] != 'self':
                param_name = first_param[0]
                param = first_param[1]
                inject_result = analysis.get(param_name)
                raise ParameterResolutionError(
                    class_name=cls.__name__,
                    parameter_name=param_name,
                    parameter_type=param.annotation,
                    reason=inject_result.reason if inject_result else "Cannot be injected",
                    missing_dependencies=unresolvable_params
                )
        
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
            instance = await self._instantiate_class(provider, context)
        elif callable(provider):
            # Factory function - call with dependency injection
            instance = await self._call_with_injection(provider, context)
        else:
            # Instance - return as-is
            instance = provider
        
        # Call initialize hook if present
        await self._call_initialize_hook_async(instance)
        
        # Track instance for disposal if needed
        self._track_instance_for_disposal(descriptor.key, instance, descriptor.scope)
        
        return instance

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
                kwargs[param_name] = await self._resolve_async_impl(inject_result.type_hint)
            elif inject_result.decision == InjectDecision.OPTIONAL:
                # For optional dependencies, only inject if explicitly registered
                if self.registry.has(inject_result.inner_type):
                    try:
                        kwargs[param_name] = await self._resolve_async_impl(inject_result.inner_type)
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
            elif inject_result.decision == InjectDecision.NO:
                # Track unresolvable parameters
                import inspect
                sig = inspect.signature(cls.__init__)
                param = sig.parameters.get(param_name)
                if param and param.default == inspect.Parameter.empty:
                    # This parameter is required but can't be injected - will cause TypeError
                    pass  # We'll handle this below

        # Check if we have any required parameters that couldn't be resolved
        import inspect
        sig = inspect.signature(cls.__init__)
        unresolvable_params = []
        for param_name, inject_result in injection_plan.items():
            if inject_result.decision == InjectDecision.NO:
                param = sig.parameters.get(param_name)
                if param and param.default == inspect.Parameter.empty and param_name not in kwargs:
                    # This parameter is required but can't be injected
                    type_hint = inject_result.type_hint or param.annotation
                    type_name = getattr(type_hint, '__name__', str(type_hint))
                    unresolvable_params.append(f"{param_name}: {type_name} - {inject_result.reason}")
        
        # Check if we have any required parameters that couldn't be resolved
        if unresolvable_params:
            from .errors import ParameterResolutionError
            # Find the first unresolvable parameter for detailed error
            for param_name, param in sig.parameters.items():
                if param_name == "self":
                    continue
                if param.default == inspect.Parameter.empty and param_name not in kwargs:
                    inject_result = injection_plan.get(param_name)
                    if inject_result is not None and inject_result.decision == InjectDecision.NO:
                        raise ParameterResolutionError(
                            class_name=cls.__name__,
                            parameter_name=param_name,
                            parameter_type=inject_result.type_hint or param.annotation,
                            reason=inject_result.reason,
                            missing_dependencies=unresolvable_params
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
                kwargs[param_name] = await self._resolve_async_impl(inject_result.type_hint)
            elif inject_result.decision == InjectDecision.OPTIONAL:
                # For optional dependencies, only inject if explicitly registered
                if self.registry.has(inject_result.inner_type):
                    try:
                        kwargs[param_name] = await self._resolve_async_impl(inject_result.inner_type)
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
        # First register the component
        descriptor = self.registry.register(key, provider, scope=scope, name=name, allow_override=True, **kwargs)
        
        # Then validate scope dependencies
        try:
            self._validate_scope_dependencies(descriptor)
            # Only check for circular dependencies if we have a class (not functions/instances)
            if inspect.isclass(descriptor.component_type):
                self._detect_circular_scope_dependencies(descriptor)
        except ConfigurationError:
            # If validation fails, remove the component and re-raise
            try:
                self.registry.remove(key, name=name)
            except KeyError:
                pass
            raise
        
        return descriptor

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

    # Scope validation and registry
    
    def register_scope(self, scope_name: str) -> None:
        """Register a new valid scope name.
        
        Args:
            scope_name: The name of the scope to register
        """
        self._valid_scopes.add(scope_name)
    
    def define_scope_hierarchy(self, hierarchy: list[str]) -> None:
        """Define the scope hierarchy from longest-lived to shortest-lived.
        
        Args:
            hierarchy: List of scope names ordered by lifetime (longest to shortest)
        """
        self._scope_hierarchy = hierarchy.copy()
        # Ensure all hierarchy scopes are registered as valid
        for scope in hierarchy:
            self._valid_scopes.add(scope)
    
    def _validate_scope_name(self, scope_name: str) -> None:
        """Validate that a scope name is registered.
        
        Args:
            scope_name: The scope name to validate
            
        Raises:
            ConfigurationError: If scope name is not valid
        """
        if scope_name not in self._valid_scopes:
            raise ConfigurationError(
                f"Invalid scope '{scope_name}'. "
                f"Available scopes: {', '.join(sorted(self._valid_scopes))}"
            )
    
    def _scope_can_depend_on(self, dependent_scope: str, dependency_scope: str) -> bool:
        """Check if one scope can depend on another based on hierarchy.
        
        A scope can depend on scopes that are longer-lived (earlier in hierarchy).
        
        Args:
            dependent_scope: The scope that has the dependency
            dependency_scope: The scope of the dependency
            
        Returns:
            True if the dependency is allowed, False otherwise
        """
        if dependent_scope not in self._scope_hierarchy or dependency_scope not in self._scope_hierarchy:
            # If either scope is not in hierarchy, allow (for extensibility)
            return True
        
        dependent_index = self._scope_hierarchy.index(dependent_scope)
        dependency_index = self._scope_hierarchy.index(dependency_scope)
        
        # Can depend on longer-lived scopes (lower index = longer lived)
        return dependency_index <= dependent_index
    
    def _validate_scope_dependencies(self, descriptor: ComponentDescriptor) -> None:
        """Validate that a component's scope dependencies are valid.
        
        Args:
            descriptor: The component descriptor to validate
            
        Raises:
            ConfigurationError: If scope dependencies are invalid
        """
        component_scope = descriptor.scope
        component_type = descriptor.component_type
        
        # Determine the actual scope name for scoped components
        if component_scope == Scope.SCOPED:
            component_scope_name = descriptor.metadata.get("scope_name", "default")
        elif component_scope == Scope.SINGLETON:
            component_scope_name = "singleton"
        elif component_scope == Scope.TRANSIENT:
            component_scope_name = "transient"
        else:
            return  # Unknown scope, skip validation
        
        # Validate the scope name exists
        if component_scope == Scope.SCOPED:
            self._validate_scope_name(component_scope_name)
        
        # Check dependencies
        try:
            if inspect.isclass(component_type):
                sig = inspect.signature(component_type.__init__)
                for param_name, param in sig.parameters.items():
                    if param_name == 'self':
                        continue
                    
                    if param.annotation != param.empty:
                        dependency_type = param.annotation
                        
                        # Skip built-in types
                        if dependency_type in (str, int, float, bool, list, dict, tuple, set):
                            continue
                        
                        # Find the dependency in registry
                        try:
                            dep_descriptor = self.registry.get(dependency_type)
                            
                            # Determine dependency scope
                            if dep_descriptor.scope == Scope.SCOPED:
                                dep_scope_name = dep_descriptor.metadata.get("scope_name", "default")
                            elif dep_descriptor.scope == Scope.SINGLETON:
                                dep_scope_name = "singleton"
                            elif dep_descriptor.scope == Scope.TRANSIENT:
                                dep_scope_name = "transient"
                            else:
                                continue  # Unknown scope, skip
                            
                            # Check if dependency is allowed
                            if not self._scope_can_depend_on(component_scope_name, dep_scope_name):
                                raise ConfigurationError(
                                    f"Invalid scope dependency: {component_type.__name__} "
                                    f"(scope: {component_scope_name}) cannot depend on "
                                    f"{dependency_type.__name__} (scope: {dep_scope_name}). "
                                    f"Components can only depend on longer-lived scopes."
                                )
                            
                        except KeyError:
                            # Dependency not registered yet, skip validation
                            # This will be caught during resolution if it's actually missing
                            continue
                            
        except (TypeError, ValueError):
            # Skip validation if we can't inspect the constructor
            pass
    
    def _detect_circular_scope_dependencies(self, descriptor: ComponentDescriptor, visited: set[type] = None) -> None:
        """Detect circular dependencies that would cause scope validation issues.
        
        This is different from runtime circular dependency detection - this only checks
        for circular dependencies that would create scope hierarchy violations.
        
        Args:
            descriptor: The component descriptor to check
            visited: Set of already visited types (for recursion detection)
            
        Raises:
            ConfigurationError: If circular dependency is detected
        """
        if visited is None:
            visited = set()
        
        component_type = descriptor.component_type
        
        if component_type in visited:
            # Only raise if we have a genuine scope-related circular dependency
            # For now, let the runtime circular dependency detection handle this
            return
        
        visited.add(component_type)
        
        try:
            if inspect.isclass(component_type):
                sig = inspect.signature(component_type.__init__)
                for param_name, param in sig.parameters.items():
                    if param_name == 'self':
                        continue
                    
                    if param.annotation != param.empty:
                        dependency_type = param.annotation
                        
                        # Skip built-in types
                        if dependency_type in (str, int, float, bool, list, dict, tuple, set):
                            continue
                        
                        try:
                            dep_descriptor = self.registry.get(dependency_type)
                            self._detect_circular_scope_dependencies(dep_descriptor, visited.copy())
                        except KeyError:
                            # Dependency not registered yet, skip check
                            continue
                            
        except (TypeError, ValueError):
            # Skip validation if we can't inspect the constructor
            pass
        
        visited.remove(component_type)

    # Scope management

    def scope(self, scope_name: str) -> ScopeManager:
        """Create a context manager for a named scope.

        This method creates a scope boundary within which all scoped components
        will share the same instance. When the scope exits, all instances are
        properly disposed.

        Args:
            scope_name: The name of the scope (e.g., "request", "session")

        Returns:
            A context manager that activates/deactivates the scope

        Examples:
            >>> async with container.scope("request"):
            ...     # All request-scoped services share instances here
            ...     service1 = await container.resolve(RequestService)
            ...     service2 = await container.resolve(RequestService)
            ...     assert service1 is service2
            ... # Instances are disposed when scope exits
        """
        from .scopes import ScopeManager
        return ScopeManager(self, scope_name)

    def enter_scope(self, scope_name: str) -> None:
        """Enter a named scope, activating it for component resolution.

        This is a low-level method used by ScopeManager. Most users should
        use the scope() context manager instead.

        Args:
            scope_name: The name of the scope to activate
        """
        # Get current active scopes
        active_scopes = _active_scopes.get()
        if active_scopes is None:
            active_scopes = {}
        else:
            # Copy to avoid modifying shared state
            active_scopes = active_scopes.copy()
        
        # Mark scope as active
        active_scopes[scope_name] = {}
        _active_scopes.set(active_scopes)

    def exit_scope(self, scope_name: str) -> None:
        """Exit a named scope, deactivating it and cleaning up instances.

        This is a low-level method used by ScopeManager. Most users should
        use the scope() context manager instead.

        Args:
            scope_name: The name of the scope to deactivate
        """
        # Clean up scoped instances
        if scope_name in self._scoped_caches:
            # Dispose of all instances in this scope
            scope_cache = self._scoped_caches[scope_name]
            for instance in scope_cache.values():
                self._call_dispose_hook(instance)
            
            # Clear the cache
            del self._scoped_caches[scope_name]
        
        # Remove from active scopes
        active_scopes = _active_scopes.get()
        if active_scopes and scope_name in active_scopes:
            active_scopes = active_scopes.copy()
            del active_scopes[scope_name]
            _active_scopes.set(active_scopes if active_scopes else None)

    # Function injection and calling methods are handled by SmartCalling mixin

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

    # Lifecycle hook methods
    
    def _call_initialize_hook(self, instance: Any) -> None:
        """Call the initialize hook on an instance if it exists (sync version)."""
        if hasattr(instance, 'initialize') and callable(getattr(instance, 'initialize')):
            try:
                instance.initialize()
            except Exception as e:
                raise ResolutionError(
                    f"Failed to initialize {type(instance).__name__}: {e}",
                    type(instance).__name__.lower(),
                    e
                ) from e
    
    async def _call_initialize_hook_async(self, instance: Any) -> None:
        """Call the initialize hook on an instance if it exists (async version)."""
        if hasattr(instance, 'initialize') and callable(getattr(instance, 'initialize')):
            try:
                initialize_method = getattr(instance, 'initialize')
                if asyncio.iscoroutinefunction(initialize_method):
                    await initialize_method()
                else:
                    initialize_method()
            except Exception as e:
                raise ResolutionError(
                    f"Failed to initialize {type(instance).__name__}: {e}",
                    type(instance).__name__.lower(),
                    e
                ) from e
    
    def _call_dispose_hook(self, instance: Any) -> None:
        """Call the dispose hook on an instance if it exists (sync version)."""
        if hasattr(instance, 'dispose') and callable(getattr(instance, 'dispose')):
            try:
                instance.dispose()
            except Exception as e:
                # Dispose failures are logged but don't raise
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to dispose {type(instance).__name__}: {e}")
    
    async def _call_dispose_hook_async(self, instance: Any) -> None:
        """Call the dispose hook on an instance if it exists (async version)."""
        if hasattr(instance, 'dispose') and callable(getattr(instance, 'dispose')):
            try:
                dispose_method = getattr(instance, 'dispose')
                if asyncio.iscoroutinefunction(dispose_method):
                    await dispose_method()
                else:
                    dispose_method()
            except Exception as e:
                # Dispose failures are logged but don't raise
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to dispose {type(instance).__name__}: {e}")
    
    def _track_instance_for_disposal(self, key: str, instance: Any, scope: Scope) -> None:
        """Track an instance for disposal based on its scope."""
        # Only track singletons and scoped instances for disposal
        # Transient instances are not tracked since they're not managed by the container
        if scope in (Scope.SINGLETON, Scope.SCOPED):
            if hasattr(instance, 'dispose') and callable(getattr(instance, 'dispose')):
                self._tracked_instances[key] = instance
    
    def clear_singletons(self) -> None:
        """Clear all singleton instances, calling dispose hooks."""
        # First, dispose of all singleton instances
        for instance in self._singleton_cache.values():
            self._call_dispose_hook(instance)
        
        # Clear the singleton cache
        self._singleton_cache.clear()
        
        # Remove disposed singletons from tracking
        # We need to identify which tracked instances are singletons
        # Since we cleared the cache, we can't use it anymore
        # Instead, we'll track which instances were disposed and remove them from tracking
        disposed_keys = []
        for key, instance in self._tracked_instances.items():
            # If this instance was in the singleton cache (now cleared), remove it from tracking
            try:
                # Try to get the descriptor to check scope
                descriptor = self.registry.get(key)
                if descriptor.scope == Scope.SINGLETON:
                    disposed_keys.append(key)
            except (KeyError, AttributeError):
                # If we can't determine the scope, err on the side of keeping it tracked
                pass
        
        for key in disposed_keys:
            if key in self._tracked_instances:
                del self._tracked_instances[key]
    
    async def clear_singletons_async(self) -> None:
        """Clear all singleton instances, calling dispose hooks (async version)."""
        # First, dispose of all singleton instances
        for instance in self._singleton_cache.values():
            await self._call_dispose_hook_async(instance)
        
        # Clear the singleton cache
        self._singleton_cache.clear()
        
        # Remove disposed singletons from tracking
        disposed_keys = []
        for key, instance in self._tracked_instances.items():
            try:
                # Try to get the descriptor to check scope
                descriptor = self.registry.get(key)
                if descriptor.scope == Scope.SINGLETON:
                    disposed_keys.append(key)
            except (KeyError, AttributeError):
                # If we can't determine the scope, err on the side of keeping it tracked
                pass
        
        for key in disposed_keys:
            if key in self._tracked_instances:
                del self._tracked_instances[key]

    # Test compatibility methods have been moved to whiskey.core.testing module
    # Use TestContainer or add_test_compatibility_methods() for legacy test support


# ScopeContext and ScopeContextManager moved to testing module


def get_current_container() -> Container | None:
    """Get the current container from context."""
    return _current_container.get()


def set_current_container(container: Container):
    """Set the current container in context and return a token."""
    return _current_container.set(container)
