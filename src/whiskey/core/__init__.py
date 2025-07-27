"""Core components of the Whiskey dependency injection framework.

This module provides the fundamental building blocks for Whiskey's Pythonic
dependency injection system. It exports all the essential classes, decorators,
and utilities needed to build applications with automatic dependency resolution.

Key Components:
    Container: Dict-like service registry with automatic dependency resolution
    Whiskey: Application class with lifecycle management and rich IoC features
    Decorators: @component, @singleton, @inject for service registration
    TypeAnalyzer: Smart type analysis for automatic injection decisions
    Scopes: Lifecycle management (singleton, transient, scoped)
    
Usage Example:
    >>> from whiskey.core import Container, component, inject, singleton
    >>> 
    >>> # Register services
    >>> @singleton
    ... class Database:
    ...     def query(self, sql: str): ...
    >>> 
    >>> @component
    ... class UserService:
    ...     def __init__(self, db: Database):
    ...         self.db = db  # Automatically injected!
    >>> 
    >>> # Use injection in functions
    >>> @inject
    ... async def process_user(user_id: int, service: UserService):
    ...     return await service.get_user(user_id)

For more detailed examples, see the individual module documentation.
"""

from whiskey.core.analyzer import InjectDecision, TypeAnalyzer
from whiskey.core.application import Whiskey
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
    provide,
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
from whiskey.core.types import Disposable, Initializable

__all__ = [
    "CircularDependencyError",
    "ConfigurationError",
    # Container
    "Container",
    # Scopes
    "ContextVarScope",
    "Disposable",
    # Types
    "Initializable",
    "InjectDecision",
    "InjectionError",
    "PerformanceMetrics",
    # Performance
    "PerformanceMonitor",
    "RegistrationError",
    "ResolutionError",
    "Scope",
    "ScopeError",
    "ScopeType",
    "ServiceDescriptor",
    # Registry
    "ServiceRegistry",
    "TypeAnalysisError",
    # Analysis
    "TypeAnalyzer",
    # Application
    "Whiskey",
    # Errors
    "WhiskeyError",
    # Global decorators
    "component",
    "configure_app",
    "factory",
    "get_app",
    "get_current_container",
    "inject",
    "on_error",
    "on_shutdown",
    # Lifecycle decorators
    "on_startup",
    "provide",
    # Global functions
    "resolve",
    "resolve_async",
    "scoped",
    "set_current_container",
    "singleton",
    "when_debug",
    # Conditional decorators
    "when_env",
    "when_production",
]