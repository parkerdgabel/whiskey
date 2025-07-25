"""Core Whiskey dependency injection framework."""

from whiskey.core.application import Application, ApplicationConfig, ComponentMetadata
from whiskey.core.container import Container
from whiskey.core.decorators import (
    Inject,
    factory,
    get_default_container,
    inject,
    provide,
    scoped,
    set_default_container,
    singleton,
)
from whiskey.core.discovery import ComponentDiscoverer, ContainerInspector, discover_components
from whiskey.core.scopes import ContextVarScope, Scope, ScopeType
from whiskey.core.types import Disposable, Initializable

__all__ = [
    # Container
    "Container",
    "get_default_container",
    "set_default_container",
    # Decorators
    "Inject",
    "provide",
    "singleton",
    "factory",
    "inject",
    "scoped",
    # Application
    "Application",
    "ApplicationConfig",
    "ComponentMetadata",
    # Discovery
    "ComponentDiscoverer",
    "ContainerInspector",
    "discover_components",
    # Scopes
    "Scope",
    "ContextVarScope",
    "ScopeType",
    # Types
    "Initializable",
    "Disposable",
]