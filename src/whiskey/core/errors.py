"""Exception hierarchy for clear error reporting in dependency injection.

This module defines a comprehensive exception hierarchy for Whiskey's dependency
injection system. Each exception type represents a specific failure mode with
clear error messages and contextual information to aid debugging.

Exception Hierarchy:
    WhiskeyError: Base exception for all Whiskey errors
    ├── ResolutionError: Component resolution failures
    │   └── CircularDependencyError: Circular dependency detected
    ├── RegistrationError: Component registration failures
    ├── InjectionError: Dependency injection failures
    ├── ScopeError: Scope-related failures
    ├── ConfigurationError: Configuration failures
    └── TypeAnalysisError: Type hint analysis failures

Usage Patterns:
    Each exception includes relevant context:
    - ResolutionError: service_key, cause
    - CircularDependencyError: dependency cycle
    - InjectionError: parameter_name, type_hint
    - TypeAnalysisError: problematic type_hint

Example:
    >>> try:
    ...     component = await container.resolve(UnregisteredComponent)
    ... except ResolutionError as e:
    ...     print(f"Failed to resolve: {e.service_key}")
    ...     if e.cause:
    ...         print(f"Underlying cause: {e.cause}")
    >>>
    >>> try:
    ...     container.register(Component, invalid_provider)
    ... except RegistrationError as e:
    ...     print(f"Registration failed: {e}")

Best Practices:
    - Catch specific exceptions when possible
    - Use WhiskeyError to catch all framework errors
    - Check exception attributes for debugging context
    - Let exceptions bubble up with clear messages
"""

from __future__ import annotations

from typing import Any


class WhiskeyError(Exception):
    """Base exception for all Whiskey-related errors."""

    pass


class ResolutionError(WhiskeyError):
    """Raised when a component cannot be resolved.

    This is the most common error, occurring when:
    - A required component is not registered
    - A component's dependencies cannot be satisfied
    - A condition for component registration is not met
    """

    def __init__(
        self, message: str, service_key: str | None = None, cause: Exception | None = None
    ):
        super().__init__(message)
        self.service_key = service_key
        self.cause = cause


class CircularDependencyError(ResolutionError):
    """Raised when circular dependencies are detected.

    This error provides information about the circular dependency chain
    to help developers understand and fix the issue.
    """

    def __init__(self, cycle: list[type]):
        self.cycle = cycle
        cycle_names = [cls.__name__ for cls in cycle]
        cycle_str = " → ".join([*cycle_names, cycle_names[0]])

        super().__init__(
            f"Circular dependency detected: {cycle_str}",
            service_key=cycle[0].__name__.lower() if cycle else None,
        )


class RegistrationError(WhiskeyError):
    """Raised when component registration fails.

    This occurs when:
    - Invalid registration parameters are provided
    - A component is registered multiple times with conflicting metadata
    - Registration conditions are invalid
    """

    pass


class InjectionError(WhiskeyError):
    """Raised when dependency injection fails.

    This occurs when:
    - Type analysis fails for a parameter
    - Required parameters cannot be injected
    - Ambiguous type hints (e.g., Union with multiple registered types)
    """

    def __init__(self, message: str, parameter_name: str | None = None, type_hint=None):
        super().__init__(message)
        self.parameter_name = parameter_name
        self.type_hint = type_hint


class ScopeError(WhiskeyError):
    """Raised when scope-related operations fail.

    This occurs when:
    - Attempting to resolve a scoped component outside its scope
    - Invalid scope configuration
    - Scope lifecycle violations
    """

    pass


class ConfigurationError(WhiskeyError):
    """Raised when application configuration is invalid.

    This occurs when:
    - Invalid application builder configuration
    - Conflicting settings
    - Missing required configuration
    """

    pass


class TypeAnalysisError(WhiskeyError):
    """Raised when type analysis fails.

    This occurs when:
    - Forward references cannot be resolved
    - Type hints are malformed
    - Unsupported type constructs are encountered
    """

    def __init__(self, message: str, type_hint=None):
        super().__init__(message)
        self.type_hint = type_hint


class ParameterResolutionError(ResolutionError):
    """Raised when a specific parameter cannot be resolved during injection.

    This provides detailed information about which parameter failed and why,
    making debugging much easier.
    """

    def __init__(
        self,
        class_name: str,
        parameter_name: str,
        parameter_type: Any,
        reason: str,
        missing_dependencies: list[str] | None = None,
    ):
        self.class_name = class_name
        self.parameter_name = parameter_name
        self.parameter_type = parameter_type
        self.reason = reason
        self.missing_dependencies = missing_dependencies or []

        # Build detailed error message
        type_name = getattr(parameter_type, "__name__", str(parameter_type))
        message = f"Cannot resolve parameter '{parameter_name}: {type_name}' for {class_name}"

        if reason:
            message += f"\nReason: {reason}"

        if self.missing_dependencies:
            message += f"\nMissing dependencies: {', '.join(self.missing_dependencies)}"

        # Add helpful suggestions
        if "not registered" in reason.lower():
            message += (f"\n\nHint: Register {type_name} using @component, "
                       f"@singleton, or container.register()")
        elif "built-in type" in reason.lower():
            message += (f"\n\nHint: Built-in types like {type_name} cannot be "
                       f"auto-injected. Provide a value when calling.")

        super().__init__(message, service_key=class_name)
