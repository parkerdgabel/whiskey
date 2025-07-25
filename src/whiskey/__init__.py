"""Whiskey - Simple, Pythonic dependency injection for AI applications."""

__version__ = "0.1.0"

# Core exports
from whiskey.core.application import Application, ApplicationConfig, ComponentMetadata
from whiskey.core.container import Container
from whiskey.core.decorators import factory, inject, provide, scoped, singleton, Inject
from whiskey.core.discovery import ComponentDiscoverer, ContainerInspector, discover_components
from whiskey.core.scopes import ContextVarScope, Scope, ScopeType
from whiskey.core.types import Disposable, Initializable

__all__ = [
    # Core DI
    "Container",
    "inject",
    "provide",
    "singleton",
    "factory",
    "scoped",
    "Inject",
    # Discovery
    "ComponentDiscoverer",
    "ContainerInspector",
    "discover_components",
    # Scopes
    "Scope",
    "ContextVarScope",
    "ScopeType",
    # Application
    "Application",
    "ApplicationConfig",
    "ComponentMetadata",
    # Types
    "Initializable",
    "Disposable",
]