"""Exception types for Whiskey framework."""

from typing import Any, Optional


class WhiskeyError(Exception):
    """Base exception for all Whiskey errors."""

    pass


class ServiceNotFoundError(WhiskeyError):
    """Raised when a requested service cannot be found."""

    def __init__(self, service_key: Any, available: Optional[list[str]] = None):
        self.service_key = service_key
        self.available = available or []
        message = f"Service '{service_key}' not found in container."
        if self.available:
            message += f"\nAvailable services: {', '.join(self.available[:5])}"
            if len(self.available) > 5:
                message += f" (and {len(self.available) - 5} more)"
        super().__init__(message)


class CircularDependencyError(WhiskeyError):
    """Raised when circular dependencies are detected."""

    def __init__(self, dependency_chain: list[Any]):
        self.dependency_chain = dependency_chain
        chain_str = " -> ".join(str(d) for d in dependency_chain)
        message = f"Circular dependency detected: {chain_str}"
        super().__init__(message)


class ScopeError(WhiskeyError):
    """Raised when there are scope-related issues."""

    pass


class InvalidServiceError(WhiskeyError):
    """Raised when a service registration is invalid."""

    pass


class InjectionError(WhiskeyError):
    """Raised when dependency injection fails."""

    def __init__(self, target: Any, parameter: str, reason: str):
        self.target = target
        self.parameter = parameter
        self.reason = reason
        message = f"Failed to inject '{parameter}' into {target}: {reason}"
        super().__init__(message)


class ConfigurationError(WhiskeyError):
    """Raised when configuration is invalid."""

    pass


class LifecycleError(WhiskeyError):
    """Raised when lifecycle operations fail."""

    pass


class ResolutionError(WhiskeyError):
    """Raised when service resolution fails."""

    def __init__(self, service_type: type, reason: str, suggestion: Optional[str] = None):
        self.service_type = service_type
        self.reason = reason
        self.suggestion = suggestion
        
        message = f"Failed to resolve {service_type.__name__}: {reason}"
        if suggestion:
            message += f"\n💡 Suggestion: {suggestion}"
        super().__init__(message)