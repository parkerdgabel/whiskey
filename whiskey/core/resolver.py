"""Dependency resolver with cycle detection for Whiskey framework."""

from __future__ import annotations

import inspect
from typing import Any, get_type_hints

from whiskey.core.exceptions import (
    CircularDependencyError,
    InjectionError,
    ResolutionError,
    ServiceNotFoundError,
)
from whiskey.core.types import (
    Initializable,
    InjectionPoint,
    ResolverContext,
    ServiceDescriptor,
    ServiceKey,
    is_optional_type,
    unwrap_optional,
)


class DependencyResolver:
    """Resolves dependencies with cycle detection."""

    def __init__(self, container: Any):  # Any to avoid circular import
        self._container = container

    async def resolve(self, service_key: ServiceKey) -> Any:
        """Resolve a service and its dependencies."""
        context = ResolverContext(
            container=self._container,
            scope=None,  # Will be set based on service descriptor
        )
        return await self._resolve_internal(service_key, context)

    async def _resolve_internal(
        self, service_key: ServiceKey, context: ResolverContext
    ) -> Any:
        """Internal resolution logic."""
        # Check for circular dependencies
        if service_key in context.stack:
            raise CircularDependencyError([*context.stack, service_key])

        # Add to resolution stack
        context.stack.append(service_key)

        try:
            # Get service descriptor
            descriptor = self._get_descriptor(service_key)
            if not descriptor:
                self._handle_missing_service(service_key)

            # Get the appropriate scope
            scope = self._container.scope_manager.get_scope(descriptor.scope)
            context.scope = scope

            # Check if instance already exists in scope
            instance = await scope.get(service_key)
            if instance is not None:
                return instance

            # Create new instance
            instance = await self._create_instance(descriptor, context)

            # Store in scope
            await scope.set(service_key, instance)

            # Initialize if needed
            if isinstance(instance, Initializable):
                await instance.initialize()

            return instance

        finally:
            # Remove from resolution stack
            context.stack.pop()

    async def _create_instance(
        self, descriptor: ServiceDescriptor, context: ResolverContext
    ) -> Any:
        """Create a new instance of a service."""
        # If we have a pre-existing instance, return it
        if descriptor.instance is not None:
            return descriptor.instance

        # If we have a factory, use it
        if descriptor.factory is not None:
            return await self._create_from_factory(descriptor.factory, context)

        # Otherwise, instantiate the implementation
        if descriptor.implementation is not None:
            return await self._create_from_class(descriptor.implementation, context)

        raise ResolutionError(
            descriptor.service_type,
            "No implementation, factory, or instance provided",
        )

    async def _create_from_factory(
        self, factory: Any, context: ResolverContext
    ) -> Any:
        """Create instance using a factory function."""
        # Get factory parameters
        injection_points = self._get_injection_points(factory)

        # Resolve dependencies
        kwargs = await self._resolve_dependencies(injection_points, context)

        # Call factory
        if inspect.iscoroutinefunction(factory):
            return await factory(**kwargs)
        else:
            return factory(**kwargs)

    async def _create_from_class(
        self, implementation: type, context: ResolverContext
    ) -> Any:
        """Create instance from a class."""
        # Get constructor parameters
        injection_points = self._get_injection_points(implementation.__init__)

        # Resolve dependencies
        kwargs = await self._resolve_dependencies(injection_points, context)

        # Create instance
        return implementation(**kwargs)

    async def _resolve_dependencies(
        self, injection_points: list[InjectionPoint], context: ResolverContext
    ) -> dict[str, Any]:
        """Resolve all dependencies for injection points."""
        kwargs = {}

        for point in injection_points:
            try:
                # Create child context for nested resolution
                child_context = context.create_child()

                # Resolve the dependency
                if point.is_optional:
                    try:
                        value = await self._resolve_internal(point.service_key, child_context)
                    except ServiceNotFoundError:
                        value = None
                else:
                    value = await self._resolve_internal(point.service_key, child_context)

                kwargs[point.parameter_name] = value

            except Exception as e:
                raise InjectionError(
                    target=context.stack[-1] if context.stack else "Unknown",
                    parameter=point.parameter_name,
                    reason=str(e),
                ) from e

        return kwargs

    def _get_injection_points(self, target: Any) -> list[InjectionPoint]:
        """Extract injection points from a callable."""
        injection_points = []

        # Get signature
        sig = inspect.signature(target)

        # Get type hints (handles forward references better)
        try:
            hints = get_type_hints(target)
        except Exception:
            # Fallback to annotations if get_type_hints fails
            hints = {}

        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls"):
                continue

            # Get type annotation
            param_type = hints.get(param_name, param.annotation)

            # Skip if no type annotation
            if param_type == param.empty:
                continue

            # Check if optional
            is_optional = is_optional_type(param_type)
            if is_optional:
                param_type = unwrap_optional(param_type)

            # Create injection point
            injection_point = InjectionPoint(
                parameter_name=param_name,
                service_key=param_type,
                is_optional=is_optional or param.default != param.empty,
            )

            injection_points.append(injection_point)

        return injection_points

    def _get_descriptor(self, service_key: ServiceKey) -> ServiceDescriptor | None:
        """Get descriptor for a service key."""
        # Try current container
        descriptor = self._container._services.get(service_key)
        if descriptor:
            return descriptor

        # Try parent container
        if self._container.parent:
            return self._container.parent.get_descriptor(service_key)

        return None

    def _handle_missing_service(self, service_key: ServiceKey) -> None:
        """Handle missing service with helpful error message."""
        # Get available services
        all_services = list(self._container.get_all_services().keys())
        available = [str(s) for s in all_services]

        # Try to provide helpful suggestions
        suggestions = []
        if isinstance(service_key, type):
            # Look for subclasses
            for key, _desc in self._container.get_all_services().items():
                if isinstance(key, type) and issubclass(key, service_key):
                    suggestions.append(f"Did you mean {key.__name__}?")

        raise ServiceNotFoundError(service_key, available)