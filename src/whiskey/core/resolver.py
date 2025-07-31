"""Unified resolver system for dependency injection.

This module consolidates all resolution logic into a cohesive, loosely coupled design.
It combines type analysis, generic resolution, and smart context detection into
a single, well-organized resolver system.

Key Design Principles:
1. Single Responsibility: Each resolver handles one aspect of resolution
2. Loose Coupling: Resolvers communicate through well-defined interfaces
3. Composition over Inheritance: Use composition to build complex resolvers
4. Clear Separation: Type analysis, resolution strategy, and execution are separate

Architecture:
    ResolverInterface (Protocol)
        ├── TypeResolver - Analyzes types and decides injection strategy
        ├── DependencyResolver - Resolves component dependencies
        ├── ScopeResolver - Handles scoped resolution
        └── AsyncResolver - Handles async/sync context adaptation
"""

from __future__ import annotations

import asyncio
import inspect
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, TypeVar, runtime_checkable
from weakref import WeakKeyDictionary

from .analyzer import InjectDecision, InjectResult, TypeAnalyzer
from .errors import CircularDependencyError, ResolutionError
from .generic_resolution import GenericTypeResolver
from .registry import ComponentDescriptor, ComponentRegistry, Scope

T = TypeVar("T")


@dataclass
class ResolutionContext:
    """Context information for a resolution operation."""
    
    key: str | type
    name: str | None = None
    overrides: dict[str, Any] = field(default_factory=dict)
    scope_context: dict[str, Any] = field(default_factory=dict)
    resolving_stack: list[str] = field(default_factory=list)
    depth: int = 0
    is_async: bool = False


@runtime_checkable
class ResolverInterface(Protocol):
    """Protocol defining the resolver interface."""
    
    def can_resolve(self, context: ResolutionContext) -> bool:
        """Check if this resolver can handle the given context."""
        ...
    
    def resolve(self, context: ResolutionContext) -> Any:
        """Resolve synchronously."""
        ...
    
    async def resolve_async(self, context: ResolutionContext) -> Any:
        """Resolve asynchronously."""
        ...


class TypeResolver:
    """Handles type analysis and injection decision making.
    
    This resolver is responsible for:
    - Analyzing type hints to determine injection strategy
    - Handling generic type resolution
    - Managing type analysis caching
    - Providing injection decisions
    """
    
    def __init__(self, registry: ComponentRegistry):
        self.registry = registry
        self._type_analyzer = TypeAnalyzer(registry)
        self._generic_resolver = GenericTypeResolver(registry)
        self._analysis_cache: WeakKeyDictionary = WeakKeyDictionary()
    
    def analyze_type(self, type_hint: Any) -> InjectResult:
        """Analyze a type and determine injection strategy."""
        # Check cache first
        if type_hint in self._analysis_cache:
            return self._analysis_cache[type_hint]
        
        # Perform analysis
        result = self._type_analyzer._analyze_type_hint(type_hint)
        
        # Cache result
        self._analysis_cache[type_hint] = result
        return result
    
    def analyze_callable(self, func: Callable) -> dict[str, InjectResult]:
        """Analyze all parameters of a callable."""
        return self._type_analyzer.analyze_callable(func)
    
    def resolve_generic(self, generic_type: Any) -> type | None:
        """Resolve a generic type to its concrete implementation."""
        return self._generic_resolver.resolve_generic(generic_type)
    
    def register_generic_implementation(self, generic_type: Any, concrete_type: type) -> None:
        """Register a concrete implementation for a generic type."""
        self._generic_resolver.register_concrete(generic_type, concrete_type)
    
    def can_auto_create(self, cls: type) -> bool:
        """Check if a class can be auto-created."""
        return self._type_analyzer.can_auto_create(cls)


