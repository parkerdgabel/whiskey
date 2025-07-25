"""Core Whiskey dependency injection framework - Pythonic API."""

from whiskey.core.analyzer import InjectDecision, TypeAnalyzer
from whiskey.core.application import Whiskey
from whiskey.core.builder import WhiskeyBuilder, create_app
from whiskey.core.container import Container, get_current_container, set_current_container
from whiskey.core.decorators import (
    component,
    configure_app,
    factory,
    get_app,
    inject,
    on_error,
    on_shutdown,
    on_startup,
    resolve,
    resolve_async,
    scoped,
    singleton,
    when_debug,
    when_env,
    when_production,
)
from whiskey.core.errors import (
    CircularDependencyError,
    ConfigurationError,
    InjectionError,
    RegistrationError,
    ResolutionError,
    ScopeError,
    TypeAnalysisError,
    WhiskeyError,
)
from whiskey.core.performance import PerformanceMetrics, PerformanceMonitor
from whiskey.core.registry import Scope, ServiceDescriptor, ServiceRegistry
from whiskey.core.scopes import ContextVarScope, ScopeType

__all__ = [
    # Container
    "Container",
    "get_current_container",
    "set_current_container",
    # Application
    "Whiskey",
    "WhiskeyBuilder",
    "create_app",
    # Global decorators
    "component",
    "singleton",
    "scoped",
    "factory",
    "inject",
    # Lifecycle decorators
    "on_startup",
    "on_shutdown",
    "on_error",
    # Conditional decorators
    "when_env",
    "when_debug",
    "when_production",
    # Global functions
    "resolve",
    "resolve_async",
    "get_app",
    "configure_app",
    # Registry
    "ServiceRegistry",
    "ServiceDescriptor",
    "Scope",
    # Performance
    "PerformanceMonitor",
    "PerformanceMetrics",
    # Analysis
    "TypeAnalyzer",
    "InjectDecision",
    # Scopes
    "ContextVarScope",
    "ScopeType",
    # Errors
    "WhiskeyError",
    "ResolutionError",
    "CircularDependencyError",
    "RegistrationError",
    "InjectionError",
    "ScopeError",
    "ConfigurationError",
    "TypeAnalysisError",
]
