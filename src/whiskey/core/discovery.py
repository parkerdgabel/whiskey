"""Automatic component discovery and registration from Python modules.

This module implements component discovery mechanisms that automatically find
and register services from Python modules and packages. It reduces boilerplate
by eliminating manual registration while providing fine-grained control over
what gets discovered and how it's registered.

Classes:
    ComponentInfo: Metadata about discovered components
    DiscoveryOptions: Configuration for discovery process
    ComponentDiscovery: Main discovery engine

Functions:
    discover_components: Find components in modules/packages
    is_component: Check if object has component markers
    get_component_metadata: Extract registration metadata
    auto_register: Register discovered components

Discovery Methods:
    1. Decorator-based: Find classes marked with @component, @singleton
    2. Naming convention: Classes ending with Service, Repository, etc.
    3. Base class: Classes inheriting from specific interfaces
    4. Custom predicates: Any callable returning bool

Features:
    - Recursive package scanning with exclusion patterns
    - Module lazy loading to reduce import overhead
    - Duplicate detection with conflict resolution
    - Registration verification and validation
    - Discovery caching for performance
    - Detailed discovery reports

Example:
    >>> from whiskey import Whiskey
    >>> from whiskey.core.discovery import discover_components
    >>> 
    >>> app = Whiskey()
    >>> 
    >>> # Discover by decorator
    >>> components = discover_components(
    ...     'myapp.services',
    ...     predicate=lambda obj: hasattr(obj, '_whiskey_component'),
    ...     recursive=True
    ... )
    >>> 
    >>> # Auto-register discovered components
    >>> for component in components:
    ...     app.container.register(component.cls, scope=component.scope)
    >>> 
    >>> # Using application's discover method
    >>> app.discover(
    ...     'myapp',
    ...     decorator_name='_component',
    ...     auto_register=True,
    ...     exclude=['tests', '__pycache__']
    ... )
    >>> 
    >>> # Custom discovery predicate
    >>> def is_repository(cls):
    ...     return (
    ...         inspect.isclass(cls) and 
    ...         cls.__name__.endswith('Repository') and
    ...         hasattr(cls, 'find_by_id')
    ...     )
    >>> 
    >>> app.discover('myapp.data', predicate=is_repository)

Best Practices:
    - Use consistent naming conventions
    - Group related components in modules
    - Exclude test and development modules
    - Verify discovered components before production
    - Cache discovery results in production
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import Any, Callable, TypeVar

from whiskey.core.container import Container

T = TypeVar("T")


class ComponentDiscoverer:
    """Discovers and optionally registers components in modules and packages.

    The ComponentDiscoverer scans Python modules for classes that match
    specified criteria and can automatically register them with a container.

    Examples:
        Basic discovery:

        >>> discoverer = ComponentDiscoverer(container)
        >>> components = discoverer.discover_module("myapp.services")
        >>> print(f"Found {len(components)} components")

        With auto-registration:

        >>> # Register all classes ending with 'Service'
        >>> discoverer.discover_package(
        ...     "myapp",
        ...     predicate=lambda cls: cls.__name__.endswith("Service"),
        ...     auto_register=True
        ... )

        By decorator:

        >>> # Find all classes with @entity decorator
        >>> entities = discoverer.discover_module(
        ...     "myapp.models",
        ...     decorator_name="_entity"
        ... )

    Attributes:
        container: The Container to register components with
        _discovered: Set tracking already discovered types
    """

    def __init__(self, container: Container):
        """Initialize discoverer with a container.

        Args:
            container: Container instance for registration
        """
        self.container = container
        self._discovered: set[type] = set()

    def discover_module(
        self,
        module_name: str | Any,
        *,
        predicate: Callable[[type], bool] | None = None,
        decorator_name: str | None = None,
    ) -> set[type]:
        """Discover components in a single module.

        Scans a module for classes that match the given criteria.
        Only classes defined in the module (not imported) are considered.

        Args:
            module_name: Fully qualified module name (e.g., "myapp.services") or module object
            predicate: Optional function to filter classes.
                      Should return True for classes to include.
            decorator_name: Optional attribute name to check for.
                          Classes must have this attribute to be included.

        Returns:
            Set of discovered component types

        Examples:
            >>> # Find all classes in a module
            >>> all_classes = discoverer.discover_module("myapp.models")

            >>> # Find classes matching a pattern
            >>> services = discoverer.discover_module(
            ...     "myapp.services",
            ...     predicate=lambda cls: cls.__name__.endswith("Service")
            ... )

            >>> # Find decorated classes
            >>> entities = discoverer.discover_module(
            ...     "myapp.models",
            ...     decorator_name="_is_entity"
            ... )
        """
        if isinstance(module_name, str):
            try:
                module = importlib.import_module(module_name)
            except ImportError:
                return set()
        else:
            # Assume it's a module object
            module = module_name
            module_name = module.__name__

        discovered = set()

        for name in dir(module):
            try:
                obj = getattr(module, name)
            except Exception:
                # Skip attributes that raise exceptions when accessed
                continue

            # Skip non-classes
            if not inspect.isclass(obj):
                continue

            # Skip imported classes (only find ones defined in this module)
            if obj.__module__ != module_name:
                continue

            # Apply filters
            if predicate and not predicate(obj):
                continue

            if decorator_name and not hasattr(obj, decorator_name):
                continue

            discovered.add(obj)
            self._discovered.add(obj)

        return discovered

    def discover_package(
        self,
        package: str | Any,
        *,
        recursive: bool = True,
        predicate: Callable[[type], bool] | None = None,
        decorator_name: str | None = None,
    ) -> set[type]:
        """Discover components in a package.

        Args:
            package: Package name or module object
            recursive: Whether to scan submodules
            predicate: Optional filter function
            decorator_name: Optional decorator attribute to check for

        Returns:
            Set of discovered component types
        """
        if isinstance(package, str):
            try:
                package = importlib.import_module(package)
            except ImportError:
                return set()

        discovered = set()

        # Discover in the package itself
        if hasattr(package, "__name__"):
            discovered.update(
                self.discover_module(
                    package.__name__, predicate=predicate, decorator_name=decorator_name
                )
            )

        # Discover in submodules if recursive
        if recursive and hasattr(package, "__path__"):
            for _, module_name, _ in pkgutil.walk_packages(
                package.__path__, prefix=package.__name__ + "."
            ):
                discovered.update(
                    self.discover_module(
                        module_name, predicate=predicate, decorator_name=decorator_name
                    )
                )

        return discovered

    def auto_register(
        self,
        components: set[type],
        *,
        scope: str | Any = "transient",
        condition: Callable[[type], bool] | None = None,
    ) -> set[type]:
        """Auto-register discovered components.

        Args:
            components: Components to register
            scope: Default scope for registration (string or Scope enum)
            condition: Optional condition to check before registering
        
        Returns:
            Set of components that were actually registered
        """
        registered = set()
        for component in components:
            if condition and not condition(component):
                continue

            # Check if already registered
            if component in self.container:
                continue

            # Auto-register with default scope - container.register expects (key, provider)
            from .registry import Scope
            if isinstance(scope, Scope):
                scope_enum = scope
            elif scope == "singleton":
                scope_enum = Scope.SINGLETON
            elif scope == "scoped":
                scope_enum = Scope.SCOPED
            else:
                scope_enum = Scope.TRANSIENT
                
            self.container.register(component, component, scope=scope_enum)
            registered.add(component)
        
        return registered


class ContainerInspector:
    """Provides introspection and debugging capabilities for containers.

    The ContainerInspector allows you to examine the state of a container,
    understand dependencies, and debug resolution issues.

    Examples:
        Basic inspection:

        >>> inspector = container.inspect()
        >>>
        >>> # List all services
        >>> services = inspector.list_services()
        >>> print(f"Registered: {[s.__name__ for s in services]}")
        >>>
        >>> # Check if a service can be resolved
        >>> if inspector.can_resolve(MyService):
        ...     service = await container.resolve(MyService)

        Debugging resolution:

        >>> # Get detailed resolution report
        >>> report = inspector.resolution_report(ComplexService)
        >>> if not report["can_resolve"]:
        ...     print("Missing dependencies:")
        ...     for dep, info in report["dependencies"].items():
        ...         if not info["registered"]:
        ...             print(f"  - {dep}: {info['type']}")

    Attributes:
        container: The Container instance to inspect
    """

    def __init__(self, container: Container):
        """Initialize inspector with a container.

        Args:
            container: Container instance to inspect
        """
        self.container = container

    def list_services(
        self,
        *,
        interface: type | None = None,
        scope: str | None = None,
        tags: set[str] | None = None,
    ) -> dict[str, Any]:
        """List registered services with optional filters.

        Args:
            interface: Only include services that inherit from this type
            scope: Only include services with this scope ("singleton", "transient", etc.)
            tags: Only include services with these tags (requires metadata)

        Returns:
            Dict of service information

        Examples:
            >>> # All singletons
            >>> singletons = inspector.list_services(scope="singleton")
            >>>
            >>> # All implementations of Repository
            >>> repos = inspector.list_services(interface=Repository)
            >>>
            >>> # Combine filters
            >>> singleton_repos = inspector.list_services(
            ...     interface=Repository,
            ...     scope="singleton"
            ... )
        """
        services = {}

        for descriptor in self.container.registry.list_all():
            component_type = descriptor.component_type
            
            # Filter by interface
            if interface and inspect.isclass(component_type) and not issubclass(component_type, interface):
                continue

            # Filter by scope
            if scope and descriptor.scope.value != scope:
                continue

            # Filter by tags
            if tags and not descriptor.has_any_tag(tags):
                continue

            services[descriptor.key] = {
                "type": component_type,
                "scope": descriptor.scope.value,
                "tags": list(descriptor.tags),
                "registered": True
            }

        return services

    def get_dependencies(self, component_type: type) -> dict[str, type]:
        """Get dependencies of a service.

        Args:
            component_type: Service type to inspect

        Returns:
            Dict mapping parameter names to types
        """
        if not inspect.isclass(component_type):
            return {}

        try:
            sig = inspect.signature(component_type)
        except (ValueError, TypeError):
            # Can't get signature for some types
            return {}

        dependencies = {}

        for param_name, param in sig.parameters.items():
            if param.annotation != param.empty:
                dependencies[param_name] = param.annotation

        return dependencies

    def can_resolve(self, component_type: type) -> bool:
        """Check if a service can be resolved.

        Args:
            component_type: Service type to check

        Returns:
            True if service is explicitly registered
        """
        # Only return True for explicitly registered services
        return component_type in self.container

    def resolution_report(self, component_type: type) -> dict[str, Any]:
        """Generate a detailed resolution report.

        Args:
            component_type: Service type to analyze

        Returns:
            Dict with resolution details
        """
        # Try to get service descriptor to determine scope
        scope = "transient"  # default
        try:
            descriptor = self.container.registry.get(component_type)
            scope = descriptor.scope.value
        except KeyError:
            pass
            
        report = {
            "type": component_type,
            "registered": component_type in self.container,
            "can_resolve": self.can_resolve(component_type),
            "dependencies": {},
            "missing_dependencies": [],
            "resolution_path": [],
            "scope": scope,
        }

        deps = self.get_dependencies(component_type)
        for param_name, dep_type in deps.items():
            # Handle Annotated types
            actual_type = dep_type
            from typing import get_args, get_origin

            origin = get_origin(dep_type)
            if origin is not None:
                try:
                    from typing import Annotated

                    if origin is Annotated:
                        args = get_args(dep_type)
                        if args:
                            actual_type = args[0]
                except ImportError:
                    pass

            can_resolve_dep = self.can_resolve(actual_type) if isinstance(actual_type, type) else False
            
            report["dependencies"][param_name] = {
                "type": dep_type,
                "actual_type": actual_type,
                "registered": actual_type in self.container
                if isinstance(actual_type, type)
                else False,
                "can_resolve": can_resolve_dep,
            }
            
            if not can_resolve_dep:
                report["missing_dependencies"].append(param_name)

        return report

    def dependency_graph(self) -> dict[type, set[type]]:
        """Build a dependency graph of all services.

        Returns:
            Dict mapping service types to their dependencies
        """
        graph = {}

        for descriptor in self.container.registry.list_all():
            component_type = descriptor.component_type
            deps = self.get_dependencies(component_type)
            graph[component_type] = {
                dep_type for dep_type in deps.values() if isinstance(dep_type, type)
            }

        return graph


def discover_components(
    module_or_package: str | Any,
    *,
    container: Container,
    auto_register: bool = False,
    **kwargs,
) -> set[type]:
    """Convenience function for component discovery.

    Args:
        module_or_package: Module or package to scan
        container: Container to use for discovery and registration
        auto_register: Whether to auto-register found components
        **kwargs: Additional arguments for discovery

    Returns:
        Set of discovered components
    """
    discoverer = ComponentDiscoverer(container)

    # Determine if it's a package or module
    if isinstance(module_or_package, str):
        if "." in module_or_package:
            # Likely a module
            components = discoverer.discover_module(module_or_package, **kwargs)
        else:
            # Likely a package
            components = discoverer.discover_package(module_or_package, **kwargs)
    else:
        # Assume it's a module object
        if hasattr(module_or_package, "__path__"):
            components = discoverer.discover_package(module_or_package, **kwargs)
        else:
            # Pass the module object directly
            components = discoverer.discover_module(module_or_package, **kwargs)

    if auto_register:
        discoverer.auto_register(components)

    return components
