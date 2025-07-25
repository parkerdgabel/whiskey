"""Component discovery and introspection for automatic registration.

This module provides utilities for discovering components in modules
and packages, enabling automatic registration and reducing boilerplate.

Key features:
    - Module and package scanning
    - Filtering by predicate or decorator
    - Automatic registration
    - Introspection and debugging tools
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
        module_name: str,
        *,
        predicate: Callable[[type], bool] | None = None,
        decorator_name: str | None = None,
    ) -> set[type]:
        """Discover components in a single module.

        Scans a module for classes that match the given criteria.
        Only classes defined in the module (not imported) are considered.

        Args:
            module_name: Fully qualified module name (e.g., "myapp.services")
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
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            return set()

        discovered = set()

        for name in dir(module):
            obj = getattr(module, name)

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
        scope: str = "transient",
        condition: Callable[[type], bool] | None = None,
    ) -> None:
        """Auto-register discovered components.

        Args:
            components: Components to register
            scope: Default scope for registration
            condition: Optional condition to check before registering
        """
        for component in components:
            if condition and not condition(component):
                continue

            # Check if already registered
            if component in self.container:
                continue

            # Auto-register with default scope
            self.container.register(component, scope=scope)


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
    ) -> list[type]:
        """List registered services with optional filters.

        Args:
            interface: Only include services that inherit from this type
            scope: Only include services with this scope ("singleton", "transient", etc.)
            tags: Only include services with these tags (requires metadata)

        Returns:
            List of matching service types

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
        services = []

        for service_type in self.container.keys():
            # Filter by interface
            if interface and not issubclass(service_type, interface):
                continue

            # Filter by scope
            if scope:
                service_scope = self.container._service_scopes.get(service_type)
                if service_scope != scope:
                    continue

            services.append(service_type)

        return services

    def get_dependencies(self, service_type: type) -> dict[str, type]:
        """Get dependencies of a service.

        Args:
            service_type: Service type to inspect

        Returns:
            Dict mapping parameter names to types
        """
        if not inspect.isclass(service_type):
            return {}

        try:
            sig = inspect.signature(service_type)
        except (ValueError, TypeError):
            # Can't get signature for some types
            return {}

        dependencies = {}

        for param_name, param in sig.parameters.items():
            if param.annotation != param.empty:
                dependencies[param_name] = param.annotation

        return dependencies

    def can_resolve(self, service_type: type) -> bool:
        """Check if a service can be resolved.

        Args:
            service_type: Service type to check

        Returns:
            True if service and all its dependencies can be resolved
        """
        if service_type in self.container:
            return True

        # Check if we can create it
        if not inspect.isclass(service_type):
            return False

        # Check all dependencies
        deps = self.get_dependencies(service_type)
        for dep_type in deps.values():
            # Handle Annotated types
            from typing import get_args, get_origin

            origin = get_origin(dep_type)
            if origin is not None:
                try:
                    from typing import Annotated

                    if origin is Annotated:
                        # Get the actual type from Annotated
                        args = get_args(dep_type)
                        if args:
                            dep_type = args[0]
                except ImportError:
                    pass

            if isinstance(dep_type, type) and not self.can_resolve(dep_type):
                return False

        return True

    def resolution_report(self, service_type: type) -> dict[str, Any]:
        """Generate a detailed resolution report.

        Args:
            service_type: Service type to analyze

        Returns:
            Dict with resolution details
        """
        report = {
            "type": service_type,
            "registered": service_type in self.container,
            "can_resolve": self.can_resolve(service_type),
            "dependencies": {},
            "scope": self.container._service_scopes.get(service_type, "transient"),
        }

        deps = self.get_dependencies(service_type)
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

            report["dependencies"][param_name] = {
                "type": dep_type,
                "actual_type": actual_type,
                "registered": actual_type in self.container
                if isinstance(actual_type, type)
                else False,
                "can_resolve": self.can_resolve(actual_type)
                if isinstance(actual_type, type)
                else False,
            }

        return report

    def dependency_graph(self) -> dict[type, set[type]]:
        """Build a dependency graph of all services.

        Returns:
            Dict mapping service types to their dependencies
        """
        graph = {}

        for service_type in self.container.keys():
            deps = self.get_dependencies(service_type)
            graph[service_type] = {
                dep_type for dep_type in deps.values() if isinstance(dep_type, type)
            }

        return graph


def discover_components(
    module_or_package: str | Any,
    *,
    container: Container | None = None,
    auto_register: bool = False,
    **kwargs,
) -> set[type]:
    """Convenience function for component discovery.

    Args:
        module_or_package: Module or package to scan
        container: Container to use (creates new if None)
        auto_register: Whether to auto-register found components
        **kwargs: Additional arguments for discovery

    Returns:
        Set of discovered components
    """
    if container is None:
        from whiskey.core.decorators import get_default_container

        container = get_default_container()

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
            components = discoverer.discover_module(module_or_package.__name__, **kwargs)

    if auto_register:
        discoverer.auto_register(components)

    return components
