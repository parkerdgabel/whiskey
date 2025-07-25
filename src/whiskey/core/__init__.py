"""Core Whiskey dependency injection framework - Pythonic API."""

from whiskey.core.application import Application
from whiskey.core.builder import ApplicationBuilder, create_app
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
    service,
    singleton,
    when_debug,
    when_env,
    when_production,
)
from whiskey.core.performance import PerformanceMonitor, PerformanceMetrics
from whiskey.core.registry import ServiceRegistry, ServiceDescriptor, Scope
from whiskey.core.scopes import ContextVarScope, ScopeType
from whiskey.core.analyzer import TypeAnalyzer, InjectDecision
from whiskey.core.errors import (
    WhiskeyError,
    ResolutionError,
    CircularDependencyError,
    RegistrationError,
    InjectionError,
    ScopeError,
    ConfigurationError,
    TypeAnalysisError,
)

__all__ = [
    # Container
    "Container",
    "get_current_container", 
    "set_current_container",
    # Application
    "Application",
    "ApplicationBuilder",
    "create_app",
    # Global decorators
    "service",
    "singleton",
    "scoped",
    "factory",
    "component",
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