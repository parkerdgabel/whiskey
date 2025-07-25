"""Custom exception types for Whiskey's DI system.

This module defines clear, specific exceptions for different types of
dependency injection failures, making debugging easier for developers.
"""

from __future__ import annotations


class WhiskeyError(Exception):
    """Base exception for all Whiskey-related errors."""
    pass


class ResolutionError(WhiskeyError):
    """Raised when a service cannot be resolved.
    
    This is the most common error, occurring when:
    - A required service is not registered
    - A service's dependencies cannot be satisfied
    - A condition for service registration is not met
    """
    
    def __init__(self, message: str, service_key: str = None, cause: Exception = None):
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
        cycle_str = " → ".join(cycle_names + [cycle_names[0]])
        
        super().__init__(
            f"Circular dependency detected: {cycle_str}",
            service_key=cycle[0].__name__.lower() if cycle else None
        )


class RegistrationError(WhiskeyError):
    """Raised when service registration fails.
    
    This occurs when:
    - Invalid registration parameters are provided
    - A service is registered multiple times with conflicting metadata
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
    
    def __init__(self, message: str, parameter_name: str = None, type_hint = None):
        super().__init__(message)
        self.parameter_name = parameter_name
        self.type_hint = type_hint


class ScopeError(WhiskeyError):
    """Raised when scope-related operations fail.
    
    This occurs when:
    - Attempting to resolve a scoped service outside its scope
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
    
    def __init__(self, message: str, type_hint = None):
        super().__init__(message)
        self.type_hint = type_hint