class DependencyResolver:
    """Handles the actual dependency resolution logic.
    
    This resolver is responsible for:
    - Creating instances with dependency injection
    - Managing resolution cache
    - Handling factory functions
    - Auto-creating unregistered types when possible
    """
    
    def __init__(self, registry: ComponentRegistry, type_resolver: TypeResolver):
        self.registry = registry
        self.type_resolver = type_resolver
        self._injection_cache: WeakKeyDictionary = WeakKeyDictionary()
        self._resolving_local = threading.local()
    
    def resolve_dependencies(self, cls: type, overrides: dict[str, Any]) -> dict[str, Any]:
        """Resolve all dependencies for a class constructor."""
        # Check cache
        if cls in self._injection_cache and not overrides:
            return self._injection_cache[cls].copy()
        
        # Analyze constructor
        analysis = self.type_resolver.analyze_callable(cls.__init__)
        
        # Build kwargs
        kwargs = {}
        for param_name, inject_result in analysis.items():
            if param_name in overrides:
                kwargs[param_name] = overrides[param_name]
            elif inject_result.decision == InjectDecision.YES:
                # This will be resolved by the calling resolver
                kwargs[param_name] = inject_result.type_hint
            elif inject_result.decision == InjectDecision.OPTIONAL:
                # Mark as optional for resolution
                kwargs[param_name] = (inject_result.inner_type, True)  # (type, is_optional)
        
        # Cache if no overrides
        if not overrides:
            self._injection_cache[cls] = kwargs.copy()
        
        return kwargs
    
    def create_instance(self, provider: Any, resolved_deps: dict[str, Any]) -> Any:
        """Create an instance with resolved dependencies."""
        if isinstance(provider, type):
            return provider(**resolved_deps)
        elif callable(provider):
            return provider(**resolved_deps)
        else:
            # Instance provider
            return provider
    
    def get_resolving_stack(self) -> set[str]:
        """Get thread-local resolving stack for circular dependency detection."""
        if not hasattr(self._resolving_local, "stack"):
            self._resolving_local.stack = set()
        return self._resolving_local.stack


class ScopeResolver:
    """Handles scope-based resolution strategies.
    
    This resolver is responsible for:
    - Managing singleton instances
    - Handling scoped instances
    - Implementing scope validation
    - Managing instance lifecycle
    """
    
    def __init__(self):
        self._singleton_cache: dict[str, Any] = {}
        self._scoped_caches: dict[str, dict[str, Any]] = {}
        self._singleton_lock = threading.RLock()
    
    def resolve_singleton(self, key: str, factory: Callable[[], Any]) -> Any:
        """Resolve a singleton instance with thread safety."""
        # Double-checked locking pattern
        if key in self._singleton_cache:
            return self._singleton_cache[key]
        
        with self._singleton_lock:
            if key in self._singleton_cache:
                return self._singleton_cache[key]
            
            instance = factory()
            self._singleton_cache[key] = instance
            return instance
    
    def resolve_scoped(self, key: str, scope_name: str, factory: Callable[[], Any], 
                      active_scopes: dict[str, dict[str, Any]] | None) -> Any:
        """Resolve a scoped instance."""
        if not active_scopes or scope_name not in active_scopes:
            raise ScopeError(f"Scope '{scope_name}' is not active")
        
        scope_cache = self._scoped_caches.setdefault(scope_name, {})
        
        if key not in scope_cache:
            instance = factory()
            scope_cache[key] = instance
        
        return scope_cache[key]
    
    def clear_scope(self, scope_name: str) -> None:
        """Clear all instances in a scope."""
        if scope_name in self._scoped_caches:
            del self._scoped_caches[scope_name]


class AsyncResolver:
    """Handles async/sync context adaptation.
    
    This resolver is responsible for:
    - Detecting execution context (sync/async)
    - Adapting resolution strategy based on context
    - Providing clear error messages for context mismatches
    - Managing async coordination
    """
    
    @staticmethod
    def is_async_context() -> bool:
        """Check if we're in an async context."""
        try:
            asyncio.get_running_loop()
            return True
        except RuntimeError:
            return False
    
    @staticmethod
    def require_sync_context(operation: str, key: Any) -> None:
        """Ensure we're not in an async context for sync operations."""
        if AsyncResolver.is_async_context():
            key_name = getattr(key, "__name__", str(key))
            raise RuntimeError(
                f"Cannot perform synchronous {operation} of '{key_name}' in async context. "
                f"Use 'await container.resolve({key_name})' instead."
            )
    
    @staticmethod
    def check_async_provider(provider: Any, key: Any) -> None:
        """Check if a provider requires async resolution."""
        if callable(provider) and asyncio.iscoroutinefunction(provider):
            key_name = getattr(key, "__name__", str(key))
            raise RuntimeError(
                f"Component '{key_name}' uses an async factory and requires async resolution. "
                f"Use 'await container.resolve({key_name})' or 'resolve_async()'."
            )


class UnifiedResolver:
    """Main resolver that coordinates all resolution strategies.
    
    This is the main entry point that combines all resolvers into a cohesive system.
    It delegates to specialized resolvers while maintaining loose coupling.
    """
    
    def __init__(self, registry: ComponentRegistry):
        self.registry = registry
        self.type_resolver = TypeResolver(registry)
        self.dependency_resolver = DependencyResolver(registry, self.type_resolver)
        self.scope_resolver = ScopeResolver()
        self.async_resolver = AsyncResolver()
    
    def resolve(self, key: str | type, name: str | None = None, **kwargs) -> Any:
        """Smart resolution that adapts to context."""
        if self.async_resolver.is_async_context():
            # Return coroutine in async context
            return self._resolve_async(key, name, **kwargs)
        else:
            # Direct resolution in sync context
            return self._resolve_sync(key, name, **kwargs)
    
    def _resolve_sync(self, key: str | type, name: str | None = None, **kwargs) -> Any:
        """Synchronous resolution implementation."""
        context = ResolutionContext(
            key=key,
            name=name,
            overrides=kwargs.get("overrides", {}),
            scope_context=kwargs.get("scope_context", {}),
            is_async=False
        )
        
        # Get descriptor
        descriptor = self._get_descriptor(context)
        
        # Check provider compatibility
        self.async_resolver.check_async_provider(descriptor.provider, key)
        
        # Check circular dependencies
        self._check_circular_dependency(context, descriptor)
        
        try:
            # Resolve based on scope
            return self._resolve_by_scope_sync(descriptor, context)
        finally:
            self._clear_resolving(context, descriptor)
    
    async def _resolve_async(self, key: str | type, name: str | None = None, **kwargs) -> Any:
        """Asynchronous resolution implementation."""
        context = ResolutionContext(
            key=key,
            name=name,
            overrides=kwargs.get("overrides", {}),
            scope_context=kwargs.get("scope_context", {}),
            is_async=True
        )
        
        # Get descriptor
        descriptor = self._get_descriptor(context)
        
        # Check circular dependencies
        self._check_circular_dependency(context, descriptor)
        
        try:
            # Resolve based on scope
            return await self._resolve_by_scope_async(descriptor, context)
        finally:
            self._clear_resolving(context, descriptor)
    
    def _get_descriptor(self, context: ResolutionContext) -> ComponentDescriptor:
        """Get component descriptor, with auto-creation fallback."""
        try:
            return self.registry.get(context.key, context.name)
        except KeyError:
            # Try auto-creation for unregistered types
            if isinstance(context.key, type) and self.type_resolver.can_auto_create(context.key):
                # Register temporarily for auto-creation
                descriptor = ComponentDescriptor(
                    key=str(context.key),
                    component_type=context.key,
                    provider=context.key,
                    scope=Scope.TRANSIENT
                )
                return descriptor
            raise ResolutionError(f"Component '{context.key}' not registered")
    
    def _check_circular_dependency(self, context: ResolutionContext, descriptor: ComponentDescriptor) -> None:
        """Check for circular dependencies."""
        resolving = self.dependency_resolver.get_resolving_stack()
        if descriptor.key in resolving:
            raise CircularDependencyError(f"Circular dependency detected: {list(resolving)} -> {descriptor.key}")
        resolving.add(descriptor.key)
    
    def _clear_resolving(self, context: ResolutionContext, descriptor: ComponentDescriptor) -> None:
        """Clear from resolving stack."""
        resolving = self.dependency_resolver.get_resolving_stack()
        resolving.discard(descriptor.key)
    
    def _resolve_by_scope_sync(self, descriptor: ComponentDescriptor, context: ResolutionContext) -> Any:
        """Resolve based on component scope (sync)."""
        if descriptor.scope == Scope.SINGLETON:
            return self.scope_resolver.resolve_singleton(
                descriptor.key,
                lambda: self._create_instance_sync(descriptor, context)
            )
        elif descriptor.scope == Scope.SCOPED:
            scope_name = descriptor.metadata.get("scope_name", "default")
            return self.scope_resolver.resolve_scoped(
                descriptor.key,
                scope_name,
                lambda: self._create_instance_sync(descriptor, context),
                context.scope_context
            )
        else:  # TRANSIENT
            return self._create_instance_sync(descriptor, context)
    
    async def _resolve_by_scope_async(self, descriptor: ComponentDescriptor, context: ResolutionContext) -> Any:
        """Resolve based on component scope (async)."""
        if descriptor.scope == Scope.SINGLETON:
            # Use sync singleton resolution in executor for thread safety
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                None,
                self.scope_resolver.resolve_singleton,
                descriptor.key,
                lambda: self._create_instance_sync(descriptor, context)
            )
        elif descriptor.scope == Scope.SCOPED:
            scope_name = descriptor.metadata.get("scope_name", "default")
            # For now, use sync version
            # TODO: Implement async scope resolution
            return self.scope_resolver.resolve_scoped(
                descriptor.key,
                scope_name,
                lambda: self._create_instance_sync(descriptor, context),
                context.scope_context
            )
        else:  # TRANSIENT
            return await self._create_instance_async(descriptor, context)
    
    def _create_instance_sync(self, descriptor: ComponentDescriptor, context: ResolutionContext) -> Any:
        """Create instance with dependency injection (sync)."""
        provider = descriptor.provider
        
        if not callable(provider) and not isinstance(provider, type):
            # Direct instance
            return provider
        
        # Get dependency map
        dep_map = self.dependency_resolver.resolve_dependencies(
            provider if isinstance(provider, type) else type(provider),
            context.overrides
        )
        
        # Resolve each dependency
        resolved = {}
        for param_name, dep_spec in dep_map.items():
            if isinstance(dep_spec, tuple):  # Optional dependency
                dep_type, is_optional = dep_spec
                try:
                    resolved[param_name] = self._resolve_sync(dep_type)
                except ResolutionError:
                    if is_optional:
                        resolved[param_name] = None
                    else:
                        raise
            else:
                # Regular dependency or override
                if param_name in context.overrides:
                    resolved[param_name] = context.overrides[param_name]
                else:
                    resolved[param_name] = self._resolve_sync(dep_spec)
        
        # Create instance
        return self.dependency_resolver.create_instance(provider, resolved)
    
    async def _create_instance_async(self, descriptor: ComponentDescriptor, context: ResolutionContext) -> Any:
        """Create instance with dependency injection (async)."""
        provider = descriptor.provider
        
        if not callable(provider) and not isinstance(provider, type):
            # Direct instance
            return provider
        
        # For now, delegate to sync version
        # TODO: Implement proper async dependency resolution
        return self._create_instance_sync(descriptor, context)


# Public API functions

def create_resolver(registry: ComponentRegistry) -> UnifiedResolver:
    """Create a new unified resolver with the given registry."""
    return UnifiedResolver(registry)